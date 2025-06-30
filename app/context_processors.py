# myproject/myapp/context_processors.py

from django.db.models import Count
from .models import Camera

def common_data(request):
    return {
        'project_name': "FaceCheck",
        'is_login': request.user.is_authenticated, # Foydalanuvchi tizimga kirganmi yoki yo'qmi
    }

def camera_status(request):
    """Add camera status information to template context"""
    context = {}
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        context['active_camera_count'] = Camera.objects.filter(active=True).count()
    return context