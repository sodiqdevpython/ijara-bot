from django.db import models

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
    
    # Media fayllar
    photos = models.JSONField(default=list, blank=True)  # [{"file_id": "", "file_unique_id": "", "width": 0, "height": 0}]
    videos = models.JSONField(default=list, blank=True)  # Video ma'lumotlari
    documents = models.JSONField(default=list, blank=True)  # Hujjatlar
    audio_files = models.JSONField(default=list, blank=True)  # Audio fayllar
    voice_messages = models.JSONField(default=list, blank=True)  # Ovozli xabarlar
    
    # Ijara aniqlash ma'lumotlari
    rental_keywords_found = models.JSONField(default=list, blank=True)  # Topilgan kalit so'zlar
    confidence_score = models.FloatField(default=0.0)  # Ishonch darajasi (0-1)
    
    # Joylashuv ma'lumotlari
    location_latitude = models.FloatField(null=True, blank=True)
    location_longitude = models.FloatField(null=True, blank=True)
    location_address = models.TextField(blank=True, null=True)
    
    # Kontakt ma'lumotlari
    contact_info = models.JSONField(default=dict, blank=True)  # Telefon, username va boshqalar
    
    # To'liq raw data
    raw_telegram_data = models.JSONField()
    
    # Vaqt ma'lumotlari
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Status
    is_processed = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)  # Admin tomonidan tasdiqlangan
    
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