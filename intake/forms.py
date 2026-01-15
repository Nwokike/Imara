from django import forms


class ReportForm(forms.Form):
    message_text = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Paste the abusive message or describe the incident here...'
        }),
        label='Message or Description'
    )
    
    screenshot = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        label='Upload Screenshot'
    )
    
    voice_note = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'audio/*'
        }),
        label='Upload Voice Note'
    )
    
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your.email@example.com'
        }),
        label='Your Email',
        help_text='Required. You will receive a confirmation if your report is escalated.'
    )
    
    consent = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='I understand that high-risk threats may be reported to authorities'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        message = cleaned_data.get('message_text')
        screenshot = cleaned_data.get('screenshot')
        voice_note = cleaned_data.get('voice_note')
        
        if not message and not screenshot and not voice_note:
            raise forms.ValidationError(
                'Please provide at least one form of evidence: a message, screenshot, or voice note.'
            )
        
        return cleaned_data


class ContactForm(forms.Form):
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your Name'
        }),
        label='Name'
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'your.email@example.com'
        }),
        label='Email Address'
    )
    subject = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'What is this regarding?'
        }),
        label='Subject'
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Your message here...'
        }),
        label='Message'
    )
