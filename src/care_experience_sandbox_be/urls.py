from django.conf import settings
from django.shortcuts import HttpResponse
from django.urls import path
from rest_framework.routers import DefaultRouter, SimpleRouter

from care_experience_sandbox_be.api.viewsets import SandboxViewSet


def healthy(request):
    return HttpResponse("OK")


router = DefaultRouter() if settings.DEBUG else SimpleRouter()
router.register(r"sandbox", SandboxViewSet, basename="care_experience_sandbox_be-sandbox")

urlpatterns = [
    path("health", healthy),
] + router.urls
