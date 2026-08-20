from django.conf import settings
from django.db import models

from care.utils.models.base import BaseModel


class SandboxJob(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    facility_name = models.CharField(max_length=1000, default="", blank=True)
    is_facility_empty = models.BooleanField(default=False)
    server_url = models.CharField(max_length=500, default="", blank=True)
    result = models.JSONField(default=dict, blank=True)
    error = models.TextField(default="", blank=True)
    # The authorized caller whose identity the seeding runs under.
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    def __str__(self):
        return f"SandboxJob {self.external_id} ({self.status})"
