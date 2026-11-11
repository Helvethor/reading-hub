from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from library.models import UserSettings
from library.themes import COOKIE, ThemeForm, selected_theme, theme_payload


def save_theme(request, choice):
    if request.user.is_authenticated:
        UserSettings.objects.update_or_create(user=request.user, defaults={"theme": choice})
    request.reading_hub_theme = choice


def theme_cookie(request, response, choice):
    if choice:
        response.set_cookie(COOKIE, choice, max_age=365 * 24 * 60 * 60,
                            httponly=True, samesite="Lax", secure=request.is_secure())
    else:
        response.delete_cookie(COOKIE, samesite="Lax")
    return response


@require_POST
def change_theme(request):
    form = ThemeForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"error": "Choose an available theme."}, status=400)
    choice = form.cleaned_data["theme"]
    save_theme(request, choice)
    if request.headers.get("Accept") == "application/json":
        response = JsonResponse(theme_payload(request))
    else:
        target = request.POST.get("next", "/")
        if not url_has_allowed_host_and_scheme(
            target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            target = "/"
        response = redirect(target)
    return theme_cookie(request, response, choice)


@login_required
@require_http_methods(["GET", "POST"])
def user_settings(request):
    form = ThemeForm(request.POST if request.method == "POST" else None,
                     initial={"theme": selected_theme(request)})
    if request.method == "POST" and form.is_valid():
        choice = form.cleaned_data["theme"]
        save_theme(request, choice)
        messages.success(request, "Your theme preference has been saved.")
        return theme_cookie(request, redirect("user-settings"), choice)
    return render(request, "registration/settings.html", {"form": form},
                  status=400 if request.method == "POST" else 200)


def administrator_required(view):
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not request.user.is_authenticated:
            if "application/json" in request.headers.get("Accept", ""):
                return JsonResponse({"error": "Your session expired. Sign in again."}, status=401)
            return redirect_to_login(request.get_full_path())
        if not request.user.is_staff:
            if "application/json" in request.headers.get("Accept", ""):
                return JsonResponse({"error": "Administrator access required."}, status=403)
            raise PermissionDenied("Administrator access required.")
        return view(request, *args, **kwargs)

    return guarded


@sensitive_post_parameters("password1", "password2")
@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = UserCreationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save(commit=False)
                first = not get_user_model().objects.exists()
                user.is_staff = user.is_superuser = first
                user.save()
        except IntegrityError:
            if not get_user_model().objects.filter(username=form.cleaned_data["username"]).exists():
                raise
            form.add_error(
                "username", get_user_model()._meta.get_field("username").error_messages["unique"]
            )
        else:
            login(request, user)
            messages.success(
                request,
                "Account created. You are the administrator of this local installation."
                if first
                else "Account created.",
            )
            return redirect("worker-controls" if first else "home")
    return render(
        request,
        "registration/signup.html",
        {
            "form": form,
            "first_account": not get_user_model().objects.exists(),
        },
        status=400 if request.method == "POST" else 200,
    )
