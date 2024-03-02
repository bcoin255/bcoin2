from django.contrib import admin
from .models import *


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    search_fields = ("name", "cost", "vip_status")


@admin.register(UserDetails)
class UserDetailsAdmin(admin.ModelAdmin):
    search_fields = ("username", "referral_code", "phone", "balance", "points")


@admin.register(OrderID)
class OrderIDAdmin(admin.ModelAdmin):
    search_fields = ("order_id",)


@admin.register(ReceiverAccount)
class ReceiverAccountAdmin(admin.ModelAdmin):
    search_fields = ("mpesa_number", "name")


@admin.register(Withdraw)
class WithdrawAdmin(admin.ModelAdmin):
    search_fields = ("username", "amount")


@admin.register(Recharge)
class RechargeAdmin(admin.ModelAdmin):
    search_fields = ("username", "amount", "mpesa_code", "mpesa_name")


@admin.register(PendingRecharge)
class RechargeAdmin(admin.ModelAdmin):
    search_fields = ("username", "amount",)


@admin.register(NewsFeed)
class NewsFeedAdmin(admin.ModelAdmin):
    search_fields = ("title", "description",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    search_fields = ("username", "created_at", "days_amount")


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    search_fields = ("parent_username", "child_username")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    search_fields = ("phone", "role")


@admin.register(SelectedReceiverAccount)
class SelectedReceiverAccountAdmin(admin.ModelAdmin):
    search_fields = ("pk",)


@admin.register(Transaction)
class TransactionAccountAdmin(admin.ModelAdmin):
    search_fields = ("pk","username", "transaction_code", "description", "account_balance", "amount")
    
