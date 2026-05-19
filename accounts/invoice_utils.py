from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils import timezone

from accounts.models import Customer, Invoice, InvoiceLineItem
from home.invoice_pdf import _format_money, build_branded_invoice_pdf, default_logo_path, get_invoice_sender_details
from home.models import PrivateAddon, PrivateBooking, PrivateService


PRIVATE_BOOKING_SERVICE_FEE = Decimal("50.00")
DEFAULT_VAT_PERCENT = Decimal("25.00")


def _q(value: Decimal | str | int | float | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _format_private_service_time(booking: PrivateBooking, service_slug: str | None = None) -> str:
    schedule_mode = getattr(booking, "schedule_mode", "same") or "same"
    if schedule_mode == "per_service" and service_slug:
        service_schedules = booking.service_schedules or {}
        service_data = service_schedules.get(service_slug) or {}
        service_date = service_data.get("date") or ""
        service_time = service_data.get("start_time") or service_data.get("time_window") or ""
        parts = [str(part).strip() for part in [service_date, service_time] if str(part or "").strip()]
        return " / ".join(parts)

    parts = []
    if getattr(booking, "appointment_date", None):
        parts.append(str(booking.appointment_date))
    if getattr(booking, "appointment_start_time", None):
        parts.append(str(booking.appointment_start_time))
    elif getattr(booking, "appointment_time_window", None):
        parts.append(str(booking.appointment_time_window))
    return " / ".join(parts)


def _private_service_map(booking: PrivateBooking):
    slugs = [slug for slug in (booking.selected_services or []) if isinstance(slug, str) and slug.strip()]
    services = PrivateService.objects.filter(slug__in=slugs)
    return {service.slug: service for service in services}


def _next_line_order(invoice: Invoice) -> int:
    return (invoice.line_items.aggregate_max_order() if hasattr(invoice.line_items, "aggregate_max_order") else None) or 0


def _ensure_service_fee_line(invoice: Invoice, currency: str):
    line, _ = InvoiceLineItem.objects.get_or_create(
        invoice=invoice,
        is_service_fee=True,
        defaults={
            "line_order": 999,
            "description": "Service Fee",
            "service_time": "",
            "quantity": Decimal("1.00"),
            "unit_price": PRIVATE_BOOKING_SERVICE_FEE,
            "discount_amount": Decimal("0.00"),
            "rot_rut_amount": Decimal("0.00"),
            "vat_percent": DEFAULT_VAT_PERCENT,
        },
    )
    changed = False
    if line.description != "Service Fee":
        line.description = "Service Fee"
        changed = True
    if _q(line.unit_price) != PRIVATE_BOOKING_SERVICE_FEE:
        line.unit_price = PRIVATE_BOOKING_SERVICE_FEE
        changed = True
    if _q(line.quantity) != Decimal("1.00"):
        line.quantity = Decimal("1.00")
        changed = True
    if changed:
        line.save()


def populate_invoice_from_private_booking(invoice: Invoice, booking: PrivateBooking, reset_items: bool = False):
    service_map = _private_service_map(booking)
    currency = ((booking.payment_currency or invoice.currency or "SEK") or "SEK").upper()

    if reset_items:
        invoice.line_items.all().delete()

    invoice.currency = currency
    invoice.booking_type = "private"
    invoice.booking_id = booking.id
    invoice.customer_number = str(booking.user_id or "")
    invoice.payment_reference = invoice.payment_reference or invoice.invoice_number
    invoice.payment_terms = invoice.payment_terms or getattr(settings, "INVOICE_DEFAULT_PAYMENT_TERMS", "10 days")
    invoice.late_interest_rate = invoice.late_interest_rate or Decimal("12.00")
    invoice.delivery_terms = invoice.delivery_terms or "Service delivery according to booking confirmation and agreed schedule."
    invoice.long_note = invoice.long_note or "Review and adjust the invoice draft before sending it to the customer."
    invoice.note = invoice.note or "Private booking invoice draft"
    if not invoice.due_date:
        base_date = booking.appointment_date or timezone.localdate()
        invoice.due_date = base_date + timedelta(days=10)
    invoice.save()

    if not invoice.line_items.exclude(is_service_fee=True).exists():
        selected_services = booking.selected_services or []
        line_order = 10
        for service_slug in selected_services:
            service = service_map.get(service_slug)
            if service is None:
                continue
            InvoiceLineItem.objects.create(
                invoice=invoice,
                line_order=line_order,
                description=service.title,
                service_time=_format_private_service_time(booking, service_slug),
                quantity=Decimal("1.00"),
                unit_price=_q(service.price),
                discount_amount=Decimal("0.00"),
                rot_rut_amount=Decimal("0.00"),
                vat_percent=DEFAULT_VAT_PERCENT,
            )
            line_order += 10

        selected_addons = booking.addons_selected or {}
        addon_slugs = []
        for service_addons in selected_addons.values():
            if not isinstance(service_addons, dict):
                continue
            for addon_slug in service_addons.keys():
                addon_slugs.append(addon_slug)
        addon_map = {addon.slug: addon for addon in PrivateAddon.objects.filter(slug__in=addon_slugs)}

        for service_slug, service_addons in selected_addons.items():
            if not isinstance(service_addons, dict):
                continue
            for addon_slug, addon_data in service_addons.items():
                if not isinstance(addon_data, dict):
                    continue
                qty = Decimal(str(addon_data.get("quantity") or 1))
                addon_price = _q(addon_data.get("price") or getattr(addon_map.get(addon_slug), "price", 0))
                unit_price = (addon_price / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if qty else addon_price
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    line_order=line_order,
                    description=addon_data.get("title") or getattr(addon_map.get(addon_slug), "title", "Add-on"),
                    service_time=_format_private_service_time(booking, service_slug),
                    quantity=qty,
                    unit_price=unit_price,
                    discount_amount=Decimal("0.00"),
                    rot_rut_amount=Decimal("0.00"),
                    vat_percent=DEFAULT_VAT_PERCENT,
                )
                line_order += 10

    _ensure_service_fee_line(invoice, currency)
    invoice.sync_amounts()
    return invoice


def create_invoice_draft_for_private_booking(booking: PrivateBooking) -> Invoice:
    customer = Customer.objects.filter(user_id=booking.user_id).first()
    if customer is None:
        raise ValueError("Customer profile is required before creating an invoice draft.")

    invoice, _ = Invoice.objects.get_or_create(
        customer=customer,
        booking_type="private",
        booking_id=booking.id,
        defaults={
            "currency": ((booking.payment_currency or "SEK") or "SEK").upper(),
            "status": "DRAFT",
            "payment_reference": "",
            "note": "Private booking invoice draft",
        },
    )
    if invoice.status != "DRAFT" and not invoice.is_locked:
        invoice.status = "DRAFT"
        invoice.save(update_fields=["status"])
    return populate_invoice_from_private_booking(invoice, booking, reset_items=not invoice.line_items.exists())


def _invoice_customer_rows(invoice: Invoice):
    customer = invoice.customer
    booking = invoice.get_booking()
    address = customer.display_address() if hasattr(customer, "display_address") else ""
    city = customer.display_city() if hasattr(customer, "display_city") else ""
    postal_code = customer.display_postal_code() if hasattr(customer, "display_postal_code") else ""
    if booking and getattr(booking, "address", None):
        address = booking.address
        city = getattr(booking, "area", None) or city
    return [
        ("Customer name", f"{customer.first_name} {customer.last_name}".strip() or customer.email or str(customer)),
        ("Address", address or "-"),
        ("Postal code and city", " / ".join(filter(None, [postal_code, city])) or "-"),
        ("Email", customer.email or getattr(customer.user, "email", "") or "-"),
        ("Phone", customer.phone or "-"),
        ("Customer number", invoice.customer_number or customer.user_id or "-"),
    ]


def _invoice_sender_rows():
    sender = get_invoice_sender_details()
    return [
        ("Company name", sender["company_name"]),
        ("Address", sender["address"]),
        ("Organization number (Org.nr)", sender["organization_number"]),
        ("VAT number", sender["vat_number"]),
        ("F-tax status", sender["f_tax_status"]),
        ("Email", sender["email"]),
        ("Phone number", sender["phone"]),
        ("Bank details", sender["bank_details"]),
    ]


def _invoice_info_rows(invoice: Invoice):
    issued_at = timezone.localtime(invoice.issued_at).strftime("%Y-%m-%d") if invoice.issued_at else timezone.localdate().strftime("%Y-%m-%d")
    due_date = invoice.due_date.strftime("%Y-%m-%d") if invoice.due_date else "-"
    return [
        ("Invoice number", invoice.invoice_number),
        ("Invoice date", issued_at),
        ("Due date", due_date),
        ("Payment terms", invoice.payment_terms or "-"),
        ("Reference number", invoice.payment_reference or invoice.invoice_number),
        ("Interest on late payment", f"{_q(invoice.late_interest_rate):.2f}%"),
    ]


def _invoice_line_rows(invoice: Invoice):
    rows = []
    for item in invoice.line_items.all():
        description = item.description
        if item.service_time:
            description = f"{description}"
        rows.append({
            "description": description,
            "date": item.service_time or "",
            "quantity": f"{_q(item.quantity):.2f}".rstrip("0").rstrip("."),
            "unit_price": _format_money(item.unit_price, invoice.currency),
            "vat_percent": f"{_q(item.vat_percent):.0f}%",
            "line_total": _format_money(item.line_total(), invoice.currency),
        })
    return rows


def _booking_invoice_summary_snapshot(invoice: Invoice):
    booking = invoice.get_booking()
    pricing_details = getattr(booking, "pricing_details", None) or {}
    snapshot = pricing_details.get("_invoice_summary") or {}
    return booking, snapshot


def _invoice_summary_rows(invoice: Invoice):
    booking, snapshot = _booking_invoice_summary_snapshot(invoice)
    currency = (snapshot.get("currency") or invoice.currency or "SEK").upper()

    def money(value):
        return _format_money(value or 0, currency)

    if snapshot:
        discount_amount = Decimal(str(snapshot.get("discount_amount", 0) or 0))
        referral_amount = Decimal(str(snapshot.get("referral_discount_amount", 0) or 0))
        reward_amount = Decimal(str(snapshot.get("reward_discount", 0) or 0))
        rut_amount = Decimal(str(snapshot.get("rot", 0) or 0))

        summary = [
            ("SUBTOTAL", money(snapshot.get("subtotal", 0)), False),
            ("VAT", money(snapshot.get("vat_amount", 0)), False),
            ("DISCOUNT", f"-{money(discount_amount + referral_amount)}" if (discount_amount + referral_amount) > 0 else money(0), False),
            ("REWARD / LOYALTY DEDUCTION", f"-{money(reward_amount)}" if reward_amount > 0 else money(0), False),
            ("SERVICE FEE", money(snapshot.get("service_fee", 0)), False),
            ("RUT DEDUCTION", f"-{money(rut_amount)}" if rut_amount > 0 else money(0), False),
            (f"FINAL TOTAL ({currency})", money(snapshot.get("final", 0)), True),
        ]
        return summary

    service_fee_amount = Decimal("0.00")
    if invoice.line_items.filter(is_service_fee=True).exists():
        service_fee_amount = sum((item.line_total() for item in invoice.line_items.filter(is_service_fee=True)), Decimal("0.00"))

    summary = [
        ("SUBTOTAL", money(invoice.subtotal_excl_vat()), False),
        ("VAT", money(invoice.vat_amount_total()), False),
        ("DISCOUNT", money(0), False),
        ("REWARD / LOYALTY DEDUCTION", money(0), False),
        ("SERVICE FEE", money(service_fee_amount), False),
        ("RUT DEDUCTION", money(0), False),
    ]
    summary.append((f"FINAL TOTAL ({currency})", money(invoice.total_amount()), True))
    return summary


def _invoice_notes(invoice: Invoice):
    booking, snapshot = _booking_invoice_summary_snapshot(invoice)
    notes = [
        f"Payment reference (OCR or reference number): {invoice.payment_reference or invoice.invoice_number}",
        f"Notes / description: {invoice.long_note or invoice.note or 'Invoice for booked services.'}",
        f"Delivery terms: {invoice.delivery_terms or '-'}",
    ]
    if booking and getattr(booking, "payment_method", ""):
        notes.append(f"Booking payment option: {booking.payment_method}")
    if snapshot:
        rot_percent = Decimal(str(snapshot.get("rot_percent", 0) or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        notes.append(f"RUT deduction: {rot_percent:.2f}% on eligible labor.")
    return notes


def _service_detail_payload(invoice: Invoice):
    booking = invoice.get_booking()
    service_title = "Booked Service"
    service_category = invoice.get_booking_type_display() if invoice.booking_type else "Service"
    service_description = invoice.long_note or invoice.note or "Invoice for booked services."
    service_date = "-"
    start_time = "-"
    end_time = "-"
    total_hours = "-"
    assigned_staff = "-"
    performed_by = f"{get_invoice_sender_details()['company_name']} Team"

    if booking and invoice.booking_type == "private":
        service_slugs = [slug for slug in (booking.selected_services or []) if isinstance(slug, str) and slug.strip()]
        first_service = PrivateService.objects.filter(slug__in=service_slugs).select_related("category").first()
        if first_service:
            service_title = first_service.title
            service_category = first_service.category.title
            service_description = first_service.description or service_description
        elif invoice.line_items.exists():
            service_title = invoice.line_items.exclude(is_service_fee=True).first().description

        if getattr(booking, "appointment_date", None):
            service_date = booking.appointment_date.strftime("%d %b %Y")
        if getattr(booking, "appointment_start_time", None):
            start_time = booking.appointment_start_time.strftime("%H:%M")
        elif getattr(booking, "appointment_time_window", None):
            start_time = str(booking.appointment_time_window)
        total_hours = str(getattr(booking, "duration_hours", "") or "").strip() or total_hours
        provider = getattr(booking, "provider", None)
        if provider:
            assigned_staff = (provider.get_full_name() or getattr(provider, "username", "") or getattr(provider, "email", "") or "-").strip()
        if total_hours not in {"", "-"} and ":" not in start_time and start_time != "-":
            try:
                hours_decimal = Decimal(str(total_hours).replace("h", "").strip())
                base_time = booking.appointment_start_time
                if base_time:
                    total_minutes = int(hours_decimal * Decimal("60"))
                    end_dt = datetime.combine(timezone.localdate(), base_time) + timedelta(minutes=total_minutes)
                    end_time = end_dt.strftime("%H:%M")
            except Exception:
                pass

    elif invoice.line_items.exists():
        first_item = invoice.line_items.exclude(is_service_fee=True).first() or invoice.line_items.first()
        if first_item:
            service_title = first_item.description

    if total_hours == "-" and invoice.line_items.exists():
        first_item = invoice.line_items.exclude(is_service_fee=True).first() or invoice.line_items.first()
        if first_item and first_item.quantity:
            total_hours = f"{_q(first_item.quantity):.2f}".rstrip("0").rstrip(".")

    return {
        "title": service_title,
        "category": service_category or "Service",
        "description": service_description or "Invoice for booked services.",
        "date": service_date,
        "start_time": start_time,
        "end_time": end_time,
        "total_hours": total_hours,
        "assigned_staff": assigned_staff,
        "performed_by": performed_by,
    }


def _property_detail_payload(invoice: Invoice):
    booking = invoice.get_booking()
    customer = invoice.customer
    address = customer.display_address() if hasattr(customer, "display_address") else ""
    city = customer.display_city() if hasattr(customer, "display_city") else ""
    postal_code = customer.display_postal_code() if hasattr(customer, "display_postal_code") else ""
    property_number = invoice.booking_id or invoice.customer_number or invoice.invoice_number

    if booking and getattr(booking, "address", None):
        address = booking.address
    if booking and getattr(booking, "area", None):
        city = booking.area
    if booking and getattr(booking, "id", None):
        property_number = booking.id

    return {
        "address": address or "-",
        "postal_city": " ".join(part for part in [postal_code, city] if part).strip() or city or postal_code or "-",
        "country": "Sweden",
        "property_number": str(property_number or "-"),
    }


def _customer_detail_payload(invoice: Invoice):
    customer = invoice.customer
    return {
        "name": f"{customer.first_name} {customer.last_name}".strip() or customer.email or str(customer),
        "customer_number": invoice.customer_number or customer.user_id or "-",
        "address": customer.display_address() if hasattr(customer, "display_address") else "-",
        "postal_city": " ".join(
            part
            for part in [
                customer.display_postal_code() if hasattr(customer, "display_postal_code") else "",
                customer.display_city() if hasattr(customer, "display_city") else "",
            ]
            if part
        ).strip() or "-",
        "country": "Sweden",
        "email": customer.email or getattr(customer.user, "email", "") or "-",
        "phone": customer.phone or "-",
    }


def render_invoice_pdf(invoice: Invoice) -> bytes:
    invoice.sync_amounts()
    sender = get_invoice_sender_details()
    property_details = _property_detail_payload(invoice)
    service_details = _service_detail_payload(invoice)
    customer_details = _customer_detail_payload(invoice)
    return build_branded_invoice_pdf({
        "brand_name": sender["company_name"],
        "tagline": "Because Home Shouldn't Be Work",
        "document_title": "Invoice",
        "document_number": invoice.invoice_number,
        "logo_path": default_logo_path(),
        "sender_rows": _invoice_sender_rows(),
        "customer_rows": _invoice_customer_rows(invoice),
        "invoice_rows": _invoice_info_rows(invoice),
        "line_items": _invoice_line_rows(invoice),
        "summary_rows": _invoice_summary_rows(invoice),
        "additional_notes": _invoice_notes(invoice),
        "customer_details": customer_details,
        "property_details": property_details,
        "service_details": service_details,
        "company_details": {
            "name": sender["company_name"],
            "organization_number": sender["organization_number"],
            "vat_number": sender["vat_number"],
            "f_tax_status": sender["f_tax_status"],
            "address": sender["address"],
            "email": sender["email"],
            "phone": sender["phone"],
            "bank_details": sender["bank_details"],
        },
        "footer_text": " | ".join([value for value in [sender["address"], sender["phone"], sender["email"]] if value and value != "-"]),
    })


def send_invoice_email(invoice: Invoice):
    customer_email = (invoice.customer.email or getattr(invoice.customer.user, "email", "") or "").strip()
    if not customer_email:
        raise ValueError("Customer email is missing.")

    pdf_bytes = render_invoice_pdf(invoice)
    subject = f"Your invoice {invoice.invoice_number}"
    body = (
        f"Hello {invoice.customer.first_name or 'Customer'},\n\n"
        "Your invoice is attached as a PDF.\n"
        f"Reference: {invoice.payment_reference or invoice.invoice_number}\n"
        f"Amount due: {_format_money(invoice.total_amount(), invoice.currency)}\n\n"
        "Best regards,\n"
        "Hembla experten"
    )
    connection = get_connection(fail_silently=False)
    try:
        connection.open()
        if not getattr(connection, "connection", None):
            raise ConnectionError("SMTP connection could not be established.")

        message = EmailMultiAlternatives(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [customer_email],
            connection=connection,
        )
        message.attach(f"{invoice.invoice_number}.pdf", pdf_bytes, "application/pdf")
        message.send(fail_silently=False)
    finally:
        try:
            connection.close()
        except Exception:
            pass
    return pdf_bytes
