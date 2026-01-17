from django.urls import path
from . import views
from .meta_views import MetaWebhookView

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('report/', views.ReportFormView.as_view(), name='report_form'),
    path('result/', views.ResultView.as_view(), name='result'),
    path('offline/', views.offline_view, name='offline'),
    path('serviceworker.js', views.serviceworker_view, name='serviceworker'),
    path('webhook/telegram/', views.TelegramWebhookView.as_view(), name='telegram_webhook'),
    path('webhook/meta/', MetaWebhookView.as_view(), name='meta_webhook'),
    path('health/', views.health_check, name='health_check'),
    path('ping/', views.keep_alive, name='keep_alive'),
    # Partner pages
    path('partner/', views.PartnerView.as_view(), name='partner'),
    path('consent/', views.consent_view, name='consent'),
    path('policies/', views.policies_view, name='policies'),
    path('contact/', views.ContactView.as_view(), name='contact'),
]
