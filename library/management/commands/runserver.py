from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import Command as StaticCommand
from django.core.management.base import CommandError


class UncachedDevelopmentHandler:
    def __init__(self, handler):
        self.handler = handler

    def __call__(self, environ, start_response):
        environ.pop("HTTP_IF_MODIFIED_SINCE", None)
        environ.pop("HTTP_IF_NONE_MATCH", None)

        def uncached_response(status, headers, exc_info=None):
            headers = [
                (key, value)
                for key, value in headers
                if key.lower() not in {"cache-control", "etag", "last-modified"}
            ]
            headers.append(("Cache-Control", "no-store"))
            return start_response(status, headers, exc_info)

        return self.handler(environ, uncached_response)


class Command(StaticCommand):
    def get_handler(self, *args, **options):
        if settings.READING_HUB_ENVIRONMENT == "production":
            raise CommandError("Use the configured production WSGI server instead of runserver.")
        handler = super().get_handler(*args, **options)
        if settings.READING_HUB_ENVIRONMENT == "development":
            return UncachedDevelopmentHandler(handler)
        return handler
