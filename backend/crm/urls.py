from rest_framework.routers import DefaultRouter

from .views import ActivityViewSet, CompanyViewSet, ContactViewSet, LeadViewSet, TaskViewSet

router = DefaultRouter()
router.register("companies", CompanyViewSet, basename="company")
router.register("contacts", ContactViewSet, basename="contact")
router.register("leads", LeadViewSet, basename="lead")
router.register("activities", ActivityViewSet, basename="activity")
router.register("tasks", TaskViewSet, basename="task")

urlpatterns = router.urls
