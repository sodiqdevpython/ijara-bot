from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import MonitoredGroup, RentalAnnouncement, RentalMediaFile, MonitoredMessage
import json


class RentalMediaFileInline(admin.TabularInline):
    model = RentalMediaFile
    extra = 0
    readonly_fields = ['preview', 'file_id', 'file_unique_id', 'file_size', 'created_at', 'download_error']
    fields = ['media_type', 'preview', 'file_name', 'mime_type', 'file_size', 'is_downloaded', 'download_error']
    
    def preview(self, obj):
        """Media fayl uchun preview ko'rsatish"""
        if not obj.id:
            return "Yangi fayl"
        
        if obj.media_type == 'photo' and obj.file_url:
            return format_html(
                '<img src="{}" style="max-width: 100px; max-height: 100px;" />',
                obj.file_url
            )
        elif obj.media_type == 'video' and obj.file_url:
            return format_html(
                '<video controls style="max-width: 200px; max-height: 150px;"><source src="{}" type="{}"></video>',
                obj.file_url,
                obj.mime_type or 'video/mp4'
            )
        elif obj.local_file:
            return format_html('<a href="{}" target="_blank">📎 Faylni ko\'rish</a>', obj.file_url)
        else:
            return format_html(
                '<span style="color: gray;">Yuklanmagan ({})</span>',
                obj.get_media_type_display()
            )
    preview.short_description = 'Preview'


@admin.register(MonitoredGroup)
class MonitoredGroupAdmin(admin.ModelAdmin):
    list_display = ['title', 'chat_id', 'announcement_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'chat_id']
    readonly_fields = ['created_at']
    
    def announcement_count(self, obj):
        count = obj.rental_announcements.count()
        if count > 0:
            # App nomini o'zingiznikiga o'zgartiring
            url = reverse('admin:monitor_rentalannouncement_changelist') + f'?group__id__exact={obj.id}'
            return format_html('<a href="{}">{} elonlar</a>', url, count)
        return '0 elonlar'
    announcement_count.short_description = 'Ijara elonlari'


@admin.register(RentalAnnouncement)
class RentalAnnouncementAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'group_title', 'user_info', 'confidence_display', 
        'media_count_display', 'verification_status', 'created_at'
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
        'contact_info_display', 'keywords_display', 'media_gallery'
    ]
    
    inlines = [RentalMediaFileInline]
    
    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('group', 'user_id', 'username', 'first_name', 'last_name', 'message_id')
        }),
        ('Xabar mazmuni', {
            'fields': ('message_text', 'keywords_display')
        }),
        ('Media fayllar', {
            'fields': ('media_gallery',),
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
    
    actions = ['verify_announcements', 'reject_announcements', 'mark_processed', 'download_missing_media']
    
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
    
    def media_count_display(self, obj):
        total_count = obj.total_media_count
        downloaded_count = obj.media_files.filter(is_downloaded=True).count()
        
        if total_count > 0:
            if downloaded_count == total_count:
                return format_html(
                    '<span style="color: green;">✓ {}/{} yuklab olingan</span>', 
                    downloaded_count, total_count
                )
            else:
                return format_html(
                    '<span style="color: orange;">⏳ {}/{} yuklab olingan</span>',
                    downloaded_count, total_count
                )
        return format_html('<span style="color: gray;">Media yo\'q</span>')
    media_count_display.short_description = 'Media fayllar'
    
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
            keywords = obj.rental_keywords_found[:10]
            return ', '.join(keywords)
        return 'Kalit so\'zlar topilmadi'
    keywords_display.short_description = 'Topilgan kalit so\'zlar'
    
    def contact_info_display(self, obj):
        if obj.contact_info:
            return mark_safe(f'<pre>{json.dumps(obj.contact_info, indent=2, ensure_ascii=False)}</pre>')
        return 'Kontakt ma\'lumotlari yo\'q'
    contact_info_display.short_description = 'Kontakt ma\'lumotlari'
    
    def media_gallery(self, obj):
        """Media fayllar gallereyasi"""
        if not obj.id:
            return "Saqlangandan keyin media fayllar ko'rsatiladi"
        
        media_files = obj.media_files.all()
        if not media_files:
            return "Media fayllar yo'q"
        
        html_parts = []
        
        for media_file in media_files:
            if media_file.media_type == 'photo' and media_file.file_url:
                html_parts.append(f'''
                    <div style="display: inline-block; margin: 5px; text-align: center;">
                        <img src="{media_file.file_url}" style="max-width: 150px; max-height: 150px; border: 1px solid #ddd;" />
                        <br><small>{media_file.display_name}</small>
                    </div>
                ''')
            elif media_file.media_type == 'video' and media_file.file_url:
                html_parts.append(f'''
                    <div style="display: inline-block; margin: 5px; text-align: center;">
                        <video controls style="max-width: 200px; max-height: 150px;">
                            <source src="{media_file.file_url}" type="{media_file.mime_type or 'video/mp4'}">
                        </video>
                        <br><small>{media_file.display_name}</small>
                    </div>
                ''')
            else:
                status = "✓" if media_file.is_downloaded else "⏳"
                html_parts.append(f'''
                    <div style="display: inline-block; margin: 5px; padding: 10px; border: 1px solid #ddd;">
                        {status} {media_file.get_media_type_display()}<br>
                        <small>{media_file.display_name}</small>
                    </div>
                ''')
        
        return mark_safe(''.join(html_parts))
    media_gallery.short_description = 'Media gallereyasi'
    
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
    
    def download_missing_media(self, request, queryset):
        # Bu funktsiyani management command orqali bajarish yaxshi bo'ladi
        count = 0
        for announcement in queryset:
            count += announcement.media_files.filter(is_downloaded=False).count()
        self.message_user(request, f'{count} ta media fayl yuklab olish kerak. Management command ishga tushiring.')
    download_missing_media.short_description = 'Media fayllarni yuklab olish'


@admin.register(RentalMediaFile)
class RentalMediaFileAdmin(admin.ModelAdmin):
    list_display = ['id', 'announcement', 'media_type', 'display_name', 'file_size', 'is_downloaded', 'created_at']
    list_filter = ['media_type', 'is_downloaded', 'created_at']
    search_fields = ['announcement__message_text', 'file_name', 'announcement__first_name']
    readonly_fields = ['preview', 'file_id', 'file_unique_id', 'created_at']
    
    def preview(self, obj):
        """Media fayl uchun preview"""
        if obj.media_type == 'photo' and obj.file_url:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px;" />',
                obj.file_url
            )
        elif obj.media_type == 'video' and obj.file_url:
            return format_html(
                '<video controls style="max-width: 300px; max-height: 200px;"><source src="{}" type="{}"></video>',
                obj.file_url,
                obj.mime_type or 'video/mp4'
            )
        elif obj.local_file:
            return format_html('<a href="{}" target="_blank">📎 Faylni ko\'rish</a>', obj.file_url)
        return "Preview yo'q"
    preview.short_description = 'Preview'


@admin.register(MonitoredMessage)
class MonitoredMessageAdmin(admin.ModelAdmin):
    """Eski monitoring system uchun admin"""
    list_display = ['id', 'group', 'first_name', 'username', 'contains_keyword', 'created_at']
    list_filter = ['contains_keyword', 'group', 'created_at']
    search_fields = ['message_text', 'first_name', 'username', 'matched_keywords']
    readonly_fields = ['created_at']