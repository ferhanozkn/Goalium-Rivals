from django.contrib import admin

from apps.imports.models import ImportJob, ImportRecord


@admin.register(ImportJob)
class ImportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "provider", "status", "license_status", "record_count", "imported_count", "error_count")
    list_filter = ("provider", "status", "license_status")
    readonly_fields = ("started_at", "finished_at", "created_at")


@admin.register(ImportRecord)
class ImportRecordAdmin(admin.ModelAdmin):
    list_display = ("job", "record_type", "external_id", "status", "target_model")
    list_filter = ("record_type", "status")
    search_fields = ("external_id", "target_model")
    readonly_fields = ("created_at", "updated_at")
