from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static


app_name = 'app'

urlpatterns = [
    # Authentication URLs
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.user_profile, name='user_profile'),  # Add this line for user profile
    
    # Teacher URLs
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/add/', views.teacher_add, name='teacher_add'),
    path('teachers/<int:pk>/', views.teacher_detail, name='teacher_detail'),
    path('teachers/<int:pk>/edit/', views.teacher_edit, name='teacher_edit'),
    path('teachers/<int:pk>/delete/', views.teacher_delete, name='teacher_delete'),
    
    # Dashboard URLs
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Department URLs
    path('departments/', views.department_list, name='department_list'),
    path('departments/add/', views.department_add, name='department_add'),
    path('departments/<int:pk>/edit/', views.department_edit, name='department_edit'),
    path('departments/<int:pk>/delete/', views.department_delete, name='department_delete'),
    
    # Group URLs
    path('groups/', views.group_list, name='group_list'),
    path('groups/add/', views.group_add, name='group_add'),
    path('groups/<int:pk>/', views.group_detail, name='group_detail'),
    path('groups/<int:pk>/edit/', views.group_edit, name='group_edit'),
    path('groups/<int:pk>/delete/', views.group_delete, name='group_delete'),
    
    # Student URLs
    path('students/', views.student_list, name='student_list'),
    path('students/add/', views.student_add, name='student_add'),
    path('students/<int:pk>/', views.student_detail, name='student_detail'),
    path('students/<int:pk>/edit/', views.student_edit, name='student_edit'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    
    # Attendance URLs
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/add/', views.attendance_add, name='attendance_add'),
    path('attendance/<int:pk>/', views.attendance_detail, name='attendance_detail'),
    path('attendance/group/<int:group_id>/', views.group_attendance, name='group_attendance'),
    path('attendance/student/<int:student_id>/', views.student_attendance, name='student_attendance'),
    
    # AI-based Attendance
    path('attendance/capture/', views.attendance_capture, name='attendance_capture'),
    path('attendance/process/', views.process_attendance, name='process_attendance'),
    
    # Reports
    path('reports/department/', views.department_report, name='department_report'),
    path('reports/group/', views.group_report, name='group_report'),
    path('reports/student/', views.student_report, name='student_report'),
    path('reports/export/', views.export_report, name='export_report'),
    
    # API endpoints for HTMX
    path('api/attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('api/groups/filter/', views.filter_groups, name='filter_groups'),
    path('api/students/filter/', views.filter_students, name='filter_students'),
    
    # Camera management
    path('cameras/', views.camera_list, name='camera_list'),
    path('cameras/add/', views.camera_add, name='camera_add'),
    path('cameras/<int:pk>/edit/', views.camera_edit, name='camera_edit'),
    path('cameras/<int:pk>/test/', views.camera_test, name='camera_test'),    path('cameras/<int:pk>/toggle/', views.camera_toggle, name='camera_toggle'),
    path('cameras/<int:pk>/delete/', views.camera_delete, name='camera_delete'),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)