from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from ..models import CustomUser
from django.views.decorators.http import require_http_methods
# 如果您还使用了 csrf_exempt，也建议一并导入
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model

User = get_user_model()
def is_admin(user):
    return user.is_superuser

@user_passes_test(is_admin)
def user_list(request):
    """用户列表：支持搜索和角色筛选"""
    query = request.GET.get('search', '')
    role = request.GET.get('role', 'all')
    
    users = CustomUser.objects.all().order_by('-id')
    if query:
        users = users.filter(name__icontains=query) | users.filter(number__icontains=query)
    if role == 'teacher':
        users = users.filter(is_teacher=True)
    elif role == 'student':
        users = users.filter(is_teacher=False)
        
    return render(request, 'admin/user_list.html', {'users': users, 'query': query, 'role': role})

@user_passes_test(is_admin)
def user_edit(request, user_id):
    """编辑用户信息"""
    user_obj = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        user_obj.name = request.POST.get('name')
        user_obj.email = request.POST.get('email')
        user_obj.number = request.POST.get('number')
        
        new_pass = request.POST.get('password')
        if new_pass: # 只有填写了新密码时才修改
            user_obj.password = make_password(new_pass)
            
        user_obj.save()
        messages.success(request, f"用户 {user_obj.name} 的资料已更新")
        return redirect('admin_user_list')
        
    return render(request, 'admin/user_form.html', {'user_obj': user_obj})

@user_passes_test(is_admin)
def user_delete(request, user_id):
    """物理删除单个用户，并保留筛选参数"""
    user_to_del = get_object_or_404(CustomUser, id=user_id)
    
    # 获取当前页面的搜索和角色参数
    search_query = request.GET.get('search', '')
    role_query = request.GET.get('role', 'all')
    
    if not user_to_del.is_superuser:
        user_to_del.delete()
        messages.success(request, f"用户已删除")

    # 拼接重定向 URL，确保筛选状态不丢失
    return redirect(f'/admin-panel/users/?search={search_query}&role={role_query}')

@user_passes_test(is_admin)
@require_http_methods(["POST"])
def batch_delete_users(request):
    """新增：批量删除勾选的用户"""
    user_ids = request.POST.getlist('selected_users')
    search_query = request.POST.get('search', '')
    role_query = request.POST.get('role', 'all')

    if user_ids:
        # 排除超级管理员，防止误删自己
        deleted_count, _ = CustomUser.objects.filter(id__in=user_ids, is_superuser=False).delete()
        messages.success(request, f"成功批量删除 {deleted_count} 名用户")
    
    return redirect(f'/admin-panel/users/?search={search_query}&role={role_query}')

def is_admin(user):
    return user.is_superuser

@user_passes_test(is_admin)
def user_change_password(request, user_id):
    """管理员强制修改学生密码"""
    user_obj = get_object_or_404(CustomUser, id=user_id)
    
    # 获取当前的筛选参数，用于保存后返回
    search_query = request.GET.get('search', '')
    role_query = request.GET.get('role', 'all')

    if request.method == 'POST':
        new_pass = request.POST.get('new_password')
        if new_pass:
            user_obj.password = make_password(new_pass)
            user_obj.save()
            messages.success(request, f"用户 {user_obj.name} 的密码修改成功！")
            # 重定向回列表并保持筛选状态
            return redirect(f'/admin-panel/users/?search={search_query}&role={role_query}')
        else:
            messages.error(request, "密码不能为空")

    return render(request, 'admin/user_password_form.html', {
        'user_obj': user_obj,
        'query': search_query,
        'role': role_query
    })
@require_POST
def user_quick_update(request):
    user_id = request.POST.get('user_id')
    field = request.POST.get('field')  # 'number' 或 'email'
    value = request.POST.get('value')

    try:
        user = User.objects.get(pk=user_id)
        
        if field == 'number':
            # 1. 唯一性检查 (检查 username 和 number 是否重复)
            if User.objects.exclude(pk=user_id).filter(username=value).exists():
                return JsonResponse({'status': 'error', 'message': f'账号/学号 [{value}] 已存在'})
            
            # 2. 同步修改！关键点：同时修改 number 和 username
            user.number = value
            user.username = value  # 确保登录账号同步更新
            
        elif field == 'email':
            if User.objects.exclude(pk=user_id).filter(email=value).exists():
                return JsonResponse({'status': 'error', 'message': f'邮箱 [{value}] 已被占用'})
            user.email = value
        
        user.save()
        return JsonResponse({'status': 'success'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})