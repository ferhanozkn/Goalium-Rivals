from rest_framework import serializers

from apps.imports.models import ImportJob, ImportRecord


class ImportRequestSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=[choice[0] for choice in ImportJob.PROVIDER_CHOICES])
    source_url = serializers.URLField(max_length=500)
    license_name = serializers.CharField(max_length=160)
    license_status = serializers.ChoiceField(
        choices=[choice[0] for choice in ImportJob._meta.get_field("license_status").choices], default="pending"
    )
    records = serializers.ListField(child=serializers.DictField(), allow_empty=False)

    def validate_license_status(self, value):
        if value == "blocked":
            raise serializers.ValidationError("Engellenmiş lisansla içe aktarma yapılamaz.")
        return value


class ImportJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportJob
        fields = [
            "id",
            "provider",
            "source_url",
            "license_name",
            "license_status",
            "status",
            "record_count",
            "imported_count",
            "skipped_count",
            "error_count",
            "error_message",
            "started_at",
            "finished_at",
            "created_at",
        ]
        read_only_fields = fields


class ImportRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportRecord
        fields = [
            "id",
            "record_type",
            "external_id",
            "raw_payload",
            "status",
            "target_model",
            "target_id",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
