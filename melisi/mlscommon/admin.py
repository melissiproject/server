from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.conf import settings

from models import Cell, CellRevision, \
     Share, Droplet, DropletRevision, UserResource, UserProfile

class CellRevisionInline(admin.TabularInline):
    model = CellRevision
    fk_name = 'cell'


class CellAdmin(admin.ModelAdmin):
    inlines = [CellRevisionInline]
    list_display = ("id", "name", "owner", "parent", "deleted")
    list_display_links = ("id", "name")
    search_fields = ("name", "owner__username")

admin.site.register(Cell, CellAdmin)

class DropletRevisionInline(admin.TabularInline):
    model = DropletRevision

class DropletAdmin(admin.ModelAdmin):
    inlines = [DropletRevisionInline]
    list_display = ("id", "name", "owner", "cell", "deleted")
    list_display_links = ("id", "name",)
    search_fields = ("name",)
    list_filter = ("deleted",)

admin.site.register(Droplet, DropletAdmin)

class ShareAdmin(admin.ModelAdmin):
    list_display = ("cell", "user", "mode", "parent")

class UserProfileInline(admin.StackedInline):
    model = UserProfile

class UserProfileAdmin(UserAdmin):
    inlines = [UserProfileInline]
    list_display = ("username", "email", "first_name", "last_name", "quota")

    def quota(self, obj):
        quota = 1.0 * obj.get_profile().quota / 1048576
        quota_limit = 1.0 * obj.get_profile().quota_limit / 1024
        return "%.2f/%.2f (%.2f%%)" % (quota,
                                       quota_limit,
                                       100.0 * quota / quota_limit)
    quota.short_description="Quota (MiB)"

admin.site.unregister(User)
admin.site.register(User, UserProfileAdmin)

admin.site.register(Share, ShareAdmin)
admin.site.register(UserResource)
