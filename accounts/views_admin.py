from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from home.models import PrivateBooking, BusinessBooking
from accounts.loyalty import award_points_for_booking
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied

@staff_member_required
@require_POST
def finalize_booking(request, booking_type, booking_id):

    if booking_type == "private":
        booking = get_object_or_404(PrivateBooking, id=booking_id)
    elif booking_type == "business":
        booking = get_object_or_404(BusinessBooking, id=booking_id)
    else:
        messages.error(request, "Invalid booking type")
        return redirect("/admin/")

    opts = booking._meta
    if not request.user.has_perm(f"{opts.app_label}.change_{opts.model_name}"):
        raise PermissionDenied

    success = award_points_for_booking(
        booking=booking,
        admin_user=request.user
    )

    if success:
        messages.success(request, "Points awarded successfully.")
    else:
        messages.warning(request, "Points were not awarded.")

    return redirect("/admin/")
