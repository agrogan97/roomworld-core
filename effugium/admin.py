from django.contrib import admin

from .models import RawLevelData

@admin.register(RawLevelData)
class RawLevelDataAdmin(admin.ModelAdmin):
    list_display = ('pk', 'userId', 'timeCreated', 'lastModified')
