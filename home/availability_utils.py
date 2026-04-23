from datetime import datetime, time, timedelta
import math
from django.utils import timezone
from django.contrib.auth import get_user_model

from home.models import PrivateBooking, BusinessBooking
from accounts.models import ProviderShift

User = get_user_model()


def _normalize_location(value):
    if not value:
        return ""
    return " ".join(str(value).split()).strip().lower()


def _booking_location_candidates(booking):
    if not booking:
        return []
    values = []
    if getattr(booking, "area", None):
        values.append(booking.area)
    if getattr(booking, "address", None):
        values.append(booking.address)
    if getattr(booking, "office_address", None):
        values.append(booking.office_address)
    return [_normalize_location(v) for v in values if v]


def provider_matches_location(provider_profile, booking):
    return True


def _booking_service_slugs(booking):
    raw_values = getattr(booking, "selected_services", None) or []
    return {str(value).strip() for value in raw_values if str(value).strip()}


def provider_matches_services(provider_profile, booking):
    required_service_slugs = _booking_service_slugs(booking)
    if not required_service_slugs:
        return True
    if not provider_profile:
        return False

    allowed_service_slugs = set(
        provider_profile.supported_services.values_list("slug", flat=True)
    )
    if not allowed_service_slugs:
        return True
    return required_service_slugs.issubset(allowed_service_slugs)


def _active_bookings_for_provider(provider):
    private_qs = PrivateBooking.objects.filter(provider=provider).exclude(
        status__in=PrivateBooking.INACTIVE_STATUSES
    )
    business_qs = BusinessBooking.objects.filter(provider=provider).exclude(
        status__in=BusinessBooking.INACTIVE_STATUSES
    )
    return list(private_qs) + list(business_qs)


def _active_shifts_for_provider(provider, date_obj=None):
    if not provider:
        return []
    qs = ProviderShift.objects.filter(provider=provider, is_active=True)
    if date_obj is not None:
        qs = qs.filter(weekday=date_obj.weekday())
    return list(qs.order_by("start_time"))


def provider_has_shift_for_window(provider, start_dt, end_dt):
    if not provider or not start_dt or not end_dt:
        return False
    if start_dt.date() != end_dt.date():
        return False

    shift_date = start_dt.date()
    shifts = _active_shifts_for_provider(provider, date_obj=shift_date)
    if not shifts:
        return False

    for shift in shifts:
        shift_start = timezone.make_aware(datetime.combine(shift_date, shift.start_time), timezone.get_current_timezone())
        shift_end = timezone.make_aware(datetime.combine(shift_date, shift.end_time), timezone.get_current_timezone())
        if start_dt >= shift_start and end_dt <= shift_end:
            return True
    return False


def has_overlap(provider, start_dt, end_dt, exclude_booking=None):
    if not provider or not start_dt or not end_dt:
        return False

    for booking in _active_bookings_for_provider(provider):
        if exclude_booking and booking.__class__ == exclude_booking.__class__ and booking.pk == exclude_booking.pk:
            continue
        for other_start, other_end in booking.get_service_windows():
            if not other_start or not other_end:
                continue
            if start_dt < other_end and end_dt > other_start:
                return True
    return False


def booking_total_minutes(duration_minutes):
    try:
        base_minutes = int(duration_minutes or 0)
    except (TypeError, ValueError):
        base_minutes = 0
    if base_minutes <= 0:
        return 0
    return base_minutes + 60


def _booking_window_or_none(booking):
    start, end = booking.get_service_window()
    return (start, end) if start and end else (None, None)


def generate_slots(provider, date_obj, duration_minutes, slot_size_minutes=30,
                   day_start=time(8, 0), day_end=time(20, 0)):
    if not provider or not date_obj or duration_minutes <= 0:
        return []

    tz = timezone.get_current_timezone()
    duration = timedelta(minutes=booking_total_minutes(duration_minutes))
    slot_size = timedelta(minutes=int(slot_size_minutes))
    shifts = _active_shifts_for_provider(provider, date_obj=date_obj)
    if not shifts:
        return []

    busy_windows = []
    for booking in _active_bookings_for_provider(provider):
        b_start, b_end = _booking_window_or_none(booking)
        if not b_start or not b_end:
            continue
        if b_start.date() != date_obj:
            continue
        busy_windows.append((b_start, b_end))

    slots = []
    for shift in shifts:
        shift_start = timezone.make_aware(datetime.combine(date_obj, max(day_start, shift.start_time)), tz)
        shift_end = timezone.make_aware(datetime.combine(date_obj, min(day_end, shift.end_time)), tz)
        cursor = shift_start
        while cursor + duration <= shift_end:
            slot_end = cursor + duration
            overlaps = any(cursor < b_end and b_start < slot_end for b_start, b_end in busy_windows)
            if not overlaps:
                slots.append(cursor)
            cursor += slot_size
    return slots


def earliest_available_slot(provider, date_obj, duration_minutes, slot_size_minutes=30,
                            day_start=time(8, 0), day_end=time(20, 0)):
    slots = generate_slots(
        provider,
        date_obj,
        duration_minutes,
        slot_size_minutes=slot_size_minutes,
        day_start=day_start,
        day_end=day_end,
    )
    return slots[0] if slots else None


def select_nearest_provider(booking, date_obj, slot_size_minutes=30):
    matched = []
    for provider in get_available_providers_for_booking(booking, date_obj=date_obj):
        earliest = earliest_available_slot(
            provider,
            date_obj,
            booking.quoted_duration_minutes or 0,
            slot_size_minutes=slot_size_minutes,
        )
        matched.append((provider, earliest))
    matched.sort(key=lambda item: item[1] or datetime.max.replace(tzinfo=timezone.get_current_timezone()))
    return matched


def provider_distance_score(provider_profile, booking):
    return 0


def get_available_providers_for_booking(booking, *, date_obj=None, start_dt=None, end_dt=None, exclude_booking=None):
    providers = (
        User.objects.filter(provider_profile__is_active=True)
        .select_related("provider_profile")
        .order_by("username")
    )
    candidates = []
    for provider in providers:
        profile = getattr(provider, "provider_profile", None)
        if not provider_matches_location(profile, booking):
            continue
        if not provider_matches_services(profile, booking):
            continue
        if date_obj is not None and not _active_shifts_for_provider(provider, date_obj=date_obj):
            continue
        if start_dt and end_dt and not provider_has_shift_for_window(provider, start_dt, end_dt):
            continue
        if start_dt and end_dt and has_overlap(provider, start_dt, end_dt, exclude_booking=exclude_booking or booking):
            continue
        candidates.append(provider)

    candidates.sort(
        key=lambda provider: (
            provider_distance_score(getattr(provider, "provider_profile", None), booking),
            (provider.get_full_name() or provider.username or "").strip().lower(),
        )
    )
    return candidates


def get_available_slots_for_booking(booking, date_obj, slot_size_minutes=30,
                                    day_start=time(8, 0), day_end=time(20, 0)):
    if not booking or not date_obj:
        return []

    duration_minutes = int(booking.quoted_duration_minutes or 0)
    if duration_minutes <= 0:
        return []

    slot_providers = {}
    for provider in get_available_providers_for_booking(booking, date_obj=date_obj):
        provider_slots = generate_slots(
            provider,
            date_obj,
            duration_minutes,
            slot_size_minutes=slot_size_minutes,
            day_start=day_start,
            day_end=day_end,
        )
        for slot in provider_slots:
            slot_providers.setdefault(slot, []).append(provider)

    ordered = []
    for slot in sorted(slot_providers.keys()):
        providers = slot_providers[slot]
        ordered.append({
            "slot": slot,
            "value": slot.strftime("%H:%M"),
            "provider_ids": [provider.id for provider in providers],
            "provider_names": [
                (provider.get_full_name() or provider.username or "").strip()
                for provider in providers
            ],
            "provider_count": len(providers),
        })
    return ordered


def provider_can_take_booking(provider, booking, *, exclude_booking=None):
    if not provider:
        return True
    profile = getattr(provider, "provider_profile", None)
    if not profile or not getattr(profile, "is_active", False):
        return False
    if not provider_matches_location(profile, booking):
        return False
    if not provider_matches_services(profile, booking):
        return False
    target_windows = booking.get_service_windows()
    for start_dt, end_dt in target_windows:
        if not provider_has_shift_for_window(provider, start_dt, end_dt):
            return False
        if has_overlap(provider, start_dt, end_dt, exclude_booking=exclude_booking or booking):
            return False
    return True


def provider_available_after_minutes(provider, now=None):
    if not provider:
        return 0
    now = now or timezone.now()
    if timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())

    overlapping = []
    for booking in _active_bookings_for_provider(provider):
        start, end = _booking_window_or_none(booking)
        if not start or not end:
            continue
        if start <= now < end:
            overlapping.append(end)

    if not overlapping:
        return 0

    soonest_end = min(overlapping)
    minutes = (soonest_end - now).total_seconds() / 60.0
    return max(0, int(math.ceil(minutes)))
