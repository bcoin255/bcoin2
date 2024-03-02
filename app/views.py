from django.db import IntegrityError
from collections import defaultdict
from django.urls import reverse
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import Product, Withdraw, PendingRecharge, Recharge, ReceiverAccount, Subscription, NewsFeed, \
    calculate_order_id, Referral, UserDetails, Transaction, default_now, Contact, SelectedReceiverAccount


generic_list = ["john doe"]


def count_weekend_days(days_ahead):
    # Get the current date
    current_date = timezone.now()

    # Initialize the count of weekend days
    weekend_count = 0

    # Loop through each day from now to the specified number of days ahead
    for day in range(days_ahead + 1):  # +1 to include the last day in the range
        # Check if the day is a Saturday (5) or Sunday (6)
        if (current_date + timezone.timedelta(days=day)).weekday() in [5, 6]:
            weekend_count += 1

    return weekend_count


def clear_pending_recharges():
    threshold_time = timezone.now() - timezone.timedelta(days=2)
    [instance.delete() for instance in PendingRecharge.objects.filter(time_stamp__lt=threshold_time)]


def migrate_data():
    call_command("makemigrations")
    call_command("migrate")


def index(request):
    user = request.user
    products = Product.objects.filter(discounted=False).order_by("name")
    discounted_products = Product.objects.filter(discounted=True).order_by("name")
    news_feeds = NewsFeed.objects.all()
    clear_pending_recharges()

    if user.is_authenticated:
        user.userdetails.total_referrals = Referral.objects.filter(parent=user).count()
        user.userdetails.active_subscriptions = Subscription.objects.filter(user=user).count()
        user.save()
        if user.is_superuser:
            if request.method == "POST":
                if request.POST.get("admin"):
                    total_user_balances = sum([single_user.userdetails.balance for single_user in User.objects.all()])
                    total_pending_withdrawals = sum([single_withdrawal.amount for single_withdrawal in Withdraw.objects.filter(complete=False)])
                    total_recharges_awaiting_authentication = sum([single_recharge.amount for single_recharge in Recharge.objects.filter(complete=False)])
                    total_pending_recharges = sum([single_recharge.amount for single_recharge in PendingRecharge.objects.all()])
                    total_complete_recharges = sum([single_recharge.amount for single_recharge in Recharge.objects.filter(complete=True)])
                    total_complete_withdrawals = sum([single_recharge.amount for single_recharge in Withdraw.objects.filter(complete=True)])

                    products_count = Product.objects.all().count()
                    vip_products_count = Product.objects.filter(vip_status=True).count()
                    total_withdrawals_count = Withdraw.objects.all().count()
                    total_recharge_count = Recharge.objects.all().count()
                    complete_withdrawal_count = Withdraw.objects.filter(complete=True).count()
                    complete_recharge_count = Recharge.objects.filter(complete=True).count()

                    subscribed_users = {subscription.user for subscription in Subscription.objects.all()}

                    # Aggregating Withdrawals by month and year
                    monthly_withdrawals = Withdraw.objects.annotate(
                        month=TruncMonth('time_stamp')
                    ).values('month').annotate(
                        total_amount=Sum('amount'),
                        total_count=Count('id')
                    ).order_by('month')

                    # Aggregating Recharges by month and year
                    monthly_recharges = Recharge.objects.annotate(
                        month=TruncMonth('created_at')
                    ).values('month').annotate(
                        total_amount=Sum('amount'),
                        total_count=Count('id')
                    ).order_by('month')

                    # Create a default dictionary to store combined data
                    combined_data = defaultdict(lambda: {'withdrawals': 0, 'recharges': 0})

                    # Populate the dictionary with data
                    for entry in monthly_withdrawals:
                        month = entry['month'].strftime("%b %Y")  # Format the month
                        combined_data[month]['withdrawals'] = entry['total_amount']

                    for entry in monthly_recharges:
                        month = entry['month'].strftime("%b %Y")  # Format the month
                        combined_data[month]['recharges'] += entry['total_amount']

                    # Convert to a list of tuples for easy iteration in the template
                    combined_data_list = list(combined_data.items())
                    
                    selected_contact = contact_in_use = None

                    current_time = default_now().time()
                    accounts = ReceiverAccount.objects.filter(Q(start_time__lte=current_time))
                    if accounts.count() > 0:
                        contact_in_use = accounts.order_by("start_time")[0]

                    mpesa_contacts = ReceiverAccount.objects.all()  # some comment

                    return render(request, "admin index.html", {
                        "total_user_balances" : total_user_balances,
                        "total_pending_withdrawals": total_pending_withdrawals,
                        "total_recharges_awaiting_authentication": total_recharges_awaiting_authentication,
                        "total_pending_recharges": total_pending_recharges,
                        "total_complete_recharges": total_complete_recharges,
                        "total_complete_withdrawals": total_complete_withdrawals,
                        "products_count": products_count,
                        "vip_products_count": vip_products_count,
                        "total_withdrawals_count": total_withdrawals_count,
                        "total_recharge_count": total_recharge_count,
                        "complete_withdrawal_count": complete_withdrawal_count,
                        "complete_recharge_count": complete_recharge_count,
                        "combined_data": combined_data_list,
                        "subscribed_users": subscribed_users,
                        "selected_contact": selected_contact,
                        "contact_in_use": contact_in_use,
                        "mpesa_contacts": mpesa_contacts,
                    })
                elif request.POST.get("index"):
                    return render(request, "index.html", {"products": products,
                                                          "discounted_products": discounted_products,
                                                          "news_feeds": news_feeds})
            return render(request, "admin login prompt.html")
    return render(request, "index.html", {"products": products, "discounted_products": discounted_products,
                                          "news_feeds": news_feeds})


def product(request, id):
    if request.user.is_authenticated:
        user_product = get_object_or_404(Product, pk=id)
        total_earnings = user_product.cycles * user_product.daily_earnings
        total_returns = round((total_earnings / user_product.cost) * 100, 2)
        return render(request, 'product_detail.html', {'product': user_product, "total_earnings": total_earnings, "total_returns": total_returns})
    else:
        messages.error(request, "Login to access products.")
        return redirect("app:login")


def user_login(request):
    if request.user.is_authenticated:
        products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()

        messages.error(request, "You are already signed in!")
        return render(request, "index.html", {"products": products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})

    if request.method == "POST":
        username = request.POST["username"].lower().strip()
        password = request.POST["password"]

        if username in generic_list or len(username) == 1:
            messages.error(request, "Username is too generic!")
            return redirect("app:login")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Login successfull")

            products = Product.objects.filter(discounted=False).order_by("name")
            discounted_products = Product.objects.filter(discounted=True).order_by("name")
            news_feeds = NewsFeed.objects.all()
            return render(request, "index.html", {"products": products,
                                                  "discounted_products": discounted_products,
                                                  "news_feeds": news_feeds})

        messages.error(request, "Invalid credentials!")
        return redirect("app:login")

    return render(request, "login.html")


def user_registration(request):
    if request.method == "POST":
        username = request.POST["username"].lower().strip()
        email = request.POST["email"].lower().strip()
        first_name = request.POST["first-name"].lower().strip()
        last_name = request.POST["last-name"].lower().strip()
        password1 = request.POST["password1"]
        password2 = request.POST["password2"]
        phone = request.POST["phone"]

        if username in generic_list or len(username) == 1:
            messages.error(request, "Username is too generic!")
            return redirect("app:register")

        if not (username and email and first_name and password1):
            messages.error(request, "All fields required!")
            return redirect("app:register")

        try:
            tel = int(phone)

            if phone[0] == "0" and len(phone) != 10:
                raise
            
            if len(phone) == 10:
                phone = "+254" + str(tel)

        except:
            messages.error(request, "Please enter a valid mpesa number")
            return redirect("app:register")

        try:
            User.objects.get(username=username)
            messages.error(request, "User with the username '" + username + "' already exist.")
            return redirect("app:index")
        except:
            pass

        if password1 == password2:

            if "is_admin" in request.POST:

                # if not User.objects.filter(username=username).exists():
                #     # Create a superuser using the createsuperuser management command
                #     call_command('createsuperuser', username=username,
                #                  email=email, interactive=False)

                #     user = User.objects.get(username=username)
                #     user.first_name = first_name
                #     user.last_name = last_name

                #     user.set_password(password1)

                #     user.userdetails.phone = phone
                #     user.userdetails.username = username

                #     user.save()

                #     if user is not None:
                #         login(request, user)

                messages.success(
                    request, "Admin creation disabled.")

                products = Product.objects.filter(discounted=False).order_by("name")
                discounted_products = Product.objects.filter(discounted=True).order_by("name")
                news_feeds = NewsFeed.objects.all()
                return render(request, "index.html", {"products": products,
                                                      "discounted_products": discounted_products,
                                                      "news_feeds": news_feeds})
            else:
                user = User.objects.create(
                    email=email,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                )

                user.set_password(password1)

                user.userdetails.phone = phone
                user.userdetails.username = username

                user.save()

                if user is not None:
                    login(request, user)

                messages.success(request, "Registration successful.")

                products = Product.objects.filter(discounted=False).order_by("name")
                discounted_products = Product.objects.filter(discounted=True).order_by("name")
                news_feeds = NewsFeed.objects.all()
                return render(request, "index.html", {"products": products,
                                                      "discounted_products": discounted_products,
                                                      "news_feeds": news_feeds})
        else:
            messages.error(request, "Password mismatch.")
            return redirect("app:register")

    return render(request, "registration.html")


def user_logout(request):
    user = request.user
    if user.is_authenticated:
        logout(request)
        messages.info(request, "Logout successful.")
        return render(request, "index.html")
    messages.error(request, "You are already logged out!")

    products = Product.objects.filter(discounted=False).order_by("name")
    discounted_products = Product.objects.filter(discounted=True).order_by("name")
    news_feeds = NewsFeed.objects.all()
    return render(request, "index.html", {"products": products,
                                          "discounted_products": discounted_products,
                                          "news_feeds": news_feeds})


def add_products(request):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            if request.method == "POST":
                name = request.POST["name"]
                daily_earnings = request.POST["daily-earnings"]
                cycles = request.POST["cycles"]
                cost = request.POST["cost"]
                description = request.POST["description"]
                quantity_limit = request.POST["quantity-limit"]
                image = request.POST["image"]
                from_price = request.POST["from-price"]
                vip_status = "vip-only" in request.POST

                try:
                    new_product = Product(
                        name=name,
                        description=description,
                        daily_earnings=daily_earnings,
                        cycles=cycles,
                        cost=cost,
                        quantity_limit=quantity_limit,
                        image=image,
                        vip_status=vip_status,
                    )
                    if from_price != 0 or from_price != "0":
                        if from_price > cost:
                            new_product.discounted = True
                            new_product.from_price = from_price
                            messages.success(request, "Product saved with a discount price of " + str(cost) +
                                             " down from " + str(from_price))
                            new_product.save()
                            return render(request, "add product.html")
                        else:
                            messages.error(request, "Product saved without discount as discounted price can not be \
                            greater than original price")
                            new_product.save()
                            return render(request, "add product.html")
                    new_product.save()
                    messages.success(request, "Product saved successfully.")
                except Exception as e:
                    messages.error(request, e)
            return render(request, "add product.html")
        messages.error(request, "This section is reserved for admins.")

        products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def pending_payments(request):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            pending = Withdraw.objects.filter(
                complete=False).order_by("time_stamp")
            return render(request, "pending payments.html", {"pending_payments": pending})
        messages.error(request, "This section is reserved to admins only.")

        products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def initiate_recharge(request):
    user = request.user
    if user.is_authenticated:
        if request.method == "POST":
            amount = int(request.POST["amount"])

            if amount < 500:
                messages.error(request, "Minimum recharge limit is 500!")
                return redirect("app:initiate_recharge")
                
            order_id = calculate_order_id()
            transaction = PendingRecharge(
                user=user,
                amount=float(amount),
                username=user.username,
                order_id=order_id
            )
            try:
                account = SelectedReceiverAccount.objects.get(pk=1).account
            except SelectedReceiverAccount.DoesNotExist:                
                current_time = default_now().time()
                end_time = (timezone.datetime.combine(timezone.now(), current_time) + timezone.timedelta(hours=5)).time()
                accounts = ReceiverAccount.objects.filter(Q(start_time__lte=current_time))
                if accounts.exists():
                    account = accounts.order_by("start_time").first()
                else:
                    try:
                        account = ReceiverAccount.objects.all().order_by("start_time").first()
                    except ReceiverAccount.DoesNotExist:
                        account = ReceiverAccount(mpesa_number='0723880323', name="JAMES GETUTU", end_time=end_time, start_time=current_time)
                        account.qr_code = "smh"
                        account.save()
            transaction.receiver_account = account
            transaction.save()
            return render(request, "complete recharge.html",
                          {"order_id": order_id, "amount": amount, "receiver": account, "recharge_id": transaction.pk})
        return render(request, "recharge options.html")
    messages.error(request, "Login required!")
    return redirect("app:login")


def complete_recharge(request, pk):
    user = request.user
    if user.is_authenticated:
        try:
            transaction = PendingRecharge.objects.get(pk=pk)
        except PendingRecharge.DoesNotExist:
            messages.error(request, "Your transaction has encountered an error. Please reinitiate transaction.")
            return render(request, "recharge options.html")
            
        if transaction.user == user:
            if request.method == "POST":
                try:
                    mpesa_name = request.POST["mpesa_name"]
                    mpesa_code = request.POST["mpesa_code"]

                    new_transaction = Recharge(
                        user=transaction.user,
                        mpesa_code=mpesa_code,
                        mpesa_name=mpesa_name,
                        username=transaction.user.username,
                        amount=transaction.amount,
                        order_id=transaction.order_id,
                        receiver_account=transaction.receiver_account
                    )
                    new_transaction.save()

                    messages.success(request, "Transaction saved. Please wait as your recharge is being effected \
                                                within 3 hours.")
                except IntegrityError:
                    messages.error(request, "Transaction with mesa code '" + mpesa_code + "' already completed.")
                transaction.delete()
        else:
            messages.error(request, "Recharge attempt ignored on account of suspicious activity!")

        products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})

    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def withdraw(request):
    user = request.user
    if user.is_authenticated:
        products = Subscription.objects.filter(user=user)
        if request.method == "POST":
            amount = int(request.POST["amount"])
            mpesa_name = request.POST["mpesa-name"]
            mpesa_number = request.POST["mpesa-number"]

            if amount < 300:
                messages.error(request, "Minimum withdrawal amount is 300!")
                return redirect("app:withdraw")

            if amount <= user.userdetails.balance:
                
                if user.userdetails.last_product is None and user.userdetails.active_subscriptions == 0:
                    messages.error(request, "Please pay for a product and work for a minimum of product-cycles days "
                                            "before you withdraw.")
                    return redirect("app:withdraw")
                    
                transaction = Withdraw(
                    user=user,
                    amount=amount,
                    username=user.username,
                    mpesa_name=mpesa_name,
                    mpesa_number=mpesa_number
                )
                transaction.save()

                balance = user.userdetails.balance - amount
                user.userdetails.balance = balance
                user.save()

                permanent_transaction = Transaction(
                    user=user,
                    amount=amount,
                    transaction_type="withdrawal",
                    username=user.username,
                    account_balance=user.userdetails.balance
                )
                permanent_transaction.save()

                messages.success(request, "You have successfully withdrawn " + str(amount) +
                                 " from your account. Your money will be sent within the next 72 hours.")

                all_products = Product.objects.filter(discounted=False).order_by("name")
                discounted_products = Product.objects.filter(discounted=True).order_by("name")
                news_feeds = NewsFeed.objects.all()
                return render(request, "index.html", {"products": all_products,
                                                      "discounted_products": discounted_products,
                                                      "news_feeds": news_feeds})
            else:
                messages.error(request, "You have insufficient balance to withdraw " + str(amount))
                return redirect("app:withdraw")

        user_products = Subscription.objects.filter(user=user)
        minimum = 500
        if user_products.count() > 0:
            for item in user_products:
                minimum = item.product.minimum_withdrawal if minimum > item.product.minimum_withdrawal else minimum
        return render(request, "withdraw.html", {"minimum": minimum, "products": products})
    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def account_details(request):
    user = request.user
    if user.is_authenticated:
        user = request.user
        subscriptions = Subscription.objects.filter(user=user)
        return render(request, "account details.html", {"subscriptions": subscriptions})
    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def pending_withdrawals(request):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            all_pending = Withdraw.objects.filter(complete=False).order_by("time_stamp")
            return render(request, "pending withdrawals.html", {"all_pending": all_pending})
        messages.error(request, "This section is reserved for admins.")

        products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
    else:
        messages.error(request, "Access reserved to authenticated admin!")
        return redirect("app:login")


def pending_recharges(request):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            all_pending = Recharge.objects.filter(complete=False).order_by("created_at")
            return render(request, "pending recharges.html", {"pending_recharges": all_pending})
        messages.error(request, "This section is reserved for admins.")

        products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def complete_transactions(request):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            complete_recharges = Recharge.objects.filter(complete=True).order_by("created_at")
            complete_withdrawals = Withdraw.objects.filter(complete=True).order_by("time_stamp")
            return render(request, "complete transactions.html", {"complete_recharges": complete_recharges,
                                                                "complete_withdrawals": complete_withdrawals})
        messages.error(request, "This section is reserved for admins.")

        products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def update_recharge(request, pk):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            transaction = Recharge.objects.get(pk=pk)
            if not transaction.complete:
                initiator = transaction.user
                initiator.userdetails.balance += transaction.amount
                initiator.save()
                transaction.complete = True
                transaction.save()
    
                permanent_transaction = Transaction(
                    user=transaction.user,
                    amount=transaction.amount,
                    transaction_type="recharge",
                    username=transaction.user.username,
                    account_balance=transaction.user.userdetails.balance
                )
                permanent_transaction.save()
    
                messages.success(request, "Recharge successfully saved.")
            else:
                messages.error(request, "This recharge is already effected.")
            all_pending = Recharge.objects.filter(complete=False).order_by("created_at")
            return render(request, "pending recharges.html", {"pending_recharges": all_pending})
        messages.error(request, "This section is reserved for admins.")

        all_products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": all_products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def update_withdrawal(request, pk):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            transaction = Withdraw.objects.get(pk=pk)
            if not transaction.complete:
                transaction.complete = True
                transaction.save()
    
                sender = transaction.user
                sender.userdetails.last_product = None
                sender.userdetails.active_subscriptions = Subscription.objects.filter(user=sender).count()
                sender.save()
    
                messages.success(request, "Withdrawal for '" + transaction.mpesa_name + "' of number '" + transaction.mpesa_number + "' approved.")
                all_pending = Withdraw.objects.filter(complete=False).order_by("time_stamp")
                return render(request, "pending withdrawals.html", {"all_pending": all_pending})
            else:
                messages.error(request, "This withdrawal is already effected.")
        messages.error(request, "This section is reserved for admins.")

        all_products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": all_products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def increase_like(request):
    if request.method == 'POST':
        news_id = request.POST.get('news_id')
        news_obj = NewsFeed.objects.get(pk=news_id)
        likes = news_obj.likes
        likes += 1
        news_obj.likes = likes
        news_obj.save()

        response_data = {'success': True, 'newLikeCount': likes}
        return JsonResponse(response_data)
    else:
        return JsonResponse({"success": False, 'error': 'Invalid request method'})


def my_wallet(request):
    user = request.user
    if user.is_authenticated:
        all_pending_withdrawals = Withdraw.objects.filter(complete=False, user=user).order_by("time_stamp")
        all_complete_withdrawals = Withdraw.objects.filter(complete=True, user=user).order_by("time_stamp")
        recharges_awaiting_authentication = Recharge.objects.filter(complete=False, user=user).order_by("created_at")
        all_complete_recharges = Recharge.objects.filter(complete=True, user=user).order_by("created_at")
        all_pending_recharges = PendingRecharge.objects.filter(user=user)
        total_pending_withdrawal = sum([withdrawal.amount for withdrawal in all_pending_withdrawals])
        total_pending_recharge = sum([recharge.amount for recharge in recharges_awaiting_authentication])
        total_complete_withdrawal = sum([withdrawal.amount for withdrawal in Withdraw.objects.filter(complete=True, user=user).order_by("time_stamp")])
        total_complete_recharge = sum([recharge.amount for recharge in Recharge.objects.filter(complete=True, user=user).order_by("created_at")])
        all_transactions = Transaction.objects.filter(user=user).order_by("-time_stamp")
        internal_activities = sum([transaction.amount for transaction in Transaction.objects.filter(Q(user=user) & Q(transaction_type__contains="payment") | Q(transaction_type__contains="referral_bonus"))])
        return render(request, "my wallet.html", {"all_pending_withdrawals": all_pending_withdrawals,
                                                  "recharges_awaiting_authentication": recharges_awaiting_authentication,
                                                  "all_pending_recharges": all_pending_recharges,
                                                  "total_pending_withdrawal": total_pending_withdrawal,
                                                  "total_pending_recharge": total_pending_recharge,
                                                  "total_complete_withdrawal": total_complete_withdrawal,
                                                  "total_complete_recharge": total_complete_recharge,
                                                  "all_complete_withdrawals": all_complete_withdrawals,
                                                  "all_complete_recharges": all_complete_recharges,
                                                  "all_transactions": all_transactions})
    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def my_profile(request):
    user = request.user
    if user.is_authenticated:
        todays_income = 0
        user_subscriptions = Subscription.objects.filter(user=user)
        if user_subscriptions.count() > 0:
            todays_income = sum([subscription.days_amount for subscription in user_subscriptions])
        total_recharges = sum([transaction.amount for transaction in Recharge.objects.filter(user=user)])
        total_withdrawals = sum([transaction.amount for transaction in Withdraw.objects.filter(user=user)])
        return render(request, "my profile.html", {"total_recharges": total_recharges,
                                                   "total_withdrawals": total_withdrawals,
                                                   "todays_income": todays_income})
    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def products(request):
    discounted_products = Product.objects.filter(discounted=True).order_by("name")
    full_priced_products = Product.objects.filter(discounted=False).order_by("name")
    return render(request, "products.html", {"discounted": discounted_products, "full_priced": full_priced_products})


def news_feeds(request, pk):
    news = NewsFeed.objects.get(pk=pk)
    news.views += 1
    news.save()
    return render(request, "news.html", {"news": news})


def contact(request):
    user = request.user
    if user.is_authenticated:
        customer_care = Contact.objects.get(role="Customer Care")
        technical_support = Contact.objects.get(role="Technical Supoort")
        return render(request, "contact.html", {"customer_care": customer_care, "technical_support": technical_support})
    messages.error(request, "Access restricted to logged in users.")
    return redirect("app:login")


def join(request, referral_code):
    try:
        referrer = UserDetails.objects.get(referral_code=referral_code).user
    except UserDetails.DoesNotExist:
        messages.error(request, "Invalid referral code!")

        all_products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": all_products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})

    if request.method == "POST":
        username = request.POST["username"].lower().strip()
        email = request.POST["email"].lower().strip()
        first_name = request.POST["first-name"].lower().strip()
        last_name = request.POST["last-name"].lower().strip()
        password1 = request.POST["password1"]
        password2 = request.POST["password2"]
        phone = request.POST["phone"]

        if username in generic_list or len(username) == 1:
            messages.error(request, "Username is too generic!")
            url = reverse('app:join', kwargs={'referral_code': str(referrer.userdetails.referral_code)})
            return redirect(url)

        if not (username and email and first_name and password1):
            messages.error(request, "All fields required!")
            url = reverse('app:join', kwargs={'referral_code': str(referrer.userdetails.referral_code)})
            return redirect(url)

        try:
            if phone[0] == "+" and len(phone) == 13:
                pass
            else:
                tel = int(phone)
    
                if phone[0] == "0" and len(phone) != 10:
                    raise
                
                if len(phone) == 10:
                    phone = "+254" + str(tel)

        except:
            messages.error(request, "Please enter a valid mpesa number")
            url = reverse('app:join', kwargs={'referral_code': str(referrer.userdetails.referral_code)})
            return redirect(url)

        try:
            User.objects.get(username=username)
            messages.error(request, "User with the username '" + username + "' already exist.")
            url = reverse('app:join', kwargs={'referral_code': str(referrer.userdetails.referral_code)})
            return redirect(url)
        except:
            pass

        if password1 == password2:
            user = User.objects.create(
                email=email,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )

            user.set_password(password1)

            user.userdetails.phone = phone
            user.userdetails.username = username

            user.save()

            new_referral = Referral(
                parent=referrer,
                child=user,
                child_username=referrer.username,
                parent_username=user.username,
            )
            new_referral.save()

            referrer.userdetails.total_referrals = Referral.objects.filter(parent=referrer).count()
            referrer.save()
            
            if user is not None:
                login(request, user)

            messages.success(request, "Registration successful.")

            all_products = Product.objects.filter(discounted=False).order_by("name")
            discounted_products = Product.objects.filter(discounted=True).order_by("name")
            news_feeds = NewsFeed.objects.all()
            return render(request, "index.html", {"products": all_products,
                                                  "discounted_products": discounted_products,
                                                  "news_feeds": news_feeds})
        else:
            messages.error(request, "Password mismatch.")
            return redirect("app:register")

    return render(request, "registration.html", {"referrer": referrer})


def invite(request):
    user = request.user
    if user.is_authenticated:
        return render(request, "invite.html")
    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def my_team(request):
    user = request.user
    if user.is_authenticated:
        my_referrals = Referral.objects.filter(parent=user)
        return render(request, "my team.html", {"referrals": my_referrals})
    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def my_machines(request):
    user = request.user
    if user.is_authenticated:
        current_time = default_now()
        is_weekday = current_time.weekday() < 5
        machines = Subscription.objects.filter(user=user)
        return render(request, "my machines.html", {"is_weekday": is_weekday, "machines": machines})
    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def buy_product(request, pk):
    user = request.user
    if user.is_authenticated:
        subscription_product = Product.objects.get(pk=pk)
        if request.method == "POST":
            products = Product.objects.filter(discounted=False).order_by("name")
            discounted_products = Product.objects.filter(discounted=True).order_by("name")
            news_feeds = NewsFeed.objects.all()
            if "yes" in request.POST:
                if user.userdetails.balance < subscription_product.cost:
                    messages.error(request, "You have insufficient balance to complete this transaction!")
                    return redirect("app:products")
                if Subscription.objects.filter(user=user, product=subscription_product).count() >= subscription_product.quantity_limit:
                    messages.error(request, "You have already purchased this product in it's maximum quantity.")
                    return redirect("app:products")

                subscription = Subscription(
                    user=user,
                    username=user.username,
                    product=subscription_product,
                    number_of_weekends=count_weekend_days(subscription_product.cycles),
                )
                subscription.save()
                
                balance = user.userdetails.balance
                user.userdetails.balance = balance - subscription_product.cost
                user.userdetails.last_product = subscription_product
                user.active_subscriptions = Subscription.objects.filter(user=user).count()
                user.save()

                permanent_transaction = Transaction(
                    user=user,
                    username=user.username,
                    amount=subscription_product.cost,
                    transaction_type="payment",
                    description="Paid to subscribe to the package " + subscription.product.name + " for a "
                                + str(subscription.product.cycles) + " days period.",
                    account_balance=user.userdetails.balance
                )
                permanent_transaction.save()

                try:
                    referral_instance = Referral.objects.get(child=user)
                    referral_instance.first_product = True
                    current_day = default_now()

                    if current_day.weekday() >= 5:
                        days_until_next_monday = 7 - current_day.weekday()
                        next_monday = current_day + timedelta(days=days_until_next_monday)
                        referral_instance.last_buy = next_monday.replace(hour=0, minute=0, second=0, microsecond=0)
                    else:
                        referral_instance.last_buy = current_day
                    referral_instance.save()

                    referrer_instance = referral_instance.parent
                    subscribed_referrals = referrer_instance.userdetails.subscribed_referrals + 1
                    referrer_instance.userdetails.subscribed_referrals = subscribed_referrals

                    if subscribed_referrals > 0 and subscribed_referrals % 5 == 0:
                        if referrer_instance.userdetails.last_subscription_payoff is None or \
                                default_now() > referrer_instance.userdetails.last_subscription_payoff:
                            referrer_payment = Transaction(
                                user=referrer_instance,
                                username=referrer_instance.username,
                                amount=500,
                                transaction_type="referral_bonus",
                                account_balance=referrer_instance.userdetails.balance
                            )
                            if referrer_instance.userdetails.subscribed_referrals > 5:
                                referrer_payment.description = "Deposited to your account as payoff for 5 more active subscribers"
                            else:
                                referrer_payment.description = "Deposited to your account as payoff for 5 active subscribers",
                            referrer_payment.save()
                            referrer_instance.userdetails.balance += 500
                            referrer_instance.userdetails.last_subscription_payoff = default_now()

                    referrer_instance.save()
                except:
                    pass

                messages.success(request, "You have successfully subscribed to the product " + subscription_product.name
                                 + ".")
                return render(request, "index.html", {"products": products, "discounted_products": discounted_products,
                                                  "news_feeds": news_feeds})
            messages.info(request, "You have cancelled this transaction.")
            return render(request, "index.html", {"products": products, "discounted_products": discounted_products,
                                                  "news_feeds": news_feeds})
        product_id = subscription_product.pk
        return render(request, "buy product.html", {"product_id": product_id})
    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def edit_profile(request):
    user = request.user
    if user.is_authenticated:
        if request.method == "POST":
            username = request.POST["username"].lower().strip()
            email = request.POST["email"].lower().strip()
            first_name = request.POST["first-name"].lower().strip()
            last_name = request.POST["last-name"].lower().strip()
            password1 = request.POST["password1"]
            password2 = request.POST["password2"]
            phone = request.POST["phone"]

            if not (username and email and first_name and password1):
                messages.error(request, "All fields required!")
                url = reverse('app:edit_profile')
                return redirect(url)
    
            try:
                if phone[0] == "+" and len(phone) == 13:
                    pass
                else:
                    tel = int(phone)
        
                    if phone[0] == "0" and len(phone) != 10:
                        raise
                    
                    if len(phone) == 10:
                        phone = "+254" + str(tel)
    
            except:
                messages.error(request, "Please enter a valid mpesa number")
                url = reverse('app:edit_profile')
                return redirect(url)
    
            try:
                User.objects.get(username=username)
                messages.error(request, "User with the username '" + username + "' already exist.")
                url = reverse('app:edit_profile')
                return redirect(url)
            except:
                pass

            if password1 == password2:
                user.username = username
                user.email = email
                user.first_name = first_name
                user.last_name = last_name
                user.userdetails.phone = phone
                user.set_password(password1)
                user.save()

                messages.success(request, "Profile updated successfully.")
                return render(request, "my profile.html")
            messages.error(request, "Password missmatch.")
            return redirect("app:edit_profile")
        return render(request, "edit profile.html")
    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def claim(request, pk):
    user = request.user
    if user.is_authenticated:
        sub = Subscription.objects.get(pk=pk)
        accumulated_amount = sub.days_amount

        if sub.user == user:
            if accumulated_amount > 1:
                max_amount = sub.product.daily_earnings * sub.product.cycles

                if accumulated_amount <= max_amount:
                    sub.days_amount -= accumulated_amount
                    sub.user.userdetails.balance += accumulated_amount
                    sub.save()
                    sub.user.save()
    
                    transaction = Transaction(
                        user=sub.user,
                        username=sub.user.username,
                        transaction_type="reception",
                        amount=accumulated_amount,
                        description="Received " + str(accumulated_amount) + " after a claim on " +
                                    str(sub.product.name) + "'s daily earnings.",
                        account_balance=sub.user.userdetails.balance
                    )
                    transaction.save()
    
                    if sub.product.cycles < (sub.created_at - default_now()).days or accumulated_amount == max_amount:
                        sub.delete()
    
                    sub.user.userdetails.active_subscriptions = Subscription.objects.filter(user=sub.user).count()
                    sub.user.save()
    
                    messages.success(request, "Claim successfully deposited into your balance account.")
                else:
                    messages.success(request, "Claim rejected on account of abnormal accumulation. Please contact support.")
            else:
                messages.error(request, "Your claim amount is smaller than the required minimum!")
        else:
            messages.error(request, "Your claim has been disregarded on account of suspicious activity!")

        current_time = timezone.now()
        is_weekday = current_time.weekday() < 5
        machines = Subscription.objects.filter(user=sub.user)

        return render(request, "my machines.html", {"is_weekday": is_weekday, "machines": machines})
    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def delete_recharge(request, pk):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            try:
                recharge = Recharge.objects.get(pk=pk)
            
                if not recharge.complete:
                    permanent_transaction = Transaction(
                        user=recharge.user,
                        amount=recharge.amount,
                        transaction_type="cancellation",
                        username=recharge.username,
                        account_balance=recharge.user.userdetails.balance,
                        description="The recharge can not be verified!"
                    )
                    permanent_transaction.save()
                    recharge.delete()
        
                    messages.success(request, "Recharge successfully deleted.")
                    all_pending = Recharge.objects.filter(complete=False).order_by("created_at")
                    return render(request, "pending recharges.html", {"pending_recharges": all_pending})
                
                else:
                    messages.error(request, "This recharge is already effected.")
            except Recharge.DoesNotExist:
                messages.error(request, "Recharge is already deleted.")
        messages.error(request, "This section is reserved for admins.")

        all_products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": all_products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def delete_withdrawal(request, pk):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            withdral = Withdraw.objects.get(pk=pk)

            withdral.user.userdetails.balance += withdral.amount
            withdral.user.save()

            permanent_transaction = Transaction(
                user=withdral.user,
                amount=withdral.amount,
                transaction_type="cancellation",
                username=withdral.username,
                account_balance=withdral.user.userdetails.balance,
                description="The withdrawal can not be verified!"
            )
            permanent_transaction.save()
            withdral.delete()

            messages.success(request, "Withdrawal successfully deleted.")
            all_pending = Withdraw.objects.filter(complete=False).order_by("time_stamp")
            return render(request, "pending withdrawals.html", {"pending_recharges": all_pending})
        messages.error(request, "This section is reserved for admins.")

        all_products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": all_products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def edit_user(request, pk):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            user_profile = User.objects.get(pk=pk)
            todays_income = 0
            user_subscriptions = Subscription.objects.filter(user=user_profile)

            if request.method == "POST":
                operation = request.POST.get('operation')
                amount = int(request.POST.get('amount'))
                message = request.POST.get('message')
                
                transaction = Transaction(
                user=user_profile,
                username=user_profile.username,
                amount=amount,
                description=message,
                )
                
                if operation == 'add':
                    user_profile.userdetails.balance += amount
                    transaction.transaction_type = "performance_bonus"                     
                    messages.success(request, "Successfully added " + str(amount) + " to " + user_profile.username + "'s account.")
                                     
                elif operation == 'subtract':
                    transaction.transaction_type = "adjustment"
                    user_profile.userdetails.balance -= amount
                    messages.success(request, "Successfully added " + str(amount) + " to " + user_profile.username + "'s account.")
                
                user_profile.save()
                
                transaction.account_balance = user_profile.userdetails.balance
                transaction.save()
            
            if user_subscriptions.count() > 0:
                todays_income = sum([subscription.days_amount for subscription in user_subscriptions])
                
            total_recharges = sum([transaction.amount for transaction in Recharge.objects.filter(user=user_profile)])
            total_withdrawals = sum([transaction.amount for transaction in Withdraw.objects.filter(user=user_profile)])

            all_pending_withdrawals = Withdraw.objects.filter(complete=False, user=user_profile).order_by("time_stamp")
            all_complete_withdrawals = Withdraw.objects.filter(complete=True, user=user_profile).order_by("time_stamp")
            recharges_awaiting_authentication = Recharge.objects.filter(complete=False, user=user_profile).order_by("created_at")
            all_complete_recharges = Recharge.objects.filter(complete=True, user=user_profile).order_by("created_at")
            all_pending_recharges = PendingRecharge.objects.filter(user=user_profile)
            total_pending_withdrawal = sum([withdrawal.amount for withdrawal in all_pending_withdrawals])
            total_pending_recharge = sum([recharge.amount for recharge in recharges_awaiting_authentication])
            total_complete_withdrawal = sum([withdrawal.amount for withdrawal in Withdraw.objects.filter(complete=True, user=user_profile).order_by("time_stamp")])
            total_complete_recharge = sum([recharge.amount for recharge in Recharge.objects.filter(complete=True, user=user_profile).order_by("created_at")])
            all_transactions = Transaction.objects.filter(user=user_profile).order_by("-time_stamp")
            internal_activities = sum([transaction.amount for transaction in Transaction.objects.filter(Q(user=user_profile) & Q(transaction_type__contains="payment") | Q(transaction_type__contains="referral_bonus"))])
            
            return render(request, "admin edit user.html", {"total_recharges": total_recharges,
                                                       "total_withdrawals": total_withdrawals,
                                                       "todays_income": todays_income,
                                                       "user_profile": user_profile,
                                                       "all_pending_withdrawals": all_pending_withdrawals,
                                                       "recharges_awaiting_authentication": recharges_awaiting_authentication,
                                                       "all_pending_recharges": all_pending_recharges,
                                                       "total_pending_withdrawal": total_pending_withdrawal,
                                                       "total_pending_recharge": total_pending_recharge,
                                                       "total_complete_withdrawal": total_complete_withdrawal,
                                                       "total_complete_recharge": total_complete_recharge,
                                                       "all_complete_withdrawals": all_complete_withdrawals,
                                                       "all_complete_recharges": all_complete_recharges,
                                                       "all_transactions": all_transactions,
                                                       "internal_activities": internal_activities})
            
        messages.error(request, "This section is reserved for admins.")

        all_products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": all_products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
        
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def admin_edit_profile(request, pk):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            user_profile = User.objects.get(pk=pk)

            if request.method == "POST":
                username = request.POST["username"].lower().strip()
                email = request.POST["email"].lower().strip()
                first_name = request.POST["first-name"].lower().strip()
                last_name = request.POST["last-name"].lower().strip()
                password1 = request.POST["password1"]
                password2 = request.POST["password2"]
                phone = request.POST["phone"]
    
                if not (username and email and first_name and last_name and password1):
                    messages.error(request, "All fields required!")
                    return redirect("app:admin_edit_profile")
    
                if password1 == password2:
                    user_profile.username = username
                    user_profile.email = email
                    user_profile.first_name = first_name
                    user_profile.last_name = last_name
                    user_profile.userdetails.phone = phone
                    user_profile.set_password(password1)
                    user_profile.save()
    
                    messages.success(request, "Profile updated successfully.")
    
                    todays_income = 0
                    user_subscriptions = Subscription.objects.filter(user=user_profile)
                    if user_subscriptions.count() > 0:
                        todays_income = sum([subscription.days_amount for subscription in user_subscriptions])
                    total_recharges = sum([transaction.amount for transaction in Recharge.objects.filter(user=user)])
                    total_withdrawals = sum([transaction.amount for transaction in Withdraw.objects.filter(user=user)])
                    return render(request, "admin edit user.html", {"total_recharges": total_recharges,
                                                               "total_withdrawals": total_withdrawals,
                                                               "todays_income": todays_income})
                messages.error(request, "Password missmatch.")
                return redirect("app:admin_edit_profile")
            
            return render(request, "admin edit profile.html", {"user_profile": user_profile})
        messages.error(request, "This section is reserved for admins.")

        all_products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": all_products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
        
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def view_user_machines(request, pk):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            user_profile = User.objects.get(pk=pk)
            machines = Subscription.objects.filter(user=user_profile)
            current_time = default_now()
            is_weekday = current_time.weekday() < 5
            return render(request, "view user machines.html", {"machines": machines, "is_weekday": is_weekday})
        
        messages.error(request, "This section is reserved for admins.")

        all_products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": all_products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
        
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def pay_user_claim(request, pk):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            sub = Subscription.objects.get(pk=pk)
            accumulated_amount = sub.days_amount
    
            if accumulated_amount > 1:
                max_amount = sub.product.daily_earnings * sub.product.cycles

                if accumulated_amount <= max_amount:
                    sub.days_amount -= accumulated_amount
                    sub.user.userdetails.balance += accumulated_amount
                    sub.save()
                    sub.user.save()
    
                    transaction = Transaction(
                        user=sub.user,
                        username=sub.user.username,
                        transaction_type="reception",
                        amount=accumulated_amount,
                        description="Received " + str(accumulated_amount) + " after a claim on " +
                                    str(sub.product.name) + "'s daily earnings.",
                        account_balance=sub.user.userdetails.balance
                    )
                    transaction.save()
    
                    if sub.product.cycles < (sub.created_at - default_now()).days or accumulated_amount == max_amount:
                        sub.delete()
    
                    sub.user.userdetails.active_subscriptions = Subscription.objects.filter(user=sub.user).count()
                    sub.user.save()
    
                    messages.success(request, "Claim successfully deposited into your balance account.")
                else:
                    messages.success(request, "Claim rejected on account of abnormal accumulation. Please view " + sub.username + "'s machine accumulations.")
            else:
                messages.error(request, "Claim amount is smaller than the required minimum!")
                
            current_time = timezone.now()
            is_weekday = current_time.weekday() < 5
            machines = Subscription.objects.filter(user=sub.user)
    
            return render(request, "view user machines.html", {"is_weekday": is_weekday, "machines": machines})
            
        messages.error(request, "This section is reserved for admins.")

        all_products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": all_products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})

    messages.error(request, "Access restricted to signed in users!")
    return redirect("app:login")


def select_receiver_accoutn(request):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            selected_account = contact_in_use = None
            if request.method == "POST":
                pk = request.POST["select"]
                if pk:
                    selected_account = ReceiverAccount.objects.get(pk=int(pk))
                    try:
                        account = SelectedReceiverAccount.objects.get(pk=1)
                        account = selected_account
                        account.save()
                    except:                    
                        SelectedReceiverAccount(pk=1, account=selected_account).save()
                    messages.success(request, "Successfully selected contact")
                else:
                    messages.error(request, "Please select one contact")
            
            total_user_balances = sum([single_user.userdetails.balance for single_user in User.objects.all()])
            total_pending_withdrawals = sum([single_withdrawal.amount for single_withdrawal in Withdraw.objects.filter(complete=False)])
            total_recharges_awaiting_authentication = sum([single_recharge.amount for single_recharge in Recharge.objects.filter(complete=False)])
            total_pending_recharges = sum([single_recharge.amount for single_recharge in PendingRecharge.objects.all()])
            total_complete_recharges = sum([single_recharge.amount for single_recharge in Recharge.objects.filter(complete=True)])
            total_complete_withdrawals = sum([single_recharge.amount for single_recharge in Withdraw.objects.filter(complete=True)])

            products_count = Product.objects.all().count()
            vip_products_count = Product.objects.filter(vip_status=True).count()
            total_withdrawals_count = Withdraw.objects.all().count()
            total_recharge_count = Recharge.objects.all().count()
            complete_withdrawal_count = Withdraw.objects.filter(complete=True).count()
            complete_recharge_count = Recharge.objects.filter(complete=True).count()

            subscribed_users = {subscription.user for subscription in Subscription.objects.all()}

            # Aggregating Withdrawals by month and year
            monthly_withdrawals = Withdraw.objects.annotate(
                month=TruncMonth('time_stamp')
            ).values('month').annotate(
                total_amount=Sum('amount'),
                total_count=Count('id')
            ).order_by('month')

            # Aggregating Recharges by month and year
            monthly_recharges = Recharge.objects.annotate(
                month=TruncMonth('created_at')
            ).values('month').annotate(
                total_amount=Sum('amount'),
                total_count=Count('id')
            ).order_by('month')

            # Create a default dictionary to store combined data
            combined_data = defaultdict(lambda: {'withdrawals': 0, 'recharges': 0})

            # Populate the dictionary with data
            for entry in monthly_withdrawals:
                month = entry['month'].strftime("%b %Y")  # Format the month
                combined_data[month]['withdrawals'] = entry['total_amount']

            for entry in monthly_recharges:
                month = entry['month'].strftime("%b %Y")  # Format the month
                combined_data[month]['recharges'] += entry['total_amount']

            # Convert to a list of tuples for easy iteration in the template
            combined_data_list = list(combined_data.items())

            selected_contact = contact_in_use = None

            try:
                selected_contact = SelectedReceiverAccount.objects.get(pk=1).account
            except:
                current_time = default_now().time()
                accounts = ReceiverAccount.objects.filter(Q(start_time__lte=current_time))
                if accounts.count() > 0:
                    contact_in_use = accounts.order_by("start_time")[0]

            mpesa_contacts = ReceiverAccount.objects.all()

            return render(request, "admin index.html", {
                "total_user_balances" : total_user_balances,
                "total_pending_withdrawals": total_pending_withdrawals,
                "total_recharges_awaiting_authentication": total_recharges_awaiting_authentication,
                "total_pending_recharges": total_pending_recharges,
                "total_complete_recharges": total_complete_recharges,
                "total_complete_withdrawals": total_complete_withdrawals,
                "products_count": products_count,
                "vip_products_count": vip_products_count,
                "total_withdrawals_count": total_withdrawals_count,
                "total_recharge_count": total_recharge_count,
                "complete_withdrawal_count": complete_withdrawal_count,
                "complete_recharge_count": complete_recharge_count,
                "combined_data": combined_data_list,
                "subscribed_users": subscribed_users,
                "selected_contact": selected_account,
                "contact_in_use": contact_in_use,
                "mpesa_contacts": mpesa_contacts,
            })
            
        messages.error(request, "This section is reserved for admins.")

        all_products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": all_products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
        
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")

def delete_selected_contact(request):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            selected_contact = SelectedReceiverAccount.objects.get(pk=1)
            selected_contact.delete()

            messages.success(request, "Successfully deselected contact")
            
            total_user_balances = sum([single_user.userdetails.balance for single_user in User.objects.all()])
            total_pending_withdrawals = sum([single_withdrawal.amount for single_withdrawal in Withdraw.objects.filter(complete=False)])
            total_recharges_awaiting_authentication = sum([single_recharge.amount for single_recharge in Recharge.objects.filter(complete=False)])
            total_pending_recharges = sum([single_recharge.amount for single_recharge in PendingRecharge.objects.all()])
            total_complete_recharges = sum([single_recharge.amount for single_recharge in Recharge.objects.filter(complete=True)])
            total_complete_withdrawals = sum([single_recharge.amount for single_recharge in Withdraw.objects.filter(complete=True)])

            products_count = Product.objects.all().count()
            vip_products_count = Product.objects.filter(vip_status=True).count()
            total_withdrawals_count = Withdraw.objects.all().count()
            total_recharge_count = Recharge.objects.all().count()
            complete_withdrawal_count = Withdraw.objects.filter(complete=True).count()
            complete_recharge_count = Recharge.objects.filter(complete=True).count()

            subscribed_users = {subscription.user for subscription in Subscription.objects.all()}

            # Aggregating Withdrawals by month and year
            monthly_withdrawals = Withdraw.objects.annotate(
                month=TruncMonth('time_stamp')
            ).values('month').annotate(
                total_amount=Sum('amount'),
                total_count=Count('id')
            ).order_by('month')

            # Aggregating Recharges by month and year
            monthly_recharges = Recharge.objects.annotate(
                month=TruncMonth('created_at')
            ).values('month').annotate(
                total_amount=Sum('amount'),
                total_count=Count('id')
            ).order_by('month')

            # Create a default dictionary to store combined data
            combined_data = defaultdict(lambda: {'withdrawals': 0, 'recharges': 0})

            # Populate the dictionary with data
            for entry in monthly_withdrawals:
                month = entry['month'].strftime("%b %Y")  # Format the month
                combined_data[month]['withdrawals'] = entry['total_amount']

            for entry in monthly_recharges:
                month = entry['month'].strftime("%b %Y")  # Format the month
                combined_data[month]['recharges'] += entry['total_amount']

            # Convert to a list of tuples for easy iteration in the template
            combined_data_list = list(combined_data.items())

            selected_contact = contact_in_use = None

            try:
                selected_contact = SelectedReceiverAccount.objects.get(pk=1).account
            except:
                current_time = default_now().time()
                accounts = ReceiverAccount.objects.filter(Q(start_time__lte=current_time))
                if accounts.count() > 0:
                    contact_in_use = accounts.order_by("start_time")[0]

            mpesa_contacts = ReceiverAccount.objects.all()

            return render(request, "admin index.html", {
                "total_user_balances" : total_user_balances,
                "total_pending_withdrawals": total_pending_withdrawals,
                "total_recharges_awaiting_authentication": total_recharges_awaiting_authentication,
                "total_pending_recharges": total_pending_recharges,
                "total_complete_recharges": total_complete_recharges,
                "total_complete_withdrawals": total_complete_withdrawals,
                "products_count": products_count,
                "vip_products_count": vip_products_count,
                "total_withdrawals_count": total_withdrawals_count,
                "total_recharge_count": total_recharge_count,
                "complete_withdrawal_count": complete_withdrawal_count,
                "complete_recharge_count": complete_recharge_count,
                "combined_data": combined_data_list,
                "subscribed_users": subscribed_users,
                "selected_contact": selected_contact,
                "contact_in_use": contact_in_use,
                "mpesa_contacts": mpesa_contacts,
            })
        
        messages.error(request, "This section is reserved for admins.")

        all_products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": all_products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
        
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def help(request):
    machines = Product.objects.all().order_by("name")
    return render(request, "help.html", {"machines": machines})


def all_users(request):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            all_users_sorted = UserDetails.objects.select_related('user').order_by('-active_subscriptions', 'username')
            return render(request, "all users.html", {"all_users": all_users_sorted})
        messages.error(request, "This section is reserved for admins.")

        products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})
    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def view_team(request, user_pk):
    user = request.user
    if user.is_authenticated:
        if user.is_superuser:
            customer = User.objects.get(pk=user_pk)
            customer_team = Referral.objects.filter(parent=customer).order_by("-first_product").order_by("-created_at")
            return render(request, "view team.html", {"referrals": customer_team, "customer": customer})

        messages.error(request, "This section is reserved for admins.")

        products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})

    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")


def all_machines(request):
    originally_priced = Product.objects.filter(discounted=False).order_by("name")
    discounted = Product.objects.filter(discounted=True).order_by("name")
    return render(request, "earning table.html", {"discounted_machines": discounted, "machines": originally_priced})


def missing_recharges(request):
    user = request.user

    if user.is_authenticated:
        if user.is_superuser:
            transactions = Transaction.objects.filter(transaction_type="recharge")
            missing_recharges = []
            total_missing_recharge = 0
            time_threshold = timedelta(minutes=30)
            
            for transaction in transactions:
                try:
                    start_time = transaction.time_stamp - time_threshold
                    end_time = transaction.time_stamp + time_threshold
                
                    results = Recharge.objects.filter(
                        user=transaction.user,
                        amount=transaction.amount,
                        created_at__range=(start_time, end_time),
                    )

                    if results.count() == 0:
                        missing_recharges.append(transaction)
                        total_missing_recharge += transaction.amount
                        
                    else:
                        pass
                except Recharge.DoesNotExist:
                    pass

            return render(request, "missing recharges.html", {"missing_recharges": missing_recharges, "total_missing_recharge": total_missing_recharge, "total_recharge_transactions": transactions.count()})
        messages.error(request, "This section is reserved for admins.")

        products = Product.objects.filter(discounted=False).order_by("name")
        discounted_products = Product.objects.filter(discounted=True).order_by("name")
        news_feeds = NewsFeed.objects.all()
        return render(request, "index.html", {"products": products,
                                              "discounted_products": discounted_products,
                                              "news_feeds": news_feeds})

    messages.error(request, "Access reserved to authenticated admin!")
    return redirect("app:login")
