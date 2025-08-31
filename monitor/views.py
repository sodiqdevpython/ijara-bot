from rest_framework import viewsets, filters
from django.core.files.base import ContentFile
import requests
from django.utils import timezone
from django.shortcuts import render
from rest_framework.decorators import action
from rest_framework.response import Response
from django.http import JsonResponse
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Avg, Max
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from .forms import QuickVerifyForm, AnnouncementFilterForm
from django.db.models import Q
from datetime import datetime, timedelta
from .models import MonitoredGroup, RentalAnnouncement, MonitoredMessage, RentalPhoto, MediaFile
from .serializers import (
    MonitoredGroupSerializer, 
    RentalAnnouncementSerializer, 
    RentalAnnouncementListSerializer,
    MonitoredMessageSerializer
)

TELEGRAM_BOT_TOKEN = "7413765945:AAHqyNsG2tvyUt0XgBd5OT0FuTA94t1SpEc"

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
    
    def perform_create(self, serializer):
        # avval asosiy e’lonni saqlaymiz
        announcement = serializer.save()

        # agar rasmlar bo‘lsa
        for photo in announcement.photos:
            file_id = photo.get("file_id")
            if not file_id:
                continue

            # 1. Telegram’dan fayl path olish
            file_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
            r = requests.get(file_info_url)
            result = r.json().get("result")

            if not result:
                continue

            file_path = result["file_path"]
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            print("PHOTO URL:", file_url)   # log uchun

            # 2. Faylni yuklab olish va DB ga saqlash
            file_response = requests.get(file_url)
            if file_response.status_code == 200:
                filename = file_path.split("/")[-1]
                rental_photo = RentalPhoto(announcement=announcement)
                rental_photo.image.save(filename, ContentFile(file_response.content), save=True)
    
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
            queryset = queryset.filter(
                Q(photos__isnull=False) | Q(videos__isnull=False) | 
                Q(documents__isnull=False) | Q(audio_files__isnull=False) |
                Q(voice_messages__isnull=False)
            ).exclude(
                photos=[], videos=[], documents=[], 
                audio_files=[], voice_messages=[]
            )
        
        return queryset
    
    @action(detail=True, methods=["get"])
    def photo_urls(self, request, pk=None):
        announcement = self.get_object()
        urls = get_photo_urls(announcement)
        
        # Debug uchun konsolga chiqarib yuborish
        for url in urls:
            print(url)

        return Response({"photo_urls": urls})
    
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
    @action(detail=True, methods=["post"])
    def add_telegram_photo(self, request, pk=None):
        announcement = self.get_object()
        file_id = request.data.get("file_id")

        if not file_id:
            return Response({"error": "file_id is required"}, status=400)

        photo = save_telegram_photo(announcement, file_id)
        if photo:
            return Response({"status": "success", "photo_id": photo.id})
        return Response({"status": "error"}, status=400)


class MonitoredMessageViewSet(viewsets.ModelViewSet):
    """Eski monitoring system uchun (agar kerak bo'lsa)"""
    queryset = MonitoredMessage.objects.select_related('group').all()
    serializer_class = MonitoredMessageSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    filterset_fields = ['group', 'user_id', 'contains_keyword']
    search_fields = ['message_text', 'first_name', 'username']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    

def dashboard_view(request):
    """Dashboard sahifasi"""
    # Bugungi sana
    today = datetime.now().date()
    
    # Bugungi e'lonlar soni
    today_announcements_count = RentalAnnouncement.objects.filter(
        created_at__date=today
    ).count()
    
    # Tasdiqlangan e'lonlar soni (bugun)
    today_verified_count = RentalAnnouncement.objects.filter(
        created_at__date=today,
        is_verified=True
    ).count()
    
    # Yuqori ishonch darajasiga ega e'lonlar (bugun)
    today_high_confidence = RentalAnnouncement.objects.filter(
        created_at__date=today,
        confidence_score__gte=0.7
    ).count()
    
    # Qayta ishlanmagan e'lonlar soni
    unprocessed_count = RentalAnnouncement.objects.filter(
        is_processed=False
    ).count()
    
    # Oxirgi 7 kunlik statistika
    last_7_days = []
    announcement_counts = []
    verified_counts = []
    
    for i in range(6, -1, -1):
        date = today - timedelta(days=i)
        last_7_days.append(date.strftime('%m-%d'))
        
        daily_count = RentalAnnouncement.objects.filter(
            created_at__date=date
        ).count()
        announcement_counts.append(daily_count)
        
        daily_verified = RentalAnnouncement.objects.filter(
            created_at__date=date,
            is_verified=True
        ).count()
        verified_counts.append(daily_verified)
    
    # Top guruhlar (oxirgi 7 kun)
    week_ago = today - timedelta(days=7)
    top_groups = RentalAnnouncement.objects.filter(
        created_at__date__gte=week_ago
    ).values(
        'group__title', 'group__chat_id'
    ).annotate(
        count=Count('id'),
        avg_confidence=Avg('confidence_score')
    ).order_by('-count')[:5]
    
    # So'nggi e'lonlar
    recent_announcements = RentalAnnouncement.objects.select_related('group').order_by('-created_at')[:10]
    
    # Ishonch darajasi bo'yicha taqsimot
    confidence_stats = {
        'very_high': RentalAnnouncement.objects.filter(confidence_score__gte=0.8).count(),
        'high': RentalAnnouncement.objects.filter(confidence_score__gte=0.6, confidence_score__lt=0.8).count(),
        'medium': RentalAnnouncement.objects.filter(confidence_score__gte=0.4, confidence_score__lt=0.6).count(),
        'low': RentalAnnouncement.objects.filter(confidence_score__lt=0.4).count(),
    }
    
    context = {
        'today_announcements_count': today_announcements_count,
        'today_verified_count': today_verified_count,
        'today_high_confidence': today_high_confidence,
        'unprocessed_count': unprocessed_count,
        'days': last_7_days,
        'announcement_counts': announcement_counts,
        'verified_counts': verified_counts,
        'top_groups': top_groups,
        'recent_announcements': recent_announcements,
        'confidence_stats': confidence_stats
    }
    
    return render(request, 'dashboard.html', context)

def dashboard_api_stats(request):
    """Dashboard uchun API statistika"""
    today = datetime.now().date()
    
    # Umum statistika
    total_announcements = RentalAnnouncement.objects.count()
    verified_announcements = RentalAnnouncement.objects.filter(is_verified=True).count()
    unprocessed_announcements = RentalAnnouncement.objects.filter(is_processed=False).count()
    
    # Bugungi statistika
    today_announcements = RentalAnnouncement.objects.filter(created_at__date=today).count()
    today_verified = RentalAnnouncement.objects.filter(created_at__date=today, is_verified=True).count()
    
    # Media fayllar statistikasi
    total_media = MediaFile.objects.count()
    photos_count = MediaFile.objects.filter(media_type='photo').count()
    videos_count = MediaFile.objects.filter(media_type='video').count()
    
    return JsonResponse({
        'total_announcements': total_announcements,
        'verified_announcements': verified_announcements,
        'unprocessed_announcements': unprocessed_announcements,
        'today_announcements': today_announcements,
        'today_verified': today_verified,
        'total_media': total_media,
        'photos_count': photos_count,
        'videos_count': videos_count
    })
    
    
    

def groups_list_view(request):
    """Barcha guruhlar ro'yxati"""
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort', '-created_at')
    
    # Guruhlarni olish va statistika bilan
    groups = MonitoredGroup.objects.annotate(
        total_announcements=Count('rental_announcements'),
        verified_announcements=Count('rental_announcements', filter=Q(rental_announcements__is_verified=True)),
        today_announcements=Count('rental_announcements', 
                                filter=Q(rental_announcements__created_at__date=timezone.now().date())),
        avg_confidence=Avg('rental_announcements__confidence_score'),
        last_announcement=Max('rental_announcements__created_at')
    ).filter(
        total_announcements__gt=0  # Faqat e'lonlari bor guruhlar
    )
    
    # Qidiruv
    if search_query:
        groups = groups.filter(
            Q(title__icontains=search_query) | 
            Q(chat_id__icontains=search_query)
        )
    
    # Saralash
    valid_sorts = ['title', '-title', 'total_announcements', '-total_announcements', 
                   'created_at', '-created_at', 'avg_confidence', '-avg_confidence']
    if sort_by in valid_sorts:
        groups = groups.order_by(sort_by)
    else:
        groups = groups.order_by('-total_announcements')
    
    # Pagination
    paginator = Paginator(groups, 12)
    page_number = request.GET.get('page')
    groups_page = paginator.get_page(page_number)
    
    context = {
        'groups': groups_page,
        'search_query': search_query,
        'sort_by': sort_by,
        'total_groups': paginator.count,
    }
    
    return render(request, 'groups_list.html', context)

def group_detail_view(request, group_id):
    """Guruh tafsilotlari va e'lonlari"""
    group = get_object_or_404(MonitoredGroup, id=group_id)
    
    # Filter form
    filter_form = AnnouncementFilterForm(request.GET)
    verify_form = QuickVerifyForm()
    
    # E'lonlarni olish
    announcements = RentalAnnouncement.objects.filter(group=group).select_related('group').prefetch_related('photo_files').order_by('-created_at')
    
    # Filtrlarni qo'llash
    if filter_form.is_valid():
        data = filter_form.cleaned_data
        
        if data.get('search'):
            announcements = announcements.filter(
                Q(message_text__icontains=data['search']) |
                Q(first_name__icontains=data['search']) |
                Q(username__icontains=data['search'])
            )
        
        if data.get('confidence_min') is not None:
            announcements = announcements.filter(confidence_score__gte=data['confidence_min'])
        
        if data.get('is_verified') == 'true':
            announcements = announcements.filter(is_verified=True)
        elif data.get('is_verified') == 'false':
            announcements = announcements.filter(is_verified=False)
            
        if data.get('has_media'):
            announcements = announcements.filter(
                Q(photos__isnull=False) | Q(videos__isnull=False)
            ).exclude(photos=[], videos=[])
            
        if data.get('date_from'):
            announcements = announcements.filter(created_at__date__gte=data['date_from'])
            
        if data.get('date_to'):
            announcements = announcements.filter(created_at__date__lte=data['date_to'])
    
    # Infinite scroll uchun AJAX so'rov tekshirish
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        page = request.GET.get('page', 1)
        paginator = Paginator(announcements, 10)
        announcements_page = paginator.get_page(page)
        
        # JSON response qaytarish
        announcements_data = []
        for announcement in announcements_page:
            announcements_data.append({
                'id': announcement.id,
                'message_text': announcement.message_text[:200] + '...' if len(announcement.message_text or '') > 200 else announcement.message_text,
                'first_name': announcement.first_name,
                'username': announcement.username,
                'confidence_score': announcement.confidence_score,
                'is_verified': announcement.is_verified,
                'is_processed': announcement.is_processed,
                'created_at': announcement.created_at.strftime('%Y-%m-%d %H:%M'),
                'photos_count': len(announcement.photos or []),
                'videos_count': len(announcement.videos or []),
                'has_media': bool(announcement.photos or announcement.videos),
                'has_photos': announcement.photo_files.exists()
            })
        
        return JsonResponse({
            'announcements': announcements_data,
            'has_next': announcements_page.has_next(),
            'next_page_number': announcements_page.next_page_number() if announcements_page.has_next() else None
        })
    
    # Oddiy HTTP so'rov uchun
    paginator = Paginator(announcements, 10)
    page_number = request.GET.get('page', 1)
    announcements_page = paginator.get_page(page_number)
    
    # Guruh statistikasi
    group_stats = {
        'total_announcements': announcements.count(),
        'verified_announcements': announcements.filter(is_verified=True).count(),
        'unprocessed_announcements': announcements.filter(is_processed=False).count(),
        'high_confidence_announcements': announcements.filter(confidence_score__gte=0.7).count(),
        'today_announcements': announcements.filter(created_at__date=timezone.now().date()).count(),
        'avg_confidence': announcements.aggregate(avg=Avg('confidence_score'))['avg'] or 0,
    }
    
    context = {
        'group': group,
        'announcements': announcements_page,
        'filter_form': filter_form,
        'verify_form': verify_form,
        'group_stats': group_stats,
        'total_announcements': paginator.count,
        'TELEGRAM_BOT_TOKEN': '7413765945:AAHqyNsG2tvyUt0XgBd5OT0FuTA94t1SpEc'
    }
    
    return render(request, 'group_detail.html', context)

def quick_verify_announcement(request):
    """E'lonni tez tasdiqlash/rad etish"""
    if request.method == 'POST':
        form = QuickVerifyForm(request.POST)
        if form.is_valid():
            announcement_id = form.cleaned_data['announcement_id']
            action = form.cleaned_data['action']
            
            try:
                announcement = RentalAnnouncement.objects.get(id=announcement_id)
                
                if action == 'verify':
                    announcement.is_verified = True
                    announcement.is_processed = True
                    message = 'E\'lon tasdiqlandi'
                    status = 'success'
                elif action == 'reject':
                    announcement.is_verified = False
                    announcement.is_processed = True
                    message = 'E\'lon rad etildi'
                    status = 'warning'
                else:
                    return JsonResponse({'success': False, 'message': 'Noto\'g\'ri harakat'})
                
                announcement.save()
                
                return JsonResponse({
                    'success': True, 
                    'message': message,
                    'status': status,
                    'new_state': {
                        'is_verified': announcement.is_verified,
                        'is_processed': announcement.is_processed
                    }
                })
                
            except RentalAnnouncement.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'E\'lon topilmadi'})
    
    return JsonResponse({'success': False, 'message': 'Noto\'g\'ri so\'rov'})