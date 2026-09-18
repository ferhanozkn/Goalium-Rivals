import uuid

from django.conf import settings
from django.db import models

from apps.content.constants import SOURCE_LICENSE_STATUS_CHOICES


class ImportJob(models.Model):
    PROVIDER_CHOICES = (("wikidata", "Wikidata"), ("openfootball", "openfootball"), ("manual", "Manual"))
    STATUS_CHOICES = (("pending", "Pending"), ("running", "Running"), ("completed", "Completed"), ("failed", "Failed"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.CharField(max_length=24, choices=PROVIDER_CHOICES)
    source_url = models.URLField(max_length=500, blank=True)
    license_name = models.CharField(max_length=160)
    license_status = models.CharField(max_length=12, choices=SOURCE_LICENSE_STATUS_CHOICES, default="pending")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    record_count = models.PositiveIntegerField(default=0)
    imported_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ImportRecord(models.Model):
    RECORD_TYPE_CHOICES = (
        ("competition", "Competition"),
        ("season", "Season"),
        ("team", "Team"),
        ("player", "Player"),
        ("career_entry", "Career entry"),
        ("match", "Match"),
        ("lineup", "Lineup"),
    )
    STATUS_CHOICES = (("pending", "Pending"), ("imported", "Imported"), ("skipped", "Skipped"), ("error", "Error"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(ImportJob, on_delete=models.CASCADE, related_name="records")
    record_type = models.CharField(max_length=24, choices=RECORD_TYPE_CHOICES)
    external_id = models.CharField(max_length=160)
    raw_payload = models.JSONField(default=dict)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    target_model = models.CharField(max_length=80, blank=True)
    target_id = models.UUIDField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "record_type", "external_id"], name="unique_import_job_record"),
        ]
