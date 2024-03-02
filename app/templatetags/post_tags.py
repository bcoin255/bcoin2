from django import template
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.timezone import make_aware, make_naive

from app.models import Subscription, default_now

register = template.Library()


@register.simple_tag
def percentage(value, total):
    return round(value / total * 100)


@register.simple_tag
def total_returns(cycles, daily_income):
    return cycles * daily_income


@register.simple_tag
def return_percentage(cycles, daily_earnings, cost):
    return round(((cycles*daily_earnings)/cost) * 100, 2)


@register.simple_tag(takes_context=True)
def show_claim_link(context, machine):
    user = context['request'].user
    current_time = default_now()

    # Check if it's a weekend
    if current_time.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
        return False

    # Check if 24 hours have passed since a specific user attribute was saved
    # Assuming this attribute is 'last_saved_time' on the user model
    if user.last_saved_time and (current_time - user.last_saved_time).total_seconds() >= 86400:
        return True

    return False


@register.simple_tag
def remaining_time(time_of_last_pay_off, machine_pk, *args):
    print("*******************************************************8")
    print()

    print("Running template tag")
    now = default_now()
    
    if time_of_last_pay_off.weekday() >= 5:
        days_until_next_monday = 7 - time_of_last_pay_off.weekday()
        time_of_last_pay_off = (time_of_last_pay_off + timedelta(days=days_until_next_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        if now.weekday() >= 5:
            now = time_of_last_pay_off

    print(f"time of last payoff {time_of_last_pay_off.date()} {time_of_last_pay_off.time()}")
    print(f"now {now.date()} {now.time()}")

    time_difference = now - time_of_last_pay_off
    print("time difference:", time_difference)

    total_full_days = time_difference.days
    print(f"total full days {total_full_days}")

    if total_full_days > 0:
        print("full days greater than 1")
        total_weekdays = 0
        if total_full_days == 1:
            current_day = time_of_last_pay_off + timedelta(days=1)
            if current_day.weekday() < 5:  # 0 to 4 represents Monday to Friday
                total_weekdays += 1
        else:
            for day in range(total_full_days):
                current_day = time_of_last_pay_off + timedelta(days=day+1)
                if current_day.weekday() < 5:  # 0 to 4 represents Monday to Friday
                    total_weekdays += 1
        print(f"total weekdays {total_weekdays}")

        if total_weekdays > 0:
            sub = Subscription.objects.get(pk=machine_pk)

            if (now - sub.created_at).days > sub.product.cycles and sub.created_at == sub.time_of_last_pay_off:
                sub.days_amount = sub.product.daily_earnings * sub.product.cycles
                sub.time_of_last_pay_off = sub.created_at + timedelta(days=sub.product.cycles)
            else:
                daily_earnings = sub.product.daily_earnings
    
                print("total weekdays:", total_weekdays)
                print("daily earnings for this product:", daily_earnings)
                print("days earnings added:", daily_earnings * total_weekdays)
                
                if daily_earnings * total_weekdays > sub.product.cycles * daily_earnings:
                    sub.days_amount = daily_earnings * sub.product.cycles
                    sub.time_of_last_pay_off = sub.created_at + timedelta(days=sub.product.cycles+sub.number_of_weekends)
                else:
                    sub.days_amount += daily_earnings * total_weekdays
                    sub.time_of_last_pay_off = time_of_last_pay_off + timedelta(days=total_full_days)
            sub.save()

    remaining_seconds = max(86400 - time_difference.total_seconds(), 0)
    print("remaining seconds:", remaining_seconds)
    total_time_remaining = timedelta(seconds=remaining_seconds)
    print("total time remaining:", total_time_remaining)
    hours, remainder = divmod(total_time_remaining.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"hours {hours} minutes {minutes} seconds {seconds}")
    print()
    print("*******************************************************8")

    return {
        "hours": hours,
        "minutes": minutes,
        "seconds": seconds
    }


@register.simple_tag
def calculate_expiry(created_at, cycles, number_of_weekends):
    # Assuming each weekend consists of 2 days (Saturday and Sunday)
    days_to_add = number_of_weekends + cycles
    expiry_date = created_at + timedelta(days=days_to_add)
    return expiry_date
