"""
URL configuration for kavita_chemist project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Admin panel
    path('admin/', admin.site.urls),

    # Main app routes (homepage + all features)
    path('', include('main.urls')),
]