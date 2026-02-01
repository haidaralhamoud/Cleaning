from dataclasses import dataclass
from typing import List, Type

from accounts import models as accounts_models
from home import models as home_models


@dataclass(frozen=True)
class DashboardItem:
    slug: str
    model: Type
    label: str
    icon: str


def get_dashboard_items() -> List[DashboardItem]:
    return [
        # Home app
        DashboardItem("contacts", home_models.Contact, "Contacts", "fa-solid fa-envelope"),
        DashboardItem("feedback", home_models.FeedbackRequest, "Feedback", "fa-solid fa-comment-dots"),
        DashboardItem("jobs", home_models.Job, "Jobs", "fa-solid fa-briefcase"),
        DashboardItem("applications", home_models.Application, "Applications", "fa-solid fa-file-lines"),
        DashboardItem("business-services", home_models.BusinessService, "Business Services", "fa-solid fa-building"),
        DashboardItem("business-bundles", home_models.BusinessBundle, "Business Bundles", "fa-solid fa-layer-group"),
        DashboardItem("business-addons", home_models.BusinessAddon, "Business Add-ons", "fa-solid fa-circle-plus"),
        DashboardItem("business-bookings", home_models.BusinessBooking, "Business Bookings", "fa-solid fa-calendar-check"),
        DashboardItem("private-categories", home_models.PrivateMainCategory, "Private Categories", "fa-solid fa-tags"),
        DashboardItem("private-services", home_models.PrivateService, "Private Services", "fa-solid fa-broom"),
        DashboardItem("service-cards", home_models.ServiceCard, "Service Cards", "fa-solid fa-layer-group"),
        DashboardItem("service-pricing", home_models.ServicePricing, "Service Pricing", "fa-solid fa-tag"),
        DashboardItem("service-estimates", home_models.ServiceEstimate, "Service Estimates", "fa-solid fa-calculator"),
        DashboardItem("service-eco", home_models.ServiceEcoPromise, "Eco Promise", "fa-solid fa-leaf"),
        DashboardItem("service-eco-points", home_models.ServiceEcoPoint, "Eco Points", "fa-solid fa-seedling"),
        DashboardItem("private-addons", home_models.PrivateAddon, "Private Add-ons", "fa-solid fa-puzzle-piece"),
        DashboardItem("private-bookings", home_models.PrivateBooking, "Private Bookings", "fa-solid fa-house"),
        DashboardItem("available-zips", home_models.AvailableZipCode, "Available Zips", "fa-solid fa-map-location-dot"),
        DashboardItem("not-available-zips", home_models.NotAvailableZipRequest, "Zip Requests", "fa-solid fa-location-dot"),
        DashboardItem("call-requests", home_models.CallRequest, "Call Requests", "fa-solid fa-phone"),
        DashboardItem("email-requests", home_models.EmailRequest, "Email Requests", "fa-solid fa-envelope-open-text"),
        DashboardItem("booking-form-docs", home_models.BookingFormDocument, "Booking Form Docs", "fa-solid fa-file-word"),
        DashboardItem("booking-notes", home_models.BookingNote, "Booking Notes", "fa-solid fa-note-sticky"),
        DashboardItem("status-history", home_models.BookingStatusHistory, "Status History", "fa-solid fa-clock-rotate-left"),
        DashboardItem("no-show", home_models.NoShowReport, "No Show Reports", "fa-solid fa-triangle-exclamation"),
        DashboardItem("schedule-rules", home_models.ScheduleRule, "Frequency Rules", "fa-solid fa-calendar-days"),
        DashboardItem("rot-settings", home_models.RotSetting, "ROT Settings", "fa-solid fa-percent"),
        DashboardItem("date-surcharges", home_models.DateSurcharge, "Date Surcharges", "fa-solid fa-percent"),
        # Pricing rules handled inside question options now
        # Accounts app
        DashboardItem("services", accounts_models.Service, "Services", "fa-solid fa-list-check"),
        DashboardItem("customers", accounts_models.Customer, "Customers", "fa-solid fa-user"),
        DashboardItem("customer-locations", accounts_models.CustomerLocation, "Customer Locations", "fa-solid fa-location-dot"),
        DashboardItem("customer-preferences", accounts_models.CustomerPreferences, "Customer Preferences", "fa-solid fa-sliders"),
        DashboardItem("payment-methods", accounts_models.PaymentMethod, "Payment Methods", "fa-solid fa-credit-card"),
        DashboardItem("communication-preferences", accounts_models.CommunicationPreference, "Communication Prefs", "fa-solid fa-comment-sms"),
        DashboardItem("loyalty-tiers", accounts_models.LoyaltyTier, "Loyalty Tiers", "fa-solid fa-trophy"),
        DashboardItem("rewards", accounts_models.Reward, "Rewards", "fa-solid fa-gift"),
        DashboardItem("promotions", accounts_models.Promotion, "Promotions", "fa-solid fa-bullhorn"),
        DashboardItem("discount-codes", accounts_models.DiscountCode, "Discount Codes", "fa-solid fa-ticket"),
        DashboardItem("provider-profiles", accounts_models.ProviderProfile, "Provider Profiles", "fa-solid fa-id-badge"),
        DashboardItem("provider-messages", accounts_models.ProviderAdminMessage, "Provider Messages", "fa-solid fa-paper-plane"),
        DashboardItem("provider-ratings", accounts_models.ProviderRatingSummary, "Provider Ratings", "fa-solid fa-star"),
        DashboardItem("booking-checklists", accounts_models.BookingChecklist, "Booking Checklists", "fa-solid fa-list"),
        DashboardItem("request-fixes", accounts_models.BookingRequestFix, "Request Fixes", "fa-solid fa-wrench"),
        DashboardItem("customer-notifications", accounts_models.CustomerNotification, "Customer Notifications", "fa-solid fa-bell"),
        DashboardItem("service-reviews", accounts_models.ServiceReview, "Service Reviews", "fa-solid fa-star-half-stroke"),
        DashboardItem("service-comments", accounts_models.ServiceComment, "Service Comments", "fa-solid fa-comment"),
        DashboardItem("service-content", home_models.ServiceCard, "Service Cards", "fa-solid fa-newspaper"),
        DashboardItem("points-transactions", accounts_models.PointsTransaction, "Points Transactions", "fa-solid fa-coins"),
        DashboardItem("referrals", accounts_models.Referral, "Referrals", "fa-solid fa-share-nodes"),
        DashboardItem("customer-notes", accounts_models.CustomerNote, "Customer Notes", "fa-solid fa-note-sticky"),
        DashboardItem("incidents", accounts_models.Incident, "Incidents", "fa-solid fa-triangle-exclamation"),
        DashboardItem("booking-notes-accounts", accounts_models.BookingNote, "Booking Notes (Accounts)", "fa-solid fa-note-sticky"),
    ]


def get_item_by_slug(slug: str):
    for item in get_dashboard_items():
        if item.slug == slug:
            return item
    return None
