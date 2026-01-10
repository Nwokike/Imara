from django.urls import path
from . import views

app_name = 'partners'

urlpatterns = [
    path('dashboard/', views.PartnerDashboardView.as_view(), name='dashboard'),
    path('pool/', views.CasePoolView.as_view(), name='pool'),
    path('claim/<int:case_id>/', views.ClaimCaseView.as_view(), name='claim_case'),
    path('apply/', views.PartnerApplicationView.as_view(), name='apply'),
]
