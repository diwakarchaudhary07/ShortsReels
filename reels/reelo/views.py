from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.forms import ModelForm
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Follow, Post, PostImage, Profile, Reel, Song, Story
from .music_catalog import get_music_songs


class ProfileForm(ModelForm):
	full_name = forms.CharField(max_length=255)
	username = forms.CharField(max_length=150)

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["full_name"].initial = self.instance.user.full_name
		self.fields["username"].initial = self.instance.user.username
		for field in self.fields.values():
			field.widget.attrs["class"] = (
				"form-check-input"
				if isinstance(field.widget, forms.CheckboxInput)
				else "form-control"
			)

	class Meta:
		model = Profile
		fields = (
			"profile_image",
			"bio",
			"website",
			"location",
			"date_of_birth",
			"is_private",
		)
		widgets = {
			"bio": forms.Textarea(attrs={"rows": 3}),
			"date_of_birth": forms.DateInput(attrs={"type": "date"}),
		}

	def clean_username(self):
		username = self.cleaned_data["username"]
		users = get_user_model().objects.filter(username=username)
		if users.exclude(pk=self.instance.user_id).exists():
			raise ValidationError("This username is already taken.")
		return username

	def save(self, commit=True):
		profile = super().save(commit=False)
		profile.user.full_name = self.cleaned_data["full_name"]
		profile.user.username = self.cleaned_data["username"]
		if commit:
			profile.save()
			profile.user.save(update_fields=["full_name", "username"])
		return profile


class ReelForm(ModelForm):
	class Meta:
		model = Reel
		fields = (
			"video_file",
			"thumbnail",
			"caption",
			"song",
			"location",
			"is_comments_enabled",
		)
		widgets = {
			"video_file": forms.FileInput(attrs={"accept": "video/*"}),
			"thumbnail": forms.FileInput(attrs={"accept": "image/*"}),
			"caption": forms.Textarea(attrs={"rows": 3, "placeholder": "Add a caption"}),
			"song": forms.HiddenInput(),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		for field in self.fields.values():
			if isinstance(field.widget, forms.CheckboxInput):
				field.widget.attrs["class"] = "form-check-input"
			elif isinstance(field.widget, forms.Select):
				field.widget.attrs["class"] = "form-select"
			else:
				field.widget.attrs["class"] = "form-control"


class StoryForm(ModelForm):
	class Meta:
		model = Story
		fields = ("image", "video", "caption")
		widgets = {
			"image": forms.FileInput(attrs={"accept": "image/*"}),
			"video": forms.FileInput(attrs={"accept": "video/*"}),
			"caption": forms.TextInput(attrs={"maxlength": 2200}),
		}

	def clean(self):
		cleaned_data = super().clean()
		image = cleaned_data.get("image")
		video = cleaned_data.get("video")
		if bool(image) == bool(video):
			raise ValidationError("Choose one photo or one video for your story.")
		if video and not (video.content_type or "").startswith("video/"):
			self.add_error("video", "Choose a valid video file.")
		return cleaned_data

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		for field in self.fields.values():
			field.widget.attrs["class"] = "form-control"


class BootstrapAuthenticationForm(AuthenticationForm):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["username"].widget.attrs.update(
			{"class": "form-control", "autocomplete": "username"}
		)
		self.fields["password"].widget.attrs.update(
			{"class": "form-control", "autocomplete": "current-password"}
		)


def home(request):
	page_obj = Paginator(_visible_posts(request.user), 20).get_page(
		request.GET.get("page")
	)
	posts = _posts_with_engagement(
		page_obj.object_list.select_related("user", "song").prefetch_related(
			"images"
		),
		request.user,
	)
	return render(
		request, "home.html", {"posts": posts, "page_obj": page_obj}
	)


def _music_song_payload(song, request):
	preview_url = song.preview_url
	if not preview_url and song.rights_cleared and song.audio_file:
		preview_url = request.build_absolute_uri(song.audio_file.url)
	return {
		"id": song.pk,
		"title": song.title,
		"artist": song.artist,
		"cover_url": song.cover_url,
		"preview_url": preview_url,
		"duration": song.duration,
		"attribution": song.attribution,
		"attribution_url": song.attribution_url,
	}


def _music_queryset():
	return Song.objects.filter(
		Q(preview_url__gt="")
		| Q(rights_cleared=True)
		| Q(provider="apple_music")
	)


@login_required
@require_GET
def music_search(request):
	query = request.GET.get("q", "").strip()[:100]
	if not query:
		return JsonResponse(
			{"results": [], "message": "Enter a song or artist to search."}
		)
	songs, degraded = get_music_songs(query=query)
	return JsonResponse(
		{
			"results": [_music_song_payload(song, request) for song in songs],
			"degraded": degraded,
			"message": (
				"Catalog search is temporarily unavailable. Showing saved songs."
				if degraded
				else ""
			),
		}
	)


@login_required
@require_GET
def music_trending(request):
	songs, degraded = get_music_songs(trending=True)
	return JsonResponse(
		{
			"results": [_music_song_payload(song, request) for song in songs],
			"degraded": degraded,
			"message": (
				"Trending music is temporarily unavailable. Showing saved songs."
				if degraded
				else ""
			),
		}
	)


@login_required
@require_GET
def music_song_detail(request, song_id):
	song = get_object_or_404(_music_queryset(), pk=song_id)
	return JsonResponse({"song": _music_song_payload(song, request)})


@login_required
def create_reel(request):
	if request.method == "POST":
		form = ReelForm(request.POST, request.FILES)
		if form.is_valid():
			song_id = request.POST.get("song")
			if song_id and not Song.objects.filter(pk=song_id).exists():
				form.add_error(None, "That song is no longer available.")
			else:
				reel = form.save(commit=False)
				reel.user = request.user
				reel.save()
				messages.success(request, "Your reel is live.")
				return redirect("reels_feed")
	else:
		form = ReelForm()
	return render(request, "create_reel.html", {"form": form})


@login_required
def create_story(request):
	if request.method == "POST":
		form = StoryForm(request.POST, request.FILES)
		song_id = request.POST.get("song_id", "").strip()
		song = None
		if song_id:
			try:
				song = Song.objects.get(pk=int(song_id))
			except (ValueError, Song.DoesNotExist):
				form.add_error(None, "That song is no longer available.")
		if form.is_valid():
			story = form.save(commit=False)
			story.user = request.user
			story.song = song
			story.save()
			messages.success(request, "Your story is live for 24 hours.")
			return redirect("stories")
	else:
		form = StoryForm()
	return render(request, "create_story.html", {"form": form})


@login_required
@require_GET
def stories(request):
	followed_user_ids = Follow.objects.filter(
		follower=request.user
	).values_list("following_id", flat=True)
	active_stories = (
		Story.objects.filter(expires_at__gt=timezone.now())
		.filter(
			Q(user=request.user)
			| Q(user_id__in=followed_user_ids)
		)
		.select_related("user", "song")
		.order_by("-created_at")
	)
	return render(request, "stories.html", {"stories": active_stories})


@login_required
def create_post(request):
	errors = []
	if request.method == "POST":
		images = request.FILES.getlist("images")
		video = request.FILES.get("video")
		cleaned_images = []
		if not images and not video:
			errors.append("Select at least one photo or a video before sharing.")
		if images and video:
			errors.append("Choose photos or one video, not both.")
		if len(images) > 10:
			errors.append("You can add up to 10 photos to a post.")
		if images and not errors:
			for image in images:
				try:
					cleaned_images.append(forms.ImageField().clean(image))
				except ValidationError:
					errors.append(f"{image.name} is not a valid image.")
		if video and not (video.content_type or "").startswith("video/"):
			errors.append("Choose a valid video file.")

		caption = request.POST.get("caption", "").strip()
		location = request.POST.get("location", "").strip()
		if len(caption) > 2200:
			errors.append("Captions can be up to 2200 characters long.")
		if len(location) > 255:
			errors.append("Locations can be up to 255 characters long.")
		visibility = request.POST.get("visibility", Post.Visibility.PUBLIC)
		if visibility not in Post.Visibility.values:
			errors.append("Select a valid audience for your post.")

		song = None
		song_id = request.POST.get("song_id", "").strip()
		if song_id:
			try:
				song = Song.objects.get(pk=int(song_id))
			except (ValueError, Song.DoesNotExist):
				errors.append("Select a valid song.")

		if not errors:
			post = Post.objects.create(
				user=request.user,
				caption=caption,
				video=video,
				location=location,
				visibility=visibility,
				song=song,
			)
			for position, image in enumerate(cleaned_images):
				PostImage.objects.create(post=post, image=image, position=position)
			messages.success(request, "Your post has been shared.")
			return redirect("profile")

	return render(
		request,
		"create_post.html",
		{"errors": errors, "start_share": bool(errors)},
	)


def _visible_posts(viewer):
	followed_user_ids = (
		Follow.objects.filter(follower=viewer).values_list("following_id", flat=True)
		if viewer.is_authenticated
		else []
	)
	public_profile = (
		Q(user__profile__is_private=False) | Q(user__profile__isnull=True)
	)
	visible = Q(visibility=Post.Visibility.PUBLIC) & (
		public_profile | Q(user_id__in=followed_user_ids)
	)
	if viewer.is_authenticated:
		visible |= Q(user_id=viewer.pk) | Q(
			visibility=Post.Visibility.FOLLOWERS,
			user_id__in=followed_user_ids,
		)
	return Post.objects.filter(visible).distinct()


def _posts_with_engagement(posts, viewer):
	posts = list(
		posts.annotate(
			likes_total=Count("likes", distinct=True),
			saves_total=Count("saved_by", distinct=True),
		)
	)
	post_ids = [post.pk for post in posts]
	liked_ids = set()
	saved_ids = set()
	if viewer.is_authenticated and post_ids:
		liked_ids = set(
			Post.likes.through.objects.filter(
				post_id__in=post_ids, user_id=viewer.pk
			).values_list("post_id", flat=True)
		)
		saved_ids = set(
			Post.saved_by.through.objects.filter(
				post_id__in=post_ids, user_id=viewer.pk
			).values_list("post_id", flat=True)
		)
	for post in posts:
		post.viewer_liked = post.pk in liked_ids
		post.viewer_saved = post.pk in saved_ids
	return posts


def _action_redirect(request, fallback, **fallback_kwargs):
	next_url = request.POST.get("next", "")
	if url_has_allowed_host_and_scheme(
		next_url,
		allowed_hosts={request.get_host()},
		require_https=request.is_secure(),
	):
		return redirect(next_url)
	return redirect(fallback, **fallback_kwargs)


@login_required
@require_POST
def toggle_post_like(request, post_id):
	post = get_object_or_404(Post, pk=post_id)
	if not _visible_posts(request.user).filter(pk=post.pk).exists():
		raise Http404
	if post.likes.filter(pk=request.user.pk).exists():
		post.likes.remove(request.user)
	else:
		post.likes.add(request.user)
	return _action_redirect(request, "post_detail", post_id=post.pk)


@login_required
@require_POST
def toggle_post_save(request, post_id):
	post = get_object_or_404(Post, pk=post_id)
	if not _visible_posts(request.user).filter(pk=post.pk).exists():
		raise Http404
	if post.saved_by.filter(pk=request.user.pk).exists():
		post.saved_by.remove(request.user)
	else:
		post.saved_by.add(request.user)
	return _action_redirect(request, "post_detail", post_id=post.pk)


@login_required
@require_POST
def toggle_follow(request, username):
	followed_user = get_object_or_404(get_user_model(), username=username)
	if followed_user.pk == request.user.pk:
		messages.error(request, "You cannot follow your own account.")
	else:
		follow, created = Follow.objects.get_or_create(
			follower=request.user, following=followed_user
		)
		if not created:
			follow.delete()
	return _action_redirect(
		request,
		"profile_detail",
		username=followed_user.username,
	)


def reels_feed(request):
	reels = Reel.objects.select_related("user", "song").filter(is_archived=False)
	for reel in reels:
		reel.thumbnail_url = reel.thumbnail.url if reel.thumbnail.name else ""
	return render(request, "reels_feed.html", {"reels": reels})


@login_required
def notifications(request):
	return render(
		request,
		"social_placeholder.html",
		{
			"page_title": "Notifications",
			"page_icon": "bi-heart",
			"page_message": "You’re all caught up.",
		},
	)


@login_required
def messages_inbox(request):
	return render(
		request,
		"social_placeholder.html",
		{
			"page_title": "Messages",
			"page_icon": "bi-chat-dots",
			"page_message": "Your messages will appear here.",
		},
	)


@login_required
def chat(request):
	return render(
		request,
		"social_placeholder.html",
		{
			"page_title": "Chat",
			"page_icon": "bi-chat-left-text",
			"page_message": "Choose a conversation to start chatting.",
		},
	)


def _profile_content_items(profile_user, viewer, is_owner):
	items = []
	posts = (
		_visible_posts(viewer)
		.filter(user=profile_user)
		.prefetch_related("images")
	)
	reels = Reel.objects.filter(user=profile_user)
	if not is_owner:
		reels = reels.filter(is_archived=False)

	for post in posts:
		images = list(post.images.all())
		preview_image = next(
			(image for image in images if image.image.name), None
		)
		items.append(
			{
				"post": post,
				"images": images,
				"preview_url": preview_image.image.url if preview_image else "",
				"created_at": post.created_at,
			}
		)

	for reel in reels:
		items.append(
			{
				"reel": reel,
				"preview_url": reel.thumbnail.url if reel.thumbnail.name else "",
				"created_at": reel.created_at,
			}
		)

	return sorted(items, key=lambda item: item["created_at"], reverse=True)


@login_required
def profile(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	followers_count = Follow.objects.filter(following=request.user).count()
	following_count = Follow.objects.filter(follower=request.user).count()
	return render(
		request,
		"profile_page.html",
		{
			"profile": profile,
			"is_owner": True,
			"can_view_profile": True,
			"content_items": _profile_content_items(request.user, request.user, True),
			"posts_count": _visible_posts(request.user)
			.filter(user=request.user)
			.count(),
			"followers_count": followers_count,
			"following_count": following_count,
			"is_following": False,
			"profile_url": request.build_absolute_uri(reverse("profile")),
		},
	)


@login_required
def edit_profile(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	if request.method == "POST":
		form = ProfileForm(request.POST, request.FILES, instance=profile)
		if form.is_valid():
			form.save()
			return redirect("profile")
	else:
		form = ProfileForm(instance=profile)
	return render(
		request,
		"profile.html",
		{
			"profile": profile,
			"form": form,
			"is_owner": True,
			"can_view_profile": True,
			"editing": True,
		},
	)


def profile_detail(request, username):
	profile_user = get_object_or_404(get_user_model(), username=username)
	profile = Profile.objects.filter(user=profile_user).first()
	is_owner = request.user.is_authenticated and request.user.pk == profile_user.pk
	is_following = request.user.is_authenticated and Follow.objects.filter(
		follower=request.user, following=profile_user
	).exists()
	can_view_profile = is_owner or not profile or not profile.is_private or is_following
	return render(
		request,
		"profile_page.html",
		{
			"profile": profile,
			"profile_user": profile_user,
			"is_owner": is_owner,
			"can_view_profile": can_view_profile,
			"content_items": (
				_profile_content_items(profile_user, request.user, is_owner)
				if can_view_profile
				else []
			),
			"posts_count": _visible_posts(request.user)
			.filter(user=profile_user)
			.count(),
			"followers_count": Follow.objects.filter(
				following=profile_user
			).count(),
			"following_count": Follow.objects.filter(
				follower=profile_user
			).count(),
			"is_following": is_following,
			"profile_url": request.build_absolute_uri(
				reverse("profile_detail", kwargs={"username": profile_user.username})
			),
		},
	)


def post_detail(request, post_id):
	post = get_object_or_404(
		Post.objects.select_related("user", "song").prefetch_related("images"),
		pk=post_id,
	)
	if not _visible_posts(request.user).filter(pk=post.pk).exists():
		raise Http404
	post.viewer_liked = request.user.is_authenticated and post.likes.filter(
		pk=request.user.pk
	).exists()
	post.viewer_saved = request.user.is_authenticated and post.saved_by.filter(
		pk=request.user.pk
	).exists()
	post.likes_total = post.like_count
	post.saves_total = post.save_count
	return render(
		request,
		"content_detail.html",
		{
			"post": post,
			"post_images": list(post.images.all()),
			"content_user": post.user,
		},
	)


def reel_detail(request, reel_id):
	reel = get_object_or_404(Reel.objects.select_related("user", "song"), pk=reel_id)
	is_owner = request.user.is_authenticated and request.user.pk == reel.user_id
	profile = Profile.objects.filter(user=reel.user).first()
	if not is_owner and ((profile and profile.is_private) or reel.is_archived):
		raise Http404
	return render(
		request,
		"content_detail.html",
		{
			"reel": reel,
			"content_user": reel.user,
			"thumbnail_url": reel.thumbnail.url if reel.thumbnail.name else "",
		},
	)


def search(request):
	query = request.GET.get("q", "").strip()
	users = get_user_model().objects.filter(username__icontains=query) if query else []
	return render(request, "search.html", {"query": query, "users": users})
