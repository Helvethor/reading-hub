from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from library.models import ReadingStyleProfile, Rendition
from library.services.reading_styles import (
    profile_key,
    style_css,
    style_token,
    token_style,
)


@require_GET
def stylesheet(request):
    try:
        settings = token_style(request.GET.get("style", ""))
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc), content_type="text/plain")
    return HttpResponse(style_css(settings), content_type="text/css; charset=utf-8")


@require_POST
@login_required
def save_profile(request, pk):
    version = get_object_or_404(Rendition, pk=pk)
    try:
        settings = token_style(request.POST.get("style", ""))
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    name = request.POST.get("profile_name", "").strip()
    errors = []
    if not name or len(name) > 100 or any(ord(char) < 32 for char in name):
        errors.append("Give your profile a name of 1–100 characters without control characters.")
    if name.casefold() == "marxist":
        errors.append("The shared Marxist preset is read-only. Choose a personal profile name.")
    if errors:
        return render(request, "library/reading_style_error.html",
                      {"version": version, "style_errors": errors}, status=400)
    try:
        with transaction.atomic():
            # Serialize default changes for one user, even when there are no profiles yet.
            get_user_model().objects.filter(pk=request.user.pk).update(id=F("id"))
            if request.POST.get("make_default") == "on":
                ReadingStyleProfile.objects.filter(owner=request.user, is_default=True).update(
                    is_default=False,
                )
            profile, _ = ReadingStyleProfile.objects.update_or_create(
                owner=request.user, name=name,
                defaults={
                    "settings": settings,
                    **({"is_default": True} if request.POST.get("make_default") == "on" else {}),
                },
            )
    except IntegrityError:
        messages.error(request, "Another profile save conflicted. Reload and retry.")
        return redirect("reader", pk=pk)
    messages.success(request, f'Reading style "{profile.name}" saved for reuse.')
    return redirect(reverse("reader", args=[pk]) + "?style=" + style_token(settings))


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
    messages.success(request, "Default reading style updated for all your publications.")
    return redirect(reverse("reader", args=[pk]) + "?style_profile=" + choice)
