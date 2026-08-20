from django.contrib.auth import get_user_model

from care.facility.models.facility import Facility


def revoke_sandbox(job):
    """Soft-delete the facility and sandbox users created for this job."""
    result = job.result or {}
    facility_id = (result.get("facility") or {}).get("id")
    if facility_id:
        Facility.objects.filter(external_id=facility_id).update(deleted=True)

    usernames = [
        user.get("username") for user in result.get("users", []) if user.get("username")
    ]
    if usernames:
        get_user_model().objects.filter(username__in=usernames).update(
            deleted=True, is_active=False
        )
