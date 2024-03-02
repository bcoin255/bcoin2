from django.urls import path, include, re_path
from . import views

app_name = "app"

admin_urls = [
    path("add_products/", views.add_products, name="add_products"),
    path("pending_withdrawals/", views.pending_withdrawals, name="pending_withdrawals"),
    path("pending_recharges/", views.pending_recharges, name="pending_recharges"),
    path("complete_transactions/", views.complete_transactions, name="complete_transactions"),
    path("update_recharge/<int:pk>/", views.update_recharge, name="update_recharge"),
    path("delete_recharge/<int:pk>/", views.delete_recharge, name="delete_recharge"),
    path("update_withdrawal/<int:pk>/", views.update_withdrawal, name="update_withdrawal"),
    path("increase_like/", views.increase_like, name="increase_likes"),
    path("edit_user/<int:pk>/", views.edit_user, name="edit_user"),  # For admin access
    path("edit_profile/<int:pk>/", views.admin_edit_profile, name="admin_edit_profile"),
    path("view_user_machines/<int:pk>/", views.view_user_machines, name="view_user_machines"),
    path("pay_user_claim/<int:pk>/", views.pay_user_claim, name="pay_user_claim"),
    path("delete_withdrawal/<int:pk>/", views.delete_withdrawal, name="delete_withdrawal"),
    path("delete_selected_contact/", views.delete_selected_contact, name="delete_selected_contact"),
    path("select_receiver_account/",views.select_receiver_accoutn, name="select_receiver_account"),
    path('all_users/', views.all_users, name="all_users"),
    path("view_team/<int:user_pk>/", views.view_team, name="view_team"),
    path("missing_recharges/", views.missing_recharges, name="missing_recharges"),
]

urlpatterns = [
    path("", views.index, name="index"),
    path('product/<int:id>/', views.product, name="product"),
    path("login/", views.user_login, name="login"),
    path("register/", views.user_registration, name="register"),
    path("logout/", views.user_logout, name="logout"),
    path("adm/", include(admin_urls)),
    path("initiate_recharge/", views.initiate_recharge, name="initiate_recharge"),
    path("complete_recharge/<int:pk>/", views.complete_recharge, name="complete_recharge"),
    path("withdraw/", views.withdraw, name="withdraw"),
    path("account_details/", views.account_details, name="account_details"),
    path("my_wallet/", views.my_wallet, name="my_wallet"),
    path("my_profile/", views.my_profile, name="my_profile"),
    path("my_team/", views.my_team, name="my_team"),
    path("products/", views.products, name="products"),
    path("news_feeds/<int:pk>/", views.news_feeds, name="news_feeds"),
    path("contact/", views.contact, name="contact"),
    re_path(r'^join/(?P<referral_code>[A-Za-z0-9#\$=&]+)/$', views.join, name='join'),
    path('invite/', views.invite, name="invite"),
    path("my_machines/", views.my_machines, name="my_machines"),
    path("my_machines/claim/<int:pk>/", views.claim, name="claim"),
    path("buy_product/", views.buy_product, name="buy_product"),
    path("buy_product/<int:pk>/", views.buy_product, name="buy_product"),
    path("edit_profile/", views.edit_profile, name="edit_profile"),
    path("help/", views.help, name="help"),
    path("all_machines/", views.all_machines, name="all_machines"),
]
