from django.urls import include, path
from . import views
app_name='accounts'
urlpatterns = [

    path("sign_up/", views.sign_up, name="sign_up"),
]