from django.db import transaction

from accounts.models import PointsTransaction


def award_points_for_booking(booking, admin_user=None):
    with transaction.atomic():
        locked = type(booking).objects.select_for_update().get(pk=booking.pk)
        if (locked.status != "COMPLETED" or locked.points_processed
                or locked.points_awarded is None or not locked.user_id):
            return False
        booking_type = "private" if locked._meta.model_name == "privatebooking" else "business"
        if PointsTransaction.objects.filter(
            user_id=locked.user_id, reason="BOOKING", booking_type=booking_type, booking_id=locked.pk
        ).exists():
            locked.points_processed = True
            locked.save(update_fields=["points_processed"])
            booking.points_processed = True
            return False
        PointsTransaction.objects.create(
            user_id=locked.user_id,
            amount=locked.points_awarded,
            reason="BOOKING",
            booking_type=booking_type,
            booking_id=locked.pk,
            note=locked.points_note or "",
            created_by=admin_user,
        )
        locked.points_processed = True
        locked.save(update_fields=["points_processed"])
        booking.points_processed = True
    return True
