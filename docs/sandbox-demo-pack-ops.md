"""
Ops note: Experience poll budget vs pack seed duration
======================================================

Full sandbox now runs ``generic_hospital_v1`` synchronously inside
``create_sandbox_task``. That is heavier than the old CARE fixture loaders.

Experience defaults (unchanged product contract)::

    CARE_SANDBOX_POLL_ATTEMPTS = 60
    CARE_SANDBOX_POLL_INTERVAL = 5   # seconds
    # ≈ 5 minutes total

If Full sandbox provisioning times out on Experience ``/sandbox/``, raise
those env vars on Experience (ops only — no UI/API change). Example::

    CARE_SANDBOX_POLL_ATTEMPTS=120
    CARE_SANDBOX_POLL_INTERVAL=5

Revoke still soft-deletes the sandbox facility + the 7 ``care-*`` users in
``result.users``. Pack ``demo_*`` users may remain until a later cleanup.
"""
