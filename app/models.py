from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import datetime
import random
import string


def generate_random_string(length=100):
    characters = string.ascii_letters + string.digits
    while True:
        code = ''.join(random.choice(characters) for _ in range(length))
        if UserDetails.objects.filter(referral_code=code).count() == 0:
            return code


def default_now():
    now = timezone.now() + timezone.timedelta(hours=3)
    return now


def calculate_order_id():
    year = datetime.now().year
    month = datetime.now().month
    day = datetime.now().day
    try:
        num = OrderID.objects.all().order_by("-pk")[0].order_id
        letters = num[:2]
        numbers = num[9:]
        new_letters = letters
        if numbers[1] == "9":
            if numbers[0] == "9":
                new_numbers = "10"
                new_numbers += numbers[2:]
                if letters[-1] == "z":
                    if letters[-2] == "z":
                        new_letters = "aa"
                    else:
                        new_letters = chr(ord(letters[-2]) + 1)
                        new_letters += "a"
                else:
                    new_letters = letters[-2]
                    new_letters += chr(ord(letters[-1]) + 1)
            else:
                new_numbers = str(int(numbers) + 1)
        else:
            new_numbers = str(int(numbers) + 1)
        order_code = new_letters + str(year) + str(month) + str(day) + new_numbers
        num = OrderID()
        num.order_id = order_code
        num.save()
        return order_code
    except:
        order_code = "dm" + str(year) + str(month) + str(day) + "000000002155"
        OrderID(order_id=order_code).save()
        return order_code


def default_end_time():
    current_time = default_now()
    end_time = current_time + timezone.timedelta(hours=5)
    return end_time.time()


def default_start_time():
    return default_now().time()


def tc_calculate():
    try:
        code_object = TC.objects.get(pk=1)
        dig = code_object.code[-1]
        code = list(code_object.code)

        if int(dig) == 9:
            dig = code_object.code[-2]
            code[-1] = "0"
            if dig == "z":
                dig = code_object.code[-3]
                code[-2] = "a"
                if dig == "Z":
                    dig = code_object.code[-4]
                    code[-3] = "A"
                    if int(dig) == 9:
                        dig = code_object.code[-5]
                        code[-4] = "0"
                        if dig == "z":
                            dig = code_object.code[-6]
                            code[-5] = "a"
                            if dig == "Z":
                                dig = code_object.code[-7]
                                code[-6] = "A"
                                if int(dig) == 9:
                                    dig = code_object.code[-8]
                                    code[-7] = "0"
                                    if dig == "z":
                                        dig = "A"
                                        code[-8] = dig
                                else:
                                    dig = int(dig) + 1
                                    code[-7] = str(dig)
                            else:
                                dig = chr(ord(dig) + 1)
                                code[-6] = dig
                        else:
                            dig = chr(ord(dig) + 1)
                            code[-5] = dig
                    else:
                        dig = int(dig) + 1
                        code[-4] = str(dig)
                else:
                    dig = chr(ord(dig) + 1)
                    code[-3] = dig
            else:
                dig = chr(ord(dig) + 1)
                code[-2] = dig
        else:
            dig = int(dig) + 1
            code[-1] = str(dig)

        new_code = "".join(code)
        code_object.code = new_code
        code_object.save()

    except:
        new_code = "Mv2Qx0Aa0"
        TC(pk=1, code=new_code).save()

    return new_code


class TC(models.Model):
    code = models.CharField(max_length=20)

    def __str__(self):
        return self.code


class Product(models.Model):
    name = models.CharField(max_length=20, default="", unique=True)
    description = models.TextField(default="")
    daily_earnings = models.IntegerField(default=0)
    cycles = models.IntegerField(default=25)
    quantity_limit = models.IntegerField(default=3)
    minimum_withdrawal = models.IntegerField(default=300)
    cost = models.IntegerField(default=0)
    image = models.CharField(max_length=2000, default="")
    vip_status = models.BooleanField(default=False)
    discounted = models.BooleanField(default=False)
    from_price = models.IntegerField(null=True)

    def __str__(self):
        return self.name


class UserDetails(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    last_product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True)
    username = models.CharField(max_length=200, default="")
    phone = models.CharField(max_length=20, default="")
    balance = models.FloatField(default=0.0)
    points = models.FloatField(default=0.0)
    referral_code = models.CharField(max_length=2000, default=generate_random_string)
    total_referrals = models.IntegerField(default=0)
    active_subscriptions = models.IntegerField(default=0)
    last_subscription_payoff = models.DateTimeField(null=True)
    subscribed_referrals = models.IntegerField(default=0)

    def __str__(self):
        return self.username


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        created = UserDetails()
        created.user = instance


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.userdetails.save()


class ReceiverAccount(models.Model):
    qr_code = models.CharField(max_length=4000, null=True)
    mpesa_number = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=50, default="")
    start_time = models.TimeField(default=default_start_time())
    end_time = models.TimeField(default=default_end_time())

    def __str__(self):
        return self.mpesa_number


class SelectedReceiverAccount(models.Model):
    account = models.ForeignKey(ReceiverAccount, on_delete=models.CASCADE)

    def __str__(self):
        return str(self.pk)


class Withdraw(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True)
    username = models.CharField(max_length=50, default="")
    amount = models.IntegerField(default=300)
    time_stamp = models.DateTimeField(default=default_now)
    complete = models.BooleanField(default=False)
    mpesa_number = models.CharField(max_length=20, default="")
    mpesa_name = models.CharField(max_length=50, default="")

    def __str__(self):
        return self.username


class Recharge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    username = models.CharField(max_length=50)
    amount = models.FloatField(default=0.0)
    complete = models.BooleanField(default=False)
    receiver_account = models.ForeignKey(ReceiverAccount, on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(default=default_now)
    mpesa_code = models.CharField(max_length=20, default="", unique=True)
    mpesa_name = models.CharField(max_length=100, default="")
    order_id = models.CharField(max_length=50, default="")

    def __str__(self):
        return self.username


class PendingRecharge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    username = models.CharField(max_length=50, default="")
    amount = models.FloatField(default=0.0)
    receiver_account = models.ForeignKey(ReceiverAccount, on_delete=models.CASCADE, null=True)
    complete = models.BooleanField(default=False)
    time_stamp = models.DateTimeField(default=default_now)
    order_id = models.CharField(max_length=50, default=calculate_order_id)

    def __str__(self):
        return self.username


class OrderID(models.Model):
    order_id = models.CharField(max_length=50)

    def __str__(self):
        return self.order_id


class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    username = models.CharField(max_length=50, default="")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=default_now)
    time_of_last_pay_off = models.DateTimeField(default=default_now)
    days_amount = models.FloatField(default=0.0)
    number_of_weekends = models.IntegerField(default=0)

    def __str__(self):
        return self.username


class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING, null=True)
    username = models.CharField(max_length=50)
    transaction_type = models.CharField(max_length=20, default="")
    time_stamp = models.DateTimeField(default=default_now)
    transaction_code = models.CharField(max_length=20, default=tc_calculate)
    description = models.TextField(default="")
    amount = models.FloatField(default=0.0)
    account_balance = models.FloatField(default=0)

    def __str__(self):
        return self.username


class NewsFeed(models.Model):
    image = models.CharField(max_length=4000, null=True)
    title = models.CharField(max_length=50)
    description = models.TextField(null=True)
    likes = models.IntegerField(default=0)
    views = models.IntegerField(default=0)

    def __str__(self):
        return self.title


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    username = models.CharField(max_length=50, default="")
    message = models.TextField(null=True)
    time_stamp = models.DateTimeField(default=default_now)
    reply = models.BooleanField(default=False)

    def __str__(self):
        return self.username


class Referral(models.Model):
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name="referrer")
    child = models.OneToOneField(User, on_delete=models.CASCADE, related_name="referred", null=True)
    current_product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True)
    parent_username = models.CharField(max_length=50, null=True)
    child_username = models.CharField(max_length=50, null=True)
    created_at = models.DateTimeField(default=default_now)
    last_buy = models.DateTimeField(null=True)
    first_product = models.BooleanField(default=False)

    def __str__(self):
        return self.parent_username


class Contact(models.Model):
    phone = models.CharField(max_length=15)
    role = models.CharField(max_length=35)

    def __str__(self):
        return self.phone
