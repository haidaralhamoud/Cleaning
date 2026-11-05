from django.core.mail.backends.base import BaseEmailBackend


class ReliableEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        from .mail_delivery import enqueue_message
        count = 0
        for message in email_messages or []:
            if not message.recipients():
                continue
            enqueue_message(message)
            count += 1
        return count
