"""
URL configuration for organizations app.
"""

from django.urls import path

from apps.organizations import views

app_name = "organizations"

urlpatterns = [
    path("switch/<int:org_id>/", views.switch_organization, name="switch"),
    path("list/", views.list_user_organizations, name="list"),
]

