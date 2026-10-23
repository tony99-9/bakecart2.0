from django.contrib import admin

from payments.models import PaymentRecord, ProcessedStripeEvent


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'order_id', 'stripe_payment_intent_id',
        'status', 'currency', 'amount_received', 'created_at',
    ]
    list_filter = ['status', 'currency']
    search_fields = ['stripe_payment_intent_id', 'order__id']
    readonly_fields = [
        'order', 'stripe_payment_intent_id', 'stripe_client_secret',
        'amount_received', 'currency', 'created_at', 'updated_at',
    ]
    ordering = ['-created_at']


@admin.register(ProcessedStripeEvent)
class ProcessedStripeEventAdmin(admin.ModelAdmin):
    list_display = ['stripe_event_id', 'event_type', 'processed_at']
    search_fields = ['stripe_event_id', 'event_type']
    readonly_fields = ['stripe_event_id', 'event_type', 'processed_at']
    ordering = ['-processed_at']
