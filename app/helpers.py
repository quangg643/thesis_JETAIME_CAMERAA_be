import pytz
from datetime import datetime


def get_vietnam_time():
    # Returns the current time in Vietnam (UTC+7)
    return datetime.now(pytz.timezone('Asia/Ho_Chi_Minh'))
