import time
import cv2
import numpy as np
import face_recognition
import requests
from django.utils import timezone
from django.db import transaction
from app.models import Group, Student, Attendance, Camera, GroupSchedule
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def get_active_groups():
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
    # Doimiy ravishda bazadan olib keladi
    students = Student.objects.filter(groups=group).select_related('user')
    encodings = []
    student_objs = []
    for student in students:
        print(student)
        if student.user.face_encoding:
            encoding = np.frombuffer(student.user.face_encoding, dtype=np.float64)
            encodings.append(encoding)
            student_objs.append(student)
    return encodings, student_objs

def get_cameras_for_group(group):
    return group.cameras.filter(active=True)

def v(image):
    import matplotlib.pyplot as plt
    plt.imshow(image)
    plt.axis('off')
    plt.show()

def process_group(group):
    encodings, students = get_students_for_group(group)
    cameras = get_cameras_for_group(group)
    print(encodings, students, cameras)
    if not encodings or not cameras:
        return
    print("---------------------------------")
    for camera in cameras:
        try:
            response = requests.get(camera.http_url, timeout=5, auth=(camera.username, camera.password))
            print(response)
            if response.status_code != 200:
                continue
            img_array = np.frombuffer(response.content, np.uint8)
            frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if frame is None:
                continue
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            v(rgb_frame)  # Optional: visualize the frame
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            for i, face_encoding in enumerate(face_encodings):
                matches = face_recognition.compare_faces(
                    encodings, face_encoding, 
                    tolerance=getattr(settings, 'FACE_RECOGNITION_TOLERANCE', 0.5)
                )
                if True in matches:
                    matched_idx = matches.index(True)
                    student = students[matched_idx]
                    with transaction.atomic():
                        Attendance.objects.get_or_create(
                            student=student,
                            group=group,
                            date=timezone.localdate(),
                            defaults={
                                'time': timezone.localtime().time(),
                                'status': 'present',
                                'marked_by': None,
                                'face_confidence': 1.0
                            }
                        )
        except Exception as e:
            print(e)
            logger.error(f"Camera error: {camera} - {e}")

def main_loop():
    logger.info("Attendance worker started.")
    while True:
        logger.info("Checking active groups and cameras...")
        groups = get_active_groups()
        for group in groups:
            process_group(group)
        logger.info("Sleeping for 10 minutes...")
        time.sleep(1)  # 10 minut uxlatadi

if __name__ == "__main__":
    # Dastur ishga tushganda bir marta ishlaydi
    main_loop()
