"""Root URL configuration."""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import path


def health(_request: HttpRequest) -> JsonResponse:
    """Liveness probe. Deliberately says nothing about internals."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz", health, name="health"),
    path("admin/", admin.site.urls),
]
