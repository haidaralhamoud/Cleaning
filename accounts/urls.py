from django.urls import include, path
from . import views
app_name='accounts'
urlpatterns = [
    path("sign_up/", views.sign_up, name="sign_up"),

    # Sidebar
    path("customer_profile_view/", views.customer_profile_view, name="customer_profile_view"),
    path("Address_and_Locations_view/", views.Address_and_Locations_view, name="Address_and_Locations_view"),
    path("my_bookimg/", views.my_bookimg, name="my_bookimg"),
    path("incident/", views.incident, name="incident"),
    path("Service_Preferences/", views.Service_Preferences, name="Service_Preferences"),
    path("Communication/", views.Communication, name="Communication"),
    path("Customer_Notes/", views.Customer_Notes, name="Customer_Notes"),
    path("Payment_and_Billing/", views.Payment_and_Billing, name="Payment_and_Billing"),
    path("Change_Password/", views.Change_Password, name="Change_Password"),
    path("Service_History_and_Ratings/", views.Service_History_and_Ratings, name="Service_History_and_Ratings"),
    path("Loyalty_and_Rewards/", views.Loyalty_and_Rewards, name="Loyalty_and_Rewards"),
    path("logout/", views.logout_view, name="logout"),
]