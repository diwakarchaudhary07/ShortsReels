
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from . import views


urlpatterns = [
	path("", views.home, name="home"),
	path("create/", views.create_reel, name="create_reel"),
	path("reels/", views.reels_feed, name="reels_feed"),
	path("notifications/", views.notifications, name="notifications"),
	path("messages/", views.messages_inbox, name="messages"),
	path("chat/", views.chat, name="chat"),
	path("profile/", views.profile, name="profile"),
	path("profile/<str:username>/", views.profile_detail, name="profile_detail"),
	path("search/", views.search, name="search"),
	path(
		"login/",
		LoginView.as_view(
			template_name="registration/login.html",
			authentication_form=views.BootstrapAuthenticationForm,
		),
		name="login",
	),
	path("logout/", LogoutView.as_view(), name="logout"),
]
