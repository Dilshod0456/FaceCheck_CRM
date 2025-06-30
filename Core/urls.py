from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns

urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),  # Tilni o‘zgartirish uchun
]

urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
)
