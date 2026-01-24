from django.urls import path
from django.views.generic import RedirectView
from django.contrib.auth.views import LogoutView
from . import views

app_name = 'partners'

urlpatterns = [
    # Auth
    path('login/', views.PartnerLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='partners:login'), name='logout'),
    path('invite/<str:token>/', views.AcceptInviteView.as_view(), name='accept_invite'),
    
    # Dashboard & Cases
    path('dashboard/', views.PartnerDashboardView.as_view(), name='dashboard'),
    path('pool/', views.CasePoolView.as_view(), name='pool'),
    path('my-cases/', views.MyCasesView.as_view(), name='my_cases'),
    path('claim/<int:case_id>/', views.ClaimCaseView.as_view(), name='claim_case'),
    path('case/<int:case_id>/', views.PartnerCaseDetailView.as_view(), name='case_detail'),
    path('settings/', views.PartnerSettingsView.as_view(), name='settings'),
    
    # Team Management
    path('team/', views.TeamListView.as_view(), name='team'),
    path('team/invite/', views.InviteTeamMemberView.as_view(), name='invite_member'),
    path('team/update/<int:member_id>/', views.UpdateMemberRoleView.as_view(), name='update_role'),
    path('team/remove/<int:member_id>/', views.RemoveMemberView.as_view(), name='remove_member'),
    path('team/cancel-invite/<int:invite_id>/', views.CancelInviteView.as_view(), name='cancel_invite'),
    
    # Legacy
    path('apply/', RedirectView.as_view(pattern_name='partner', permanent=False), name='apply'),
]


