from accounts.models import PointsTransaction
from django.db import transaction

def award_points_for_booking(booking, admin_user=None):
    """
    Award points manually decided by admin after booking completion.
    """

    # 1️⃣ شروط الأمان
    if booking.status != "COMPLETED":
        return False

    if booking.points_processed:
        return False

    if booking.points_awarded is None:
        return False

    user = booking.user
    if not user:
        return False

    booking_type = (
        "private"
        if booking.__class__.__name__ == "PrivateBooking"
        else "business"
    )

    # 2️⃣ تنفيذ آمن
    with transaction.atomic():
        PointsTransaction.objects.create(
            user=user,
            amount=booking.points_awarded,
            reason="BOOKING",
            booking_type=booking_type,
            booking_id=booking.id,
            note=booking.points_note or "",
            created_by=admin_user
        )

        booking.points_processed = True
        booking.save(update_fields=["points_processed"])

    return True
