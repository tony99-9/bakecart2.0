from .models import Item
from django.contrib import admin

class ItemAdmin(admin.ModelAdmin):
    list_display = ('id')  # Display these fields in the list view


admin.site.register(Item)