import uuid

from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GameSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("kind", models.CharField(choices=[("practice", "Practice"), ("live_1v1", "Live 1v1"), ("async_duel", "Async duel"), ("room", "Room")], max_length=20)),
                ("modes", models.JSONField(default=list)),
                ("language", models.CharField(choices=[("tr", "Türkçe"), ("en", "English")], default="tr", max_length=2)),
                ("status", models.CharField(choices=[("waiting", "Waiting"), ("active", "Active"), ("finished", "Finished"), ("expired", "Expired")], default="waiting", max_length=12)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Match",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("match_type", models.CharField(choices=[("live_1v1", "Live 1v1"), ("practice", "Practice"), ("async_duel", "Async duel"), ("room", "Room")], default="live_1v1", max_length=20)),
                ("origin", models.CharField(choices=[("matchmaking", "Matchmaking"), ("invite", "Invite"), ("room", "Room")], default="invite", max_length=20)),
                ("is_mixed", models.BooleanField(default=True)),
                ("language", models.CharField(choices=[("tr", "Türkçe"), ("en", "English")], default="tr", max_length=2)),
                ("status", models.CharField(choices=[("waiting", "Waiting"), ("live", "Live"), ("finished", "Finished"), ("forfeit", "Forfeit")], default="waiting", max_length=12)),
                ("max_players", models.PositiveSmallIntegerField(default=2)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("game_session", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="match", to="quiz.gamesession")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="MatchParticipant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("display_name", models.CharField(max_length=80)),
                ("score", models.IntegerField(default=0)),
                ("connected", models.BooleanField(default=False)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("guest_session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="match_participations", to="accounts.guestsession")),
                ("match", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participants", to="quiz.match")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="match_participations", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["joined_at"]},
        ),
        migrations.CreateModel(
            name="Round",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("order", models.PositiveSmallIntegerField()),
                ("mode", models.CharField(choices=[("hangman", "Hangman"), ("career_path", "Career path"), ("timed_trivia", "Timed trivia"), ("historical_score", "Historical score"), ("missing_lineup", "Missing lineup")], max_length=24)),
                ("payload", models.JSONField(default=dict)),
                ("deadline", models.DateTimeField()),
                ("status", models.CharField(choices=[("pending", "Pending"), ("active", "Active"), ("finished", "Finished"), ("timeout", "Timeout")], default="pending", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("match", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rounds", to="quiz.match")),
            ],
            options={"ordering": ["order"]},
        ),
        migrations.CreateModel(
            name="Answer",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("raw_answer", models.TextField(blank=True)),
                ("normalized_answer", models.TextField(blank=True)),
                ("result", models.CharField(choices=[("correct", "Correct"), ("wrong", "Wrong"), ("timeout", "Timeout"), ("skipped", "Skipped")], max_length=12)),
                ("response_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("points", models.IntegerField(default=0)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("participant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="answers", to="quiz.matchparticipant")),
                ("round", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="answers", to="quiz.round")),
            ],
        ),
        migrations.AddIndex(
            model_name="match",
            index=models.Index(fields=["status", "created_at"], name="quiz_match_status_410fd1_idx"),
        ),
        migrations.AddConstraint(
            model_name="matchparticipant",
            constraint=models.UniqueConstraint(condition=Q(("user__isnull", False)), fields=("match", "user"), name="unique_user_per_match"),
        ),
        migrations.AddConstraint(
            model_name="matchparticipant",
            constraint=models.UniqueConstraint(condition=Q(("guest_session__isnull", False)), fields=("match", "guest_session"), name="unique_guest_per_match"),
        ),
        migrations.AddConstraint(
            model_name="round",
            constraint=models.UniqueConstraint(fields=("match", "order"), name="unique_round_order"),
        ),
        migrations.AddConstraint(
            model_name="answer",
            constraint=models.UniqueConstraint(fields=("round", "participant"), name="unique_answer_per_round_participant"),
        ),
    ]
