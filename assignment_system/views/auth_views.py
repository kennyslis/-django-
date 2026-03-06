import random

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render

from ..models import CustomUser


def custom_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            if user.is_superuser:
                return redirect("admin_dashboard")
            elif user.is_teacher:
                return redirect("teacher_assignment_management")
            else:
                return redirect("assignment_list")
        else:
            return render(
                request,
                "auth/custom_login.html",
                {"error_message": "账户或密码错误。"}
            )

    return render(request, "auth/custom_login.html")


def register_user(request):
    if request.method == "POST":
        number = request.POST.get("number")
        username = request.POST.get("username")
        password = request.POST.get("password")
        name = request.POST.get("name")
        email = request.POST.get("email")
        is_teacher = request.POST.get("is_teacher") == "on"

        if CustomUser.objects.filter(username=username).exists():
            return render(
                request,
                "auth/register_user.html",
                {"error_message": "用户名已存在，请更换。"}
            )

        if number and CustomUser.objects.filter(number=number).exists():
            return render(
                request,
                "auth/register_user.html",
                {"error_message": "学号已存在，请检查后重试。"}
            )

        user = CustomUser.objects.create_user(
            username=username,
            password=password,
            is_teacher=is_teacher,
            name=name,
            email=email,
            number=number
        )

        login(request, user)
        return HttpResponseRedirect("/login/")

    return render(request, "auth/register_user.html")


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return render(
                request,
                "auth/forgot_password.html",
                {"error_message": "该邮箱不存在，请检查后重试。"}
            )

        verification_code = str(random.randint(100000, 999999))

        from django.core.mail import send_mail
        send_mail(
            "密码重置验证码",
            f"您的密码重置验证码是: {verification_code}",
            "2819024054@qq.com",
            [user.email],
            fail_silently=False,
        )

        request.session["verification_code"] = verification_code
        request.session["email"] = email

        return redirect("verify_code")

    return render(request, "auth/forgot_password.html")


def verify_code(request):
    if request.method == "POST":
        entered_code = request.POST.get("code")
        verification_code = request.session.get("verification_code")

        if entered_code == verification_code:
            return redirect("reset_password")
        else:
            return render(
                request,
                "auth/verify_code.html",
                {"error_message": "验证码错误，请检查后重试。"}
            )

    return render(request, "auth/verify_code.html")


def reset_password(request):
    if request.method == "POST":
        new_password = request.POST.get("new_password")
        email = request.session.get("email")

        if not email:
            return redirect("forgot_password")

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            return render(
                request,
                "auth/reset_password.html",
                {"error_message": "用户不存在。"}
            )

        user.set_password(new_password)
        user.save()

        request.session.pop("verification_code", None)
        request.session.pop("email", None)

        messages.success(request, "密码已成功重置，请重新登录。")
        return redirect("custom_login")

    return render(request, "auth/reset_password.html")


@login_required
def update_profile(request):
    user = request.user

    if request.method == "POST":
        name = request.POST.get("username")
        email = request.POST.get("email")
        number = request.POST.get("number")

        if number and CustomUser.objects.filter(number=number).exclude(id=user.id).exists():
            return render(
                request,
                "student/update_profile.html",
                {"user": user, "error_message": "学号已存在，请选择其他学号。"}
            )

        user.name = name
        user.email = email
        user.number = number
        user.save()

        return render(
            request,
            "student/update_profile.html",
            {"user": user, "error_message": "个人信息更新成功！"}
        )

    return render(request, "student/update_profile.html", {"user": user})