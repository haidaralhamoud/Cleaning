from django.urls import include, path
from . import views

app_name='home'
urlpatterns = [
    path('', views.home,name='home'),
    path('about', views.about,name='about'),
    path('contact', views.contact,name='contact'),
    path('Privacy_Policy', views.Privacy_Policy,name='Privacy_Policy'),
    path("faq/", views.faq, name="faq"),
    path("Accessibility_Statement/", views.Accessibility_Statement, name="Accessibility_Statement"),
    path("Cookies_Policy/", views.Cookies_Policy, name="Cookies_Policy"),
    path("T_C/", views.T_C, name="T_C"),
   
    path("careers_home/", views.careers_home, name="careers_home"),
    path("apply/<int:job_id>/", views.apply_page, name="apply_page"),
]
