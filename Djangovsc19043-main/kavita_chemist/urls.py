from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # 👉 Chemist App Homepage
    path('', include('store.urls')),

    # 👉 Your old project (login, features, etc.)
    path('main/', include('main.urls')),
]
