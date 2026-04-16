"""
URL configuration for PRO project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path , include
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.auth import views as auth_views
from accounts.views import RememberMeLoginView
from accounts import views as account_views
urlpatterns = [
    path("accounts/login/", RememberMeLoginView.as_view(), name="login"),
    path("accounts/password_reset/", account_views.password_reset_request, name="password_reset"),
    path("accounts/password_reset/verify/", account_views.password_reset_verify, name="password_reset_verify"),
    path("accounts/password_reset/new/", account_views.password_reset_new, name="password_reset_new"),
    path("accounts/password_reset/success/", account_views.password_reset_success, name="password_reset_success"),
    path('i18n/', include('django.conf.urls.i18n')),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/', include('allauth.urls')),
    path('admin/', admin.site.urls),
    path('', include('home.urls' , namespace='home') ),
    path('accounts/', include('accounts.urls' , namespace='accounts') ),
    path('accounts/', include('social_django.urls', namespace='social')),
]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

