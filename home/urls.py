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
]
