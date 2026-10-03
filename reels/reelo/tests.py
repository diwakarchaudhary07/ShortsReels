from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from PIL import Image

from .models import Follow, Post, PostImage, Profile, Reel, Song, Story
from .music_catalog import AppleMusicCatalog


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

	def test_profile_page_is_read_only_and_links_to_edit(self):
		self.client.force_login(self.user)
		response = self.client.get(reverse("profile"))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "creator")
		self.assertContains(response, reverse("edit_profile"))
		self.assertContains(response, "Share Profile")
		self.assertContains(response, "http://testserver/profile/")
		self.assertContains(response, 'data-profile-tab="post"')
		self.assertContains(response, 'data-profile-tab="reel"')
		self.assertNotContains(response, 'name="bio"')
		self.assertContains(response, "No posts or reels yet")

	def test_owner_can_edit_profile_and_username(self):
		self.client.force_login(self.user)
		response = self.client.post(
			reverse("edit_profile"),
			{
				"full_name": "Updated Creator",
				"username": "updated-creator",
				"bio": "Making short videos",
				"website": "https://example.com",
				"location": "London",
				"date_of_birth": "1998-06-15",
				"is_private": "on",
			},
		)

		self.assertRedirects(response, reverse("profile"))
		self.user.refresh_from_db()
		self.assertEqual(self.user.full_name, "Updated Creator")
		self.assertEqual(self.user.username, "updated-creator")
		profile = self.user.profile
		self.assertEqual(profile.bio, "Making short videos")
		self.assertEqual(profile.website, "https://example.com")
		self.assertEqual(profile.location, "London")
		self.assertEqual(profile.date_of_birth, date(1998, 6, 15))
		self.assertTrue(profile.is_private)
		updated_profile = self.client.get(reverse("profile"))
		self.assertContains(updated_profile, "updated-creator")
		self.assertContains(updated_profile, "Updated Creator")
		self.assertContains(updated_profile, "Making short videos")
		self.assertNotContains(updated_profile, 'name="bio"')

	def test_edit_profile_requires_authentication(self):
		response = self.client.get(reverse("edit_profile"))

		self.assertRedirects(
			response, f"{reverse('login')}?next={reverse('edit_profile')}"
		)

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

	def make_thumbnail(self):
		image_data = BytesIO()
		Image.new("RGB", (8, 8), "orange").save(image_data, format="JPEG")
		return SimpleUploadedFile(
			"reel-cover.jpg", image_data.getvalue(), content_type="image/jpeg"
		)

	def test_navigation_destinations_render_and_mark_active_page(self):
		for route_name in (
			"home",
			"reels_feed",
			"messages",
			"chat",
			"search",
			"profile",
			"edit_profile",
			"create_reel",
			"create_post",
			"stories",
			"create_story",
			"notifications",
		):
			with self.subTest(route_name=route_name):
				response = self.client.get(reverse(route_name))
				self.assertEqual(response.status_code, 200)

		feed_response = self.client.get(reverse("reels_feed"))
		self.assertContains(feed_response, 'href="/reels/"')
		self.assertContains(feed_response, 'aria-current="page"')
		reel_form_response = self.client.get(reverse("create_reel"))
		self.assertContains(reel_form_response, "Record with camera")
		self.assertContains(reel_form_response, 'data-camera-modes="video"')

	def test_uploaded_reel_is_saved_and_shown_in_feed(self):
		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				song = Song.objects.create(
					title="Summer tune",
					audio_file=SimpleUploadedFile(
						"summer.mp3", b"audio-data", content_type="audio/mpeg"
					),
				)
				response = self.client.post(
					reverse("create_reel"),
					{
						"caption": "First reel with a longer caption",
						"song": str(song.pk),
						"location": "London",
						"thumbnail": self.make_thumbnail(),
						"video_file": SimpleUploadedFile(
							"first-reel.mp4", b"video-data", content_type="video/mp4"
						),
					},
				)
				self.assertRedirects(response, reverse("reels_feed"))
				reel = Reel.objects.get(user=self.user)
				self.assertEqual(reel.caption, "First reel with a longer caption")
				self.assertEqual(reel.song, song)
				self.assertEqual(reel.location, "London")
				self.assertTrue(Path(reel.video_file.path).is_file())
				self.assertTrue(Path(reel.thumbnail.path).is_file())
				reel.likes_count = 3
				reel.shares_count = 2
				reel.save(update_fields=("likes_count", "shares_count"))

				feed_response = self.client.get(reverse("reels_feed"))
				self.assertContains(feed_response, "First reel with a longer caption")
				self.assertContains(feed_response, "London")
				self.assertContains(feed_response, "Summer tune")
				self.assertContains(feed_response, 'reel-action-count">3</span>')
				self.assertContains(feed_response, 'class="reel-video"')
				self.assertContains(feed_response, reel.video_file.url)
				self.assertContains(feed_response, reel.thumbnail.url)

	def test_archived_reels_are_hidden_from_feed(self):
		Reel.objects.create(
			user=self.user,
			video_file="reels/archived.mp4",
			caption="Archived moment",
			is_archived=True,
		)

		response = self.client.get(reverse("reels_feed"))

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, "Archived moment")


class ProfileContentTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username="profile-content-user",
			password="test-password",
			full_name="Profile Content User",
		)
		self.client.force_login(self.user)

	def make_image(self):
		image_data = BytesIO()
		Image.new("RGB", (8, 8), "orange").save(image_data, format="JPEG")
		return SimpleUploadedFile(
			"profile-post.jpg", image_data.getvalue(), content_type="image/jpeg"
		)

	def test_profile_shows_posts_and_reels_newest_first_with_detail_links(self):
		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				post = Post.objects.create(user=self.user, caption="Older post")
				post_image = PostImage.objects.create(
					post=post, image=self.make_image()
				)
				reel = Reel.objects.create(
					user=self.user,
					video_file=SimpleUploadedFile(
						"profile-reel.mp4", b"video-data", content_type="video/mp4"
					),
					caption="Newest reel",
				)
				Post.objects.filter(pk=post.pk).update(
					created_at=post.created_at - timedelta(days=1)
				)

				response = self.client.get(reverse("profile"))
				self.assertEqual(response.status_code, 200)
				self.assertContains(response, post_image.image.url)
				self.assertContains(response, reverse("post_detail", args=[post.pk]))
				self.assertContains(response, reverse("reel_detail", args=[reel.pk]))
				self.assertContains(response, 'aria-label="Reel"')
				self.assertLess(
					response.content.index(reverse("reel_detail", args=[reel.pk]).encode()),
					response.content.index(reverse("post_detail", args=[post.pk]).encode()),
				)

				post_detail = self.client.get(reverse("post_detail", args=[post.pk]))
				reel_detail = self.client.get(reverse("reel_detail", args=[reel.pk]))
				self.assertContains(post_detail, "Older post")
				self.assertContains(post_detail, post_image.image.url)
				self.assertContains(reel_detail, "Newest reel")
				self.assertContains(reel_detail, reel.video_file.url)


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
		self.assertContains(response, "REELO MUSIC")
		self.assertContains(response, "Search songs or artists")
		self.assertContains(response, 'data-camera-modes="photo,video"')
		self.assertContains(response, 'data-camera-photo-target="#photo-input"')
		self.assertContains(response, 'data-camera-video-target="#video-input"')
		self.assertContains(response, "data-camera-dialog")
		self.assertContains(response, "Live camera preview")
		self.assertContains(response, "Flip camera")
		self.assertContains(response, "Retake")

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

	def test_video_post_persists_location_visibility_and_video(self):
		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(
					reverse("create_post"),
					{
						"caption": "A day out",
						"location": "London",
						"visibility": "followers",
						"video": SimpleUploadedFile(
							"moment.mp4", b"video-data", content_type="video/mp4"
						),
					},
				)

				post = Post.objects.get(user=self.user)
				self.assertRedirects(response, reverse("profile"))
				self.assertEqual(post.caption, "A day out")
				self.assertEqual(post.location, "London")
				self.assertEqual(post.visibility, Post.Visibility.FOLLOWERS)
				self.assertTrue(Path(post.video.path).is_file())


class SocialPostTests(TestCase):
	def setUp(self):
		self.author = get_user_model().objects.create_user(
			username="post-author",
			password="post-password",
			full_name="Post Author",
		)
		self.viewer = get_user_model().objects.create_user(
			username="post-viewer",
			password="post-password",
			full_name="Post Viewer",
		)
		self.post = Post.objects.create(
			user=self.author,
			caption="A public moment",
		)

	def test_home_feed_shows_public_posts_and_supports_like_and_save(self):
		self.client.force_login(self.viewer)
		response = self.client.get(reverse("home"))

		self.assertContains(response, "A public moment")
		self.assertContains(response, reverse("toggle_post_like", args=[self.post.pk]))
		self.assertRedirects(
			self.client.post(reverse("toggle_post_like", args=[self.post.pk])),
			reverse("post_detail", args=[self.post.pk]),
		)
		self.assertTrue(self.post.likes.filter(pk=self.viewer.pk).exists())
		self.assertEqual(self.post.like_count, 1)

		self.client.post(reverse("toggle_post_like", args=[self.post.pk]))
		self.assertFalse(self.post.likes.filter(pk=self.viewer.pk).exists())
		self.client.post(reverse("toggle_post_save", args=[self.post.pk]))
		self.assertTrue(self.post.saved_by.filter(pk=self.viewer.pk).exists())
		self.assertEqual(self.post.save_count, 1)

	def test_followers_and_private_visibility_are_enforced(self):
		self.post.visibility = Post.Visibility.FOLLOWERS
		self.post.save(update_fields=("visibility",))
		self.client.force_login(self.viewer)

		self.assertNotContains(self.client.get(reverse("home")), "A public moment")
		self.assertEqual(
			self.client.get(reverse("post_detail", args=[self.post.pk])).status_code,
			404,
		)
		self.client.post(
			reverse("toggle_follow", args=[self.author.username]),
			{"next": reverse("home")},
		)
		self.assertTrue(
			Follow.objects.filter(follower=self.viewer, following=self.author).exists()
		)
		self.assertContains(self.client.get(reverse("home")), "A public moment")

		self.post.visibility = Post.Visibility.PRIVATE
		self.post.save(update_fields=("visibility",))
		self.assertNotContains(self.client.get(reverse("home")), "A public moment")
		self.client.force_login(self.author)
		self.assertContains(self.client.get(reverse("home")), "A public moment")

	def test_private_profile_public_posts_are_only_visible_to_followers(self):
		Profile.objects.create(user=self.author, is_private=True)
		self.client.force_login(self.viewer)

		self.assertNotContains(self.client.get(reverse("home")), "A public moment")
		self.client.post(reverse("toggle_follow", args=[self.author.username]))
		self.assertContains(self.client.get(reverse("home")), "A public moment")
		self.assertContains(
			self.client.get(
				reverse("profile_detail", args=[self.author.username])
			),
			"A public moment",
		)


class MusicLibraryTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username="music-user",
			password="music-password",
			full_name="Music User",
		)
		self.client.force_login(self.user)
		self.song = Song.objects.create(
			title="Heeriye",
			artist="Jasleen Royal",
			cover_url="https://example.com/cover.jpg",
			preview_url="https://example.com/preview.mp3",
			duration=30,
			external_id="reelo:test-heeriye",
			provider="test",
			attribution="Open catalog",
			attribution_url="https://example.com/song",
			is_trending=True,
		)

	def test_music_endpoints_search_trending_detail_and_require_authentication(self):
		response = self.client.get(
			reverse("music_search"), {"q": "Heeriye"}
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["results"][0]["title"], "Heeriye")
		self.assertEqual(
			response.json()["results"][0]["preview_url"],
			"https://example.com/preview.mp3",
		)
		self.assertEqual(
			self.client.get(reverse("music_trending")).json()["results"][0]["id"],
			self.song.pk,
		)
		self.assertEqual(
			self.client.get(
				reverse("music_song_detail", args=[self.song.pk])
			).json()["song"]["artist"],
			"Jasleen Royal",
		)

		self.client.logout()
		self.assertEqual(
			self.client.get(
				reverse("music_search"), {"q": "Heeriye"}
			).status_code,
			302,
		)

	def test_music_key_is_not_rendered_in_reelo_pages_or_api_responses(self):
		secret = "private-apple-signing-key"
		with override_settings(
			APPLE_MUSIC_TEAM_ID="",
			APPLE_MUSIC_KEY_ID="",
			APPLE_MUSIC_PRIVATE_KEY=secret,
		):
			page = self.client.get(reverse("create_post"))
			api = self.client.get(
				reverse("music_search"), {"q": "Heeriye"}
			)

		self.assertNotContains(page, secret)
		self.assertNotContains(api, secret)
		self.assertContains(page, "REELO MUSIC")

	def test_apple_catalog_normalizes_and_deduplicates_by_external_id(self):
		catalog = AppleMusicCatalog()
		resource = {
			"id": "track-1",
			"attributes": {
				"name": "Kesariya",
				"artistName": "Arijit Singh",
				"durationInMillis": 210000,
				"artwork": {
					"url": "https://is1-ssl.mzstatic.com/image/{w}x{h}bb.{f}"
				},
				"previews": [{"url": "https://audio-ssl.itunes.apple.com/preview.m4a"}],
				"url": "https://music.apple.com/in/song/track-1",
			},
		}

		normalized = catalog.normalize(resource)
		self.assertEqual(normalized["duration"], 210)
		self.assertEqual(normalized["provider"], "apple_music")
		self.assertEqual(
			normalized["cover_url"],
			"https://is1-ssl.mzstatic.com/image/300x300bb.jpg",
		)
		with patch.object(AppleMusicCatalog, "search", return_value=[resource]):
			from .music_catalog import _save_catalog_resources

			first = _save_catalog_resources(
				AppleMusicCatalog().search("Kesariya")
			)
			second = _save_catalog_resources(
				AppleMusicCatalog().search("Kesariya")
			)
		self.assertEqual(first[0].pk, second[0].pk)
		self.assertEqual(
			Song.objects.filter(
				external_id="apple_music:in:track-1"
			).count(),
			1,
		)

	def test_rate_limit_falls_back_to_database_and_marks_response_degraded(self):
		with override_settings(
			APPLE_MUSIC_TEAM_ID="team",
			APPLE_MUSIC_KEY_ID="key",
			APPLE_MUSIC_PRIVATE_KEY="private",
		):
			with (
				patch.object(
					AppleMusicCatalog, "_developer_token", return_value="token"
				),
				patch(
					"reelo.music_catalog.urlopen",
					side_effect=HTTPError(
						"https://api.music.apple.com",
						429,
						"Too Many Requests",
						{},
						None,
					),
				),
			):
				response = self.client.get(
					reverse("music_search"), {"q": "Heeriye"}
				)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()["degraded"])
		self.assertIn("Heeriye", [item["title"] for item in response.json()["results"]])

	def test_story_composer_attaches_song_and_hides_expired_stories(self):
		image_data = BytesIO()
		Image.new("RGB", (8, 8), "purple").save(image_data, format="JPEG")
		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(
					reverse("create_story"),
					{
						"caption": "A short-lived moment",
						"song_id": str(self.song.pk),
						"image": SimpleUploadedFile(
							"story.jpg",
							image_data.getvalue(),
							content_type="image/jpeg",
						),
					},
				)
				self.assertRedirects(response, reverse("stories"))
				story = Story.objects.get(user=self.user)
				self.assertEqual(story.song, self.song)
				self.assertGreater(story.expires_at, story.created_at)

				Story.objects.create(
					user=self.user,
					image="stories/old.jpg",
					expires_at=story.created_at - timedelta(seconds=1),
				)
				stories_response = self.client.get(reverse("stories"))
				self.assertContains(stories_response, "A short-lived moment")
				self.assertNotContains(stories_response, "old.jpg")
