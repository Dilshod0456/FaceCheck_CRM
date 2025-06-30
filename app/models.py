from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('super_admin', 'Super Admin'),
        ('management', 'Rahbariyat'),
        ('teacher', 'O\'qituvchi'),
        ('student', 'O\'quvchi'),
        ('parent', 'Ota-ona'),
    )
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    phone_number = models.CharField(max_length=15, blank=True)
    profile_image = models.ImageField(upload_to='profile_pictures/', null=False, blank=False)
    face_encoding = models.BinaryField(null=True, blank=True)

    class Meta:
        verbose_name = _('Foydalanuvchi')
        verbose_name_plural = _('Foydalanuvchilar')

    def clean(self):
        if not self.profile_image:
            raise ValidationError('Profile image majburiy!')
        super().clean()

    def save(self, *args, **kwargs):
        # Profile image o‘zgarganda encoding yangilash
        from django.core.files.storage import default_storage
        import numpy as np
        import face_recognition
        import cv2
        update_encoding = False
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).first()
            if old and old.profile_image != self.profile_image:
                update_encoding = True
        else:
            update_encoding = True
        super().save(*args, **kwargs)
        if update_encoding and self.profile_image:
            try:
                path = self.profile_image.path if hasattr(self.profile_image, 'path') else default_storage.path(self.profile_image.name)
                img = cv2.imread(path)
                if img is not None:
                    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    encodings = face_recognition.face_encodings(rgb_img)
                    if encodings:
                        encoding_bytes = np.asarray(encodings[0]).tobytes()
                        if isinstance(encoding_bytes, bytes):
                            self.face_encoding = encoding_bytes
                        else:
                            self.face_encoding = None
                        super().save(update_fields=['face_encoding'])
                    else:
                        self.face_encoding = None
                        super().save(update_fields=['face_encoding'])
            except Exception:
                self.face_encoding = None
                super().save(update_fields=['face_encoding'])

class Department(models.Model):
    name = models.CharField(_('Bo\'lim nomi'), max_length=100)
    description = models.TextField(_('Tavsif'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _('Bo\'lim')
        verbose_name_plural = _('Bo\'limlar')

class Camera(models.Model):
    name = models.CharField(_('Kamera nomi'), max_length=100)
    ip_address = models.CharField(_('IP manzil'), max_length=200)
    username = models.CharField(_('Foydalanuvchi'), max_length=100, blank=True, null=True)
    password = models.CharField(_('Parol'), max_length=100, blank=True, null=True)
    location = models.CharField(_('Joylashuv'), max_length=200, blank=True)
    active = models.BooleanField(_('Faol'), default=True)
    last_status = models.CharField(_('Oxirgi holat'), max_length=50, blank=True)
    last_checked = models.DateTimeField(_('Oxirgi tekshiruv'), null=True, blank=True)
    groups = models.ManyToManyField('Group', related_name='cameras', verbose_name=_('Guruhlar'))
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Kamera')
        verbose_name_plural = _('Kameralar')
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.ip_address})"
    
    @property
    def http_url(self):
        """Generate HTTP snapshot URL for the camera (for still images)"""
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.ip_address}/capture"
        return f"http://{self.ip_address}/capture"

class Group(models.Model):
    name = models.CharField(_('Nomi'), max_length=100)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='groups')
    teacher = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='teaching_groups')
    start_date = models.DateField(_('Boshlanish sanasi'))
    end_date = models.DateField(_('Tugash sanasi'))
    active = models.BooleanField(_('Faol'), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Guruh')
        verbose_name_plural = _('Guruhlar')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.department.name})"

class Student(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    groups = models.ManyToManyField(Group, related_name='students')
    parents = models.ManyToManyField(CustomUser, related_name='children')
    student_id = models.CharField(_("O'quvchi ID"), max_length=20, unique=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.student_id}"

    class Meta:
        verbose_name = _("O'quvchi")
        verbose_name_plural = _("O'quvchilar")

    def clean(self):
        if not self.user.profile_image:
            raise ValidationError('Profile image majburiy!')
        super().clean()

class Attendance(models.Model):
    ATTENDANCE_STATUS = (
        ('present', 'Keldi'),
        ('absent', 'Kelmadi'),
        ('late', 'Kechikdi'),
        ('excused', 'Sababli'),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField(_('Sana'))
    time = models.TimeField(_('Vaqt'))
    status = models.CharField(max_length=10, choices=ATTENDANCE_STATUS)
    marked_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True)
    face_confidence = models.FloatField(_('Yuz aniqlash ishonchliligi'), null=True)
    note = models.TextField(_('Izoh'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = _('Davomat')
        verbose_name_plural = _('Davomatlar')
        unique_together = ['student', 'group', 'date']

class AttendanceImage(models.Model):
    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='attendance_images/')
    detected_faces = models.JSONField(default=list)
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Davomat rasmi')
        verbose_name_plural = _('Davomat rasmlari')

class GroupSchedule(models.Model):
    group = models.ForeignKey('Group', on_delete=models.CASCADE, related_name='schedules')
    weekday = models.IntegerField(choices=[(i, day) for i, day in enumerate([
        'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba'])])
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        unique_together = ('group', 'weekday', 'start_time', 'end_time')
        verbose_name = 'Dars vaqti'
        verbose_name_plural = 'Dars vaqtlari'

    def __str__(self):
        return f"{self.group.name} - {self.get_weekday_display()} {self.start_time}-{self.end_time}"

