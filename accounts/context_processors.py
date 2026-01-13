from accounts.models import ChatMessage


def chat_notifications(request):
    if not request.user.is_authenticated:
        return {}

    customer_unread = ChatMessage.objects.filter(
        is_read=False,
        thread__customer=request.user
    ).exclude(
        sender=request.user
    ).count()

    provider_unread = ChatMessage.objects.filter(
        is_read=False,
        thread__provider=request.user
    ).exclude(
        sender=request.user
    ).count()

    return {
        "customer_unread_messages": customer_unread,
        "provider_unread_messages": provider_unread,
    }

def unread_messages(request):
    if not request.user.is_authenticated:
        return {}

    count = ChatMessage.objects.filter(
        is_read=False,
        thread__provider=request.user
    ).exclude(
        sender=request.user
    ).count()

    return {
        "unread_messages_count": count
    }
