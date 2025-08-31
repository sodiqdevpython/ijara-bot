from rest_framework import serializers
from .models import MonitoredGroup, RentalAnnouncement, RentalMediaFile, MonitoredMessage

class MonitoredGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoredGroup
        fields = '__all__'


class RentalMediaFileSerializer(serializers.ModelSerializer):
    file_url = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    
    class Meta:
        model = RentalMediaFile
        fields = [
            'id', 'media_type', 'file_id', 'file_unique_id', 'file_size',
            'mime_type', 'file_name', 'width', 'height', 'duration',
            'local_file', 'download_url', 'file_url', 'display_name',
            'telegram_data', 'created_at', 'is_downloaded', 'download_error'
        ]
        read_only_fields = ['id', 'created_at', 'file_url', 'display_name']


class RentalAnnouncementSerializer(serializers.ModelSerializer):
    group = serializers.StringRelatedField()
    total_media_count = serializers.SerializerMethodField()
    media_files = RentalMediaFileSerializer(many=True, read_only=True)  # Media fayllarni ham ko'rsatish

    class Meta:
        model = RentalAnnouncement
        fields = [
            'id', 'group', 'user_id', 'username',
            'first_name', 'last_name', 'message_text',
            'message_id', 'confidence_score',
            'created_at', 'updated_at',
            'is_processed', 'is_verified',
            'total_media_count', 'media_files',  # media_files qo'shildi
            'rental_keywords_found', 'contact_info',
            'location_latitude', 'location_longitude', 'location_address',
            'photos_data', 'videos_data', 'documents_data', 
            'audio_files_data', 'voice_messages_data'
        ]

    def get_total_media_count(self, obj):
        return obj.total_media_count


class RentalAnnouncementListSerializer(serializers.ModelSerializer):
    """Ro'yxat ko'rinishi uchun qisqartirilgan serializer"""
    group_name = serializers.CharField(source='group.title', read_only=True)
    keywords_count = serializers.IntegerField(source='rental_keywords_found.__len__', read_only=True)
    has_media = serializers.SerializerMethodField()
    confidence_percentage = serializers.SerializerMethodField()
    media_count = serializers.ReadOnlyField(source='total_media_count')
    
    class Meta:
        model = RentalAnnouncement
        fields = [
            'id', 'group_name', 'user_id', 'username', 'first_name',
            'message_text', 'keywords_count', 'has_media', 'media_count',
            'confidence_score', 'confidence_percentage', 'location_latitude',
            'location_longitude', 'created_at', 'is_processed', 'is_verified'
        ]
    
    def get_has_media(self, obj):
        return obj.total_media_count > 0
    
    def get_confidence_percentage(self, obj):
        return int(obj.confidence_score * 100)


class MonitoredMessageSerializer(serializers.ModelSerializer):
    """Eski model uchun serializer (agar kerak bo'lsa)"""
    group_name = serializers.CharField(source='group.title', read_only=True)
    
    class Meta:
        model = MonitoredMessage
        fields = '__all__'