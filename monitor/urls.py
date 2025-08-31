from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'monitoredgroup', views.MonitoredGroupViewSet)
router.register(r'rental-announcements', views.RentalAnnouncementViewSet)
router.register(r'monitored-messages', views.MonitoredMessageViewSet)  # Eski system

urlpatterns = [
    path('', include(router.urls)),
]

# Yoki alohida URL'lar:
# urlpatterns = [
#     path('api/groups/', views.MonitoredGroupViewSet.as_view({'get': 'list', 'post': 'create'})),
#     path('api/rental-announcements/', views.RentalAnnouncementViewSet.as_view({'get': 'list', 'post': 'create'})),
#     path('api/rental-announcements/<int:pk>/', views.RentalAnnouncementViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update'})),
#     path('api/rental-announcements/statistics/', views.RentalAnnouncementViewSet.as_view({'get': 'statistics'})),
#     path('api/rental-announcements/unprocessed/', views.RentalAnnouncementViewSet.as_view({'get': 'unprocessed'})),
#     path('api/rental-announcements/<int:pk>/verify/', views.RentalAnnouncementViewSet.as_view({'post': 'verify'})),
#     path('api/rental-announcements/<int:pk>/reject/', views.RentalAnnouncementViewSet.as_view({'post': 'reject'})),
# ]