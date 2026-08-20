from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _

PLUGIN_NAME = "care_experience_sandbox_be"


class CareExperienceSandboxConfig(AppConfig):
    name = PLUGIN_NAME
    verbose_name = _("Care experience sandbox")

    def ready(self):
        import care_experience_sandbox_be.signals  # noqa F401
