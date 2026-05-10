import pytz
from datetime import datetime


def get_vietnam_time():
    # Returns the current time in Vietnam (UTC+7)
    return datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

def calculate_initial_fee(product, duration):
    total_hours = duration.total_seconds() / 3600
    days = duration.days

    if total_hours <= 6:
        return product.six_hour_price
    elif total_hours <= 24:
        return product.one_day_price
    elif days == 1: # 24h to 48h
        return product.two_day_price
    elif days == 2: # 48h to 72h
        return product.three_day_price
    else:
        # For rentals > 3 days (72h+)
        # Base (3 days) + (Full days beyond 3 * additional_day_price)
        extra_days = days - 2 
        return product.three_day_price + (extra_days * product.additional_day_price)