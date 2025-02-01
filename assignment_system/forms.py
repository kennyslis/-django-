from django import forms
from .models import Assignment,Scores,Submission
from django.core.exceptions import ValidationError
class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['file', 'comments']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'accept': '.ipynb'}),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')

        if file:
            # 检查文件后缀名
            if not file.name.endswith('.ipynb'):
                raise ValidationError("只能提交 .ipynb 格式的文件。")
        return file
class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'due_date']
        widgets = {
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class ScoreForm(forms.ModelForm):
    class Meta:
        model = Scores
        fields = ['score']
