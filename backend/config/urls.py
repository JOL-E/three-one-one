from django.contrib import admin
from django.urls import path
from ninja import NinjaAPI

api = NinjaAPI(title="311")


@api.get("/health")
def health(request: object) -> dict[str, str]:
    return {"status": "ok"}


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
