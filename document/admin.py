from django.contrib import admin
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('name', 'admin', 'is_live', 'share_token', 'created_at', 'updated_at')
    readonly_fields = ('admin', 'share_token', 'created_at', 'updated_at')
    search_fields = ('name', 'admin__email', 'share_token')
    list_filter = ('is_live', 'created_at')
    ordering = ('-created_at',)

    # Optional: restrict which fields are editable in the form
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing object
            return self.readonly_fields
        return ('created_at', 'updated_at')  # Allow setting admin/share_token on creation if needed
