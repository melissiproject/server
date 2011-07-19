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
    list_display = ("id", "name", "owner", "cell",
                    "content_size", "overall_size", "deleted")
    list_display_links = ("id", "name",)
    search_fields = ("name", "owner__username")
    list_filter = ("deleted",)

    def content_size(self, obj):
        size = "%.2f" % (1.0 * obj.content.size / 1048576)
        return size if size != "0.00" else "~0.00"
    content_size.short_description = "Content Size (MiB)"

    def overall_size(self, obj):
        size = "%.2f" % (1.0 * obj.overall_size() / 1048576)
        return size if size != "0.00" else "~0.00"
    overall_size.short_description = "Overall Size (MiB)"


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
