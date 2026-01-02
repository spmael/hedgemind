"""
URL configuration for portfolios app.
"""

from django.urls import path

from apps.portfolios import views

app_name = "portfolios"

urlpatterns = [
    path("upload/", views.upload_holdings, name="upload_holdings"),
    path("imports/<int:import_id>/status/", views.import_status, name="import_status"),
    path("imports/<int:import_id>/preflight/", views.run_preflight, name="run_preflight"),
    path("imports/<int:import_id>/start/", views.start_import, name="start_import"),
    path(
        "imports/<int:import_id>/export-missing/",
        views.export_missing_instruments,
        name="export_missing_instruments",
    ),
]

