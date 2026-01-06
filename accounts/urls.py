from django.urls import include, path
from . import views
app_name='accounts'
urlpatterns = [
    path("sign_up/", views.sign_up, name="sign_up"),

    # Sidebar
    path("customer_profile_view/", views.customer_profile_view, name="customer_profile_view"),
    path("Address_and_Locations_view/", views.Address_and_Locations_view, name="Address_and_Locations_view"),
    path("Address_and_Locations_view/<int:location_id>/set_location_primary", views.set_location_primary, name="set_location_primary"),
    path("Address_and_Locations_view/<int:location_id>/delete_location/", views.delete_location, name="delete_location"),
    path("address-locations/<int:location_id>/edit_address_and_locations/",views.edit_address_and_locations,name="edit_address_and_locations"),
    path("my_bookimg/", views.my_bookimg, name="my_bookimg"),
    path("incident/", views.incident, name="incident"),
    path("Service_Preferences/", views.Service_Preferences, name="Service_Preferences"),
    path("Communication/", views.Communication, name="Communication"),
    path("Customer_Notes/", views.Customer_Notes, name="Customer_Notes"),
    path("Payment_and_Billing/", views.Payment_and_Billing, name="Payment_and_Billing"),
    path("payment-billing/default/<int:pk>/", views.set_payment_default, name="set_payment_default"),
    path("payment-billing/delete/<int:pk>/", views.delete_payment_method, name="delete_payment_method"),
    path("Change_Password/", views.Change_Password, name="Change_Password"),
    path("Service_History_and_Ratings/", views.Service_History_and_Ratings, name="Service_History_and_Ratings"),
    path("Loyalty_and_Rewards/", views.Loyalty_and_Rewards, name="Loyalty_and_Rewards"),
    
    # Subpages
    path("add_Customer_Notes/", views.add_Customer_Notes, name="add_Customer_Notes"),
    path("Add_Payment_Method/", views.Add_Payment_Method, name="Add_Payment_Method"),
    path("Add_Address_and_Locations/", views.Add_Address_and_Locations, name="Add_Address_and_Locations"),
    path("Incident_Report_order/<int:incident_id>", views.Incident_Report_order, name="Incident_Report_order"),
    path("view_service_details/", views.view_service_details, name="view_service_details"),
    path("chat/", views.chat, name="chat"),
    path("Add_on_Service_Request/", views.Add_on_Service_Request, name="Add_on_Service_Request"),
    path("Media/", views.Media, name="Media"),
    path("Report_Incident/", views.Report_Incident, name="Report_Incident"),
    
    path("logout/", views.logout_view, name="logout"),
]