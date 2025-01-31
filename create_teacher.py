import os
import django
from django.conf import settings

# 设置 Django 环境变量
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "assignment_system.settings")  # 替换为你的项目设置模块
django.setup()

from assignment_system.models import CustomUser  # 替换为你的应用名

def create_teacher(username, name, password):
    """通过用户名、姓名和密码创建一个教师用户"""
    # 获取或创建教师用户
    teacher, created = CustomUser.objects.get_or_create(
        username=username,
        defaults={  
            'is_staff': True,     # 设置为后台管理权限
            'is_superuser': False, 
            'name': name,         # 使用传入的姓名
            'is_teacher': True,   # 设置 is_teacher 为 True，表示是老师
        }
    )

    if created:
        teacher.set_password(password)  # 设置密码
        teacher.save()
        print(f"教师用户 {teacher.name} 创建成功，状态：{created}")
    else:
        print(f"教师用户 {teacher.name} 已存在。")

if __name__ == "__main__":
    # 提示用户输入教师账号、姓名和密码
    username = input("请输入教师账号: ")
    name = input("请输入教师姓名: ")
    password = input("请输入教师密码: ")

    create_teacher(username, name, password)
