from django.urls import path, re_path
from . import views
from . import reportviews
from .auth import CustomAuthentication
from django.contrib.auth import views as auth_views

urlpatterns = [
    re_path(r'^$', views.home, name='home'),
    path('login/', auth_views.LoginView.as_view(authentication_form=CustomAuthentication, template_name='login.html'), name='login'),
    path('logout/', views.logout_student, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('resend_signup_email/', views.resend_signup_email, name='resend_signup_email'),
    path('change_email/', views.change_email, name='change_email'),
    re_path(r'^api/(?P<action>[0-9a-zA-Z_]+)$', views.api, name='api'),
    re_path(r'^assignment_report/(?P<assignment_id>[0-9a-zA-Z_]+)$', views.assignment_report, name='assignment_report'),
    re_path(r'^assignment_aggregate_report/(?P<assignment_id>[0-9a-zA-Z_]+)$', views.assignment_aggregate_report, name='assignment_aggregate_report'),
    re_path(r'^moss_submit/(?P<assignment_id>[0-9a-zA-Z_]+)$', views.moss_submit, name='moss_submit'),
    re_path(r'^moss_view/(?P<assignment_id>[0-9a-zA-Z_]+)$', views.moss_view, name='moss_view'),
    re_path(r'^course/(?P<course_id>[0-9]+)$', views.course, name='course'),
    re_path(r'^course/(?P<course_id>[0-9]+)/(?P<assignment_id>[0-9]+)$', views.course, name='course'),
    path('download/', views.download),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    re_path(r'^reset/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('password/', views.change_password, name='change_password'),
    path('account_activation_sent/', views.account_activation_sent, name='account_activation_sent'),
    re_path(r'^activate/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$', views.activate, name='activate'),
    re_path(r'^loginas/(?P<student_id>[0-9a-zA-Z_]+)$$', views.loginas, name='loginas'),
    path('request_extension/', views.request_extension),
    re_path(r'^course_students_stat/(?P<course_id>[0-9a-zA-Z_]+)$', reportviews.course_students_stat, name='course_students_stat'),
]