from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from ...models import Camera
from ...attendance_worker import AttendanceMonitor
import time
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Starts the threaded attendance monitoring system'

    def handle(self, *args, **kwargs):
        self.stdout.write('Starting attendance monitoring...')
        
        monitor = AttendanceMonitor()
        
        try:
            while True:
                # Get active cameras and their associated groups
                cameras = Camera.objects.filter(
                    active=True,
                    groups__active=True
                ).distinct()
                
                if cameras.exists():
                    monitor.start_monitoring(list(cameras))
                    self.stdout.write(f'Monitoring {cameras.count()} cameras...')
                    
                    # Run for 20 minutes
                    time.sleep(1200)
                    
                    # Stop monitoring
                    monitor.stop_monitoring()
                    self.stdout.write('Pausing monitoring...')
                else:
                    logger.warning('No active cameras found')
                
                # Wait for next cycle
                time.sleep(60)  # Wait 1 minute before checking again
                
        except KeyboardInterrupt:
            self.stdout.write('Stopping attendance monitoring...')
            monitor.stop_monitoring()
