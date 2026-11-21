from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("runs", views.AgentRunViewSet, basename="agent-run")

approve = views.StepDecisionView.as_view(approve=True)
reject = views.StepDecisionView.as_view(approve=False)

urlpatterns = [
    path("steps/<int:pk>/approve/", approve, name="agent-step-approve"),
    path("steps/<int:pk>/reject/", reject, name="agent-step-reject"),
    *router.urls,
]
