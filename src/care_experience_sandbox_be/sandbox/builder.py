from care.emr.models.organization import Organization
from care.emr.resources.encounter.constants import StatusChoices
from care.emr.resources.location.spec import (
    FacilityLocationFormChoices,
    FacilityLocationModeChoices,
)
from care.emr.resources.organization.spec import OrganizationTypeChoices
from care.fixtures.base import AttributeDict
from care.fixtures.billing import load_billing
from care.fixtures.constants import FACILITY_DEPARTMENTS, INVENTORY_ITEMS, LAB_TESTS
from care.fixtures.scripts.default_fixtures import (
    load_inventory,
    load_lab_definitions,
    load_scheduling,
)
from care.security.models import RoleModel
from django.db import transaction

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

SEED_PATIENT_COUNT = 10
SEED_DEVICE_COUNT = 5
SEED_BED_COUNT = 5
SEED_SUPPLIER_COUNT = 3


def _pick_or_create_geo(base):
    """Reuse the first existing state and its first district; create defaults if none."""
    govt = OrganizationTypeChoices.govt.value
    state = (
        Organization.objects.filter(org_type=govt, parent__isnull=True)
        .order_by("id")
        .first()
    )
    if state is None:
        resp = base.create_organization(org_type=govt, name="Kerala")
        state_id, state_name = resp.id, resp.name
    else:
        state_id, state_name = str(state.external_id), state.name

    district = (
        Organization.objects.filter(org_type=govt, parent__external_id=state_id)
        .order_by("id")
        .first()
    )
    if district is None:
        resp = base.create_organization(
            org_type=govt, name="Ernakulam", parent=state_id
        )
        district_id, district_name = resp.id, resp.name
    else:
        district_id, district_name = str(district.external_id), district.name

    return state_id, state_name, district_id, district_name


def _seed_full_facility(
    base, facility_id, district_id, administration, roles_map, created_users, short
):
    """Mirror the facility-scoped seeding of care's load_fixtures into this sandbox."""
    loaded_data = {}

    departments = {}
    if administration:
        departments["Administration"] = administration
    for name in FACILITY_DEPARTMENTS:
        departments[name] = base.create_facility_organization(facility_id, name=name)
    loaded_data["departments"] = len(departments)
    general_medicine = departments["General Medicine"]

    ward = base.create_location(
        facility_id,
        name="Ward A",
        form=FacilityLocationFormChoices.wa.value,
        mode=FacilityLocationModeChoices.kind.value,
        organizations=[general_medicine.id],
    )
    for idx in range(1, SEED_BED_COUNT + 1):
        base.create_location(
            facility_id,
            name=f"Bed {idx}",
            description=f"Bed {idx} in {ward.name}",
            parent=ward.id,
            form=FacilityLocationFormChoices.bd.value,
            mode=FacilityLocationModeChoices.instance.value,
            organizations=[general_medicine.id],
        )
    loaded_data["locations"] = 1 + SEED_BED_COUNT

    for i in range(1, SEED_DEVICE_COUNT + 1):
        base.create_device(facility_id, registered_name=f"Device {i} {short}")
    loaded_data["devices"] = SEED_DEVICE_COUNT

    patients = []
    encounters = {}
    for _ in range(SEED_PATIENT_COUNT):
        patient = base.create_patient(district_id)
        patients.append(patient)
        encounters[patient.id] = base.create_encounter(
            patient.id,
            facility_id,
            organizations=[general_medicine.id],
            status=StatusChoices.in_progress.value,
        )
    loaded_data["patients"] = len(patients)
    loaded_data["encounters"] = len(encounters)

    suppliers = []
    for i in range(1, SEED_SUPPLIER_COUNT + 1):
        suppliers.append(
            base.create_organization(
                org_type=OrganizationTypeChoices.product_supplier.value,
                name=f"Supplier {i} {short}",
            )
        )

    # Doctor already sits on Administration; hide it so load_scheduling won't re-add.
    scheduling_departments = {
        name: org for name, org in departments.items() if name != "Administration"
    }

    def _run(label, fn):
        # Savepoint so one heavy loader failing does not abort the whole sandbox.
        try:
            with transaction.atomic():
                fn()
            loaded_data[label] = True
        except Exception:  # noqa: BLE001
            loaded_data[label] = False

    _run(
        "lab_definitions",
        lambda: load_lab_definitions(base, facility_id, departments),
    )
    if loaded_data.get("lab_definitions"):
        loaded_data["lab_tests"] = len(LAB_TESTS)

    _run(
        "inventory",
        lambda: load_inventory(base, facility_id, departments, suppliers, ward),
    )
    if loaded_data.get("inventory"):
        loaded_data["inventory_items"] = len(INVENTORY_ITEMS)

    _run("billing", lambda: load_billing(base, facility_id, patients, encounters))
    _run(
        "scheduling",
        lambda: load_scheduling(
            base,
            facility_id,
            created_users,
            patients,
            scheduling_departments,
            roles_map,
        ),
    )
    _run(
        "report_templates",
        lambda: base.load_templates_from_file(facility=facility_id),
    )
    _run(
        "questionnaires",
        lambda: base.load_questionnaires_from_file([district_id]),
    )

    return loaded_data


def build_sandbox(
    base, sandbox_id, is_facility_empty, facility_name="", server_url=""
):
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
        (
            org
            for org in base.get_facility_organizations(facility_id)
            if org.name == "Administration"
        ),
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
    created_users = {}
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
        created_users[role_name] = user
        if administration:
            base.add_user_to_facility_organization(
                facility_id, administration.id, user.id, role_id
            )
        users.append(
            {
                "username": username,
                "password": password,
                "role": role_name,
                "sign_in_url": server_url,
                "is_primary": role_name == PRIMARY_ROLE,
            }
        )

    # Shape roles like base.get_roles() (.id == external_id) for the care loaders.
    roles_map = {
        name: AttributeDict({"id": str(r.external_id), "name": name})
        for name, r in roles.items()
    }

    # Empty facilities load nothing; full facilities mirror care's load_fixtures.
    loaded_data = {}
    if not is_facility_empty:
        loaded_data = _seed_full_facility(
            base,
            facility_id,
            district_id,
            administration,
            roles_map,
            created_users,
            short,
        )

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
