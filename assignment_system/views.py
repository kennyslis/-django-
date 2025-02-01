from time import timezone
from django.shortcuts import render, redirect, get_object_or_404
from .models import Assignment, Submission,CustomUser,Scores
from .forms import SubmissionForm, AssignmentForm,ScoreForm
from django.contrib.auth import authenticate, login,get_user_model
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse, HttpResponseRedirect,JsonResponse
from django.contrib.auth.decorators import user_passes_test,login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
import csv
import urllib.parse
from django.contrib import messages 
import nbformat
from django.core.exceptions import ValidationError
from nbconvert import HTMLExporter
from django.db.models import Max
def change_pass_html(request):
    students = CustomUser.objects.filter(is_teacher=False)  # 获取所有学生
    return render(request, 'change_pass.html', {
        'students': students
    })
def grade_port(request):
    assignments = Assignment.objects.all()  # 获取所有作业
    students = CustomUser.objects.filter(is_teacher=False)  # 获取所有学生

    submission_status = []  # 用于存储每个作业的提交状态
    for assignment in assignments:
        assignment_status = []  # 该作业的所有学生提交情况
        for student in students:
            submission = Submission.objects.filter(assignment=assignment, student=student).first()
            assignment_status.append({
                'student': student,
                'submitted': submission is not None,
                'submission': submission
            })
        submission_status.append({
            'assignment_id': assignment.id,
            'status': assignment_status
        })
    return render(request, 'grade_port.html', {
        'assignments': assignments,
        'submission_status': submission_status,
        'students': students
    })
def view_ipynb_as_html(request, submission_id):
    # 获取作业提交记录
    submission = get_object_or_404(Submission, id=submission_id)

    # 读取 `.ipynb` 文件内容（Django 的 FileField 以二进制模式存储）
    notebook_content = submission.file.read().decode("utf-8")

    # 解析 `.ipynb` 为 JSON
    notebook = nbformat.reads(notebook_content, as_version=4)

    # 转换为 HTML
    html_exporter = HTMLExporter()
    html_exporter.template_name = "classic"
    body, _ = html_exporter.from_notebook_node(notebook)

    # 返回 HTML 响应
    return HttpResponse(body, content_type="text/html")
# 登录功能
def custom_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if hasattr(user, 'is_teacher') and user.is_teacher:  # 老师跳转
                return redirect('/teacher/assignments/')
            else:  
                return redirect('/assignments/')
        else:
            return HttpResponse('用户名或密码错误', status=401)

    return render(request, 'custom_login.html')

# 用户注册功能
def register_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        name = request.POST.get('name')  # 新增：获取学生的姓名
        is_teacher = request.POST.get('is_teacher') == 'on'  # 判断是否为老师

        user = CustomUser.objects.create_user(
            username=username,
            password=password,
            is_teacher=is_teacher,
            name=name
        )
      
        login(request, user)
        return HttpResponseRedirect('/login/')  # 或者直接跳转到学生或老师的主页

    return render(request, 'register_user.html')

# 判断是否为老师
def is_teacher(user):
    return user.is_teacher  # 确保是老师

# 老师作业管理
@user_passes_test(is_teacher)
def teacher_assignment_management(request):
    assignments = Assignment.objects.all()  # 获取所有作业
    students = CustomUser.objects.filter(is_teacher=False)  # 获取所有学生

    submission_status = []  # 用于存储每个作业的提交状态
    for assignment in assignments:
        assignment_status = []  # 该作业的所有学生提交情况
        for student in students:
            submission = Submission.objects.filter(assignment=assignment, student=student).first()
            assignment_status.append({
                'student': student,
                'submitted': submission is not None,
                'submission': submission
            })
        submission_status.append({
            'assignment_id': assignment.id,
            'status': assignment_status
        })

    return render(request, 'teacher_assignment_management.html', {
        'assignments': assignments,
        'submission_status': submission_status,
        'students': students
    })

@user_passes_test(is_teacher)
def edit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)

    if request.method == 'POST':
        form = AssignmentForm(request.POST, instance=assignment)
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

# 作业列表（学生查看）



# 老师布置作业
@user_passes_test(is_teacher)
def create_assignment(request):
    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            form.save()  # 保存作业
            return redirect('teacher_assignment_management')  # 重定向到作业管理页面
    else:
        form = AssignmentForm()

    return render(request, 'create_assignment.html', {'form': form})

# 查看已提交作业
def view_submissions(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    students = CustomUser.objects.filter(is_teacher=False)
    submissions = Submission.objects.filter(assignment=assignment)
    scores = Scores.objects.filter(assignment=assignment)
    score_dict = {score.student.id: score.score for score in scores}

    # 获取每个学生的最新提交时间，直接与学生关联
    student_submission_times = submissions.values('student').annotate(latest_submission_time=Max('creat_at'))

    # 将成绩和提交时间直接关联到学生
    for student in students:
        student.score = score_dict.get(student.id, None)  # 如果没有成绩，score 为 None
        student.has_submission = any(submission.student == student for submission in submissions)

    return render(request, 'view_submissions.html', {
        'assignment': assignment,
        'students': students,  # 获取所有学生
        'submissions': submissions,
    })
def grade_submission(request, assignment_id, student_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student = get_object_or_404(CustomUser, id=student_id)

    # 基于作业和学生
    submission = Submission.objects.filter(assignment=assignment, student=student).first()

    # 如果没有提交记录，则为该学生创建一个默认的0分记录
    if not submission:
        # 创建一个提交记录对象
        submission = Submission(student=student, assignment=assignment)
        submission.save()

        # 创建一个默认的0分评分记录
        score = Scores(student=student, assignment=assignment, score=0, submission=submission)
        score.save()
    else:
        # 如果已有提交记录，则获取或创建评分记录
        score, created = Scores.objects.get_or_create(student=submission.student, assignment=submission.assignment)

        # 如果该学生已有成绩但没有提交，则创建一个默认评分
        if not score.submission:
            score.submission = submission
            score.save()

    # 处理评分表单提交
    if request.method == 'POST':
        form = ScoreForm(request.POST, instance=score)
        if form.is_valid():
            # 如果评分为空，设置为0
            if not form.cleaned_data['score']:
                form.cleaned_data['score'] = 0
            form.save()
            return redirect('view_submissions', assignment_id=submission.assignment.id)
    else:
        form = ScoreForm(instance=score)

    return render(request, 'grade_submission.html', {
        'form': form,
        'submission': submission
    })

def export_scores(request):#导出成绩

    assignment_id = request.GET.get('assignment', 'all')

    all_students = CustomUser.objects.filter(is_teacher=False)

    if assignment_id == 'all':
        assignments = Assignment.objects.all()  
    else:
        
        assignments = Assignment.objects.filter(id=assignment_id)
    
    file_name = "总成绩"
    if assignment_id != 'all':
        assignment = assignments.first()  
        file_name = f"{assignment.title}_成绩"

    encoded_file_name = urllib.parse.quote(file_name)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{encoded_file_name}.csv"'

    writer = csv.writer(response)

    writer.writerow(['姓名', '作业', '成绩'])

    for assignment in assignments:

        for student in all_students:#遍历所有学生

            score = Scores.objects.filter(student=student, assignment=assignment).first()


            if not score:
                score = Scores(student=student, assignment=assignment, score=0)
                score.save()

            writer.writerow([score.student.name, score.assignment.title, score.score])

    return response


def export_non_submitted(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    all_students = CustomUser.objects.filter(is_teacher=False)
    submitted_student_ids = Submission.objects.filter(assignment=assignment).values_list('student_id', flat=True)
    non_submitted_students = all_students.exclude(id__in=submitted_student_ids)
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="non_submitted_{assignment.title}.txt"'
    if non_submitted_students.exists():
        response.write(f"以下学生未提交作业:\n{assignment.title}:\n")
        for student in non_submitted_students:
            response.write(f"{student.name}\n")
    else:
        response.write("所有学生已提交。\n")
    
    return response
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



##########################################################学生操作##############################################################

def check_grade(request):
    if not request.user.is_authenticated:
        return redirect('custom_login')

    student = request.user  # 当前登录的学生

    # 获取学生的所有成绩
    scores = Scores.objects.filter(student=student)

    # 获取所有作业
    assignments = Assignment.objects.all()

    # 将成绩和作业组合成一个字典，直接在后端处理
    assignment_scores = {}
    for assignment in assignments:
        score = scores.filter(assignment=assignment).first()  # 获取每个作业的成绩
        assignment_scores[assignment] = score  # 将作业和成绩存储为字典

    return render(request, 'check_grade.html', {
        'assignment_scores': assignment_scores  # 将成绩字典传递给模板
    })




def assignment_list(request):
    assignments = Assignment.objects.all()
    return render(request, 'assignment_list.html', {'assignments': assignments})

# 学生提交作业@login_required
@login_required
def student_submission(request, assignment_id):
# 截止日期是否已过
    assignment = Assignment.objects.get(id=assignment_id)
    if timezone.now() > assignment.due_date:
        return render(request, 'student_submission.html', {
            'assignment': assignment,
            'error_message': '作业提交已过截止日期，无法提交！'
        })
    student = request.user
    submission, created = Submission.objects.get_or_create(student=student, assignment=assignment)

    if request.method == 'POST':
        form = SubmissionForm(request.POST, request.FILES, instance=submission)
        if form.is_valid():
            form.save()
            return render(request, 'student_submission.html', {
            'assignment': assignment,
            'error_message': '作业已成功提交！'
        }) # 提交后返回作业列表
    else:
        form = SubmissionForm(instance=submission)

    return render(request, 'student_submission.html', {'form': form, 'assignment': assignment})

