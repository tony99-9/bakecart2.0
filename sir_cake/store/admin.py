from .models import BasketItem
from django.contrib import admin

class AuthorAdmin(admin.ModelAdmin):
    list_display = ('id', 'item_to_buy')  # Display these fields in the list view
    search_fields = ('item_to_buy',)  # Enable search by the 'name' field
    list_filter = ('item_to_buy',)  # Add a filter for birth dates


admin.site.register(BasketItem)