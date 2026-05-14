import math

import pytz
from datetime import datetime


def get_vietnam_time():
    # Returns the current time in Vietnam (UTC+7)
    return datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))

def calculate_initial_fee(product, duration):
    total_hours = duration.total_seconds() / 3600
    
    # 1. Short term fixed tiers
    if total_hours <= 6:
        return product.six_hour_price
    if total_hours <= 24:
        return product.one_day_price
    if total_hours <= 48:
        return product.two_day_price
    if total_hours <= 72:
        return product.three_day_price

    billable_days = math.ceil(total_hours / 24)
    extra_days = billable_days - 3
    
    return product.three_day_price + (extra_days * product.additional_day_price)