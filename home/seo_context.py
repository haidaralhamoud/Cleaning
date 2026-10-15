import json

from django.conf import settings
from django.templatetags.static import static
from django.utils.safestring import mark_safe

DEFAULT_TITLE = "Cleaning Services in Stockholm | Hembla Experten"
DEFAULT_DESCRIPTION = (
    "Professional home and business cleaning services in Stockholm. "
    "Book online with Hembla Experten."
)

PAGE_METADATA = {
    "home:home": (
        "Home Cleaning in Stockholm | Hembla Experten",
        "Professional home and business cleaning services in Stockholm. Book online with Hembla Experten.",
    ),
    "home:about": (
        "About Hembla Experten | Stockholm Cleaning Company",
        "Meet Hembla Experten AB and learn about our professional cleaning services across Stockholm.",
    ),
    "home:contact": (
        "Contact Hembla Experten | Cleaning Services Stockholm",
        "Contact Hembla Experten to ask a question or arrange professional cleaning in Stockholm.",
    ),
    "home:faq": (
        "Cleaning FAQ | Hembla Experten Stockholm",
        "Find answers about booking, pricing, and professional cleaning services from Hembla Experten.",
    ),
    "home:all_services_private": (
        "Home Cleaning Services in Stockholm | Hembla Experten",
        "Explore professional home cleaning services in Stockholm and choose the service that fits your home.",
    ),
    "home:business_all_services": (
        "Business Cleaning Services in Stockholm | Hembla Experten",
        "Explore flexible office and business cleaning services for workplaces across Stockholm.",
    ),
    "home:airbnb_management": (
        "Airbnb Management in Stockholm | Hembla Experten",
        "Reliable Airbnb cleaning and property support for hosts and short-term rentals in Stockholm.",
    ),
    "home:Privacy_Policy": (
        "Privacy Policy | Hembla Experten",
        "Read how Hembla Experten handles and protects personal information.",
    ),
    "home:Cookies_Policy": (
        "Cookie Policy | Hembla Experten",
        "Learn how Hembla Experten uses cookies and related technologies on this website.",
    ),
    "home:T_C": (
        "Terms and Conditions | Hembla Experten",
        "Read the terms and conditions for Hembla Experten cleaning services.",
    ),
    "home:Accessibility_Statement": (
        "Accessibility Statement | Hembla Experten",
        "Read the Hembla Experten website accessibility statement and contact information.",
    ),
}


def seo_site(request):
    """Shared canonical, social metadata, and trusted business identity."""
    site_url = settings.PUBLIC_SITE_URL
    canonical_url = f"{site_url}{request.path or '/'}"
    logo_url = f"{site_url}{static('images/logo.png')}"
    default_image_url = f"{site_url}{static('images/hero2.jpeg')}"
    view_name = request.resolver_match.view_name if request.resolver_match else ""
    page_title, page_description = PAGE_METADATA.get(
        view_name, (DEFAULT_TITLE, DEFAULT_DESCRIPTION)
    )
    business_schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "@id": f"{site_url}/#business",
        "name": settings.BUSINESS_NAME,
        "url": f"{site_url}/",
        "logo": logo_url,
        "image": default_image_url,
        "telephone": settings.BUSINESS_PHONE,
        "email": settings.BUSINESS_EMAIL,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": settings.BUSINESS_STREET_ADDRESS,
            "postalCode": settings.BUSINESS_POSTAL_CODE,
            "addressLocality": settings.BUSINESS_LOCALITY,
            "addressRegion": settings.BUSINESS_REGION,
            "addressCountry": settings.BUSINESS_COUNTRY,
        },
        "areaServed": {"@type": "AdministrativeArea", "name": settings.BUSINESS_REGION},
        "priceRange": "$$",
        "openingHoursSpecification": [{
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": [
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday",
            ],
            "opens": settings.BUSINESS_OPENING_TIME,
            "closes": settings.BUSINESS_CLOSING_TIME,
        }],
    }
    schema_json = json.dumps(business_schema, ensure_ascii=False).replace("<", "\\u003c")
    return {
        "seo_site_url": site_url,
        "seo_canonical_url": canonical_url,
        "seo_default_image_url": default_image_url,
        "seo_title": page_title,
        "seo_description": page_description,
        "seo_business_schema": mark_safe(schema_json),
        "seo_is_homepage": view_name == "home:home",
    }
