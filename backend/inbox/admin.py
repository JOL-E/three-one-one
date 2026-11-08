"""Django admin: a developer's view of the data.

The admin writes to the models directly, past the services, so it can break
rules the services enforce (the database constraints still hold). The real UI
for the owner is the React app (M4).
"""

from django.contrib import admin

from .models import Activity, Item, Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["name", "state", "is_general", "created_at"]
    list_filter = ["state"]


class ActivityInline(admin.TabularInline):  # type: ignore[type-arg]
    model = Activity
    extra = 0
    can_delete = False
    readonly_fields = ["created_at", "author", "kind", "text", "old_value", "new_value"]

    def has_add_permission(self, request, obj=None):  # type: ignore[no-untyped-def]
        return False  # append-only, written by the services


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ["title", "project", "status", "position", "created_at"]
    list_filter = ["status", "project"]
    inlines = [ActivityInline]
