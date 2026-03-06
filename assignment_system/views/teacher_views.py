import json
import random

import pandas as pd

from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.db.models import Avg
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ..forms import AssignmentForm, ScoreForm
from ..models import Assignment, CustomUser, Scores, Submission
from ..services.ai_service import generate_form_config


def is_teacher(user):
    return user.is_teacher


@csrf_exempt
@require_http_methods(["POST"])
def ai_generate_form_config(request):
    try:
        data = json.loads(request.body)
        user_prompt = data.get("prompt", "")

        form_config = generate_form_config(user_prompt)
        return JsonResponse({"status": "success", "config": form_config})
    except Exception as e:
        return JsonResponse({"status": "error", "message": f"AI 识别失败: {str(e)}"})


@user_passes_test(is_teacher)
def import_students(request):
    new_students = []

    if request.method == "POST":
        excel_file = request.FILES.get("excel_file")
        if not excel_file:
            messages.error(request, "请先上传 Excel 文件。")
            return render(request, "teacher/import_students.html")

        try:
            df = pd.read_excel(excel_file)

            for _, row in df.iterrows():
                number = str(row.iloc[0]).strip()
                name = str(row.iloc[1]).strip()
                email = str(row.iloc[2]).strip()

                if CustomUser.objects.filter(number=number).exists():
                    continue

                password = str(random.randint(100000, 999999))

                student = CustomUser.objects.create(
                    username=number,
                    number=number,
                    name=name,
                    email=email,
                    is_teacher=False,
                    password=make_password(password),
                )
                new_students.append(student)

                try:
                    send_mail(
                        "账号已创建",
                        f"你好，{name}，你的账号已创建。\n账号：{number}\n密码：{password}",
                        "2819024054@qq.com",
                        [email],
                        fail_silently=True,
                    )
                except Exception:
                    pass

            messages.success(request, f"成功导入 {len(new_students)} 名学生。")
        except Exception as e:
            messages.error(request, f"导入失败：{str(e)}")

    return render(request, "teacher/import_students.html", {"new_students": new_students})


@user_passes_test(is_teacher)
def change_pass_html(request):
    students = CustomUser.objects.filter(is_teacher=False, is_superuser=False)
    return render(request, "auth/change_pass.html", {"students": students})


@user_passes_test(is_teacher)
def change_password(request):
    if request.method == "POST":
        student_id = request.POST.get("student")
        new_password = request.POST.get("new_password")

        if not new_password:
            return JsonResponse({"status": "error", "message": "请输入新密码。"})

        if student_id == "all":
            students = CustomUser.objects.filter(is_teacher=False, is_superuser=False)
            for student in students:
                student.password = make_password(new_password)
                student.save()
            return JsonResponse({"status": "success", "message": "所有学生密码已重置成功。"})
        else:
            try:
                student = CustomUser.objects.get(id=student_id, is_teacher=False)
                student.password = make_password(new_password)
                student.save()
                return JsonResponse({"status": "success", "message": f"{student.name} 的密码修改成功。"})
            except CustomUser.DoesNotExist:
                return JsonResponse({"status": "error", "message": "学生不存在。"})

    return JsonResponse({"status": "error", "message": "非法请求。"})


@user_passes_test(is_teacher)
def grade_port(request):
    assignments = Assignment.objects.all().order_by("id")
    students_quantity = CustomUser.objects.filter(is_teacher=False, is_superuser=False).count()

    submission_status = []
    all_scores = []

    assignment_labels = []
    boxplot_data = []

    for assignment in assignments:
        submitted_count = Submission.objects.filter(
            assignment=assignment
        ).values("student").distinct().count()

        not_submitted_count = max(students_quantity - submitted_count, 0)

        submission_status.append({
            "assignment_id": assignment.id,
            "assignment_title": assignment.title,
            "submitted_count": submitted_count,
            "not_submitted_count": not_submitted_count,
        })

        scores = [
            float(s) for s in
            Scores.objects.filter(assignment=assignment)
            .values_list("score", flat=True)
            if s is not None
        ]

        if scores:
            all_scores.extend(scores)
            assignment_labels.append(assignment.title)
            boxplot_data.append(scores)

    if all_scores:
        sorted_scores = sorted(all_scores)
        avg_score = round(sum(all_scores) / len(all_scores), 2)
        max_score = max(all_scores)
        median_score = sorted_scores[len(sorted_scores) // 2]
    else:
        avg_score = 0
        max_score = 0
        median_score = 0

    stats_summary = {
        "avg": avg_score,
        "max": max_score,
        "median": median_score,
    }

    return render(
        request,
        "teacher/grade_port.html",
        {
            "assignments": assignments,
            "submission_status": submission_status,
            "stats": stats_summary,
            "boxplot_data": json.dumps(boxplot_data),
            "boxplot_labels": json.dumps(assignment_labels),
            "students_quantity": students_quantity,
            "now": timezone.now(),
            "user": request.user,
        }
    )

@user_passes_test(is_teacher)
def teacher_assignment_management(request):
    assignments = Assignment.objects.all().order_by("-due_date")
    students_quantity = CustomUser.objects.filter(is_teacher=False, is_superuser=False).count()

    submission_status = []
    for assignment in assignments:
        submitted_count = Submission.objects.filter(assignment=assignment).values("student").distinct().count()
        submission_status.append({
            "assignment_id": assignment.id,
            "submitted_count": submitted_count
        })

    return render(
        request,
        "teacher/teacher_assignment_management.html",
        {
            "assignments": assignments,
            "submission_status": submission_status,
            "students_quantity": students_quantity,
            "now": timezone.now(),
            "user": request.user,
        }
    )


@user_passes_test(is_teacher)
def create_assignment(request):
    if request.method == "POST":
        form = AssignmentForm(request.POST, request.FILES)
        if form.is_valid():
            assignment = form.save(commit=False)

            custom_fields_data = request.POST.getlist("custom_fields_data")
            parsed_fields = []
            for item in custom_fields_data:
                try:
                    parsed_fields.append(json.loads(item))
                except Exception:
                    pass

            assignment.custom_fields = parsed_fields
            assignment.save()

            return redirect("teacher_assignment_management")
    else:
        form = AssignmentForm()

    return render(request, "teacher/create_assignment.html", {"form": form})


@user_passes_test(is_teacher)
def edit_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)

    if request.method == "POST":
        form = AssignmentForm(request.POST, request.FILES, instance=assignment)
        if form.is_valid():
            form.save()
            return redirect("teacher_assignment_management")
    else:
        form = AssignmentForm(instance=assignment)

    return render(
        request,
        "teacher/edit_assignment.html",
        {"form": form, "assignment": assignment}
    )


@user_passes_test(is_teacher)
def delete_assignment(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)

    if request.method == "POST":
        assignment.delete()
        return redirect("teacher_assignment_management")

    return render(
        request,
        "teacher/confirm_delete.html",
        {"assignment": assignment}
    )


@user_passes_test(is_teacher)
def view_submissions(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    all_assignments = Assignment.objects.all().order_by("id")
    filter_type = request.GET.get("filter", "all")

    students = CustomUser.objects.filter(is_teacher=False, is_superuser=False).order_by("number")
    submissions = Submission.objects.filter(assignment=assignment).select_related("student")
    scores = Scores.objects.filter(assignment=assignment)

    score_map = {s.student_id: s.score for s in scores}
    submission_map = {s.student_id: s for s in submissions}

    student_rows = []
    for student in students:
        sub = submission_map.get(student.id)
        has_submission = sub is not None

        if filter_type == "not_submitted" and has_submission:
            continue

        dynamic_content = []
        if has_submission and sub.custom_answers:
            for key, value in sub.custom_answers.items():
                dynamic_content.append((key, value))

        student_rows.append({
            "id": student.id,
            "username": student.number,
            "name": student.name,
            "has_submission": has_submission,
            "sub_id": sub.id if sub else None,
            "score": score_map.get(student.id),
            "dynamic_content": dynamic_content,
        })

    return render(
        request,
        "teacher/view_submissions.html",
        {
            "assignment": assignment,
            "all_assignments": all_assignments,
            "students": student_rows,
            "submissions": submissions,
            "filter": filter_type,
        }
    )


@csrf_exempt
@user_passes_test(is_teacher)
@require_http_methods(["POST"])
def batch_grade(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    score = request.POST.get("score")
    student_ids = request.POST.getlist("student_ids")

    if score is None or not student_ids:
        return JsonResponse({"status": "error", "message": "参数不完整"})

    try:
        score = float(score)
    except ValueError:
        return JsonResponse({"status": "error", "message": "分数格式错误"})

    for sid in student_ids:
        student = get_object_or_404(CustomUser, id=sid)
        score_obj, _ = Scores.objects.get_or_create(student=student, assignment=assignment)
        score_obj.score = score
        score_obj.save()

    return JsonResponse({"status": "success"})


@user_passes_test(is_teacher)
def grade_submission(request, assignment_id, student_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student = get_object_or_404(CustomUser, id=student_id)
    submission = get_object_or_404(Submission, assignment=assignment, student=student)

    score_obj, _ = Scores.objects.get_or_create(student=student, assignment=assignment)
    message = None

    if request.method == "POST":
        form = ScoreForm(request.POST, instance=score_obj)
        if form.is_valid():
            form.save()
            message = "评分已保存"
    else:
        form = ScoreForm(instance=score_obj)

    return render(
        request,
        "teacher/grade_submission.html",
        {
            "submission": submission,
            "form": form,
            "message": message,
        }
    )


@user_passes_test(is_teacher)
def ai_assistant_page(request):
    return render(request, "teacher/ai_assistant.html")

@csrf_exempt
@user_passes_test(is_teacher)
@require_http_methods(["POST"])
def ai_teacher_assistant_api(request):
    try:
        data = json.loads(request.body)
        user_prompt = (data.get("prompt") or "").strip()

        if not user_prompt:
            return JsonResponse({"status": "error", "message": "empty prompt"}, status=400)

        from ..services.ai_service import parse_teacher_query_with_llm, execute_teacher_query

        intent_obj = parse_teacher_query_with_llm(user_prompt)
        result = execute_teacher_query(intent_obj, user_prompt=user_prompt)

        return JsonResponse({
            "status": "success",
            "reply": result.get("reply"),
            "table": result.get("table"),
            "chart": result.get("chart"),
        })

    except Exception as e:
        return JsonResponse({"status": "error", "message": f"AI 处理失败: {str(e)}"}, status=500)