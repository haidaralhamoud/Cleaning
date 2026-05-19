from django.core.cache import cache

from accounts.models import ChatMessage, Customer


CHAT_COUNTS_CACHE_TTL = 30
SIDEBAR_CUSTOMER_CACHE_TTL = 60


def _chat_counts_for_user(user):
    if hasattr(user, "_chat_counts_cache"):
        return user._chat_counts_cache

    cache_key = f"accounts:chat-counts:{user.pk}"
    counts = cache.get(cache_key)
    if counts is None:
        customer_unread = ChatMessage.objects.filter(
            is_read=False,
            thread__customer=user
        ).exclude(
            sender=user
        ).count()

        provider_unread = ChatMessage.objects.filter(
            is_read=False,
            thread__provider=user
        ).exclude(
            sender=user
        ).count()

        counts = {
            "customer_unread": customer_unread,
            "provider_unread": provider_unread,
        }
        cache.set(cache_key, counts, CHAT_COUNTS_CACHE_TTL)

    user._chat_counts_cache = counts
    return counts


def chat_notifications(request):
    if not request.user.is_authenticated:
        return {}

    counts = _chat_counts_for_user(request.user)

    return {
        "customer_unread_messages": counts["customer_unread"],
        "provider_unread_messages": counts["provider_unread"],
    }

def unread_messages(request):
    if not request.user.is_authenticated:
        return {}

    counts = _chat_counts_for_user(request.user)

    return {
        "unread_messages_count": counts["provider_unread"]
    }

def sidebar_customer(request):
    if not request.user.is_authenticated:
        return {}

    if hasattr(request, "_sidebar_customer_cache"):
        customer = request._sidebar_customer_cache
    else:
        cache_key = f"accounts:sidebar-customer:{request.user.pk}"
        customer = cache.get(cache_key)
        if customer is None:
            customer = Customer.objects.filter(user=request.user).first()
            cache.set(cache_key, customer, SIDEBAR_CUSTOMER_CACHE_TTL)
        request._sidebar_customer_cache = customer

    if not customer:
        return {}

    return {
        "sidebar_customer": customer,
    }
