from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin

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

admin.site.register(Droplet, DropletAdmin)

class ShareAdmin(admin.ModelAdmin):
    list_display = ("cell", "user", "mode", "parent")

admin.site.register(Share, ShareAdmin)
admin.site.register(UserResource)
admin.site.register(UserProfile)
