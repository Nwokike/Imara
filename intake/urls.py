from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('report/', views.ReportFormView.as_view(), name='report_form'),
    path('result/', views.ResultView.as_view(), name='result'),
    path('webhook/telegram/', views.TelegramWebhookView.as_view(), name='telegram_webhook'),
    path('health/', views.health_check, name='health_check'),
    path('ping/', views.keep_alive, name='keep_alive'),
]
