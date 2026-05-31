import math

import pytz
from datetime import datetime


def get_vietnam_time():
    local_time = datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
    return local_time.replace(tzinfo=None)

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

def verify_shift_is_editable(date_str, shift_type):
    """
    Enforces time locks on backend mutations matching operational timezone requirements.
    Returns (True, None) if editable, or (False, error_message) if locked out.
    """
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return False, "Invalid date formatting sequence."

    # Fetch active localized Vietnam production time
    vn_now = get_vietnam_time()
    today_date = vn_now.date()
    current_hour = vn_now.hour

    # Rule 1: Calendar target is a past date
    if target_date < today_date:
        return False, "Schedules on past dates cannot be modified."

    # Rule 2: Calendar target is a future date
    if target_date > today_date:
        return True, None

    # Rule 3: Target date is TODAY -> check shift block hours
    if shift_type == 'morning' and current_hour >= 8:
        return False, "The morning shift timeframe has already started or completed."
    
    if shift_type == 'afternoon' and current_hour >= 12:
        return False, "The afternoon shift timeframe has already started or completed."
    
    if shift_type == 'evening' and current_hour >= 17:
        return False, "The evening shift timeframe has already started or completed."
    
    if shift_type == 'night' and (current_hour >= 22 or current_hour < 4):
        return False, "The night shift timeframe has already started or completed."

    return True, None