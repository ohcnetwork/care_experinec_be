import traceback

from celery import current_app, shared_task

from care_experience_sandbox_be.models import SandboxJob
from care_experience_sandbox_be.sandbox import build_sandbox, sandbox_context


@shared_task
def create_sandbox_task(job_id):
    job = SandboxJob.objects.get(id=job_id)
    job.status = SandboxJob.Status.RUNNING
    job.save(update_fields=["status", "modified_date"])

    try:
        with sandbox_context(actor_user=job.created_by) as base:
            result = build_sandbox(
                base,
                job.external_id,
                job.is_facility_empty,
                job.facility_name,
                job.server_url,
            )
        job.result = result
        job.status = SandboxJob.Status.COMPLETED
        job.save(update_fields=["result", "status", "modified_date"])
    except Exception:
        job.error = traceback.format_exc()
        job.status = SandboxJob.Status.FAILED
        job.save(update_fields=["error", "status", "modified_date"])
        raise


@current_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    return

