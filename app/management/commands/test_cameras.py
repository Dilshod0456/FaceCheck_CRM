from django.core.management.base import BaseCommand
import cv2
import time
from ...models import Group

class Command(BaseCommand):
    help = 'Test camera connections for all groups'

    def handle(self, *args, **kwargs):
        groups = Group.objects.filter(active=True).exclude(camera_ip__isnull=True).exclude(camera_ip='')
        
        for group in groups:
            self.stdout.write(f'Testing camera for group {group.name}...')
            
            try:
                # Try to connect to the camera
                cap = cv2.VideoCapture(group.camera_ip)
                
                if not cap.isOpened():
                    self.stdout.write(self.style.ERROR(
                        f'Failed to connect to camera {group.camera_ip}'
                    ))
                    continue
                
                # Try to read a frame
                ret, frame = cap.read()
                if not ret:
                    self.stdout.write(self.style.ERROR(
                        f'Failed to read frame from camera {group.camera_ip}'
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f'Successfully connected to camera {group.camera_ip}'
                    ))
                
                # Release the camera
                cap.release()
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Error testing camera {group.camera_ip}: {str(e)}'
                ))
            
            # Wait a bit before testing next camera
            time.sleep(1)
