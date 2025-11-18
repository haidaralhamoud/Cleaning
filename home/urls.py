from django.urls import include, path
from . import views

app_name='home'
urlpatterns = [
    path('', views.home,name='home'),
    path('about', views.about,name='about'),
    path('contact', views.contact,name='contact'),
    path('Privacy_Policy', views.Privacy_Policy,name='Privacy_Policy'),
    path("faq/", views.faq, name="faq"),
]