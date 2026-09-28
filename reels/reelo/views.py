from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.forms import ModelForm
from django.shortcuts import get_object_or_404, redirect, render

from .models import Profile, Reel


class ProfileForm(ModelForm):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
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


class ReelForm(ModelForm):
	class Meta:
		model = Reel
		fields = ("video_file", "caption")
		widgets = {
			"video_file": forms.FileInput(attrs={"accept": "video/*"}),
			"caption": forms.Textarea(attrs={"rows": 3, "placeholder": "Add a caption"}),
		}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields["video_file"].widget.attrs["class"] = "form-control"
		self.fields["caption"].widget.attrs["class"] = "form-control"


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
	return render(request, "home.html")


@login_required
def create_reel(request):
	if request.method == "POST":
		form = ReelForm(request.POST, request.FILES)
		if form.is_valid():
			reel = form.save(commit=False)
			reel.user = request.user
			reel.save()
			messages.success(request, "Your reel is live.")
			return redirect("reels_feed")
	else:
		form = ReelForm()
	return render(request, "create_reel.html", {"form": form})


def reels_feed(request):
	reels = Reel.objects.select_related("user").all()
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


@login_required
def profile(request):
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
		},
	)


def profile_detail(request, username):
	profile_user = get_object_or_404(get_user_model(), username=username)
	profile = Profile.objects.filter(user=profile_user).first()
	is_owner = request.user.is_authenticated and request.user.pk == profile_user.pk
	can_view_profile = is_owner or not profile or not profile.is_private
	return render(
		request,
		"profile.html",
		{
			"profile": profile,
			"profile_user": profile_user,
			"is_owner": is_owner,
			"can_view_profile": can_view_profile,
		},
	)


def search(request):
	query = request.GET.get("q", "").strip()
	users = get_user_model().objects.filter(username__icontains=query) if query else []
	return render(request, "search.html", {"query": query, "users": users})
