from decimal import Decimal
from .models import (
    PrivateService,
    PrivateAddon,
    ServiceQuestionRule,
    AddonRule,
    ScheduleRule,
    PrivateBooking,
    DateSurcharge
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


def calculate_booking_price(booking):

    services_total = Decimal("0.00")
    addons_total = Decimal("0.00")

    selected_slugs = booking.selected_services or []
    services = PrivateService.objects.filter(slug__in=selected_slugs)

    # --------------------------
    # 1) SERVICE PRICES
    # --------------------------
    for service in services:
        price = service.price
        answers = (booking.service_answers or {}).get(service.slug, {})

        for rule in service.pricing_rules.all():
            if answers.get(rule.question_key) == rule.answer_value:
                price += rule.price_change

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

            if addon.price_per_unit > 0:
                for _, val in fields.items():
                    if str(val).isdigit():
                        price += addon.price_per_unit * int(val)

            # addon rules
            for rule in addon.pricing_rules.all():
                if fields.get(rule.question_key) == rule.answer_value:
                    price += rule.price_change

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
            


        # time window
        if booking.appointment_time_window:
            tw = booking.appointment_time_window.strip()
            rule = ScheduleRule.objects.filter(key="time_window", value=tw).first()
            if rule:
                schedule_extra += apply_percentage(subtotal, rule.price_change)

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

            tw = data.get("time_window")
            if tw:
                rule = ScheduleRule.objects.filter(key="time_window", value=tw).first()
                if rule:
                    schedule_extra += apply_percentage(subtotal, rule.price_change)

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
    # تطبيق زيادة التاريخ
    final_with_date = apply_date_surcharge(booking, subtotal)

    # total = subtotal + schedule_extra + فرق الزيادة من التاريخ
    final = final_with_date + schedule_extra

    return {
        "services_total": float(services_total),
        "addons_total": float(addons_total),
        "subtotal": float(subtotal),
        "schedule_extra": float(schedule_extra),
        "rot": 0.0,
        "final": float(final),
    }
