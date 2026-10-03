from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Follow, Post, PostImage, Profile, Reel, Song, Story, User


class ProfileInline(admin.StackedInline):
	model = Profile
	can_delete = False
	extra = 0


@admin.register(User)
class CustomUserAdmin(UserAdmin):
	list_display = ("username", "full_name", "email", "mobile_no", "is_staff")
	inlines = (ProfileInline,)
	fieldsets = UserAdmin.fieldsets + (
		("Profile", {"fields": ("full_name", "mobile_no", "dob", "address", "profile_image", "gender")}),
	)
	add_fieldsets = UserAdmin.add_fieldsets + (
		("Profile", {"fields": ("full_name", "email")}),
	)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
	list_display = ("user", "location", "is_private", "followers_count", "following_count", "updated_at")
	list_filter = ("is_private",)
	search_fields = ("user__username", "user__full_name", "bio", "location")


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
	list_display = ("follower", "following", "created_at")
	search_fields = ("follower__username", "following__username")
	readonly_fields = ("created_at",)


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
	list_display = (
		"user",
		"caption",
		"song",
		"location",
		"views_count",
		"likes_count",
		"is_archived",
		"created_at",
	)
	list_filter = ("is_archived", "is_comments_enabled", "created_at")
	search_fields = ("user__username", "caption", "location", "song__title")
	list_editable = ("is_archived",)
	readonly_fields = ("created_at", "updated_at")


class PostImageInline(admin.TabularInline):
	model = PostImage
	extra = 0


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
	list_display = ("user", "visibility", "location", "song", "created_at")
	list_filter = ("visibility", "created_at")
	search_fields = ("user__username", "caption", "location", "song__title")
	inlines = (PostImageInline,)


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
	list_display = (
		"title",
		"artist",
		"provider",
		"is_trending",
		"rights_cleared",
		"created_at",
	)
	list_filter = ("provider", "is_trending", "rights_cleared")
	search_fields = ("title", "artist", "external_id")
	readonly_fields = ("created_at",)


@admin.register(Story)
class StoryAdmin(admin.ModelAdmin):
	list_display = ("user", "song", "created_at", "expires_at")
	list_filter = ("created_at", "expires_at")
	search_fields = ("user__username", "caption", "song__title")
	readonly_fields = ("created_at",)

admin.site.site_header = "ShortsReels administration"
admin.site.site_title = "ShortsReels admin"
admin.site.index_title = "Manage ShortsReels"
