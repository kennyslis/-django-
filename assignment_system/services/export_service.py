import csv
import os
import zipfile
from io import BytesIO

from django.conf import settings

from ..models import Assignment, Submission, CustomUser, Scores


def build_assignment_zip(assignment):
    """
    打包单个作业的所有提交文件，返回 BytesIO
    """
    submissions = Submission.objects.filter(assignment=assignment)

    byte_data = BytesIO()
    with zipfile.ZipFile(byte_data, "w") as zip_file:
        for sub in submissions:
            if sub.custom_answers:
                for val in sub.custom_answers.values():
                    if isinstance(val, str):
                        full_path = os.path.join(settings.MEDIA_ROOT, val)
                        if os.path.exists(full_path):
                            arcname = os.path.join(assignment.title, os.path.basename(full_path))
                            zip_file.write(full_path, arcname=arcname)

    byte_data.seek(0)
    return byte_data


def build_batch_assignment_zip(assignments, root_dir):
    """
    批量打包多个作业，返回 BytesIO
    """
    byte_data = BytesIO()

    with zipfile.ZipFile(byte_data, "w") as zip_file:
        for assignment in assignments:
            submissions = Submission.objects.filter(assignment=assignment)
            for sub in submissions:
                if sub.custom_answers:
                    for val in sub.custom_answers.values():
                        if isinstance(val, str):
                            full_path = os.path.join(settings.MEDIA_ROOT, val)
                            if os.path.exists(full_path):
                                filename = os.path.basename(full_path)
                                arcname = os.path.join(root_dir, assignment.title, filename)
                                zip_file.write(full_path, arcname=arcname)

    byte_data.seek(0)
    return byte_data


def build_scores_csv_response(response, assignments):
    """
    向 HttpResponse 写入成绩 CSV
    """
    all_students = CustomUser.objects.filter(is_teacher=False, is_superuser=False)

    response.write("\ufeff")
    writer = csv.writer(response, quotechar='"', quoting=csv.QUOTE_MINIMAL)

    columns = ["学号", "姓名"] + [a.title for a in assignments]
    writer.writerow(columns)

    for student in all_students:
        row = [student.number, student.name]
        for a in assignments:
            score = Scores.objects.filter(student=student, assignment=a).first()
            submission_exists = Submission.objects.filter(student=student, assignment=a).exists()
            if not submission_exists:
                row.append("未提交")
            else:
                row.append(score.score if score else 0)
        writer.writerow(row)

    return response


def build_non_submitted_text(assignment):
    """
    返回未交名单文本
    """
    all_students = CustomUser.objects.filter(is_teacher=False, is_superuser=False)
    submitted_student_ids = Submission.objects.filter(assignment=assignment).values_list("student_id", flat=True)
    non_submitted_students = all_students.exclude(id__in=submitted_student_ids)

    student_list = "以下学生未提交作业:\n"
    if non_submitted_students.exists():
        for student in non_submitted_students:
            student_list += f"{student.name}  {student.number}  {assignment.title}\n"
    else:
        student_list = "所有学生已提交。\n"

    return student_list