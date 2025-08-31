from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import MonitoredGroup, RentalAnnouncement, MonitoredMessage
import json


@admin.register(MonitoredGroup)
class MonitoredGroupAdmin(admin.ModelAdmin):
    list_display = ['title', 'chat_id', 'announcement_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'chat_id']
    readonly_fields = ['created_at']
    
    def announcement_count(self, obj):
        count = obj.rental_announcements.count()
        if count > 0:
            url = reverse('admin:monitor_rentalannouncement_changelist') + f'?group__id__exact={obj.id}'
            return format_html('<a href="{}">{} elonlar</a>', url, count)
        return '0 elonlar'
    announcement_count.short_description = 'Ijara elonlari'


@admin.register(RentalAnnouncement)
class RentalAnnouncementAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'group_title', 'user_info', 'confidence_display', 
        'has_media_display', 'verification_status', 'created_at'
    ]
    list_filter = [
        'is_verified', 'is_processed', 'group', 
        'confidence_score', 'created_at'
    ]
    search_fields = [
        'message_text', 'first_name', 'last_name', 'username',
        'rental_keywords_found', 'group__title'
    ]
    readonly_fields = [
        'created_at', 'updated_at', 'raw_telegram_data_display',
        'media_info_display', 'contact_info_display', 'keywords_display'
    ]
    
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('group', 'user_id', 'username', 'first_name', 'last_name', 'message_id')
        }),
        ('Xabar mazmuni', {
            'fields': ('message_text', 'keywords_display')
        }),
        ('Media fayllar', {
            'fields': ('media_info_display',),
            'classes': ('collapse',)
        }),
        ('Tahlil natijalari', {
            'fields': ('confidence_score', 'rental_keywords_found')
        }),
        ('Joylashuv', {
            'fields': ('location_latitude', 'location_longitude', 'location_address'),
            'classes': ('collapse',)
        }),
        ('Kontakt ma\'lumotlari', {
            'fields': ('contact_info_display',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_processed', 'is_verified')
        }),
        ('Texnik ma\'lumotlar', {
            'fields': ('created_at', 'updated_at', 'raw_telegram_data_display'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['verify_announcements', 'reject_announcements', 'mark_processed']
    
    def group_title(self, obj):
        return obj.group.title
    group_title.short_description = 'Guruh'
    
    def user_info(self, obj):
        username_part = f"@{obj.username}" if obj.username else ""
        return f"{obj.first_name or ''} {obj.last_name or ''} {username_part}".strip()
    user_info.short_description = 'Foydalanuvchi'
    
    def confidence_display(self, obj):
        percentage = int(obj.confidence_score * 100)
        if percentage >= 70:
            color = 'green'
        elif percentage >= 40:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, f'{percentage}%'
        )
    confidence_display.short_description = 'Ishonch darajasi'
    
    def has_media_display(self, obj):
        media_count = (
            len(obj.photos or []) + len(obj.videos or []) + 
            len(obj.documents or []) + len(obj.audio_files or []) + 
            len(obj.voice_messages or [])
        )
        if media_count > 0:
            return format_html(
                '<span style="color: green;">✓ {} ta fayl</span>', 
                media_count
            )
        return format_html('<span style="color: gray;">Media yo\'q</span>')
    has_media_display.short_description = 'Media fayllar'
    
    def verification_status(self, obj):
        if not obj.is_processed:
            return format_html('<span style="color: orange;">⏳ Kutilmoqda</span>')
        elif obj.is_verified:
            return format_html('<span style="color: green;">✓ Tasdiqlangan</span>')
        else:
            return format_html('<span style="color: red;">✗ Rad etilgan</span>')
    verification_status.short_description = 'Status'
    
    def keywords_display(self, obj):
        if obj.rental_keywords_found:
            keywords = obj.rental_keywords_found[:10]  # Birinchi 10 tani ko'rsatish
            return ', '.join(keywords)
        return 'Kalit so\'zlar topilmadi'
    keywords_display.short_description = 'Topilgan kalit so\'zlar'
    
    def contact_info_display(self, obj):
        if obj.contact_info:
            return mark_safe(f'<pre>{json.dumps(obj.contact_info, indent=2, ensure_ascii=False)}</pre>')
        return 'Kontakt ma\'lumotlari yo\'q'
    contact_info_display.short_description = 'Kontakt ma\'lumotlari'
    
    def media_info_display(self, obj):
        media_info = []
        if obj.photos:
            media_info.append(f"Rasmlar: {len(obj.photos)} ta")
        if obj.videos:
            media_info.append(f"Videolar: {len(obj.videos)} ta")
        if obj.documents:
            media_info.append(f"Hujjatlar: {len(obj.documents)} ta")
        if obj.audio_files:
            media_info.append(f"Audio: {len(obj.audio_files)} ta")
        if obj.voice_messages:
            media_info.append(f"Ovozli xabarlar: {len(obj.voice_messages)} ta")
        
        if media_info:
            return mark_safe('<br>'.join(media_info))
        return 'Media fayllar yo\'q'
    media_info_display.short_description = 'Media ma\'lumotlari'
    
    def raw_telegram_data_display(self, obj):
        if obj.raw_telegram_data:
            return mark_safe(f'<pre>{json.dumps(obj.raw_telegram_data, indent=2, ensure_ascii=False)[:1000]}...</pre>')
        return 'Raw data yo\'q'
    raw_telegram_data_display.short_description = 'Raw Telegram Data'
    
    # Admin actions
    def verify_announcements(self, request, queryset):
        updated = queryset.update(is_verified=True, is_processed=True)
        self.message_user(request, f'{updated} ta elon tasdiqlandi.')
    verify_announcements.short_description = 'Tanlangan elonlarni tasdiqlash'
    
    def reject_announcements(self, request, queryset):
        updated = queryset.update(is_verified=False, is_processed=True)
        self.message_user(request, f'{updated} ta elon rad etildi.')
    reject_announcements.short_description = 'Tanlangan elonlarni rad etish'
    
    def mark_processed(self, request, queryset):
        updated = queryset.update(is_processed=True)
        self.message_user(request, f'{updated} ta elon qayta ishlandi deb belgilandi.')
    mark_processed.short_description = 'Qayta ishlangan deb belgilash'


@admin.register(MonitoredMessage)
class MonitoredMessageAdmin(admin.ModelAdmin):
    """Eski monitoring system uchun admin (agar kerak bo'lsa)"""
    list_display = ['id', 'group', 'first_name', 'username', 'contains_keyword', 'created_at']
    list_filter = ['contains_keyword', 'group', 'created_at']
    search_fields = ['message_text', 'first_name', 'username', 'matched_keywords']
    readonly_fields = ['created_at']