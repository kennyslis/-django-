import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ..models import Assignment, Scores, Submission


def assignment_list(request):
    if not request.user.is_authenticated:
        return redirect("custom_login")

    now = timezone.now()
    filter_type = request.GET.get("filter", "all")

    assignments = Assignment.objects.all().order_by("due_date")

    submissions = Submission.objects.filter(
        student=request.user,
        assignment=OuterRef("pk")
    )

    assignments = assignments.annotate(has_submission=Exists(submissions))

    if filter_type == "not_submitted":
        assignments = assignments.filter(has_submission=False)

    return render(
        request,
        "student/assignment_list.html",
        {
            "assignments": assignments,
            "now": now,
            "filter": filter_type,
            "user": request.user,
        }
    )


@login_required
def student_submission(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student = request.user

    if timezone.now() > assignment.due_date:
        return render(
            request,
            "student/student_submission.html",
            {
                "assignment": assignment,
                "error_message": "作业已截止，无法提交！"
            }
        )

    submission, _ = Submission.objects.get_or_create(student=student, assignment=assignment)

    if request.method == "POST":
        old_answers = submission.custom_answers or {}
        new_answers = {}
        custom_fields = assignment.custom_fields or []

        for field in custom_fields:
            field_name = field.get("name")
            field_type = field.get("type")
            form_key = f"custom_{field_name}"

            if field_type == "file":
                uploaded_file = request.FILES.get(form_key)

                if uploaded_file:
                    ext = os.path.splitext(uploaded_file.name)[1].lower()
                    filename = f"{student.name}_{student.username}{ext}"

                    relative_dir = os.path.join("submissions", assignment.title)
                    relative_path = os.path.join(relative_dir, filename)
                    full_path = os.path.join(settings.MEDIA_ROOT, relative_path)

                    os.makedirs(os.path.dirname(full_path), exist_ok=True)

                    if os.path.exists(full_path):
                        os.remove(full_path)

                    with open(full_path, "wb+") as destination:
                        for chunk in uploaded_file.chunks():
                            destination.write(chunk)

                    new_answers[field_name] = relative_path.replace("\\", "/")
                else:
                    new_answers[field_name] = old_answers.get(field_name)
            else:
                new_answers[field_name] = request.POST.get(form_key)

        submission.custom_answers = new_answers
        submission.save()

        Scores.objects.get_or_create(
            student=student,
            assignment=assignment,
            defaults={"score": 0}
        )

        return render(
            request,
            "student/student_submission.html",
            {
                "assignment": assignment,
                "error_message": "提交成功！"
            }
        )

    return render(
        request,
        "student/student_submission.html",
        {"assignment": assignment}
    )


def check_grade(request):
    if not request.user.is_authenticated:
        return redirect("custom_login")

    student = request.user
    scores = Scores.objects.filter(student=student)
    assignments = Assignment.objects.all().order_by("due_date")

    submissions = Submission.objects.filter(
        student=student,
        assignment=OuterRef("pk")
    )
    assignments = assignments.annotate(has_submission=Exists(submissions))

    assignment_scores = {}
    for assignment in assignments:
        score = scores.filter(assignment=assignment).first()
        assignment_scores[assignment] = score

    return render(
        request,
        "student/check_grade.html",
        {
            "assignment_scores": assignment_scores,
            "assignments": assignments,
            "user": student,
        }
    )