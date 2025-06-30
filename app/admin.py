from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, Department, Group, Student, Attendance, AttendanceImage, Camera, GroupSchedule

class GroupScheduleInline(admin.TabularInline):
    model = GroupSchedule
    extra = 1

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'user_type', 'is_staff')
    list_filter = ('user_type', 'is_staff', 'is_superuser', 'groups')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'user_type')}),
        (_('Profile'), {'fields': ('profile_image',)}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'user_type', 'profile_image'),
        }),
    )
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('username',)
    exclude = ('face_encoding',)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Profile image o'zgargan bo'lsa yoki yangi user bo'lsa encodingni yangilash
        from django.core.files.storage import default_storage
        import numpy as np
        import face_recognition
        import cv2
        update_encoding = False
        if change:
            old = type(obj).objects.filter(pk=obj.pk).first()
            if old and old.profile_image != obj.profile_image:
                update_encoding = True
        else:
            update_encoding = True
        if update_encoding and obj.profile_image:
            try:
                path = obj.profile_image.path if hasattr(obj.profile_image, 'path') else default_storage.path(obj.profile_image.name)
                img = cv2.imread(path)
                if img is not None:
                    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    encodings = face_recognition.face_encodings(rgb_img)
                    if encodings:
                        obj.face_encoding = np.asarray(encodings[0]).tobytes()
                    else:
                        obj.face_encoding = None
                    obj.save(update_fields=['face_encoding'])
            except Exception:
                pass

class CameraAdmin(admin.ModelAdmin):
    list_display = ('name', 'ip_address', 'location', 'active', 'last_status', 'last_checked')
    list_filter = ('active', 'last_status', 'groups')
    search_fields = ('name', 'ip_address', 'location')
    filter_horizontal = ('groups',)
    readonly_fields = ('last_status', 'last_checked')
    fieldsets = (
        (None, {
            'fields': ('name', 'ip_address', 'location', 'active')
        }),
        (_('Authentication'), {
            'fields': ('username', 'password'),
            'classes': ('collapse',)
        }),
        (_('Groups'), {
            'fields': ('groups',)
        }),
        (_('Status'), {
            'fields': ('last_status', 'last_checked'),
        })
    )

class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

class GroupAdmin(admin.ModelAdmin):
    inlines = [GroupScheduleInline]
    list_display = ('name', 'department', 'teacher', 'active', 'start_date', 'end_date')
    search_fields = ('name',)
    list_filter = ('department', 'active')

class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'get_full_name', 'get_groups')
    search_fields = ('student_id', 'user__username', 'user__first_name', 'user__last_name')
    filter_horizontal = ('groups', 'parents')
    raw_id_fields = ('user',)

    def get_full_name(self, obj):
        return obj.user.get_full_name()
    get_full_name.short_description = _('Full Name')

    def get_groups(self, obj):
        return ", ".join([g.name for g in obj.groups.all()])
    get_groups.short_description = _('Groups')

class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'group', 'date', 'time', 'status', 'marked_by')
    list_filter = ('status', 'date', 'group')
    search_fields = ('student__user__username', 'group__name')
    raw_id_fields = ('student', 'group', 'marked_by')
    date_hierarchy = 'date'

class AttendanceImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'image', 'created_at', 'processed')
    list_filter = ('processed',)
    date_hierarchy = 'created_at'

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Group, GroupAdmin)
admin.site.register(Student, StudentAdmin)
admin.site.register(Attendance, AttendanceAdmin)
admin.site.register(AttendanceImage, AttendanceImageAdmin)
admin.site.register(Camera, CameraAdmin)
admin.site.register(GroupSchedule)
