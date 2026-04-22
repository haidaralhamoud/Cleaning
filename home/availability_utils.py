from datetime import datetime, time, timedelta
import math
from django.utils import timezone
from django.contrib.auth import get_user_model

from home.models import PrivateBooking, BusinessBooking

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
    booking_locations = _booking_location_candidates(booking)
    if not booking_locations:
        return True
    if not provider_profile:
        return False
    provider_values = [
        provider_profile.area,
        provider_profile.city,
        provider_profile.region,
    ] + (provider_profile.nearby_areas or [])
    provider_values = [_normalize_location(v) for v in provider_values if v]
    if not provider_values:
        return False
    for booking_loc in booking_locations:
        for provider_loc in provider_values:
            if not booking_loc or not provider_loc:
                continue
            if booking_loc == provider_loc:
                return True
            if booking_loc in provider_loc or provider_loc in booking_loc:
                return True
    return False


def _active_bookings_for_provider(provider):
    private_qs = PrivateBooking.objects.filter(provider=provider).exclude(
        status__in=PrivateBooking.INACTIVE_STATUSES
    )
    business_qs = BusinessBooking.objects.filter(provider=provider).exclude(
        status__in=BusinessBooking.INACTIVE_STATUSES
    )
    return list(private_qs) + list(business_qs)


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
    start_of_day = timezone.make_aware(datetime.combine(date_obj, day_start), tz)
    end_of_day = timezone.make_aware(datetime.combine(date_obj, day_end), tz)

    duration = timedelta(minutes=booking_total_minutes(duration_minutes))
    slot_size = timedelta(minutes=int(slot_size_minutes))

    busy_windows = []
    for booking in _active_bookings_for_provider(provider):
        b_start, b_end = _booking_window_or_none(booking)
        if not b_start or not b_end:
            continue
        if b_start.date() != date_obj:
            continue
        busy_windows.append((b_start, b_end))

    slots = []
    cursor = start_of_day
    while cursor + duration <= end_of_day:
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
    booking_locations = _booking_location_candidates(booking)
    if not booking_locations:
        return 0
    if not provider_profile:
        return 10_000

    provider_values = [
        provider_profile.area,
        provider_profile.city,
        provider_profile.region,
    ] + (provider_profile.nearby_areas or [])
    provider_values = [_normalize_location(v) for v in provider_values if v]
    if not provider_values:
        return 10_000

    best_score = 10_000
    for booking_loc in booking_locations:
        for provider_loc in provider_values:
            if booking_loc == provider_loc:
                best_score = min(best_score, 0)
            elif booking_loc in provider_loc or provider_loc in booking_loc:
                best_score = min(best_score, 1)
    return best_score


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
    start_dt = getattr(booking, "start_datetime", None)
    end_dt = getattr(booking, "end_datetime", None)
    if start_dt and end_dt and has_overlap(provider, start_dt, end_dt, exclude_booking=exclude_booking or booking):
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
