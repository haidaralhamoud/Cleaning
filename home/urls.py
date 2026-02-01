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
    path("feedback/", views.feedback_request, name="feedback_request"),
    path("services/contact/submit/", views.service_contact_submit, name="service_contact_submit"),
    path("dashboard/", views.dashboard_home, name="dashboard_home"),
    path("dashboard/notifications/", views.dashboard_notifications_api, name="dashboard_notifications_api"),
    path("dashboard/<str:model>/", views.dashboard_model_list, name="dashboard_model_list"),
    path("dashboard/<str:model>/add/", views.dashboard_model_create, name="dashboard_model_create"),
    path("dashboard/<str:model>/<int:pk>/edit/", views.dashboard_model_edit, name="dashboard_model_edit"),
    path("dashboard/<str:model>/<int:pk>/delete/", views.dashboard_model_delete, name="dashboard_model_delete"),
    path(
        "dashboard/date-surcharges/quick-weekend/",
        views.dashboard_date_surcharge_quick_weekend,
        name="dashboard_date_surcharge_quick_weekend",
    ),
    path("thank-you/", views.private_thank_you, name="thank_you_page"),
   
    path("careers_home/", views.careers_home, name="careers_home"),
    path("apply/<int:job_id>/", views.apply_page, name="apply_page"),

    path("business/services/", views.all_services_business, name="business_all_services"),

# Step 1 — All Services

path(
    "business/start-booking/",
    views.business_start_booking,
    name="business_start_booking"
),

    # Step 2 — Company Info
path(
    "business/company-info/<int:booking_id>/",
    views.business_company_info,
    name="business_company_info"
),


    # Step 3 — Office Setup
    path(
        "business/office-setup/<int:booking_id>/",
        views.business_office_setup,
        name="business_office_setup"
    ),

    # Step 4 — Bundles
    path(
        "business/bundles/<int:booking_id>/",
        views.business_bundles,
        name="business_bundles"
    ),

    # Step 5 — Services Needed
   path(
    "business/services-needed/<int:booking_id>/",
    views.business_services_needed,
    name="business_services_needed"
),

    # Step 6 — Add-ons
   path("business/addons/<int:booking_id>/", views.business_addons, name="business_addons"),


    # Step 7 — Frequency
   path("business/frequency/<int:booking_id>/", views.business_frequency, name="business_frequency"),


    # Step 8 — Scheduling & Notes
   path(
    "business/scheduling/<int:booking_id>/",
    views.business_scheduling,
    name="business_scheduling",
),


    # Step 9 — Thank You
    path(
        "business/thank-you/<int:booking_id>/",
        views.business_thank_you,
        name="business_thank_you"
    ),
#===============================================================================================


    path("services/private/", views.all_services, name="all_services_private"), 
    path("private/booking/<slug:service_slug>/zip/",views.private_zip_step1,name="private_zip_step1"),
    path(
        "private/booking/<slug:service_slug>/available/",
        views.private_zip_available,
        name="private_zip_available"
    ),
    path("ajax/submit-call-request/", views.submit_call_request, name="submit_call_request"),

    path(
            "private/booking/<slug:service_slug>/start/",
            views.private_booking_start,
            name="private_booking_start"
        ),
        path(
            "private/booking/<int:booking_id>/services/",
            views.private_booking_services,
            name="private_booking_services"
        ),

        path("private/cart/continue/", views.private_cart_continue, name="private_cart_continue"),
        path("private/cart/", views.private_cart, name="private_cart"),
path("private/cart/remove-json/<slug:service_slug>/", 
     views.private_cart_remove_json, 
     name="private_cart_remove_json"),
        path("private/cart/add/<slug:slug>/", views.private_cart_add, name="private_cart_add"),
path("private/cart/count/", views.private_cart_count, name="private_cart_count"),
path(
    "private/booking/<int:booking_id>/schedule/",
    views.private_booking_schedule,
    name="private_booking_schedule"
),
path(
    "private/api/booking/<int:booking_id>/price/",
    views.private_price_api,
    name="private_price_api"
),

path(
    "private/api/booking/<int:booking_id>/update-answer/",
    views.private_update_answer_api,
    name="private_update_answer_api"
),



path(
    "private/api/booking/<int:booking_id>/update-addons/",
    views.private_update_addons_api,
    name="private_update_addons_api"
),

# Checkout page
path(
    "booking/<int:booking_id>/checkout/",
    views.private_booking_checkout,
    name="private_booking_checkout"
),

path("booking/add-note/", views.add_booking_note, name="add_booking_note"),


]
