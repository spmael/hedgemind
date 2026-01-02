"""
URL configuration for reports app.
"""

from django.urls import path

from apps.reports import views

app_name = "reports"

urlpatterns = [
    path("", views.reports_list, name="reports_list"),
    path(
        "<int:report_id>/download/<str:file_type>/",
        views.download_report,
        name="download_report",
    ),
]
