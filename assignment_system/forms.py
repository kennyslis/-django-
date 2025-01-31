from django import forms
from .models import Assignment,Scores,Submission
class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['file', 'comments']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'accept': '.ipynb'}),
        }
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
