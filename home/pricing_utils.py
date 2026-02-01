from decimal import Decimal
from .models import (
    PrivateService,
    PrivateAddon,
    ScheduleRule,
    PrivateBooking,
    DateSurcharge,
    RotSetting,
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

def _normalize_answers(value):
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]

def _options_price(options, answers):
    total = Decimal("0.00")
    if not options:
        return total
    answer_set = set(str(a) for a in _normalize_answers(answers))
    for opt in options:
        if isinstance(opt, dict):
            value_key = str(opt.get("value") or opt.get("label") or "")
            if value_key and value_key in answer_set:
                total += _coerce_decimal(opt.get("price", 0))
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

    selected_slugs = booking.selected_services or []
    services = PrivateService.objects.filter(slug__in=selected_slugs)

    # --------------------------
    # 1) SERVICE PRICES
    # --------------------------
    for service in services:
        price = service.price
        answers = (booking.service_answers or {}).get(service.slug, {})

        questions = service.questions or {}
        for q_key, q_info in questions.items():
            if not q_info:
                continue
            options = q_info.get("options") or []
            if not options:
                continue
            price += _options_price(options, answers.get(q_key))
            duration_minutes += _options_duration(options, answers.get(q_key))

        services_total += price

    subtotal = services_total

    # --------------------------
    # 2) ADDONS
    # --------------------------
    addons_data = booking.addons_selected or {}
    for svc, addons in addons_data.items():
        for addon_slug, fields in addons.items():
            try:
                addon = PrivateAddon.objects.get(slug=addon_slug)
            except PrivateAddon.DoesNotExist:
                continue

            price = addon.price

            questions = addon.questions or {}
            for q_key, q_info in questions.items():
                if not q_info:
                    continue
                options = q_info.get("options") or []
                if not options:
                    continue
                price += _options_price(options, fields.get(q_key))
                duration_minutes += _options_duration(options, fields.get(q_key))

            if addon.price_per_unit > 0:
                for _, val in fields.items():
                    if str(val).isdigit():
                        price += addon.price_per_unit * int(val)

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
            rule = ScheduleRule.objects.filter(key="frequency_type", value=freq).first()
            if rule:
                schedule_extra += apply_percentage(subtotal, rule.price_change)

        # days
        for d in booking.day_work_best or []:
            rule = ScheduleRule.objects.filter(key="day", value=d).first()
            if rule:
                schedule_extra += apply_percentage(subtotal, rule.price_change)

    else:
        # per service mode
        sched = booking.service_schedules or {}
        for svc, data in sched.items():

            freq = data.get("frequency")
            if freq:
                rule = ScheduleRule.objects.filter(key="frequency_type", value=freq).first()
                if rule:
                    schedule_extra += apply_percentage(subtotal, rule.price_change)

            for d in data.get("days", []):
                rule = ScheduleRule.objects.filter(key="day", value=d).first()
                if rule:
                    schedule_extra += apply_percentage(subtotal, rule.price_change)

    # --------------------------
    # 4) FINAL TOTAL
    # --------------------------
    final_with_date = apply_date_surcharge(booking, subtotal)
    date_surcharge = final_with_date - subtotal
    final = final_with_date + schedule_extra

    rot_setting = RotSetting.objects.order_by("-updated_at").first()
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
        "final": float(final - rot_amount),
        "duration_minutes": float(duration_minutes),
        "duration_hours": float(duration_hours),
        "duration_seconds": duration_seconds,
    }
