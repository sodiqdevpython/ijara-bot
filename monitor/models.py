from django.db import models
import os

def rental_media_upload_path(instance, filename):
    """Media fayllar uchun upload path"""
    return f'rental_media/{instance.announcement.id}/{filename}'

class MonitoredGroup(models.Model):
    chat_id = models.BigIntegerField(unique=True)
    title = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class RentalAnnouncement(models.Model):
    # Asosiy ma'lumotlar
    group = models.ForeignKey(MonitoredGroup, on_delete=models.CASCADE, related_name='rental_announcements')
    user_id = models.BigIntegerField()
    username = models.CharField(max_length=512, null=True, blank=True)
    first_name = models.CharField(max_length=2048, null=True, blank=True)
    last_name = models.CharField(max_length=2048, null=True, blank=True)
    
    # Xabar ma'lumotlari
    message_text = models.TextField(blank=True, null=True)
    message_id = models.BigIntegerField()
    
    # Media fayllar (JSON ma'lumotlari)
    photos_data = models.JSONField(default=list, blank=True)  # [{"file_id": "", "width": 0, "height": 0}]
    videos_data = models.JSONField(default=list, blank=True)  
    documents_data = models.JSONField(default=list, blank=True)  
    audio_files_data = models.JSONField(default=list, blank=True)  
    voice_messages_data = models.JSONField(default=list, blank=True)  
    
    # Ijara aniqlash ma'lumotlari
    rental_keywords_found = models.JSONField(default=list, blank=True)  
    confidence_score = models.FloatField(default=0.0)  
    
    # Joylashuv ma'lumotlari
    location_latitude = models.FloatField(null=True, blank=True)
    location_longitude = models.FloatField(null=True, blank=True)
    location_address = models.TextField(blank=True, null=True)
    
    # Kontakt ma'lumotlari
    contact_info = models.JSONField(default=dict, blank=True)  
    
    # To'liq raw data
    raw_telegram_data = models.JSONField()
    
    # Vaqt ma'lumotlari
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Status
    is_processed = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)  
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['group', 'created_at']),
            models.Index(fields=['user_id']),
            models.Index(fields=['is_processed']),
            models.Index(fields=['confidence_score']),
        ]
    
    def __str__(self):
        return f"[{self.group.title}] {self.first_name or ''} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def total_media_count(self):
        return (len(self.photos_data or []) + 
                len(self.videos_data or []) + 
                len(self.documents_data or []) +
                len(self.audio_files_data or []) +
                len(self.voice_messages_data or []))


class RentalMediaFile(models.Model):
    """Media fayllarni saqlash uchun alohida model"""
    MEDIA_TYPES = [
        ('photo', 'Photo'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('audio', 'Audio'),
        ('voice', 'Voice Message'),
        ('video_note', 'Video Note'),
    ]
    
    announcement = models.ForeignKey(RentalAnnouncement, on_delete=models.CASCADE, related_name='media_files')
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPES)
    
    # Telegram ma'lumotlari
    file_id = models.CharField(max_length=512)
    file_unique_id = models.CharField(max_length=512)
    
    # Fayl ma'lumotlari
    file_size = models.BigIntegerField(null=True, blank=True)
    mime_type = models.CharField(max_length=256, null=True, blank=True)
    file_name = models.CharField(max_length=512, null=True, blank=True)
    
    # Rasm/video o'lchamlari
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)  # video/audio uchun
    
    # Saqlangan fayl
    local_file = models.FileField(upload_to=rental_media_upload_path, null=True, blank=True)
    download_url = models.URLField(null=True, blank=True)  # Telegram URL
    
    # Metadata
    telegram_data = models.JSONField(default=dict)
    
    # Vaqt
    created_at = models.DateTimeField(auto_now_add=True)
    is_downloaded = models.BooleanField(default=False)
    download_error = models.TextField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['announcement', 'media_type']),
            models.Index(fields=['file_id']),
        ]
    
    def __str__(self):
        return f"{self.get_media_type_display()} - {self.announcement}"
    
    @property
    def file_url(self):
        """Fayl URL ni qaytarish"""
        if self.local_file and os.path.exists(self.local_file.path):
            return self.local_file.url
        elif self.download_url:
            return self.download_url
        return None
    
    @property
    def display_name(self):
        """Ko'rsatish uchun nom"""
        if self.file_name:
            return self.file_name
        return f"{self.get_media_type_display()}_{self.id}"


# Eski MonitoredMessage modelni saqlab qolish
class MonitoredMessage(models.Model):
    group = models.ForeignKey(MonitoredGroup, on_delete=models.CASCADE, related_name='messages')
    user_id = models.BigIntegerField()
    username = models.CharField(max_length=512, null=True, blank=True)
    first_name = models.CharField(max_length=2048, null=True, blank=True)
    message_text = models.TextField()
    contains_keyword = models.BooleanField(default=False)
    matched_keywords = models.TextField(blank=True, null=True)
    raw_data = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.group}] {self.first_name or ''} ({self.user_id})"