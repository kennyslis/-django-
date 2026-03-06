from django.urls import path

from .views import auth_views, student_views, teacher_views, file_views, report_views
from .llm import ai_teacher_assistant_llm
from .admin_views import dashboard as admin_dash
from .admin_views import users as admin_user
from .admin_views.users import user_quick_update


urlpatterns = [
    # =========================
    # 登录 / 注册 / 找回密码
    # =========================
    path("", auth_views.custom_login, name="custom_login"),
    path("login/", auth_views.custom_login, name="custom_login"),
    path("register/", auth_views.register_user, name="register"),
    path("forgot-password/", auth_views.forgot_password, name="forgot_password"),
    path("verify-code/", auth_views.verify_code, name="verify_code"),
    path("reset-password/", auth_views.reset_password, name="reset_password"),
    path("update_profile/", auth_views.update_profile, name="update_profile"),

    # =========================
    # 学生端
    # =========================
    path("assignments/", student_views.assignment_list, name="assignment_list"),
    path("assignment/<int:assignment_id>/submit/", student_views.student_submission, name="student_submission"),
    path("check_grade", student_views.check_grade, name="check_grade"),

    # =========================
    # 老师端
    # =========================
    path("import/", teacher_views.import_students, name="import_students"),

    path("teacher/assignments/", teacher_views.teacher_assignment_management, name="teacher_assignment_management"),
    path("teacher/assignments/create/", teacher_views.create_assignment, name="create_assignment"),
    path("teacher/assignments/delete/<int:assignment_id>/", teacher_views.delete_assignment, name="delete_assignment"),
    path("teacher/assigments/edit_assignment/<int:assignment_id>/", teacher_views.edit_assignment, name="edit_assignment"),

    path("assignment/<int:assignment_id>/submissions/", teacher_views.view_submissions, name="view_submissions"),
    path("assignment/<int:assignment_id>/submissions/<int:student_id>/grade/", teacher_views.grade_submission, name="grade_submission"),
    path("batch_grade/<int:assignment_id>/", teacher_views.batch_grade, name="batch_grade"),

    path("teacher/grade_port", teacher_views.grade_port, name="grade_port"),
    path("teacher/change_pass/", teacher_views.change_pass_html, name="change_pass_html"),
    path("change_password/", teacher_views.change_password, name="change_password"),

    # AI 生成作业表单
    path("teacher/ai/generate_form/", teacher_views.ai_generate_form_config, name="ai_generate_form_config"),

    # AI 小助手
    path("ai/", teacher_views.ai_assistant_page, name="ai_assistant"),
    path("ai/api/", teacher_views.ai_teacher_assistant_api, name="ai_assistant_api"),

    # =========================
    # 文件 / 导出 / 预览
    # =========================
    path("view-notebook/<int:submission_id>/", file_views.view_ipynb_as_html, name="view_ipynb"),
    path("assignment/<int:assignment_id>/download_all/", file_views.download_all_submissions, name="download_all_submissions"),
    path("assignment/download_batch/", file_views.download_batch_submissions, name="download_batch_submissions"),
    path("assignments/export/", file_views.export_scores, name="export_scores"),
    path("export_non_submitted/<int:assignment_id>/", file_views.export_non_submitted, name="export_non_submitted"),

    # =========================
    # 学情分析
    # =========================
    path("learning-report/", report_views.learning_report_page, name="learning_report"),
    path("learning-report/data/", report_views.learning_report_data, name="learning_report_data"),
    path("learning-report/pdf/", report_views.learning_report_pdf, name="learning_report_pdf"),

    # =========================
    # 管理员后台
    # =========================
    path("admin-panel/", admin_dash.admin_dashboard, name="admin_dashboard"),
    path("admin-panel/users/", admin_user.user_list, name="admin_user_list"),
    path("admin-panel/users/edit/<int:user_id>/", admin_user.user_edit, name="admin_user_edit"),
    path("admin-panel/users/delete/<int:user_id>/", admin_user.user_delete, name="admin_user_delete"),
    path("admin-panel/users/batch-delete/", admin_user.batch_delete_users, name="batch_delete_users"),
    path("admin-panel/users/password/<int:user_id>/", admin_user.user_change_password, name="admin_user_change_password"),
    path("admin-panel/users/quick-update/", user_quick_update, name="admin_user_quick_update"),
]