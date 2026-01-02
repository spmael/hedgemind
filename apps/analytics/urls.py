"""
URL configuration for analytics app.
"""

from django.urls import path

from apps.analytics import views

app_name = "analytics"

urlpatterns = [
    path("daily-close/", views.run_daily_close, name="run_daily_close"),
    path(
        "runs/<int:run_id>/status/", views.daily_close_status, name="daily_close_status"
    ),
    path("runs/<int:run_id>/mark-official/", views.mark_official, name="mark_official"),
]
