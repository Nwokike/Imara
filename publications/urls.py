from django.urls import path
from . import views

app_name = 'publications'

urlpatterns = [
    path('', views.ArticleListView.as_view(), name='article_list'),
    path('<slug:slug>/', views.ArticleDetailView.as_view(), name='article_detail'),
    path('<slug:slug>/comment/', views.SubmitCommentView.as_view(), name='submit_comment'),
]

