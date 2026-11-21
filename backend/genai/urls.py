from django.urls import path

from . import views

urlpatterns = [
    path("draft-email/", views.DraftEmailView.as_view(), name="genai-draft-email"),
    path("summarize-activity/", views.SummarizeActivityView.as_view(), name="genai-summarize"),
    path("action-items-to-tasks/", views.ActionItemsToTasksView.as_view(), name="genai-to-tasks"),
    path("status/", views.StatusView.as_view(), name="genai-status"),
    path("usage/", views.UsageView.as_view(), name="genai-usage"),
]
