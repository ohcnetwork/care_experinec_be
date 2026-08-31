from care.emr.models.organization import Organization
from care.emr.resources.organization.spec import OrganizationTypeChoices
from care.security.models import RoleModel

from care_experience_sandbox_be.settings import plugin_settings

# (role name as synced in care, username prefix)
SANDBOX_ROLES = [
    ("Administrator", "care-admin"),
    ("Facility Admin", "care-fac-admin"),
    ("Doctor", "care-doctor"),
    ("Nurse", "care-nurse"),
    ("Staff", "care-staff"),
    ("Volunteer", "care-volunteer"),
    ("Pharmacist", "care-pharmacist"),
]

# The role whose credentials are surfaced as the primary sign-in.
PRIMARY_ROLE = "Facility Admin"

DEFAULT_DEMO_PACK_SLUG = "generic_hospital_v1"


def _pick_or_create_geo(base):
    """Reuse the first existing state and its first district; create defaults if none."""
    govt = OrganizationTypeChoices.govt.value
    state = Organization.objects.filter(org_type=govt, parent__isnull=True).order_by("id").first()
    if state is None:
        resp = base.create_organization(org_type=govt, name="Kerala")
        state_id, state_name = resp.id, resp.name
    else:
        state_id, state_name = str(state.external_id), state.name

    district = Organization.objects.filter(org_type=govt, parent__external_id=state_id).order_by("id").first()
    if district is None:
        resp = base.create_organization(org_type=govt, name="Ernakulam", parent=state_id)
        district_id, district_name = resp.id, resp.name
    else:
        district_id, district_name = str(district.external_id), district.name

    return state_id, state_name, district_id, district_name


def _seed_with_demo_pack(facility_id, district_id, requested_by):
    """Attach generic_hospital_v1 to the sandbox facility (sync, in-process)."""
    try:
        from care_demo_facility_setup.services.sandbox_attach import (
            seed_existing_facility,
            summarize_seed_run_counts,
        )
    except ImportError as exc:
        msg = (
            "care_demo_facility_setup is required for full sandbox seeding. "
            "Ensure the plugin is installed and listed in plug_config."
        )
        raise RuntimeError(msg) from exc

    run = seed_existing_facility(
        facility_external_id=facility_id,
        geo_organization_external_id=district_id,
        requested_by=requested_by,
        pack_slug=DEFAULT_DEMO_PACK_SLUG,
    )
    return summarize_seed_run_counts(run)


def build_sandbox(base, sandbox_id, is_facility_empty, facility_name="", server_url=""):
    password = plugin_settings.SANDBOX_DEFAULT_PASSWORD
    short = str(sandbox_id).replace("-", "")[:8]
    facility_name = (facility_name or "").strip() or f"Sandbox Facility {short}"

    state_id, state_name, district_id, district_name = _pick_or_create_geo(base)

    role_orgs = {}
    for role_name, _prefix in SANDBOX_ROLES:
        role_orgs[role_name] = base.create_organization(
            org_type=OrganizationTypeChoices.role.value,
            name=f"{role_name} {short}",
        )

    facility = base.create_facility(
        district_id,
        name=facility_name,
        facility_type="Private Hospital",
    )
    facility_id = facility.id

    administration = next(
        (org for org in base.get_facility_organizations(facility_id) if org.name == "Administration"),
        None,
    )

    # Query RoleModel directly; the role-list API is paginated and can drop roles.
    wanted = [name for name, _ in SANDBOX_ROLES]
    roles = {r.name: r for r in RoleModel.objects.filter(name__in=wanted)}
    missing = [name for name in wanted if name not in roles]
    if missing:
        msg = f"Required roles not found (run sync_permissions_roles): {missing}"
        raise RuntimeError(msg)

    users = []
    for role_name, prefix in SANDBOX_ROLES:
        role_id = str(roles[role_name].external_id)
        username = f"{prefix}-{short}"
        user = base.create_user(
            district_id,
            role_orgs=[
                {
                    "organization": role_orgs[role_name].id,
                    "role": role_id,
                }
            ],
            username=username,
            email=f"{username}@care.test",
            password=password,
        )
        if administration:
            base.add_user_to_facility_organization(facility_id, administration.id, user.id, role_id)
        users.append(
            {
                "username": username,
                "password": password,
                "role": role_name,
                "sign_in_url": server_url,
                "is_primary": role_name == PRIMARY_ROLE,
            }
        )

    # Empty: shell only. Full: attach demo pack to this facility (sync).
    loaded_data = {}
    if not is_facility_empty:
        requested_by = getattr(base, "user", None)
        loaded_data = _seed_with_demo_pack(facility_id, district_id, requested_by)

    return {
        "server": server_url,
        "default_password": password,
        "is_facility_empty": is_facility_empty,
        "facility": {
            "id": facility_id,
            "name": facility.name,
            "type": "Private Hospital",
            "district": district_name,
            "state": state_name,
        },
        "users": users,
        "loaded_data": loaded_data,
    }
