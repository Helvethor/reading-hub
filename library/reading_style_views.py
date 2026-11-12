import json

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from library.models import (
    ReadingStyleAccountDefault,
    ReadingStyleOutputOverride,
    ReadingStyleProfile,
    Rendition,
)
from library.services.reading_styles import (
    DEFAULTS,
    apply_layer_changes,
    normalize_work_type,
    profile_key,
    resolve_style,
    rendition_work_type,
    selected_style,
    style_context,
    style_presentation_token,
    style_css,
    style_token,
    stylesheet_url,
    token_style,
    validate_style,
    validate_style_layer,
    work_type_keys,
)
from library.themes import profile_for_theme, selected_theme


def _request_data(request):
    if request.content_type == "application/json":
        if len(request.body) > 32768:
            raise ValueError("The reading style request is too large.")
        try:
            data = json.loads(request.body)
        except (TypeError, ValueError, UnicodeDecodeError) as exc:
            raise ValueError("Send a valid reading style request.") from exc
    else:
        data = request.POST.dict()
    if not isinstance(data, dict):
        raise ValueError("Send a reading style object.")
    return data


def _preference_layer(user, rendition, work_type, scope):
    if scope == "account":
        return (ReadingStyleAccountDefault.objects.filter(
            owner=user, work_type=work_type,
        ).values_list("settings", flat=True).first() or {})
    return (ReadingStyleOutputOverride.objects.filter(
        owner=user, rendition=rendition,
    ).values_list("settings", flat=True).first() or {})


def _store_preference_layer(user, rendition, work_type, scope, settings):
    if scope == "account":
        model, lookup = ReadingStyleAccountDefault, {"owner": user, "work_type": work_type}
    else:
        model, lookup = ReadingStyleOutputOverride, {"owner": user, "rendition": rendition}
    if settings:
        model.objects.update_or_create(**lookup, defaults={"settings": settings})
    else:
        model.objects.filter(**lookup).delete()


def _style_result(request, data, *, rendition=None, work_type=None, guest_overrides=None):
    scope = data.get("scope", "output")
    if scope not in {"output", "account"}:
        raise ValueError("Choose This version or My defaults.")
    if scope == "account" and not request.user.is_authenticated:
        raise ValueError("Sign in to save My defaults across devices.")
    if scope == "output" and rendition is None:
        raise ValueError("Choose an exact version before changing This version.")
    if work_type is None:
        work_type = rendition_work_type(rendition)
    if work_type not in work_type_keys():
        raise ValueError("Choose an available work type.")

    changes = data.get("changes", {})
    reset = data.get("reset", [])
    if not isinstance(changes, dict) or not isinstance(reset, list):
        raise ValueError("Style changes and resets must be objects and lists.")
    changes = validate_style_layer(changes)
    current_layer = (
        _preference_layer(request.user, rendition, work_type, scope)
        if request.user.is_authenticated else validate_style_layer(guest_overrides or {})
    )
    updated_layer = apply_layer_changes(current_layer, changes, reset)
    changed = bool(changes or reset)
    persisted = False
    if changed and request.user.is_authenticated:
        with transaction.atomic():
            _store_preference_layer(request.user, rendition, work_type, scope, updated_layer)
        persisted = True
    elif changed:
        guest_overrides = updated_layer

    resolved = resolve_style(
        work_type,
        user=request.user,
        rendition=rendition,
        guest_overrides=guest_overrides if not request.user.is_authenticated else None,
    )
    theme = selected_theme(request)
    token = style_token(resolved["settings"])
    return {
        "settings": resolved["settings"],
        "origins": resolved["origins"],
        "layer": updated_layer if scope == "output" or request.user.is_authenticated else {},
        "layers": resolved["layers"],
        "overridden": sorted(updated_layer if request.user.is_authenticated or changed else {}),
        "work_type": resolved["work_type"],
        "output_id": resolved["output_id"],
        "rendition_id": resolved["rendition_id"],
        "scope": scope,
        "theme": theme,
        "token": token,
        "presentation": style_presentation_token(
            resolved["settings"], theme, work_type=resolved["work_type"],
            origins=resolved["origins"],
        ),
        "stylesheet": stylesheet_url(token, theme),
        "persisted": request.user.is_authenticated,
        "updated": persisted,
        "guest": not request.user.is_authenticated,
    }


@require_http_methods(["GET", "POST"])
def preview(request):
    try:
        data = _request_data(request) if request.method == "POST" else request.GET.dict()
        rendition_id = data.get("rendition_id")
        rendition = None
        if rendition_id:
            if not str(rendition_id).isascii() or not str(rendition_id).isdecimal():
                raise ValueError("Choose an available exact version.")
            rendition = get_object_or_404(Rendition, pk=int(rendition_id))
        if data.get("work_type") is not None:
            work_type = data["work_type"]
        else:
            work_type = rendition_work_type(rendition)
        guest_overrides = data.get("guest_overrides", {})
        if not isinstance(guest_overrides, dict):
            raise ValueError("Guest style settings must be an object.")
        result = _style_result(
            request, data, rendition=rendition, work_type=work_type,
            guest_overrides=guest_overrides,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    response = JsonResponse(result)
    response["Cache-Control"] = "no-store"
    response["Vary"] = "Cookie"
    return response


@require_POST
@login_required
def import_legacy_profile(request):
    try:
        data = _request_data(request)
        key = profile_key(str(data.get("profile_id", "")))
        work_type = data.get("work_type")
        if work_type not in work_type_keys():
            raise ValueError("Choose an available work type.")
        profile = get_object_or_404(ReadingStyleProfile, pk=key, owner=request.user)
        settings = validate_style(profile.settings)
        _store_preference_layer(request.user, None, work_type, "account", settings)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({
        "imported": True,
        "profile": profile.name,
        "work_type": work_type,
        "message": f'“{profile.name}” was copied to My defaults for {work_type}. '
                   "The legacy profile and its ownership remain unchanged.",
    })


@require_POST
@login_required
def import_guest(request):
    try:
        data = _request_data(request)
        rendition_id = data.get("rendition_id")
        if not isinstance(rendition_id, int) or rendition_id < 1:
            raise ValueError("Choose an exact version for the guest settings.")
        rendition = get_object_or_404(Rendition, pk=rendition_id)
        guest = validate_style_layer(data.get("settings"))
        if not guest:
            raise ValueError("There are no guest settings to import.")
        current = _preference_layer(request.user, rendition, "", "output")
        merged = {**validate_style_layer(current), **guest}
        _store_preference_layer(request.user, rendition, "", "output", merged)
        resolved = resolve_style(
            rendition_work_type(rendition), user=request.user, rendition=rendition,
        )
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    token = style_token(resolved["settings"])
    theme = selected_theme(request)
    return JsonResponse({
        "settings": resolved["settings"],
        "origins": resolved["origins"],
        "layer": merged,
        "overridden": sorted(merged),
        "work_type": resolved["work_type"],
        "token": token,
        "presentation": style_presentation_token(
            resolved["settings"], theme, work_type=resolved["work_type"],
            origins=resolved["origins"],
        ),
        "stylesheet": stylesheet_url(token, theme),
        "message": "Guest style choices were explicitly imported for this exact version.",
    })


@require_GET
def stylesheet(request):
    try:
        settings = token_style(request.GET.get("style", ""))
        theme = request.GET.get("theme", "")
        profile = profile_for_theme(theme)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc), content_type="text/plain")
    response = HttpResponse(style_css(settings, profile=profile),
                            content_type="text/css; charset=utf-8")
    response["Cache-Control"] = "no-store"
    return response


@require_POST
@login_required
def save_profile(request, pk):
    version = get_object_or_404(Rendition, pk=pk)
    try:
        settings = token_style(request.POST.get("style", ""))
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    name = request.POST.get("profile_name", "").strip()
    operation = request.POST.get("operation", "")
    if request.POST.get("make_default") == "on":
        return HttpResponse(
            "Legacy profile defaults are preserved but no longer applied. "
            "Import a profile explicitly into My defaults for a work type.",
            status=410,
        )
    target = None
    if operation == "update":
        try:
            key = profile_key(request.POST.get("profile_id", ""))
        except ValueError as exc:
            return HttpResponseBadRequest(str(exc))
        target = get_object_or_404(ReadingStyleProfile, pk=key, owner=request.user)
        name = target.name
    elif operation not in {"", "create"}:
        return HttpResponseBadRequest("Choose Save as new or Update profile.")
    errors = []
    if not name or len(name) > 100 or any(ord(char) < 32 for char in name):
        errors.append("Give your profile a name of 1–100 characters without control characters.")
    if name.casefold() == "marxist":
        errors.append("The shared Marxist preset is read-only. Choose a personal profile name.")
    if errors:
        if request.headers.get("Accept") == "application/json":
            return JsonResponse({"error": " ".join(errors)}, status=400)
        return render(request, "library/reading_style_error.html",
                      {"version": version, "style_errors": errors}, status=400)
    try:
        with transaction.atomic():
            # Serialize default changes for one user, even when there are no profiles yet.
            get_user_model().objects.filter(pk=request.user.pk).update(id=F("id"))
            if target:
                target.refresh_from_db()
            if operation == "create" and ReadingStyleProfile.objects.filter(
                owner=request.user, name=name,
            ).exists():
                return HttpResponse(
                    "A profile with this name exists. Choose it and use Update profile.",
                    status=409,
                )
            if request.POST.get("make_default") == "on":
                ReadingStyleProfile.objects.filter(owner=request.user, is_default=True).update(
                    is_default=False,
                )
            changes = {
                "settings": settings,
                **({"is_default": True} if request.POST.get("make_default") == "on" else {}),
            }
            if target:
                target.settings = settings
                if request.POST.get("make_default") == "on":
                    target.is_default = True
                target.save(update_fields=["settings", "is_default", "updated_at"])
                profile = target
            elif operation == "create":
                profile = ReadingStyleProfile.objects.create(
                    owner=request.user, name=name, **changes,
                )
            else:
                profile, _ = ReadingStyleProfile.objects.update_or_create(
                    owner=request.user, name=name, defaults=changes,
                )
    except IntegrityError:
        if request.headers.get("Accept") == "application/json":
            return JsonResponse({"error": "Another profile save conflicted. Reload and retry."},
                                status=409)
        messages.error(request, "Another profile save conflicted. Reload and retry.")
        return redirect("reader", pk=pk)
    if request.headers.get("Accept") == "application/json":
        return JsonResponse({"id": profile.pk, "name": profile.name,
                             "default": style_context(request)["reading_default_profile"]})
    messages.success(request, f'Reading style "{profile.name}" saved for reuse.')
    return redirect(reverse("reader", args=[pk]) + f"?style_profile={profile.pk}")


@require_POST
@login_required
def default_profile(request, pk):
    return HttpResponse(
        "Legacy global profile defaults are preserved but no longer applied. "
        "Import a profile explicitly into My defaults for a work type.",
        status=410,
    )
