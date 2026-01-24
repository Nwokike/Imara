from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif']
ALLOWED_AUDIO_TYPES = ['audio/mpeg', 'audio/mp3', 'audio/wav', 'audio/ogg', 'audio/webm', 'audio/x-m4a']


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
        label='Upload Screenshot',
        help_text='Maximum file size: 10MB. Supported formats: JPEG, PNG, WebP, GIF'
    )
    
    voice_note = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'audio/*'
        }),
        label='Upload Voice Note',
        help_text='Maximum file size: 10MB. Supported formats: MP3, WAV, OGG, WebM'
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
        label='I understand that high-risk threats may be shared with verified support partners'
    )
    
    def clean_screenshot(self):
        screenshot = self.cleaned_data.get('screenshot')
        if screenshot:
            if screenshot.size > MAX_FILE_SIZE:
                raise ValidationError(
                    f'File size exceeds the maximum allowed size of {MAX_FILE_SIZE // (1024*1024)}MB. '
                    'Please upload a smaller file.'
                )
            
            content_type = screenshot.content_type
            if content_type not in ALLOWED_IMAGE_TYPES:
                raise ValidationError(
                    f'Invalid file type. Allowed formats: JPEG, PNG, WebP, GIF. '
                    f'Received: {content_type}'
                )
        return screenshot
    
    def clean_voice_note(self):
        voice_note = self.cleaned_data.get('voice_note')
        if voice_note:
            if voice_note.size > MAX_FILE_SIZE:
                raise ValidationError(
                    f'File size exceeds the maximum allowed size of {MAX_FILE_SIZE // (1024*1024)}MB. '
                    'Please upload a smaller file.'
                )
            
            content_type = getattr(voice_note, 'content_type', None)
            if not content_type:
                name = getattr(voice_note, 'name', '')
                ext = name.lower().split('.')[-1] if '.' in name else ''
                ext_to_mime = {
                    'mp3': 'audio/mpeg',
                    'wav': 'audio/wav',
                    'ogg': 'audio/ogg',
                    'webm': 'audio/webm',
                    'm4a': 'audio/x-m4a'
                }
                content_type = ext_to_mime.get(ext, '')
            
            if content_type and content_type not in ALLOWED_AUDIO_TYPES:
                raise ValidationError(
                    f'Invalid file type. Allowed formats: MP3, WAV, OGG, WebM. '
                    f'Received: {content_type or "unknown"}'
                )
        return voice_note

    name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Your name (optional)'
        }),
        label='Your Name (Optional)',
        help_text='Optional. You can use a nickname.'
    )

    location = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'City, Country (e.g. Lagos, Nigeria)'
        }),
        label='Location',
        help_text='Required for high-risk reports (threats, violence) to connect you with help.'
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
