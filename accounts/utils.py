import uuid

def generate_referral_code():
    return uuid.uuid4().hex[:8].upper()
