"""The project's test runner.

Two things the default `DiscoverRunner` gets wrong here, both consequences of
decisions made elsewhere in the project and neither worth reversing:

1. `apps` is a namespace package (no `__init__.py`), which is deliberate. From
   Python 3.11 unittest's discovery no longer walks into one, so a bare
   `python manage.py test` silently finds zero tests — the worst possible
   failure mode for a CI step, because it passes. `build_suite` names the
   local apps explicitly instead of discovering them.

2. `STORAGES["staticfiles"]` is WhiteNoise's manifest storage, which refuses
   to resolve `{% static %}` for any file missing from the manifest. Tests run
   with `DEBUG=False` and CI runs them *before* `collectstatic`, so every page
   render would fail on a manifest that does not exist yet. Tests get plain
   static storage; the manifest is still proven by the collectstatic step.
"""

from django.apps import apps
from django.conf import settings
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings

LOCAL_APP_PREFIX = "apps."


class ProjectTestRunner(DiscoverRunner):
    def build_suite(self, test_labels=None, **kwargs):
        if not test_labels:
            test_labels = [
                f"{config.name}.tests"
                for config in apps.get_app_configs()
                if config.name.startswith(LOCAL_APP_PREFIX)
            ]
        return super().build_suite(test_labels, **kwargs)

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        # override_settings rather than assigning to settings.STORAGES: the
        # staticfiles storage is a lazy object that only rebuilds itself when
        # the setting_changed signal fires.
        self._storage_override = override_settings(
            STORAGES={
                **settings.STORAGES,
                "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
            }
        )
        self._storage_override.enable()

    def teardown_test_environment(self, **kwargs):
        self._storage_override.disable()
        super().teardown_test_environment(**kwargs)
