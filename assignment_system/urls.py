from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('assignments/', views.assignment_list, name='assignment_list'),  # 学生查看所有作业
    path('assignment/<int:assignment_id>/submit/', views.student_submission, name='student_submission'),  # 学生提交作业
    path('teacher/assignments/', views.teacher_assignment_management, name='teacher_assignment_management'),  # 老师管理作业
    path('teacher/assignments/create/', views.create_assignment, name='create_assignment'),  # 布置新作业
    path('login/', views.custom_login, name='custom_login'),
    path('register/', views.register_user, name='register'), 
    path('assignment/<int:assignment_id>/submissions/', views.view_submissions, name='view_submissions'),
    path('teacher/assignments/delete/<int:assignment_id>/', views.delete_assignment, name='delete_assignment'),
    path('assignment/<int:assignment_id>/export_non_submitted/', views.export_non_submitted, name='export_non_submitted'),
    path('assignments/export/', views.export_scores, name='export_scores'),
    path('teacher/assigments/edit_assignment/<int:assignment_id>/', views.edit_assignment, name='edit_assignment'),
    path('assignment/<int:assignment_id>/submissions/<int:student_id>/grade/', views.grade_submission, name='grade_submission'),
    path('change_password/', views.change_password, name='change_password'),
    path('view-notebook/<int:submission_id>/', views.view_ipynb_as_html, name='view_ipynb'),
    path('teacher/grade_port', views.grade_port, name='grade_port'),
    path('teacher/change_pass/', views.change_pass_html, name='change_pass_html'),
    path('check_grade',views.check_grade,name='check_grade'),
    path('update_profile/', views.update_profile, name='update_profile'),
    path('export_non_submitted/<int:assignment_id>/', views.export_non_submitted, name='export_non_submitted'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-code/', views.verify_code, name='verify_code'),
    path('reset-password/', views.reset_password, name='reset_password'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)