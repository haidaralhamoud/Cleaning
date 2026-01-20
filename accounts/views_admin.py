from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from home.models import PrivateBooking, BusinessBooking
from accounts.loyalty import award_points_for_booking

@staff_member_required
def finalize_booking(request, booking_type, booking_id):

    if booking_type == "private":
        booking = get_object_or_404(PrivateBooking, id=booking_id)
    elif booking_type == "business":
        booking = get_object_or_404(BusinessBooking, id=booking_id)
    else:
        messages.error(request, "Invalid booking type")
        return redirect("/admin/")

    success = award_points_for_booking(
        booking=booking,
        admin_user=request.user
    )

    if success:
        messages.success(request, "Points awarded successfully.")
    else:
        messages.warning(request, "Points were not awarded.")

    return redirect("/admin/")
