from rest_framework import serializers
from .models import MonitoredGroup, RentalAnnouncement, MonitoredMessage

class MonitoredGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonitoredGroup
        fields = '__all__'


class RentalAnnouncementSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.title', read_only=True)
    
    class Meta:
        model = RentalAnnouncement
        fields = [
            'id', 'group', 'group_name', 'user_id', 'username', 
            'first_name', 'last_name', 'message_text', 'message_id',
            'photos', 'videos', 'documents', 'audio_files', 
            'voice_messages', 'rental_keywords_found', 
            'confidence_score', 'location_latitude', 'location_longitude',
            'location_address', 'contact_info', 'raw_telegram_data',
            'created_at', 'updated_at', 'is_processed', 'is_verified'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class RentalAnnouncementListSerializer(serializers.ModelSerializer):
    """Ro'yxat ko'rinishi uchun qisqartirilgan serializer"""
    group_name = serializers.CharField(source='group.title', read_only=True)
    keywords_count = serializers.IntegerField(source='rental_keywords_found.__len__', read_only=True)
    has_media = serializers.SerializerMethodField()
    confidence_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = RentalAnnouncement
        fields = [
            'id', 'group_name', 'user_id', 'username', 'first_name',
            'message_text', 'keywords_count', 'has_media', 
            'confidence_score', 'confidence_percentage', 'location_latitude',
            'location_longitude', 'created_at', 'is_processed', 'is_verified'
        ]
    
    def get_has_media(self, obj):
        return bool(obj.photos or obj.videos or obj.documents or obj.audio_files or obj.voice_messages)
    
    def get_confidence_percentage(self, obj):
        return int(obj.confidence_score * 100)


class MonitoredMessageSerializer(serializers.ModelSerializer):
    """Eski model uchun serializer (agar kerak bo'lsa)"""
    group_name = serializers.CharField(source='group.title', read_only=True)
    
    class Meta:
        model = MonitoredMessage
        fields = '__all__'