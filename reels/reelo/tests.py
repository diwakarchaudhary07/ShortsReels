from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from PIL import Image

from .models import Post, Profile, Reel, Song


class CustomUserTests(TestCase):
	def test_user_profile_fields_and_authentication(self):
		custom_user = get_user_model().objects.create_user(
			username="profile-user",
			password="test-password",
			full_name="Profile User",
			email="profile@example.com",
			mobile_no="5551234567",
			dob=date(1995, 4, 12),
			address="123 Example Street",
			gender="F",
		)

		self.assertEqual(custom_user.full_name, "Profile User")
		self.assertEqual(custom_user.email, "profile@example.com")
		self.assertEqual(custom_user.mobile_no, "5551234567")
		self.assertEqual(custom_user.dob, date(1995, 4, 12))
		self.assertEqual(custom_user.address, "123 Example Street")
		self.assertEqual(custom_user.gender, "F")
		self.assertTrue(custom_user.check_password("test-password"))


class ProfileTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username="creator",
			password="test-password",
			full_name="Shorts Creator",
		)

	def test_owner_can_save_profile(self):
		self.client.force_login(self.user)
		response = self.client.post(
			"/profile/",
			{
				"bio": "Making short videos",
				"website": "https://example.com",
				"location": "London",
				"date_of_birth": "1998-06-15",
				"is_private": "on",
			},
		)

		self.assertRedirects(response, "/profile/")
		profile = self.user.profile
		self.assertEqual(profile.bio, "Making short videos")
		self.assertEqual(profile.website, "https://example.com")
		self.assertEqual(profile.location, "London")
		self.assertEqual(profile.date_of_birth, date(1998, 6, 15))
		self.assertTrue(profile.is_private)

	def test_private_profile_hides_details_from_visitors(self):
		Profile.objects.create(
			user=self.user,
			bio="Only for me",
			is_private=True,
		)

		response = self.client.get("/profile/creator/")

		self.assertContains(response, "This account is private")
		self.assertNotContains(response, "Only for me")


class ReelNavigationTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username="reel-creator",
			password="test-password",
			full_name="Reel Creator",
		)
		self.client.force_login(self.user)

	def test_navigation_destinations_render_and_mark_active_page(self):
		for route_name in (
			"home",
			"reels_feed",
			"messages",
			"chat",
			"search",
			"profile",
			"create_reel",
			"create_post",
			"notifications",
		):
			with self.subTest(route_name=route_name):
				response = self.client.get(reverse(route_name))
				self.assertEqual(response.status_code, 200)

		feed_response = self.client.get(reverse("reels_feed"))
		self.assertContains(feed_response, 'href="/reels/"')
		self.assertContains(feed_response, 'aria-current="page"')

	def test_uploaded_reel_is_saved_and_shown_in_feed(self):
		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(
					reverse("create_reel"),
					{
						"caption": "First reel",
						"video_file": SimpleUploadedFile(
							"first-reel.mp4", b"video-data", content_type="video/mp4"
						),
					},
				)
				self.assertRedirects(response, reverse("reels_feed"))
				reel = Reel.objects.get(user=self.user)
				self.assertEqual(reel.caption, "First reel")
				self.assertTrue(Path(reel.video_file.path).is_file())

				feed_response = self.client.get(reverse("reels_feed"))
				self.assertContains(feed_response, "First reel")
				self.assertContains(feed_response, 'class="reel-video"')
				self.assertContains(feed_response, reel.video_file.url)


class PostCreationTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username="post-creator",
			password="test-password",
			full_name="Post Creator",
		)
		self.client.force_login(self.user)

	def make_image(self, name, color):
		image_data = BytesIO()
		Image.new("RGB", (8, 8), color).save(image_data, format="JPEG")
		return SimpleUploadedFile(name, image_data.getvalue(), content_type="image/jpeg")

	def test_create_post_renders_photo_and_editor_controls(self):
		response = self.client.get(reverse("create_post"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Select photos")
		self.assertContains(response, "Audio")
		self.assertContains(response, "Overlay")
		self.assertContains(response, "Ratio")

	def test_uploaded_photos_caption_and_song_are_saved(self):
		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				song = Song.objects.create(
					title="Evening",
					artist="Example Artist",
					audio_file=SimpleUploadedFile(
						"evening.mp3", b"audio-data", content_type="audio/mpeg"
					),
				)
				response = self.client.post(
					reverse("create_post"),
					{
						"caption": "A good day",
						"song_id": str(song.pk),
						"images": [
							self.make_image("first.jpg", "red"),
							self.make_image("second.jpg", "blue"),
						],
					},
				)

				post = Post.objects.get(user=self.user)
				self.assertRedirects(response, reverse("profile"))
				self.assertEqual(post.caption, "A good day")
				self.assertEqual(post.song, song)
				self.assertEqual(post.images.count(), 2)
				self.assertEqual(
					list(post.images.values_list("position", flat=True)), [0, 1]
				)
				for post_image in post.images.all():
					self.assertTrue(Path(post_image.image.path).is_file())

	def test_invalid_image_is_rejected_without_creating_post(self):
		response = self.client.post(
			reverse("create_post"),
			{
				"images": SimpleUploadedFile(
					"not-an-image.jpg", b"not image data", content_type="image/jpeg"
				),
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "not a valid image")
		self.assertFalse(Post.objects.filter(user=self.user).exists())
