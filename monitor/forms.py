from django import forms

# Forms
class AnnouncementFilterForm(forms.Form):
    search = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'E\'lonlarda qidirish...', 
        'class': 'form-control'
    }))
    confidence_min = forms.FloatField(required=False, widget=forms.NumberInput(attrs={
        'min': 0, 'max': 1, 'step': 0.1, 
        'class': 'form-control',
        'placeholder': 'Min ishonch darajasi'
    }))
    is_verified = forms.ChoiceField(choices=[
        ('', 'Barcha holatlar'),
        ('true', 'Faqat tasdiqlangan'),
        ('false', 'Tasdiqlanmagan'),
    ], required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    has_media = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={
        'class': 'form-check-input'
    }))
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={
        'type': 'date', 'class': 'form-control'
    }))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={
        'type': 'date', 'class': 'form-control'
    }))

class QuickVerifyForm(forms.Form):
    announcement_id = forms.IntegerField(widget=forms.HiddenInput())
    action = forms.CharField(max_length=10, widget=forms.HiddenInput())