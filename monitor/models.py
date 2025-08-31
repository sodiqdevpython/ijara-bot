from django.db import models
import os

def media_upload_path(instance, filename):
    """Media fayllar uchun upload path"""
    # announcement_id/media_type/filename
    return f"rental_media/{instance.announcement.id}/{instance.media_type}/{filename}"

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
    
    # Media fayllar (eski JSON fieldlar saqlanadi backup uchun)
    photos = models.JSONField(default=list, blank=True)
    videos = models.JSONField(default=list, blank=True)
    documents = models.JSONField(default=list, blank=True)
    audio_files = models.JSONField(default=list, blank=True)
    voice_messages = models.JSONField(default=list, blank=True)
    
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

class MediaFile(models.Model):
    """Media fayllarni saqlash uchun alohida model"""
    MEDIA_TYPE_CHOICES = [
        ('photo', 'Photo'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('audio', 'Audio'),
        ('voice', 'Voice Message'),
        ('video_note', 'Video Note'),
    ]
    
    announcement = models.ForeignKey(RentalAnnouncement, on_delete=models.CASCADE, related_name='media_files')
    
    # Telegram file ma'lumotlari
    file_id = models.CharField(max_length=512)
    file_unique_id = models.CharField(max_length=512)
    media_type = models.CharField(max_length=20, choices=MEDIA_TYPE_CHOICES)
    
    # Fayl ma'lumotlari
    file_name = models.CharField(max_length=512, null=True, blank=True)
    mime_type = models.CharField(max_length=128, null=True, blank=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    
    # Rasm/video uchun o'lchamlar
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    duration = models.IntegerField(null=True, blank=True)  # Video/audio uchun
    
    # Haqiqiy fayl
    file_path = models.FileField(upload_to=media_upload_path, null=True, blank=True)
    
    # Download status
    is_downloaded = models.BooleanField(default=False)
    download_error = models.TextField(null=True, blank=True)
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)  # Qo'shimcha ma'lumotlar
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['announcement', 'media_type']),
            models.Index(fields=['file_id']),
            models.Index(fields=['is_downloaded']),
        ]
    
    def __str__(self):
        return f"{self.media_type} - {self.file_name or self.file_id[:20]}"
    
    @property
    def file_url(self):
        """Fayl URL sini qaytarish"""
        if self.file_path:
            return self.file_path.url
        return None
    
    def delete_file(self):
        """Faylni o'chirish"""
        if self.file_path and os.path.exists(self.file_path.path):
            os.remove(self.file_path.path)

# Eski MonitoredMessage modelni saqlab qolish (agar kerak bo'lsa)
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
    
class RentalPhoto(models.Model):
    announcement = models.ForeignKey(
        RentalAnnouncement,
        on_delete=models.CASCADE,
        related_name="photo_files"
    )
    image = models.ImageField(upload_to="rental_photos/")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Photo for {self.announcement.id}"
