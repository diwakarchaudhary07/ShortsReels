from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


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


class Reel(models.Model):
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="reels",
	)
	video_file = models.FileField(upload_to="reels/")
	caption = models.CharField(max_length=300, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ("-created_at",)

	def __str__(self):
		return self.caption or f"Reel by {self.user.username}"
