from django.shortcuts import render, redirect, get_object_or_404
from sympy import Q
import numpy as np
from django.db.models import Max, Avg
from django.conf import settings
from .models import Assignment, Submission,CustomUser,Scores
from .forms import SubmissionForm, AssignmentForm,ScoreForm
from django.contrib.auth import authenticate, login,get_user_model
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse, HttpResponseRedirect,JsonResponse
from django.contrib.auth.decorators import user_passes_test,login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Exists, OuterRef
from django.core.mail import send_mail
from django.contrib import messages
import random
import csv
import nbformat
from nbconvert import HTMLExporter
import pandas as pd
import json
import requests
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import os
from django.core.files.storage import default_storage
import zipfile
from django.http import FileResponse
from io import BytesIO
def is_teacher(user):
    return user.is_teacher  # 确保是老师
# 2. 批量下载：按 姓名+学号 规范后的文件名打包
@user_passes_test(is_teacher)
def download_all_submissions(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    submissions = Submission.objects.filter(assignment=assignment)
    
    byte_data = BytesIO()
    with zipfile.ZipFile(byte_data, 'w') as zip_file:
        for sub in submissions:
            if sub.custom_answers:
                for val in sub.custom_answers.values():
                    if isinstance(val, str):
                        full_path = os.path.join(settings.MEDIA_ROOT, val)
                        if os.path.exists(full_path):
                            # arcname 设为：作业标题/姓名_学号.后缀
                            # 这样解压后就是一个以作业名命名的文件夹
                            arcname = os.path.join(assignment.title, os.path.basename(full_path))
                            zip_file.write(full_path, arcname=arcname)
    
    byte_data.seek(0)
    response = FileResponse(byte_data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{assignment.title}_submissions.zip"'
    return response

@user_passes_test(is_teacher)
def download_batch_submissions(request):
    """批量打包多个作业：根文件夹 > 作业文件夹 > 学生文件"""
    assignment_ids = request.GET.getlist('assignment')
    
    if not assignment_ids:
        return HttpResponse("未选择任何作业进行打包", status=400)

    assignments = Assignment.objects.filter(id__in=assignment_ids)
    
    # 定义压缩包内的根文件夹名称（例如：2025-12-31_作业打包汇总）
    root_dir = f"Batch_Export_{timezone.now().strftime('%Y%m%d')}"
    
    byte_data = BytesIO()
    with zipfile.ZipFile(byte_data, 'w') as zip_file:
        for assignment in assignments:
            submissions = Submission.objects.filter(assignment=assignment)
            
            for sub in submissions:
                if sub.custom_answers:
                    for val in sub.custom_answers.values():
                        # 识别物理路径
                        if isinstance(val, str) and (val.startswith('submissions/') or '/' in val):
                            full_path = os.path.join(settings.MEDIA_ROOT, val)
                            
                            if os.path.exists(full_path):
                                filename = os.path.basename(full_path)
                                
                                # 【核心修改】：构建三级路径
                                # 结构：根文件夹 / 作业标题 / 学生文件名
                                arcname = os.path.join(root_dir, assignment.title, filename)
                                
                                zip_file.write(full_path, arcname=arcname)
    
    byte_data.seek(0)
    zip_filename = f"{root_dir}.zip"
    response = FileResponse(byte_data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
    return response

@csrf_exempt
@require_http_methods(["POST"])
def ai_generate_form_config(request):
    try:
        data = json.loads(request.body)
        user_prompt = data.get('prompt', '')
        
        # 核心：重新平衡“按需生成”与“格式识别”的逻辑
        system_prompt = (
            "你是一个极其死板且精准的 Django 表单 JSON 生成器。请严格根据用户需求生成 JSON 数组。\n"
            "【字段识别规则】：\n"
            "1. **普通文本识别**：如果用户提到‘姓名’、‘学号’、‘心得’等，type 必须设为 'text' 或 'textarea'。\n"
            "2. **文件格式识别**：只要用户提到后缀（如 ipynb, zip），type 必须设为 'file'，并包含 'accept' 字段（如 '.ipynb'）。\n"
            "3. **全中文 Label**：所有的 'label' 字段必须使用准确的中文描述。\n"
            "4. **按需生成**：用户没提到的字段绝对不要生成。但只要提到了，就必须生成。\n"
            "5. **统一命名**：所有字段的 'name' 统一固定为 'task'。\n"
            "只返回纯 JSON 数组，严禁包含任何 Markdown 标签（如 ```json）或解释文字。"
        )

        # views.py
        response = requests.post(
        "http://localhost:11434/api/generate",
        json={
        "model": "qwen2:7b",  # 必须与 ollama list 中的名称完全一致
        "prompt": f"{system_prompt}\n用户当前需求：{user_prompt}", 
        "stream": False
    },
    timeout=30
    )

        if response.status_code == 200:
            raw_response = response.json().get('response', '').strip()
            # 强化清理逻辑，防止 image_ff2ee2.png 所示的解析错误
            clean_json = raw_response.replace('```json', '').replace('```', '').strip()
            
            parsed_data = json.loads(clean_json)
            form_config = parsed_data if isinstance(parsed_data, list) else [parsed_data]
            return JsonResponse({'status': 'success', 'config': form_config})
            
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f"AI 识别失败: {str(e)}"})
@login_required
def import_students(request):
    if request.method == 'POST' and request.FILES['excel_file']:
        excel_file = request.FILES['excel_file']
        df = pd.read_excel(excel_file)
        new_students = [] 
        for _, row in df.iterrows():
            number = row['学号']
            print(number)
            name = row['姓名']
            email=row['邮箱']
            password = str(random.randint(100000, 999999))
            user, created = CustomUser.objects.get_or_create(
                number=number,  
                defaults={
                    'username': str(number),
                    'name': name,
                    'password': password,
                    'email': email,
                    'is_teacher': False,  
                }
            )
            if created:
                user.set_password(password) 
                user.save()
                new_students.append({
                    'number': number,
                    'name': name,
                    'email': email,
                    'password': password
                })

            send_mail(
            '密码',
            f'您的账号是{number},您的密码是: {password}',
            '2819024054@qq.com', 
            [email],
            fail_silently=False,
        )
        messages.success(request, "学生信息导入成功！")
     
        return render(request, 'import_students.html', {'new_students': new_students})

    return render(request, 'import_students.html')  
def change_pass_html(request):
    students = CustomUser.objects.filter(is_teacher=False)  # 获取所有学生
    return render(request, 'change_pass.html', {
        'students': students
    })
@user_passes_test(is_teacher)
def grade_port(request):
    assignments = Assignment.objects.all()
    students_count = CustomUser.objects.filter(is_teacher=False).count()
    
    # 1. 核心指标计算：显式转换为 float 解决 Decimal 报错
    all_scores = [float(s) for s in Scores.objects.filter(score__gt=0).values_list('score', flat=True)]
    
    stats_summary = {
        'avg': round(np.mean(all_scores), 1) if all_scores else 0,
        'median': round(np.median(all_scores), 1) if all_scores else 0,
        'max': max(all_scores) if all_scores else 0,
        'total_submissions': Submission.objects.count()
    }

    # 2. 箱线图数据 (成绩分布)
    boxplot_data = []
    assignment_labels = []
    for assignment in assignments:
        a_scores = [float(s) for s in Scores.objects.filter(assignment=assignment, score__gt=0).values_list('score', flat=True)]
        if len(a_scores) >= 1:
            res = [
                float(np.min(a_scores)),
                float(np.percentile(a_scores, 25)),
                float(np.median(a_scores)),
                float(np.percentile(a_scores, 75)),
                float(np.max(a_scores))
            ]
            boxplot_data.append(res)
            assignment_labels.append(assignment.title)

    # 3. 柱状图数据 (提交率情况)
    submission_status = []
    for assignment in assignments:
        submitted_count = Submission.objects.filter(assignment=assignment).count()
        submission_status.append({
            'assignment_title': assignment.title,
            'submitted_count': submitted_count,
            'not_submitted_count': students_count - submitted_count 
        })
    
    return render(request, 'grade_port.html', {
        'assignments': assignments,
        'submission_status': submission_status,
        'stats': stats_summary,
        'boxplot_data': json.dumps(boxplot_data),
        'boxplot_labels': json.dumps(assignment_labels),
        'now': timezone.now()
    })
def view_ipynb_as_html(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id)
    file_path = None
    if submission.custom_answers:
        for val in submission.custom_answers.values():
            if isinstance(val, str) and val.lower().endswith('.ipynb'):
                file_path = val
                break
    if not file_path:
        return HttpResponse("未找到 .ipynb 文件")

    try:
        from django.core.files.storage import default_storage
        with default_storage.open(file_path, 'rb') as f: # 必须用 rb 模式
            content_bytes = f.read()
            notebook_content = content_bytes.decode('utf-8') # 显式解码
        
        notebook = nbformat.reads(notebook_content, as_version=4)
        body, _ = HTMLExporter(template_name="classic").from_notebook_node(notebook)
        return HttpResponse(body, content_type="text/html")
    except Exception as e:
        return HttpResponse(f"预览失败 (请确保文件为UTF-8编码): {str(e)}")
# 登录功能
def custom_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            # 1. 优先检查是否是超级管理员
            if user.is_superuser:
                return redirect('admin_dashboard')
            # 2. 老师跳转逻辑
            elif user.is_teacher:
                return redirect('/teacher/assignments/')
            # 3. 学生跳转逻辑
            else:
                return redirect('/assignments/')
        else:
            return render(request, 'custom_login.html', {"error_message": "账户或密码错误."})

    return render(request, 'custom_login.html')

# 用户注册功能
def register_user(request):
    if request.method == 'POST':
        number=request.POST.get('number')
        username = request.POST.get('username')
        password = request.POST.get('password')
        name = request.POST.get('name')  # 新增：获取学生的姓名
        is_teacher = request.POST.get('is_teacher') == 'on'  # 判断是否为老师
        email = request.POST.get('email')  # 新增：获取邮箱地址

        user = CustomUser.objects.create_user(
            username=username,
            password=password,
            is_teacher=is_teacher,
            name=name,
            email=email,
            number=number

        )
      
        login(request, user)
        return HttpResponseRedirect('/login/')  # 或者直接跳转到学生或老师的主页

    return render(request, 'register_user.html')



# 老师作业管理
@user_passes_test(is_teacher)
def teacher_assignment_management(request):
    assignments = Assignment.objects.all()  # 获取所有作业
    students = CustomUser.objects.filter(is_teacher=False,is_superuser=False)  # 获取所有学生
    students_quantity = len(students)  # 总学生数
    submission_status = []  # 用于存储每个作业的提交状态
    submitted_counts = []  # 用于存储每个作业的已提交人数

    for assignment in assignments:
        submitted_count = 0  # 该作业的已提交人数
        for student in students:
            submission = Submission.objects.filter(assignment=assignment, student=student).first()
            if submission is not None:
                submitted_count += 1  # 如果提交了作业，则已提交人数加 1
        
        # 记录该作业的提交人数
        submission_status.append({
            'assignment_id': assignment.id,
            'submitted_count': submitted_count
        })

    return render(request, 'teacher_assignment_management.html', {
        'assignments': assignments,
        'submission_status': submission_status,
        'students_quantity': students_quantity,  # 总学生数
    })

@user_passes_test(is_teacher)
def edit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)

    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES,instance=assignment )
        if form.is_valid():
            form.save()
            return redirect('teacher_assignment_management')  # 编辑后返回作业管理页面
    else:
        form = AssignmentForm(instance=assignment)

    return render(request, 'edit_assignment.html', {'form': form, 'assignment': assignment})


@user_passes_test(is_teacher)
def delete_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)

    if request.method == 'POST':
        assignment.delete()
        return redirect('teacher_assignment_management')  # 删除后返回作业管理页面

    return render(request, 'confirm_delete.html', {'assignment': assignment})





# 老师布置作业
@user_passes_test(is_teacher)
def create_assignment(request):
    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES)
        if form.is_valid():
            # 先不提交数据库
            assignment = form.save(commit=False)
            
            # 这里的 'custom_fields_data' 必须对应 create_assignment.html 中隐藏域的 name
            custom_fields_raw = request.POST.getlist('custom_fields_data')
            if custom_fields_raw:
                # 将 JSON 字符串解析为 Python 列表并存入模型
                assignment.custom_fields = [json.loads(f) for f in custom_fields_raw]
            
            assignment.save()
            return redirect('teacher_assignment_management')
    else:
        form = AssignmentForm()
    return render(request, 'create_assignment.html', {'form': form})

# 查看已提交作业
@user_passes_test(is_teacher)
def view_submissions(request, assignment_id):
    filter_type = request.GET.get('filter', 'all') 
    assignment = get_object_or_404(Assignment, id=assignment_id)
    # 保留逻辑：获取所有作业用于页面顶部的快速切换
    all_assignments = Assignment.objects.all()
    students = CustomUser.objects.filter(is_teacher=False,is_superuser=False)
    
    submissions = Submission.objects.filter(assignment=assignment).select_related('student')
    submission_dict = {sub.student.id: sub for sub in submissions}
    scores = Scores.objects.filter(assignment=assignment)
    score_dict = {score.student.id: score.score for score in scores}

    for student in students:
        sub = submission_dict.get(student.id)
        student.score = score_dict.get(student.id, None)
        student.has_submission = sub is not None
        student.dynamic_content = []
        if sub and sub.custom_answers:
            student.dynamic_content = [(k, v) for k, v in sub.custom_answers.items()]
            student.sub_id = sub.id

    if filter_type == 'not_submitted':
        students = [s for s in students if not s.has_submission]

    return render(request, 'view_submissions.html', {
        'assignment': assignment,
        'all_assignments': all_assignments, # 传递给模板
        'students': students, 
        'submissions': submissions,
        'filter': filter_type,  
    })

# 批量打分
@csrf_exempt
@user_passes_test(is_teacher)
@require_http_methods(["POST"])
def batch_grade(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    # 接收弹窗传来的统一分数和学生ID列表
    score_val = request.POST.get('score')
    student_ids = request.POST.getlist('student_ids')
    
    try:
        if not score_val or not student_ids:
            return JsonResponse({'status': 'error', 'message': '分数或学生列表不能为空'})

        for s_id in student_ids:
            student = get_object_or_404(CustomUser, id=s_id)
            # 更新或创建成绩记录
            score_obj, _ = Scores.objects.get_or_create(student=student, assignment=assignment)
            score_obj.score = float(score_val)
            score_obj.save()
            
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
def grade_submission(request, assignment_id, student_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student = get_object_or_404(CustomUser, id=student_id)
    submission = Submission.objects.filter(assignment=assignment, student=student).first()

    if not submission:
        submission = Submission(student=student, assignment=assignment)
        submission.save()
        score = Scores(student=student, assignment=assignment, score=0, submission=submission)
        score.save()
    else:

        score, _= Scores.objects.get_or_create(student=submission.student, assignment=submission.assignment)

    if request.method == 'POST':
        form = ScoreForm(request.POST, instance=score)
        if form.is_valid():
            print(form.cleaned_data['score'])
            if not form.cleaned_data['score'] or score.score <= 0 or score.score>100:
                message="成绩不能为空，且必须大于0不超过100"
                return render(request, 'grade_submission.html', {
            'form': form,
            'submission': submission,
            'message': message})
            
            else:
                form.cleaned_data['score'] = 0
                form.save()
                return redirect('view_submissions', assignment_id=submission.assignment.id)
    else:
        form = ScoreForm(instance=score)

    return render(request, 'grade_submission.html', {
        'form': form,
        'submission': submission
    })



def export_scores(request): 
    assignment_ids = request.GET.getlist('assignment')  

    all_students = CustomUser.objects.filter(is_teacher=False,is_superuser=False)

    if 'all' in assignment_ids or not assignment_ids:  
        assignments = Assignment.objects.all()
    else:
        assignments = Assignment.objects.filter(id__in=assignment_ids)

    file_name = "总成绩"
    if assignments.count() == 1:
        file_name = f"{assignments.first().title}_成绩"

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{file_name}.csv"'

    response.write('\ufeff')  # 防止中文乱码
    writer = csv.writer(response, quotechar='"', quoting=csv.QUOTE_MINIMAL)

    # 修复报错点：直接遍历 assignments 对象获取 title
    columns = ['学号', '姓名'] + [f"{a.title}" for a in assignments]
    writer.writerow(columns)

    for student in all_students:
        row = [student.number, student.name]
        for a in assignments: # 避免使用 assignment 变量名以防冲突
            score = Scores.objects.filter(student=student, assignment=a).first()
            submission_exists = Submission.objects.filter(student=student, assignment=a).exists()
            if not submission_exists:
                row.append("未提交")
            else:
                row.append(score.score if score else 0)
        writer.writerow(row)

    return response

#导出未提交
def export_non_submitted(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    
    all_students = CustomUser.objects.filter(is_teacher=False,is_superuser=False)
    submitted_student_ids = Submission.objects.filter(assignment=assignment).values_list('student_id', flat=True)
    non_submitted_students = all_students.exclude(id__in=submitted_student_ids)
    
    # 生成未提交作业学生名单文本
    student_list = "以下学生未提交作业:\n"
    if non_submitted_students.exists():
        for student in non_submitted_students:
            student_list += f"{student.name}  {student.number}  {assignment.title}\n"
    else:
        student_list = "所有学生已提交。\n"
    
    return JsonResponse({'student_list': student_list})

#修改密码
@user_passes_test(is_teacher)
def change_password(request):
    if request.method == 'POST':
        student_id = request.POST.get('student')
        new_password = request.POST.get('new_password')

        if not new_password:  # 防止空密码
            return JsonResponse({'status': 'error', 'message': '密码不能为空！'})

        try:
            if student_id != 'all':  # 修改单个学生密码
                student = get_user_model().objects.get(id=student_id)
                student.password = make_password(new_password)
                student.save()
                return JsonResponse({'status': 'success', 'message': f'{student.name} 的密码已成功修改！'})
            else:  # 修改所有学生密码
                students = get_user_model().objects.filter(is_teacher=False)
                for student in students:
                    student.password = make_password(new_password)
                    student.save()
                return JsonResponse({'status': 'success', 'message': '所有学生密码已成功修改！'})
        except get_user_model().DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '学生不存在！'})

    return JsonResponse({'status': 'error', 'message': '无效请求！'}, status=400)



##########################################################################################学生操作##############################################################




def verify_code(request):
    if request.method == 'POST':
        entered_code = request.POST.get('code')
        email = request.session.get('email')
        verification_code = request.session.get('verification_code')

        if entered_code == verification_code:
            # 如果验证码正确，允许用户设置新密码
            return redirect('reset_password')

        else:

            return render(request, 'verify_code.html',{
                'error_message': '验证码错误，请检查后重试。'})

    return render(request, 'verify_code.html')
def reset_password(request):
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        email = request.session.get('email')

        user = CustomUser.objects.get(email=email)
        user.set_password(new_password)
        user.save()

        messages.success(request, "密码已成功重置，请登录。")
        return redirect('custom_login')

    return render(request, 'reset_password.html')

def forgot_password(request):#找回密码
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            
            return render(request, 'forgot_password.html',{
                'error_message': '该邮箱不存在，请检查后重试。'})

        verification_code = str(random.randint(100000, 999999))

        send_mail(
            '密码重置验证码',
            f'您的密码重置验证码是: {verification_code}',
            '2819024054@qq.com', 
            [email],
            fail_silently=False,
        )
        request.session['verification_code'] = verification_code
        request.session['email'] = email

        return redirect('verify_code')  

    return render(request, 'forgot_password.html')
@login_required
def update_profile(request):
    if request.method == 'POST':
        # 获取用户输入的信息
        name = request.POST.get('username')
        email = request.POST.get('email')
        number = request.POST.get('number')  # 获取学号

        # 获取当前登录的用户
        user = request.user

        # 判断学号是否已存在（排除当前用户）
        if CustomUser.objects.filter(number=number).exclude(id=user.id).exists():
            error_message = "学号已存在，请选择其他学号。"
            return render(request, 'update_profile.html', {'user': user, 'error_message': error_message})

        # 更新用户信息
        user.name = name  # 更新用户名
        user.email = email  # 更新邮箱
        user.number = number
        user.save()

        return render(request, 'update_profile.html', { 'error_message': '个人信息更新成功！','user': user}) # 假设你有个人主页的页面，跳转到个人主页

    return render(request, 'update_profile.html', {'user': request.user})
def check_grade(request):
    if not request.user.is_authenticated:
        return redirect('custom_login')

    student = request.user 
    scores = Scores.objects.filter(student=student)
    assignments = Assignment.objects.all()
    submissions = Submission.objects.filter(
        student=request.user, 
        assignment=OuterRef('pk')
    )
    assignments = assignments.annotate(has_submission=Exists(submissions))
    # 将成绩和作业组合成一个字典，直接在后端处理
    assignment_scores = {}
    for assignment in assignments:
        score = scores.filter(assignment=assignment).first()  # 获取每个作业的成绩
        assignment_scores[assignment] = score  # 将作业和成绩存储为字典
    # for assignment, score in assignment_scores.items():
    #     print(assignment.title, score)
    return render(request, 'check_grade.html', {
        'assignment_scores': assignment_scores,
         'assignments': assignments
    })






def assignment_list(request):
    now = timezone.now()
    filter_type = request.GET.get('filter', 'all')  # 获取URL中的filter参数，默认值为'all'

 
    assignments = Assignment.objects.all()

  
    submissions = Submission.objects.filter(
        student=request.user, 
        assignment=OuterRef('pk')
    )
    assignments = assignments.annotate(has_submission=Exists(submissions))

    if filter_type == 'not_submitted':
 
        assignments = assignments.filter(has_submission=False)
    elif filter_type == 'all':
 
        assignments = assignments.all()

    return render(request, 'assignment_list.html', {
        'assignments': assignments,
        'now': now,
        'filter': filter_type,  
    })


# 学生提交作业@login_required
# 学生提交作业视图
# 1. 学生提交：实现文件夹归类与规范命名
@login_required
def student_submission(request, assignment_id):
    # 1. 获取作业对象和学生对象
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student = request.user
    
    # 2. 截止日期检查
    if timezone.now() > assignment.due_date:
        return render(request, 'student_submission.html', {
            'assignment': assignment, 
            'error_message': '作业已截止，无法提交！'
        })

    # 3. 获取或创建提交记录
    submission, _ = Submission.objects.get_or_create(student=student, assignment=assignment)

    if request.method == 'POST':
        # 初始化数据字典
        old_answers = submission.custom_answers or {}
        new_answers = {}
        custom_fields = assignment.custom_fields or []
        
        for field in custom_fields:
            field_name = field['name']
            form_key = f"custom_{field_name}"
            
            if field['type'] == 'file':
                uploaded_file = request.FILES.get(form_key)
                if uploaded_file:
                    # 4. 规范化命名：姓名_学号.后缀
                    ext = os.path.splitext(uploaded_file.name)[1].lower()
                    filename = f"{student.name}_{student.username}{ext}"
                    
                    # 5. 构建物理路径：media/submissions/作业标题/姓名_学号.后缀
                    # 使用 os.path.join 确保跨平台路径正确
                    relative_dir = os.path.join('submissions', assignment.title)
                    relative_path = os.path.join(relative_dir, filename)
                    full_path = os.path.join(settings.MEDIA_ROOT, relative_path)

                    # 6. 核心修复：强制覆盖逻辑
                    # 如果物理文件已存在，直接删除，防止 Django 自动在文件名后加随机字符
                    if os.path.exists(full_path):
                        os.remove(full_path)
                    
                    # 7. 确保作业文件夹存在
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    
                    # 8. 直接写入文件内容
                    with open(full_path, 'wb+') as destination:
                        for chunk in uploaded_file.chunks():
                            destination.write(chunk)
                    
                    # 9. 数据库存入统一的相对路径，斜杠统一为正斜杠
                    new_answers[field_name] = relative_path.replace('\\', '/')
                else:
                    # 如果没有上传新文件，保留旧路径
                    new_answers[field_name] = old_answers.get(field_name)
            else:
                # 处理文本、数字等普通字段
                new_answers[field_name] = request.POST.get(form_key)

        # 10. 保存动态内容到数据库
        submission.custom_answers = new_answers
        submission.save()
        
        # 11. 确保成绩记录存在
        Scores.objects.get_or_create(student=student, assignment=assignment, defaults={'score': 0})
        
        return render(request, 'student_submission.html', {
            'assignment': assignment, 
            'error_message': '提交成功！'
        })

    return render(request, 'student_submission.html', {'assignment': assignment})

