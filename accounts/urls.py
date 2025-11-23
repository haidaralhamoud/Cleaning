from django.urls import include, path
from . import views
app_name='accounts'
urlpatterns = [
    path("sign_up/", views.sign_up, name="sign_up"),
    path("customer_profile_view/", views.customer_profile_view, name="customer_profile_view"),
    path("Address_and_Locations_view/", views.Address_and_Locations_view, name="Address_and_Locations_view"),
    path("my_bookimg/", views.my_bookimg, name="my_bookimg"),
    path("incident/", views.incident, name="incident"),
    path("Service_Preferences/", views.Service_Preferences, name="Service_Preferences"),
    path("Communication/", views.Communication, name="Communication"),
    path("Customer_Notes/", views.Customer_Notes, name="Customer_Notes"),
    path("Payment_and_Billing/", views.Payment_and_Billing, name="Payment_and_Billing"),
]