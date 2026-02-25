from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test
from ..models import Assignment, Submission, CustomUser

def is_admin(user):
    return user.is_superuser

@user_passes_test(is_admin)
def admin_dashboard(request):
    """管理员控制台首页：数据概览"""
    stats = {
        'total_students': CustomUser.objects.filter(is_teacher=False).count(),
        'total_teachers': CustomUser.objects.filter(is_teacher=True, is_superuser=False).count(),
        'total_assignments': Assignment.objects.count(),
        'total_submissions': Submission.objects.count(),
    }
    return render(request, 'admin/dashboard.html', {'stats': stats})