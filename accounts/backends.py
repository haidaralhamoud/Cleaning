from django.contrib.auth.models import User
from django.contrib.auth.backends import ModelBackend
from accounts.models import Customer

class EmailPhoneUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        user = None

        # 1) Email login
        try:
            user = User.objects.get(email=username)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            pass

        # 2) Phone login (from Customer model)
        if user is None:
            try:
                customer = Customer.objects.get(phone=username)
                user = customer.user
            except (Customer.DoesNotExist, Customer.MultipleObjectsReturned):
                pass

        # 3) Username login
        if user is None:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return None

        # Check password
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        
        return None
