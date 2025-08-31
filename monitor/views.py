from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg
from datetime import datetime, timedelta
from .models import MonitoredGroup, RentalAnnouncement, MonitoredMessage
from .serializers import (
    MonitoredGroupSerializer, 
    RentalAnnouncementSerializer, 
    RentalAnnouncementListSerializer,
    MonitoredMessageSerializer
)


class MonitoredGroupViewSet(viewsets.ModelViewSet):
    queryset = MonitoredGroup.objects.all()
    serializer_class = MonitoredGroupSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['chat_id']
    search_fields = ['title']


class RentalAnnouncementViewSet(viewsets.ModelViewSet):
    queryset = RentalAnnouncement.objects.select_related('group').all()
    serializer_class = RentalAnnouncementSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = [
        'group', 'user_id', 'is_processed', 'is_verified',
        'group__chat_id'
    ]
    search_fields = [
        'message_text', 'first_name', 'last_name', 'username',
        'rental_keywords_found', 'contact_info'
    ]
    ordering_fields = ['created_at', 'confidence_score', 'updated_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RentalAnnouncementListSerializer
        return RentalAnnouncementSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Confidence score bo'yicha filtrlash
        min_confidence = self.request.query_params.get('min_confidence')
        if min_confidence:
            try:
                min_confidence = float(min_confidence)
                queryset = queryset.filter(confidence_score__gte=min_confidence)
            except (ValueError, TypeError):
                pass
        
        # Vaqt oralig'i bo'yicha filtrlash
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(created_at__date__lte=date_to)
            except ValueError:
                pass
        
        # Media mavjudligi bo'yicha filtrlash
        has_media = self.request.query_params.get('has_media')
        if has_media == 'true':
            queryset = queryset.exclude(
                photos_data=[],
                videos_data=[],
                documents_data=[],
                audio_files_data=[],
                voice_messages_data=[]
            )

        
        return queryset
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistik ma'lumotlarni qaytarish"""
        queryset = self.get_queryset()
        
        # Asosiy hisoblar
        total_count = queryset.count()
        verified_count = queryset.filter(is_verified=True).count()
        processed_count = queryset.filter(is_processed=True).count()
        high_confidence_count = queryset.filter(confidence_score__gte=0.7).count()
        
        # Bugungi kunning statistikasi
        today = datetime.now().date()
        today_count = queryset.filter(created_at__date=today).count()
        
        # Oxirgi hafta
        week_ago = datetime.now() - timedelta(days=7)
        week_count = queryset.filter(created_at__gte=week_ago).count()
        
        # Guruhlar bo'yicha statistika
        group_stats = queryset.values('group__title', 'group_id').annotate(
            count=Count('id'),
            avg_confidence=Avg('confidence_score')
        ).order_by('-count')[:10]
        
        # Eng faol foydalanuvchilar
        user_stats = queryset.values('username', 'first_name', 'user_id').annotate(
            count=Count('id'),
            avg_confidence=Avg('confidence_score')
        ).order_by('-count')[:10]
        
        # Ishonch darajasi bo'yicha taqsimot
        confidence_distribution = {
            'very_high': queryset.filter(confidence_score__gte=0.8).count(),
            'high': queryset.filter(confidence_score__gte=0.6, confidence_score__lt=0.8).count(),
            'medium': queryset.filter(confidence_score__gte=0.4, confidence_score__lt=0.6).count(),
            'low': queryset.filter(confidence_score__lt=0.4).count(),
        }
        
        return Response({
            'total_announcements': total_count,
            'verified_announcements': verified_count,
            'processed_announcements': processed_count,
            'high_confidence_announcements': high_confidence_count,
            'today_announcements': today_count,
            'week_announcements': week_count,
            'confidence_distribution': confidence_distribution,
            'top_groups': group_stats,
            'top_users': user_stats
        })
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Ijara elonini tasdiqlash"""
        announcement = self.get_object()
        announcement.is_verified = True
        announcement.is_processed = True
        announcement.save()
        
        return Response({
            'message': 'Announcement verified successfully',
            'is_verified': announcement.is_verified
        })
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Ijara elonini rad etish"""
        announcement = self.get_object()
        announcement.is_verified = False
        announcement.is_processed = True
        announcement.save()
        
        return Response({
            'message': 'Announcement rejected',
            'is_verified': announcement.is_verified
        })
    
    @action(detail=False, methods=['get'])
    def unprocessed(self, request):
        """Qayta ishlanmagan elonlarni olish"""
        queryset = self.get_queryset().filter(is_processed=False)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def high_confidence(self, request):
        """Yuqori ishonch darajasiga ega elonlar"""
        min_confidence = float(request.query_params.get('min_confidence', 0.7))
        queryset = self.get_queryset().filter(confidence_score__gte=min_confidence)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MonitoredMessageViewSet(viewsets.ModelViewSet):
    """Eski monitoring system uchun (agar kerak bo'lsa)"""
    queryset = MonitoredMessage.objects.select_related('group').all()
    serializer_class = MonitoredMessageSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['group', 'user_id', 'contains_keyword']
    search_fields = ['message_text', 'first_name', 'username']
    ordering_fields = ['created_at']
    ordering = ['-created_at']