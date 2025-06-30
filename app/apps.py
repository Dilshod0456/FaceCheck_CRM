from django.apps import AppConfig
import threading
import logging
import os

logger = logging.getLogger(__name__)

class AppConfiguration(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    
    def ready(self):
        # Import here to avoid circular imports
        from . import attendance_worker
        
        # Prevent running twice in development server
        if os.environ.get('RUN_MAIN'):
            def start_worker():
                try:
                    logger.info("Starting attendance worker thread...")
                    attendance_worker.main_loop()
                except Exception as e:
                    logger.error(f"Attendance worker error: {e}")
            worker_thread = threading.Thread(target=start_worker, daemon=True, name="AttendanceWorker")
            worker_thread.start()
