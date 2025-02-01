from django.db import models
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import AbstractUser
import os
import nbformat
from nbconvert import HTMLExporter
from django.core.files.base import ContentFile
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError
class CustomUser(AbstractUser):
    number = models.IntegerField(unique=True, verbose_name='学号', null=True, blank=True)
    name = models.CharField(max_length=100, verbose_name='姓名', default='Unknown')
    is_teacher = models.BooleanField(default=False, verbose_name="是否为老师")
    id=models.BigAutoField(primary_key=True)

    def __str__(self):
        return str(self.number)

    @classmethod
    def create_teacher(cls, username, password):
        """创建一个专属的老师用户"""
        teacher, created = cls.objects.get_or_create(
            username=username,
            defaults={  
                'is_staff': True,     # 表示有后台管理权限
                'is_superuser': False, 
                'name': 'Teacher',    # 可以设置老师的默认名称
                'is_teacher': True,   # 设置 is_teacher 为 True，表示是老师
            }
        )
        
        if created:  
            teacher.set_password(password)  
            teacher.save()
            return teacher, 'created'
        else:
            return teacher, 'exists'  

class Question(models.Model):
    id = models.BigAutoField(primary_key=True)
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')

    def __str__(self):
        return self.question_text

    def was_published_recently(self):
        return self.pub_date >= timezone.now() - timezone.timedelta(days=1)


class Assignment(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateTimeField()

    def __str__(self):
        return self.title

def get_upload_path(instance, filename):
    # 动态生成文件上传路径，基于作业标题
    assignment_title = instance.assignment.title.replace(' ', '_')
    return os.path.join('submissions', assignment_title, filename)



class Submission(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assignment = models.ForeignKey('Assignment', on_delete=models.CASCADE)
    file = models.FileField(upload_to=get_upload_path)  # 动态上传路径
    submission_date = models.DateTimeField(auto_now_add=True)
    comments = models.TextField(blank=True, null=True)
    creat_at=models.DateTimeField(auto_now=True)
    def save(self, *args, **kwargs):
        """自动为提交文件生成标准化的文件名"""
        if self.assignment.due_date < timezone.now():
            raise ValidationError("作业提交已过截止日期，无法提交！")
        if self.file:
            # 为提交的文件动态生成文件名
            new_filename = f"{self.student.name}_{self.assignment.title}.ipynb"
            self.file.name = new_filename

        super(Submission, self).save(*args, **kwargs)


class Scores(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assignment = models.ForeignKey('Assignment', on_delete=models.CASCADE)
    score = models.DecimalField(max_digits=5, decimal_places=2,verbose_name="成绩",default=0)
    submission=models.ForeignKey('Submission',on_delete=models.CASCADE,related_name='score', null=True, blank=True,default=None)
    def Meta(self):
        unique_together = ('student', 'assignment')
    def __str__(self):
        return f"{self.student.username} - {self.assignment.title} - {self.score}"



