from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Profile, Reel, User


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


@admin.register(Reel)
class ReelAdmin(admin.ModelAdmin):
	list_display = ("user", "caption", "created_at")
	search_fields = ("user__username", "caption")

admin.site.site_header = "ShortsReels administration"
admin.site.site_title = "ShortsReels admin"
admin.site.index_title = "Manage ShortsReels"
