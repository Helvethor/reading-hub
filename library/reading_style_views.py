from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from library.models import ReadingStyleProfile, Rendition
from library.services.reading_styles import (
    profile_key,
    selected_style,
    style_context,
    style_css,
    style_token,
    stylesheet_url,
    token_style,
)


@require_GET
def preview(request):
    try:
        settings = selected_style(request)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    token = style_token(settings)
    response = JsonResponse({
        "settings": settings, "token": token,
        "stylesheet": stylesheet_url(token),
    })
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def stylesheet(request):
    try:
        settings = token_style(request.GET.get("style", ""))
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc), content_type="text/plain")
    from library.themes import themed_profile

    response = HttpResponse(style_css(settings, profile=themed_profile(request)),
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
    get_object_or_404(Rendition, pk=pk)
    choice = request.POST.get("style_profile", "")
    with transaction.atomic():
        get_user_model().objects.filter(pk=request.user.pk).update(id=F("id"))
        profile = None
        if choice != "marxist":
            try:
                key = profile_key(choice)
            except ValueError as exc:
                return HttpResponseBadRequest(str(exc))
            profile = get_object_or_404(ReadingStyleProfile, pk=key, owner=request.user)
        ReadingStyleProfile.objects.filter(owner=request.user, is_default=True).update(
            is_default=False,
        )
        if profile:
            profile.is_default = True
            profile.save(update_fields=["is_default"])
    if request.headers.get("Accept") == "application/json":
        return JsonResponse({"default": choice})
    messages.success(request, "Default reading style updated for all your publications.")
    return redirect(reverse("reader", args=[pk]) + "?style_profile=" + choice)
