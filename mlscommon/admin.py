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
    list_display = ("name", "owner", "parent")

admin.site.register(Cell, CellAdmin)

class DropletRevisionInline(admin.TabularInline):
    model = DropletRevision

class DropletAdmin(admin.ModelAdmin):
    inlines = [DropletRevisionInline]

admin.site.register(Droplet, DropletAdmin)

admin.site.register(Share)
admin.site.register(UserResource)
admin.site.register(UserProfile)
