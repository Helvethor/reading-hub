from django.apps import AppConfig


class LibraryConfig(AppConfig):
    name = "library"

    def ready(self):
        from library.profile import get_profile

        get_profile().validate()
