from decimal import Decimal
from django.conf import settings
from .models import (
    PrivateService,
    PrivateAddon,
    ScheduleRule,
    PrivateBooking,
    DateSurcharge,
    RotSetting,
    CurrencyRate,
)
from datetime import datetime

def apply_date_surcharge(booking, base_price):
    """
    يطبّق الزيادة على السعر حسب التاريخ أو اليوم.
    Always convert appointment_date (string → date)
    """
    if not booking.appointment_date:
        return base_price

    # ---------------------------
    # 🔥 تحويل string → datetime.date
    # ---------------------------
    if isinstance(booking.appointment_date, str):
        try:
            date_obj = datetime.strptime(booking.appointment_date, "%Y-%m-%d").date()
        except:
            return base_price
    else:
        date_obj = booking.appointment_date

    weekday = date_obj.strftime("%a")  # Mon / Tue / Sat / Sun

    total = base_price

    for rule in DateSurcharge.objects.all():

        # القانون حسب اليوم
        if rule.rule_type == "weekday" and rule.weekday == weekday:
            if rule.surcharge_type == "percent":
                total += (total * (rule.amount / 100))
            else:
                total += rule.amount

        # القانون حسب تاريخ معين
        if rule.rule_type == "date" and rule.date == date_obj:
            if rule.surcharge_type == "percent":
                total += (total * (rule.amount / 100))
            else:
                total += rule.amount

    return total

def apply_percentage(base, percent):
    return base * (Decimal(percent) / Decimal("100"))

def _coerce_decimal(value):
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0.00")


def _normalize_currency(value, default="SEK"):
    return (value or default or "SEK").upper()


def _build_currency_rates(target_currency):
    target = _normalize_currency(target_currency)
    rates = {(target, target): Decimal("1.0")}
    for rate in CurrencyRate.objects.filter(is_active=True):
        rates[(
            _normalize_currency(rate.source_currency),
            _normalize_currency(rate.target_currency),
        )] = _coerce_decimal(rate.exchange_rate)
    return rates


def _convert_currency(amount, source_currency, target_currency, rates):
    source = _normalize_currency(source_currency)
    target = _normalize_currency(target_currency)
    amount = _coerce_decimal(amount)
    if source == target:
        return amount
    return amount * rates.get((source, target), Decimal("1.0"))

def _normalize_answers(value):
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]

def _options_price(options, answers, source_currency, target_currency, currency_rates):
    total = Decimal("0.00")
    if not options:
        return total
    answer_set = set(str(a) for a in _normalize_answers(answers))
    for opt in options:
        if isinstance(opt, dict):
            value_key = str(opt.get("value") or opt.get("label") or "")
            if value_key and value_key in answer_set:
                total += _convert_currency(
                    opt.get("price", 0),
                    source_currency,
                    target_currency,
                    currency_rates,
                )
    return total

def _options_duration(options, answers):
    total = Decimal("0.00")
    if not options:
        return total
    answer_set = set(str(a) for a in _normalize_answers(answers))
    for opt in options:
        if isinstance(opt, dict):
            value_key = str(opt.get("value") or opt.get("label") or "")
            if value_key and value_key in answer_set:
                total += _coerce_decimal(opt.get("duration", 0))
    return total


def calculate_booking_price(booking):
    services_total = Decimal("0.00")
    addons_total = Decimal("0.00")
    duration_minutes = Decimal("0.00")
    target_currency = _normalize_currency(getattr(settings, "STRIPE_CURRENCY", "SEK"))
    currency_rates = _build_currency_rates(target_currency)

    selected_slugs = booking.selected_services or []
    services = list(PrivateService.objects.filter(slug__in=selected_slugs))
    addon_slugs = {
        addon_slug
        for addons in (booking.addons_selected or {}).values()
        for addon_slug in addons.keys()
    }
    addons_by_slug = {
        addon.slug: addon
        for addon in PrivateAddon.objects.filter(slug__in=addon_slugs)
    }
    schedule_rules = {
        (rule.key, rule.value): rule
        for rule in ScheduleRule.objects.filter(key__in=["frequency_type", "day"])
    }
    date_surcharge_rules = list(DateSurcharge.objects.all())
    rot_setting = RotSetting.objects.order_by("-updated_at").first()

    # --------------------------
    # 1) SERVICE PRICES
    # --------------------------
    default_service_duration = Decimal(str(getattr(booking, "DEFAULT_DURATION_MINUTES", 120)))

    for service in services:
        source_currency = getattr(service, "price_currency", target_currency)
        price = _convert_currency(service.price, source_currency, target_currency, currency_rates)
        answers = (booking.service_answers or {}).get(service.slug, {})
        service_duration = Decimal("0.00")

        questions = service.questions or {}
        for q_key, q_info in questions.items():
            if not q_info:
                continue
            options = q_info.get("options") or []
            if not options:
                continue
            price += _options_price(options, answers.get(q_key), source_currency, target_currency, currency_rates)
            service_duration += _options_duration(options, answers.get(q_key))

        if service_duration <= 0:
            service_duration = default_service_duration

        duration_minutes += service_duration

        services_total += price

    subtotal = services_total

    # --------------------------
    # 2) ADDONS
    # --------------------------
    addons_data = booking.addons_selected or {}
    for svc, addons in addons_data.items():
        for addon_slug, fields in addons.items():
            addon = addons_by_slug.get(addon_slug)
            if addon is None:
                continue

            source_currency = getattr(addon, "price_currency", target_currency)
            price = _convert_currency(addon.price, source_currency, target_currency, currency_rates)

            questions = addon.questions or {}
            for q_key, q_info in questions.items():
                if not q_info:
                    continue
                options = q_info.get("options") or []
                if not options:
                    continue
                price += _options_price(options, fields.get(q_key), source_currency, target_currency, currency_rates)
                duration_minutes += _options_duration(options, fields.get(q_key))

            if addon.price_per_unit > 0:
                for _, val in fields.items():
                    if str(val).isdigit():
                        price += _convert_currency(
                            addon.price_per_unit * int(val),
                            source_currency,
                            target_currency,
                            currency_rates,
                        )

            addons_total += price

    subtotal += addons_total

    # --------------------------
    # 3) SCHEDULE RULES
    # --------------------------
    schedule_extra = Decimal("0.00")

    if getattr(booking, "schedule_mode", "same") == "same":

        # date surcharge
        if booking.appointment_date:
            final_with_date = apply_date_surcharge(booking, subtotal)
            final = final_with_date + schedule_extra

            # ما في rule مباشرة للـ date هنا، يعالجها apply_date_surcharge
            


        # frequency
        if booking.frequency_type:
            freq = booking.frequency_type.strip()
            rule = schedule_rules.get(("frequency_type", freq))
            if rule:
                schedule_extra += apply_percentage(subtotal, rule.price_change)

        # days
        for d in booking.day_work_best or []:
            rule = schedule_rules.get(("day", d))
            if rule:
                schedule_extra += apply_percentage(subtotal, rule.price_change)

    else:
        # per service mode
        sched = booking.service_schedules or {}
        for svc, data in sched.items():

            freq = data.get("frequency")
            if freq:
                rule = schedule_rules.get(("frequency_type", freq))
                if rule:
                    schedule_extra += apply_percentage(subtotal, rule.price_change)

            for d in data.get("days", []):
                rule = schedule_rules.get(("day", d))
                if rule:
                    schedule_extra += apply_percentage(subtotal, rule.price_change)

    # --------------------------
    # 4) FINAL TOTAL
    # --------------------------
    final_with_date = subtotal
    if booking.appointment_date:
        final_with_date = subtotal
        if isinstance(booking.appointment_date, str):
            try:
                date_obj = datetime.strptime(booking.appointment_date, "%Y-%m-%d").date()
            except Exception:
                date_obj = None
        else:
            date_obj = booking.appointment_date

        if date_obj:
            weekday = date_obj.strftime("%a")
            for rule in date_surcharge_rules:
                if rule.rule_type == "weekday" and rule.weekday == weekday:
                    if rule.surcharge_type == "percent":
                        final_with_date += (final_with_date * (rule.amount / 100))
                    else:
                        final_with_date += rule.amount
                if rule.rule_type == "date" and rule.date == date_obj:
                    if rule.surcharge_type == "percent":
                        final_with_date += (final_with_date * (rule.amount / 100))
                    else:
                        final_with_date += rule.amount
    date_surcharge = final_with_date - subtotal
    final = final_with_date + schedule_extra

    rot_percent = _coerce_decimal(rot_setting.amount) if rot_setting else Decimal("0.00")
    if rot_percent < 0:
        rot_percent = Decimal("0.00")
    rot_amount = final * (rot_percent / Decimal("100"))
    if rot_amount > final:
        rot_amount = final

    duration_seconds = int(duration_minutes * Decimal("60")) if duration_minutes else 0
    duration_hours = float(duration_minutes) / 60 if duration_minutes else 0.0
    return {
        "services_total": float(services_total),
        "addons_total": float(addons_total),
        "subtotal": float(subtotal),
        "schedule_extra": float(schedule_extra),
        "date_surcharge": float(date_surcharge),
        "rot": float(rot_amount),
        "rot_percent": float(rot_percent),
        "currency": target_currency.lower(),
        "final": float(final - rot_amount),
        "duration_minutes": float(duration_minutes),
        "duration_hours": float(duration_hours),
        "duration_seconds": duration_seconds,
    }
