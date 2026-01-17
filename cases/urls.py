from django.urls import path
from . import views

app_name = 'cases'

urlpatterns = [
    path('<uuid:case_id>/', views.CaseDetailView.as_view(), name='case_detail'),
]
