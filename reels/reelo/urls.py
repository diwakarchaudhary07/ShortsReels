
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from . import views


urlpatterns = [
	path("", views.home, name="home"),
	path("create/", views.create_reel, name="create_reel"),
	path("stories/", views.stories, name="stories"),
	path("stories/create/", views.create_story, name="create_story"),
	path("posts/create/", views.create_post, name="create_post"),
	path("posts/<int:post_id>/", views.post_detail, name="post_detail"),
	path(
		"posts/<int:post_id>/like/",
		views.toggle_post_like,
		name="toggle_post_like",
	),
	path(
		"posts/<int:post_id>/save/",
		views.toggle_post_save,
		name="toggle_post_save",
	),
	path("reels/", views.reels_feed, name="reels_feed"),
	path("reels/<int:reel_id>/", views.reel_detail, name="reel_detail"),
	path("notifications/", views.notifications, name="notifications"),
	path("messages/", views.messages_inbox, name="messages"),
	path("chat/", views.chat, name="chat"),
	path("profile/", views.profile, name="profile"),
	path("profile/edit/", views.edit_profile, name="edit_profile"),
	path("profile/<str:username>/", views.profile_detail, name="profile_detail"),
	path(
		"profile/<str:username>/follow/",
		views.toggle_follow,
		name="toggle_follow",
	),
	path("search/", views.search, name="search"),
	path("api/music/search/", views.music_search, name="music_search"),
	path("api/music/trending/", views.music_trending, name="music_trending"),
	path(
		"api/music/<int:song_id>/",
		views.music_song_detail,
		name="music_song_detail",
	),
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
