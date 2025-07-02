import os
import time
import cv2
import numpy as np
import face_recognition
import requests
import logging
from datetime import datetime
from django.utils import timezone
from django.db import transaction, IntegrityError
from django.conf import settings
from app.models import Group, Student, Attendance, Camera, GroupSchedule

logger = logging.getLogger(__name__)

# Cropped yuzlar uchun katalog
FACE_SAVE_DIR = os.path.join(settings.MEDIA_ROOT, 'detected_faces')
os.makedirs(FACE_SAVE_DIR, exist_ok=True)

def get_active_groups():
    """Hozirgi vaqtda aktiv bo‘lgan guruhlarni olish."""
    now = timezone.localtime()
    weekday = now.weekday()
    time_now = now.time()
    group_ids = GroupSchedule.objects.filter(
        weekday=weekday,
        start_time__lte=time_now,
        end_time__gte=time_now
    ).values_list('group_id', flat=True)
    return Group.objects.filter(id__in=group_ids, active=True)

def get_students_for_group(group):
    """Guruhdagi talabalar va ularning encodinglari."""
    students = Student.objects.filter(groups=group).select_related('user')
    encodings, student_objs = [], []
    for student in students:
        try:
            if student.user.face_encoding:
                encoding = np.frombuffer(student.user.face_encoding, dtype=np.float64)
                encodings.append(encoding)
                student_objs.append(student)
        except Exception as e:
            logger.warning(f"Encoding error for student {student.id}: {e}")
    return encodings, student_objs

def get_cameras_for_group(group):
    """Guruhga biriktirilgan faol kameralar."""
    return group.cameras.filter(active=True)

def find_best_match(encodings, face_encoding, tolerance=0.5):
    """Evklid masofa bo‘yicha eng yaqin moslik va confidence qaytaradi."""
    distances = face_recognition.face_distance(encodings, face_encoding)
    if len(distances) == 0:
        return None, None
    best_idx = np.argmin(distances)
    if distances[best_idx] <= tolerance:
        return best_idx, 1.0 - distances[best_idx]
    return None, None

def save_cropped_face(rgb_frame, location, group_id, student_id):
    """Aniqlangan yuzni crop qilib, faylga saqlaydi."""
    try:
        top, right, bottom, left = location
        face_img = rgb_frame[top:bottom, left:right]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"group{group_id}_student{student_id}_{timestamp}.jpg"
        filepath = os.path.join(FACE_SAVE_DIR, filename)
        bgr_face = cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR)
        cv2.imwrite(filepath, bgr_face)
        return filename
    except Exception as e:
        logger.error(f"Error saving cropped face: {e}")
        return None

def process_group(group):
    """Guruh bo‘yicha yuzlarni aniqlash va davomatni belgilash."""
    encodings, students = get_students_for_group(group)
    cameras = get_cameras_for_group(group)
    if not encodings or not cameras:
        logger.info(f"No encodings or cameras found for group {group.id}")
        return

    for camera in cameras:
        try:
            response = requests.get(camera.http_url, timeout=5, auth=(camera.username, camera.password))
            if response.status_code != 200:
                logger.warning(f"Camera {camera.id} returned status {response.status_code}")
                continue

            img_array = np.frombuffer(response.content, np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if frame is None:
                logger.warning(f"Invalid image from camera {camera.id}")
                continue

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for face_encoding, location in zip(face_encodings, face_locations):
                tolerance = getattr(settings, 'FACE_RECOGNITION_TOLERANCE', 0.5)
                best_idx, confidence = find_best_match(encodings, face_encoding, tolerance)
                if best_idx is not None:
                    student = students[best_idx]
                    with transaction.atomic():
                        attendance, created = Attendance.objects.get_or_create(
                            student=student,
                            group=group,
                            date=timezone.localdate(),
                            defaults={
                                'time': timezone.localtime().time(),
                                'status': 'present',
                                'marked_by': None,
                                'face_confidence': round(confidence, 4)
                            }
                        )
                        if created:
                            filename = save_cropped_face(rgb_frame, location, group.id, student.id)
                            logger.info(f"Marked attendance for student {student.id} in group {group.id}, confidence: {confidence:.4f}, image: {filename}")
                        else:
                            logger.debug(f"Attendance already exists for student {student.id} in group {group.id}")
        except Exception as e:
            logger.exception(f"Camera error: {camera} - {e}")

def main_loop(interval=1):
    """Davomat tizimini uzluksiz ishga tushiradi."""
    logger.info("Attendance worker started.")
    while True:
        try:
            logger.info("Checking active groups...")
            groups = get_active_groups()
            for group in groups:
                process_group(group)
        except Exception as e:
            logger.exception(f"Unexpected error in main loop: {e}")
        time.sleep(interval)

if __name__ == "__main__":
    # Dastur ishga tushganda bir marta ishlaydi
    main_loop()
