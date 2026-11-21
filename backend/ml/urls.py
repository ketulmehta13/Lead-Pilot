from django.urls import path

from . import views

urlpatterns = [
    path("score-lead/<int:pk>/", views.ScoreLeadView.as_view(), name="ml-score-lead"),
    path("metrics/", views.MetricsView.as_view(), name="ml-metrics"),
    path("forecast/", views.ForecastView.as_view(), name="ml-forecast"),
    path("segments/", views.SegmentsView.as_view(), name="ml-segments"),
    path("retrain/", views.RetrainView.as_view(), name="ml-retrain"),
    path("rescore-all/", views.RescoreAllView.as_view(), name="ml-rescore-all"),
    path("classify-ticket/", views.ClassifyTicketView.as_view(), name="ml-classify-ticket"),
]
