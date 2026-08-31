"""Unit tests for sandbox builder demo-pack wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

from care_experience_sandbox_be.sandbox.builder import (
    DEFAULT_DEMO_PACK_SLUG,
    _seed_with_demo_pack,
    build_sandbox,
)


class SeedWithDemoPackTests(TestCase):
    def test_calls_attach_service_sync(self):
        run = SimpleNamespace(external_id="run-1")
        with (
            patch(
                "care_demo_facility_setup.services.sandbox_attach.seed_existing_facility",
                return_value=run,
            ) as seed_fn,
            patch(
                "care_demo_facility_setup.services.sandbox_attach.summarize_seed_run_counts",
                return_value={"patients": 10},
            ) as summarize,
        ):
            loaded = _seed_with_demo_pack(
                "fac-1",
                "geo-1",
                SimpleNamespace(is_superuser=True),
            )

        seed_fn.assert_called_once_with(
            facility_external_id="fac-1",
            geo_organization_external_id="geo-1",
            requested_by=seed_fn.call_args.kwargs["requested_by"],
            pack_slug=DEFAULT_DEMO_PACK_SLUG,
        )
        summarize.assert_called_once_with(run)
        self.assertNotIn("_meta", loaded)
        self.assertEqual(loaded["patients"], 10)

    def test_clear_error_when_demo_plugin_missing(self):
        import builtins

        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "care_demo_facility_setup.services.sandbox_attach" or (
                name == "care_demo_facility_setup.services" and fromlist and "sandbox_attach" in fromlist
            ):
                raise ImportError("missing plugin")
            return real_import(name, globals, locals, fromlist, level)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaisesRegex(RuntimeError, "care_demo_facility_setup is required"):
                _seed_with_demo_pack("f", "g", SimpleNamespace())


class BuildSandboxEmptyPathTests(TestCase):
    @patch("care_experience_sandbox_be.sandbox.builder.RoleModel")
    @patch("care_experience_sandbox_be.sandbox.builder.Organization")
    def test_empty_skips_demo_pack(self, org_model, role_model):
        org_model.objects.filter.return_value.order_by.return_value.first.side_effect = [
            SimpleNamespace(external_id="state-1", name="Kerala"),
            SimpleNamespace(external_id="dist-1", name="Ernakulam"),
        ]
        role_names = [
            "Administrator",
            "Facility Admin",
            "Doctor",
            "Nurse",
            "Staff",
            "Volunteer",
            "Pharmacist",
        ]
        role_model.objects.filter.return_value = [
            SimpleNamespace(name=name, external_id=f"role-{i}") for i, name in enumerate(role_names)
        ]

        base = MagicMock()
        base.create_organization.side_effect = lambda **kwargs: SimpleNamespace(
            id=f"org-{kwargs['name']}", name=kwargs["name"]
        )
        base.create_facility.return_value = SimpleNamespace(id="fac-1", name="Empty Fac")
        base.get_facility_organizations.return_value = [SimpleNamespace(id="admin-org", name="Administration")]
        base.create_user.side_effect = lambda *a, **k: SimpleNamespace(id=f"user-{k['username']}")
        base.user = SimpleNamespace(is_superuser=True)

        with patch("care_experience_sandbox_be.sandbox.builder._seed_with_demo_pack") as seed:
            result = build_sandbox(
                base,
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                is_facility_empty=True,
                facility_name="Empty Fac",
                server_url="https://care.test",
            )

        seed.assert_not_called()
        self.assertEqual(result["loaded_data"], {})
        self.assertEqual(len(result["users"]), 7)
        self.assertEqual(result["facility"]["id"], "fac-1")

    @patch("care_experience_sandbox_be.sandbox.builder.RoleModel")
    @patch("care_experience_sandbox_be.sandbox.builder.Organization")
    def test_full_calls_demo_pack(self, org_model, role_model):
        org_model.objects.filter.return_value.order_by.return_value.first.side_effect = [
            SimpleNamespace(external_id="state-1", name="Kerala"),
            SimpleNamespace(external_id="dist-1", name="Ernakulam"),
        ]
        role_names = [
            "Administrator",
            "Facility Admin",
            "Doctor",
            "Nurse",
            "Staff",
            "Volunteer",
            "Pharmacist",
        ]
        role_model.objects.filter.return_value = [
            SimpleNamespace(name=name, external_id=f"role-{i}") for i, name in enumerate(role_names)
        ]

        base = MagicMock()
        base.create_organization.side_effect = lambda **kwargs: SimpleNamespace(
            id=f"org-{kwargs['name']}", name=kwargs["name"]
        )
        base.create_facility.return_value = SimpleNamespace(id="fac-1", name="Full Fac")
        base.get_facility_organizations.return_value = [SimpleNamespace(id="admin-org", name="Administration")]
        base.create_user.side_effect = lambda *a, **k: SimpleNamespace(id=f"user-{k['username']}")
        base.user = SimpleNamespace(is_superuser=True)

        with patch(
            "care_experience_sandbox_be.sandbox.builder._seed_with_demo_pack",
            return_value={"patients": 10},
        ) as seed:
            result = build_sandbox(
                base,
                "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                is_facility_empty=False,
                facility_name="Full Fac",
                server_url="https://care.test",
            )

        seed.assert_called_once_with("fac-1", "dist-1", base.user)
        self.assertNotIn("_meta", result["loaded_data"])
        self.assertEqual(result["loaded_data"]["patients"], 10)
        self.assertEqual(len(result["users"]), 7)
