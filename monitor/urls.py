from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'monitoredgroup', views.MonitoredGroupViewSet)
router.register(r'rental-announcements', views.RentalAnnouncementViewSet)
router.register(r'monitored-messages', views.MonitoredMessageViewSet)

urlpatterns = [
    path('', include(router.urls)),
]