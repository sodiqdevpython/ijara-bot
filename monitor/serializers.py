from rest_framework import serializers
from .models import MonitoredGroup, RentalAnnouncement, MonitoredMessage, MediaFile, RentalPhoto

class MediaFileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = MediaFile
        fields = [
            'id', 'file_id', 'file_unique_id', 'media_type',
            'file_name', 'mime_type', 'file_size', 'file_size_mb',
            'width', 'height', 'duration', 'file_url',
            'is_downloaded', 'download_error', 'metadata', 'created_at'
        ]
    
    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file_path and request:
            return request.build_absolute_uri(obj.file_path.url)
        return None
    
    def get_file_size_mb(self, obj):
        if obj.file_size:
            return round(obj.file_size / (1024 * 1024), 2)
        return None

class MonitoredGroupSerializer(serializers.ModelSerializer):
    total_announcements = serializers.SerializerMethodField()
    
    class Meta:
        model = MonitoredGroup
        fields = '__all__'
    
    def get_total_announcements(self, obj):
        return obj.rental_announcements.count()

class RentalAnnouncementSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.title', read_only=True)
    media_files = MediaFileSerializer(many=True, read_only=True)
    media_files_count = serializers.SerializerMethodField()
    total_file_size_mb = serializers.SerializerMethodField()
    
    class Meta:
        model = RentalAnnouncement
        fields = [
            'id', 'group', 'group_name', 'user_id', 'username', 
            'first_name', 'last_name', 'message_text', 'message_id',
            'photos', 'videos', 'documents', 'audio_files', 
            'voice_messages', 'rental_keywords_found', 
            'confidence_score', 'location_latitude', 'location_longitude',
            'location_address', 'contact_info', 'raw_telegram_data',
            'created_at', 'updated_at', 'is_processed', 'is_verified',
            'media_files', 'media_files_count', 'total_file_size_mb'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_media_files_count(self, obj):
        return obj.media_files.count()
    
    def get_total_file_size_mb(self, obj):
        total_size = sum(
            media.file_size or 0 for media in obj.media_files.all()
        )
        return round(total_size / (1024 * 1024), 2) if total_size > 0 else 0

class RentalAnnouncementListSerializer(serializers.ModelSerializer):
    """Ro'yxat ko'rinishi uchun qisqartirilgan serializer"""
    group_name = serializers.CharField(source='group.title', read_only=True)
    keywords_count = serializers.IntegerField(source='rental_keywords_found.__len__', read_only=True)
    has_media = serializers.SerializerMethodField()
    confidence_percentage = serializers.SerializerMethodField()
    media_files_count = serializers.SerializerMethodField()
    downloaded_files_count = serializers.SerializerMethodField()
    
    class Meta:
        model = RentalAnnouncement
        fields = [
            'id', 'group_name', 'user_id', 'username', 'first_name',
            'message_text', 'keywords_count', 'has_media', 
            'confidence_score', 'confidence_percentage', 'location_latitude',
            'location_longitude', 'created_at', 'is_processed', 'is_verified',
            'media_files_count', 'downloaded_files_count'
        ]
    
    def get_has_media(self, obj):
        return obj.media_files.exists()
    
    def get_confidence_percentage(self, obj):
        return int(obj.confidence_score * 100)
    
    def get_media_files_count(self, obj):
        return obj.media_files.count()
    
    def get_downloaded_files_count(self, obj):
        return obj.media_files.filter(is_downloaded=True).count()

class MonitoredMessageSerializer(serializers.ModelSerializer):
    """Eski model uchun serializer (agar kerak bo'lsa)"""
    group_name = serializers.CharField(source='group.title', read_only=True)
    
    class Meta:
        model = MonitoredMessage
        fields = '__all__'
        
class RentalPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalPhoto
        fields = ['id', 'image', 'created_at']

class RentalAnnouncementSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.title', read_only=True)
    photo_files = RentalPhotoSerializer(many=True, read_only=True)  # << qo‘shildi
    
    class Meta:
        model = RentalAnnouncement
        fields = [
            'id', 'group', 'group_name', 'user_id', 'username', 
            'first_name', 'last_name', 'message_text', 'message_id',
            'photos', 'videos', 'documents', 'audio_files', 
            'voice_messages', 'rental_keywords_found', 
            'confidence_score', 'location_latitude', 'location_longitude',
            'location_address', 'contact_info', 'raw_telegram_data',
            'created_at', 'updated_at', 'is_processed', 'is_verified',
            'photo_files',  # << qo‘shildi
        ]
