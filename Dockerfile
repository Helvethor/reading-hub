# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e
ARG PYTHON_IMAGE=python:3.14.8-slim-bookworm@sha256:44e000a07b48bef1517a2b14adc93c17af728ca98858b5e24c6e1b18de1b2ef2
ARG NODE_IMAGE=node:22-bookworm-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee

FROM ${NODE_IMAGE} AS frontend-assets
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY frontend/ ./frontend/
COPY library/static/library/ ./library/static/library/
RUN npm run build

FROM ${PYTHON_IMAGE} AS runtime-base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN sed -i \
        -e 's|http://deb.debian.org/debian-security|https://snapshot.debian.org/archive/debian-security/20261021T000000Z|' \
        -e 's|http://deb.debian.org/debian|https://snapshot.debian.org/archive/debian/20261021T000000Z|' \
        /etc/apt/sources.list.d/debian.sources \
    && printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99snapshot \
    && apt-get update \
    && apt-get install --no-install-recommends -y \
        fontconfig \
        fonts-noto-core \
        libffi8 \
        libfontconfig1 \
        libgdk-pixbuf-2.0-0 \
        libharfbuzz-subset0 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        shared-mime-info \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /tmp/requirements.lock
RUN grep -Ev '^(pypdf|ruff)==' /tmp/requirements.lock > /tmp/requirements-runtime.lock \
    && python -m pip install --no-cache-dir -r /tmp/requirements-runtime.lock \
    && python -m pip check \
    && groupadd --system --gid 10001 readinghub \
    && useradd --system --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin readinghub \
    && install -d -o 10001 -g 10001 /app /app/staticfiles /var/lib/reading-hub
WORKDIR /app

FROM runtime-base AS application-source
COPY --chown=10001:10001 config/ ./config/
COPY --chown=10001:10001 library/ ./library/
COPY --chown=10001:10001 profiles/ ./profiles/
COPY --chown=10001:10001 manage.py container_healthcheck.py ./

FROM application-source AS static-assets
ENV DJANGO_SETTINGS_MODULE=config.production_settings \
    READING_HUB_ENVIRONMENT=production \
    READING_HUB_DATA=/tmp/reading-hub-static-data \
    READING_HUB_STATIC_ROOT=/app/staticfiles
COPY --from=frontend-assets --chown=10001:10001 /build/library/static/library/generated/ ./library/static/library/generated/
RUN python manage.py collectstatic --noinput

FROM runtime-base AS production
WORKDIR /app
COPY --from=application-source --chown=10001:10001 /app/ /app/
COPY --from=frontend-assets --chown=10001:10001 /build/library/static/library/generated/ ./library/static/library/generated/
COPY --from=static-assets --chown=10001:10001 /app/staticfiles/ ./staticfiles/
ARG SOURCE_REVISION
RUN test -n "$SOURCE_REVISION"
ENV DJANGO_SETTINGS_MODULE=config.production_settings \
    READING_HUB_ENVIRONMENT=production \
    READING_HUB_DATA=/var/lib/reading-hub \
    READING_HUB_STATIC_ROOT=/app/staticfiles \
    XDG_CACHE_HOME=/tmp/.cache \
    READING_HUB_REVISION=${SOURCE_REVISION}
LABEL org.opencontainers.image.revision="${SOURCE_REVISION}"
EXPOSE 8000
VOLUME ["/var/lib/reading-hub"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "container_healthcheck.py"]
USER 10001:10001
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--access-logfile", "-", "config.production_wsgi:application"]
