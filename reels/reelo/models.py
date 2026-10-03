from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


def story_expiry():
	return timezone.now() + timedelta(hours=24)


class User(AbstractUser):
	REQUIRED_FIELDS = ["email", "full_name"]

	class Gender(models.TextChoices):
		MALE = "M", "Male"
		FEMALE = "F", "Female"
		OTHER = "O", "Other"
		PREFER_NOT_TO_SAY = "N", "Prefer not to say"

	full_name = models.CharField(max_length=255)
	email = models.EmailField(blank=True)
	mobile_no = models.CharField(max_length=20, blank=True)
	dob = models.DateField(null=True, blank=True)
	address = models.TextField(blank=True)
	profile_image = models.ImageField(
		upload_to="profiles/", blank=True, null=True
	)
	gender = models.CharField(
		max_length=1, choices=Gender.choices, blank=True
	)

	def __str__(self):
		return self.full_name or self.username


class Profile(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="profile",
	)
	profile_image = models.ImageField(
		upload_to="profiles/", blank=True, null=True
	)
	bio = models.TextField(max_length=500, blank=True)
	website = models.URLField(blank=True)
	location = models.CharField(max_length=120, blank=True)
	date_of_birth = models.DateField(blank=True, null=True)
	is_private = models.BooleanField(default=False)
	followers_count = models.PositiveIntegerField(default=0)
	following_count = models.PositiveIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.user.username}'s profile"


class Follow(models.Model):
	follower = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="following",
	)
	following = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="followers",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(
				fields=("follower", "following"), name="unique_user_follow"
			),
			models.CheckConstraint(
				condition=~models.Q(follower=models.F("following")),
				name="prevent_self_follow",
			),
		]
		ordering = ("-created_at",)

	def __str__(self):
		return f"{self.follower} follows {self.following}"


class Reel(models.Model):
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="reels",
	)
	video_file = models.FileField(upload_to="reels/")
	thumbnail = models.ImageField(
		upload_to="reels/thumbnails/", blank=True, null=True
	)
	caption = models.CharField(max_length=2200, blank=True)
	song = models.ForeignKey(
		"Song",
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="reels",
	)
	location = models.CharField(max_length=255, blank=True)
	views_count = models.PositiveBigIntegerField(default=0)
	likes_count = models.PositiveIntegerField(default=0)
	comments_count = models.PositiveIntegerField(default=0)
	shares_count = models.PositiveIntegerField(default=0)
	saves_count = models.PositiveIntegerField(default=0)
	is_archived = models.BooleanField(default=False)
	is_comments_enabled = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ("-created_at",)

	def __str__(self):
		return self.caption or f"Reel by {self.user.username}"


class Song(models.Model):
	title = models.CharField(max_length=255)
	artist = models.CharField(max_length=255, blank=True)
	cover_url = models.URLField(blank=True)
	preview_url = models.URLField(blank=True)
	duration = models.PositiveIntegerField(default=0)
	external_id = models.CharField(
		max_length=255,
		unique=True,
		null=True,
		blank=True,
	)
	provider = models.CharField(max_length=64, default="reelo")
	attribution = models.CharField(max_length=255, blank=True)
	attribution_url = models.URLField(blank=True)
	rights_cleared = models.BooleanField(default=False)
	audio_file = models.FileField(
		upload_to="songs/",
		blank=True,
		null=True,
		help_text="Only upload audio Reelo has explicit rights to use.",
	)
	is_trending = models.BooleanField(default=False)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("title", "artist")

	def __str__(self):
		return f"{self.title} - {self.artist}" if self.artist else self.title


class Story(models.Model):
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="stories",
	)
	image = models.ImageField(upload_to="stories/images/", blank=True, null=True)
	video = models.FileField(upload_to="stories/videos/", blank=True, null=True)
	caption = models.CharField(max_length=2200, blank=True)
	song = models.ForeignKey(
		Song,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="stories",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	expires_at = models.DateTimeField(default=story_expiry, db_index=True)

	class Meta:
		ordering = ("-created_at",)
		constraints = [
			models.CheckConstraint(
				condition=(
					models.Q(image__gt="", video__in=("", None))
					| models.Q(video__gt="", image__in=("", None))
				),
				name="story_has_exactly_one_media",
			),
		]

	def __str__(self):
		return f"Story by {self.user.username}"

	@property
	def is_expired(self):
		return self.expires_at <= timezone.now()


class Post(models.Model):
	class Visibility(models.TextChoices):
		PUBLIC = "public", "Public"
		FOLLOWERS = "followers", "Followers"
		PRIVATE = "private", "Private"

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="posts",
	)
	caption = models.TextField(max_length=2200, blank=True)
	video = models.FileField(upload_to="posts/videos/", blank=True)
	location = models.CharField(max_length=255, blank=True)
	visibility = models.CharField(
		max_length=20,
		choices=Visibility.choices,
		default=Visibility.PUBLIC,
	)
	song = models.ForeignKey(
		Song,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="posts",
	)
	likes = models.ManyToManyField(
		settings.AUTH_USER_MODEL,
		related_name="liked_posts",
		blank=True,
	)
	saved_by = models.ManyToManyField(
		settings.AUTH_USER_MODEL,
		related_name="saved_posts",
		blank=True,
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("-created_at",)

	def __str__(self):
		return f"Post by {self.user.username}"

	@property
	def like_count(self):
		return self.likes.count()

	@property
	def save_count(self):
		return self.saved_by.count()


class PostImage(models.Model):
	post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
	image = models.ImageField(upload_to="posts/")
	position = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ("position", "pk")

	def __str__(self):
		return f"Image {self.position + 1} for {self.post}"
