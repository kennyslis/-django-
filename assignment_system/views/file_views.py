from io import BytesIO
import os

import nbformat
from nbconvert import HTMLExporter

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.core.files.storage import default_storage
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404

from ..models import Assignment, Submission
from ..services.export_service import (
    build_assignment_zip,
    build_batch_assignment_zip,
    build_scores_csv_response,
    build_non_submitted_text,
)


def is_teacher(user):
    return user.is_teacher


@user_passes_test(is_teacher)
def download_all_submissions(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    byte_data = build_assignment_zip(assignment)

    response = FileResponse(byte_data, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{assignment.title}_submissions.zip"'
    return response


@user_passes_test(is_teacher)
def download_batch_submissions(request):
    assignment_ids = request.GET.getlist("assignment")

    if not assignment_ids:
        return HttpResponse("未选择任何作业进行打包", status=400)

    assignments = Assignment.objects.filter(id__in=assignment_ids)

    from django.utils import timezone
    root_dir = f"Batch_Export_{timezone.now().strftime('%Y%m%d')}"
    byte_data = build_batch_assignment_zip(assignments, root_dir)

    response = FileResponse(byte_data, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{root_dir}.zip"'
    return response


def export_scores(request):
    from ..models import Assignment

    assignment_ids = request.GET.getlist("assignment")

    if "all" in assignment_ids or not assignment_ids:
        assignments = Assignment.objects.all()
    else:
        assignments = Assignment.objects.filter(id__in=assignment_ids)

    file_name = "总成绩"
    if assignments.count() == 1:
        file_name = f"{assignments.first().title}_成绩"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{file_name}.csv"'

    response = build_scores_csv_response(response, assignments)
    return response


def export_non_submitted(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)
    student_list = build_non_submitted_text(assignment)
    return JsonResponse({"student_list": student_list})


def view_ipynb_as_html(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id)

    file_path = None
    if submission.custom_answers:
        for val in submission.custom_answers.values():
            if isinstance(val, str) and val.lower().endswith(".ipynb"):
                file_path = val
                break

    if not file_path:
        return HttpResponse("未找到 .ipynb 文件")

    try:
        with default_storage.open(file_path, "rb") as f:
            notebook_content = f.read().decode("utf-8")

        notebook = nbformat.reads(notebook_content, as_version=4)
        exporter = HTMLExporter()
        body, _ = exporter.from_notebook_node(notebook)

        return HttpResponse(body, content_type="text/html")
    except Exception as e:
        return HttpResponse(f"预览失败: {str(e)}")