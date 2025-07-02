from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import numpy as np
import face_recognition
import cv2
from django.core.files.storage import default_storage
import logging
import time
logger = logging.getLogger(__name__)



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

    def extract_face_encoding(self, image_path):
        try:
            img = cv2.imread(image_path)
            if img is None:
                logger.warning(f"Image could not be read: {image_path}")
                return None

            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_img)

            if not face_locations:
                logger.info("No face detected in the image.")
                return None

            # 1-chi yuz koordinatasini olish
            top, right, bottom, left = face_locations[0]

            # ✅ To‘g‘ri argument bilan encoding olish
            encodings = face_recognition.face_encodings(rgb_img, known_face_locations=[(top, right, bottom, left)])

            if encodings:
                return np.asarray(encodings[0], dtype=np.float64).tobytes()
        except Exception as e:
            logger.error(f"Error during face encoding extraction: {e}")
        return None

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        profile_changed = False

        if not is_new:
            try:
                old = type(self).objects.get(pk=self.pk)
                profile_changed = old.profile_image != self.profile_image
            except type(self).DoesNotExist:
                profile_changed = True
        else:
            profile_changed = True

        # STEP 1: Avval Fayl kirish uchun rasmni saqlang
        super().save(*args, **kwargs)
        # STEP 2: Endi yuz kodlash (faqat yangi yoki yangilangan bo'lsa)
        if profile_changed and self.profile_image:
            try:
                path = self.profile_image.path if hasattr(self.profile_image, 'path') else default_storage.path(self.profile_image.name)
                encoding = self.extract_face_encoding(path)

                if encoding and isinstance(encoding, (bytes, bytearray, memoryview)):
                    self.face_encoding = encoding
                else:
                    self.face_encoding = None

                # Only update face_encoding field
                super().save(update_fields=['face_encoding'])

            except Exception as e:
                logger.error(f"Failed to update face encoding: {e}")
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

