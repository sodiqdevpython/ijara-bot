import asyncio
import logging
import json
import requests
import httpx
import re
from datetime import datetime, timedelta
from typing import Dict, List
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ChatType, ParseMode
from aiogram.client.default import DefaultBotProperties

BOT_TOKEN = "7413765945:AAHqyNsG2tvyUt0XgBd5OT0FuTA94t1SpEc"
API_BASE = "http://127.0.0.1:8000"
TIMEOUT = 800

# Media group kutish vaqti (soniyalarda)
MEDIA_GROUP_TIMEOUT = 2

# Ijara kalit so'zlari
RENTAL_KEYWORDS = [
    # O'zbek tilida
    "ijara", "ijaraga", "rent", "rental", "arenda", 
    "uy", "xonadon", "kvartira", "dom", "apartment",
    "sotiladi", "ijargaberiladi", "beriladi", 
    "narx", "narxi", "pul", "so'm", "sum", "dollar", "$",
    "xona", "room", "yotoqxona", "bedroom",
    "hammom", "oshxona", "kitchen", "bathroom",
    "yangi", "new", "ta'mirli", "remont",
    "metro", "avtovokzal", "markazga", "yaqin",
    "telefon", "tel", "contact", "bog'laning",
    "rasm", "photo", "video", "ko'rish",
    "kirish", "entry", "deposit", "kafolat",
    "kommunal", "utilities", "gaz", "svet", "suv",
    
    # Rus tilida
    "квартира", "дом", "комната", "сдается", "сдаю",
    "аренда", "снять", "цена", "рубль", "евро",
    "новый", "ремонт", "метро", "центр", "рядом",
    "телефон", "звонить", "фото", "видео",
    "залог", "коммунальные", "газ", "свет", "вода",
    
    # Ingliz tilida
    "house", "apartment", "room", "bedroom", "flat",
    "rent", "lease", "price", "month", "monthly",
    "new", "renovated", "near", "close", "metro",
    "phone", "call", "photo", "pictures", "deposit"
]

# Narx belgilarini aniqlash uchun regex
PRICE_PATTERNS = [
    r'\b\d+[\s]*(?:so\'m|sum|сум|руб|rub|\$|usd|€|eur)\b',
    r'\b\d+[\s]*(?:ming|тыс|k|thousand)\b',
    r'\b\d+[\s]*(?:million|mln|млн)\b',
    r'\$\s*\d+',
    r'\d+\s*\$',
    r'\b\d{3,}\b'  # 3 yoki undan ko'p raqam
]

# Kontakt ma'lumotlarini aniqlash
CONTACT_PATTERNS = [
    r'\+?\d{1,4}[\s\-\(\)]*\d{2,3}[\s\-\(\)]*\d{3,4}[\s\-\(\)]*\d{2,4}',  # Telefon raqamlari
    r'@\w+',  # Username
    r't\.me/\w+',  # Telegram link
]

# Bot va dispatcher yaratish
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Media group kutish uchun storage
media_groups: Dict[str, Dict] = {}


def backend_post(endpoint: str, payload: dict):
    """Backend ga POST request yuborish"""
    try:
        logging.info(f"📤 Sending POST to {API_BASE}{endpoint}")
        
        response = requests.post(f"{API_BASE}{endpoint}", json=payload, timeout=TIMEOUT)
        
        logging.info(f"📥 Backend response status: {response.status_code}")
        
        if response.status_code >= 400:
            logging.error(f"❌ Backend error response: {response.text}")
            return None
        
        response.raise_for_status()
        result = response.json()
        logging.info(f"✅ Backend POST successful: {endpoint}")
        return result
        
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Backend POST error: {e}")
        if hasattr(e, 'response') and e.response:
            logging.error(f"❌ Response content: {e.response.text}")
        return None
    except Exception as e:
        logging.error(f"❌ Unexpected error in backend_post: {e}")
        return None


async def backend_get(endpoint: str) -> list | dict:
    """Backend dan GET request"""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{API_BASE}{endpoint}")
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logging.error(f"❌ Backend GET error: {e}")
        return None


async def get_telegram_file_url(file_id: str) -> dict:
    """Telegram faylini URL sini olish"""
    try:
        file_info = await bot.get_file(file_id)
        file_path = file_info.file_path
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        
        return {
            'file_id': file_id,
            'file_path': file_path,
            'download_url': download_url,
            'file_size': getattr(file_info, 'file_size', None),
            'success': True
        }
        
    except Exception as e:
        logging.error(f"❌ Get file URL error for {file_id}: {e}")
        return {
            'file_id': file_id,
            'error': str(e),
            'success': False
        }


def analyze_rental_content(text: str, user_data: dict, media_count: int) -> dict:
    """Ijara elonini aniqlash va tahlil qilish"""
    if not text:
        text = ""
    
    text_lower = text.lower()
    
    # Kalit so'zlarni topish
    found_keywords = []
    for keyword in RENTAL_KEYWORDS:
        if keyword.lower() in text_lower:
            found_keywords.append(keyword)
    
    # Narxlarni topish
    prices_found = []
    for pattern in PRICE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        prices_found.extend(matches)
    
    # Kontakt ma'lumotlarini topish
    contacts_found = []
    for pattern in CONTACT_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        contacts_found.extend(matches)
    
    # Ishonch darajasini hisoblash
    confidence = 0.0
    
    # Kalit so'zlar uchun ball
    if found_keywords:
        confidence += min(len(found_keywords) * 0.15, 0.6)
    
    # Narx mavjudligi uchun ball
    if prices_found:
        confidence += 0.25
    
    # Kontakt ma'lumotlari uchun ball
    if contacts_found:
        confidence += 0.2
    
    # Media fayllar uchun ball (rasmlar ijara elonida muhim)
    if media_count > 0:
        confidence += min(media_count * 0.05, 0.3)
    
    # Username yoki telefon mavjudligi
    if user_data.get('username') or any('phone' in str(contact).lower() for contact in contacts_found):
        confidence += 0.1
    
    # Maksimal 1.0 gacha
    confidence = min(confidence, 1.0)
    
    return {
        'keywords_found': found_keywords,
        'prices_found': prices_found,
        'contacts_found': contacts_found,
        'confidence_score': confidence,
        'is_likely_rental': confidence >= 0.3  # 30% dan yuqori ishonch darajasi
    }


async def extract_media_info_with_urls(message: types.Message) -> dict:
    """Xabardan media ma'lumotlarini ajratib olish va URL larini olish"""
    media_info = {
        'photos': [],
        'videos': [],
        'documents': [],
        'audio_files': [],
        'voice_messages': [],
        'video_notes': []
    }
    
    try:
        # Photos
        if message.photo:
            logging.info(f"📸 Processing photo from message {message.message_id}")
            largest_photo = max(message.photo, key=lambda x: x.width * x.height)
            
            url_info = await get_telegram_file_url(largest_photo.file_id)
            
            photo_data = {
                'file_id': largest_photo.file_id,
                'file_unique_id': largest_photo.file_unique_id,
                'width': largest_photo.width,
                'height': largest_photo.height,
                'file_size': getattr(largest_photo, 'file_size', None),
            }
            
            if url_info['success']:
                photo_data.update({
                    'download_url': url_info['download_url'],
                    'file_path': url_info['file_path']
                })
            
            media_info['photos'].append(photo_data)
            logging.info(f"✅ Added photo: {largest_photo.file_id}")
        
        # Videos
        if message.video:
            logging.info(f"🎥 Processing video from message {message.message_id}")
            url_info = await get_telegram_file_url(message.video.file_id)
            
            video_data = {
                'file_id': message.video.file_id,
                'file_unique_id': message.video.file_unique_id,
                'width': message.video.width,
                'height': message.video.height,
                'duration': message.video.duration,
                'file_size': getattr(message.video, 'file_size', None),
                'mime_type': getattr(message.video, 'mime_type', None),
            }
            
            if url_info['success']:
                video_data.update({
                    'download_url': url_info['download_url'],
                    'file_path': url_info['file_path']
                })
            
            media_info['videos'].append(video_data)
            logging.info(f"✅ Added video: {message.video.file_id}")
        
        # Documents
        if message.document:
            logging.info(f"📄 Processing document from message {message.message_id}")
            url_info = await get_telegram_file_url(message.document.file_id)
            
            doc_data = {
                'file_id': message.document.file_id,
                'file_unique_id': message.document.file_unique_id,
                'file_name': getattr(message.document, 'file_name', None),
                'mime_type': getattr(message.document, 'mime_type', None),
                'file_size': getattr(message.document, 'file_size', None),
            }
            
            if url_info['success']:
                doc_data.update({
                    'download_url': url_info['download_url'],
                    'file_path': url_info['file_path']
                })
            
            media_info['documents'].append(doc_data)
            logging.info(f"✅ Added document: {message.document.file_id}")
        
        # Audio
        if message.audio:
            logging.info(f"🎵 Processing audio from message {message.message_id}")
            url_info = await get_telegram_file_url(message.audio.file_id)
            
            audio_data = {
                'file_id': message.audio.file_id,
                'file_unique_id': message.audio.file_unique_id,
                'duration': message.audio.duration,
                'performer': getattr(message.audio, 'performer', None),
                'title': getattr(message.audio, 'title', None),
                'file_size': getattr(message.audio, 'file_size', None),
            }
            
            if url_info['success']:
                audio_data.update({
                    'download_url': url_info['download_url'],
                    'file_path': url_info['file_path']
                })
            
            media_info['audio_files'].append(audio_data)
            logging.info(f"✅ Added audio: {message.audio.file_id}")
        
        # Voice messages
        if message.voice:
            logging.info(f"🎤 Processing voice from message {message.message_id}")
            url_info = await get_telegram_file_url(message.voice.file_id)
            
            voice_data = {
                'file_id': message.voice.file_id,
                'file_unique_id': message.voice.file_unique_id,
                'duration': message.voice.duration,
                'file_size': getattr(message.voice, 'file_size', None),
            }
            
            if url_info['success']:
                voice_data.update({
                    'download_url': url_info['download_url'],
                    'file_path': url_info['file_path']
                })
            
            media_info['voice_messages'].append(voice_data)
            logging.info(f"✅ Added voice: {message.voice.file_id}")
        
        # Video notes
        if message.video_note:
            logging.info(f"🎬 Processing video note from message {message.message_id}")
            url_info = await get_telegram_file_url(message.video_note.file_id)
            
            video_note_data = {
                'file_id': message.video_note.file_id,
                'file_unique_id': message.video_note.file_unique_id,
                'length': message.video_note.length,
                'duration': message.video_note.duration,
                'file_size': getattr(message.video_note, 'file_size', None),
            }
            
            if url_info['success']:
                video_note_data.update({
                    'download_url': url_info['download_url'],
                    'file_path': url_info['file_path']
                })
            
            media_info['video_notes'].append(video_note_data)
            logging.info(f"✅ Added video note: {message.video_note.file_id}")
    
    except Exception as e:
        logging.error(f"❌ Media extraction error: {e}")
    
    # Log qilish
    total_media = sum(len(media_info[key]) for key in media_info.keys())
    if total_media > 0:
        logging.info(f"📋 Extracted {total_media} media files from message {message.message_id}")
    
    return media_info


def merge_media_info(*media_infos) -> dict:
    """Bir necha media_info ni birlashtirish"""
    merged = {
        'photos': [],
        'videos': [],
        'documents': [],
        'audio_files': [],
        'voice_messages': [],
        'video_notes': []
    }
    
    for media_info in media_infos:
        for key in merged.keys():
            if key in media_info and media_info[key]:
                merged[key].extend(media_info[key])
    
    return merged


async def get_group_pk(chat_id: int) -> int | None:
    data = await backend_get(f"/api/monitoredgroup/?chat_id={chat_id}")
    if not data:
        return None
    lst = data if isinstance(data, list) else data.get("results", [])
    return lst[0]["id"] if lst else None


async def upsert_group(chat: types.Chat) -> int:
    pk = await get_group_pk(chat.id)
    if pk:
        return pk
    
    result = backend_post("/api/monitoredgroup/", {
        "chat_id": chat.id,
        "title": chat.title or f"Group-{chat.id}",
    })
    
    if result:
        return await get_group_pk(chat.id)
    return None


def save_rental_announcement_and_media(group_pk: int, main_message: types.Message, analysis_result: dict, merged_media_info: dict, all_texts: List[str]) -> bool:
    """Ijara elonini va media fayllarni saqlash"""
    try:
        logging.info(f"💾 Starting to save rental announcement...")
        
        # Joylashuv ma'lumotlari
        location_data = {}
        if main_message.location:
            location_data = {
                'location_latitude': main_message.location.latitude,
                'location_longitude': main_message.location.longitude,
                'location_address': getattr(main_message.location, 'address', None)
            }
        
        # Kontakt ma'lumotlarini tayyorlash
        contact_info = {
            'telegram_username': main_message.from_user.username,
            'found_contacts': analysis_result.get('contacts_found', []),
            'user_id': main_message.from_user.id
        }
        
        # Barcha textlarni birlashtirish
        combined_text = "\n".join(filter(None, all_texts))
        
        # Media sonini hisoblash
        total_media_count = sum(len(merged_media_info.get(key, [])) for key in merged_media_info.keys())
        
        logging.info(f"📊 Announcement details: {total_media_count} media files, confidence: {analysis_result.get('confidence_score', 0):.2f}")
        
        # Asosiy announcement payload
        announcement_payload = {
            "group": group_pk,
            "user_id": main_message.from_user.id,
            "username": main_message.from_user.username or "",
            "first_name": main_message.from_user.first_name or "",
            "last_name": main_message.from_user.last_name or "",
            "message_text": combined_text,
            "message_id": main_message.message_id,
            
            # Media ma'lumotlari JSON formatda
            "photos_data": merged_media_info.get('photos', []),
            "videos_data": merged_media_info.get('videos', []),
            "documents_data": merged_media_info.get('documents', []),
            "audio_files_data": merged_media_info.get('audio_files', []),
            "voice_messages_data": merged_media_info.get('voice_messages', []),
            
            # Tahlil natijalari
            "rental_keywords_found": analysis_result.get('keywords_found', []),
            "confidence_score": analysis_result.get('confidence_score', 0.0),
            
            # Kontakt va joylashuv
            "contact_info": contact_info,
            **location_data,
            
            # Raw data
            "raw_telegram_data": json.loads(main_message.model_dump_json()),
            
            "is_processed": False,
            "is_verified": False
        }
        
        # Debug: payload ni log qilish
        logging.info(f"🔍 Payload keys: {list(announcement_payload.keys())}")
        logging.info(f"🔍 Photos count: {len(announcement_payload['photos_data'])}")
        logging.info(f"🔍 Videos count: {len(announcement_payload['videos_data'])}")
        
        # Announcement yaratish
        logging.info("📤 Creating rental announcement...")
        announcement_result = backend_post("/api/rental-announcements/", announcement_payload)
        
        if not announcement_result:
            logging.error("❌ Failed to create announcement")
            return False
        
        announcement_id = announcement_result.get('id')
        if not announcement_id:
            logging.error("❌ No announcement ID returned from API")
            return False
        
        logging.info(f"✅ Created announcement with ID: {announcement_id}")
        
        # Media fayllar uchun alohida yozuvlar yaratish - ASOSIY TUZATISH
        media_files_saved = 0
        total_media_files = 0
        
        # Photos ni saqlash
        for photo_data in merged_media_info.get('photos', []):
            total_media_files += 1
            logging.info(f"📸 Saving photo {photo_data['file_id']}")
            
            media_payload = {
                'announcement': announcement_id,
                'media_type': 'photo',
                'file_id': photo_data['file_id'],
                'file_unique_id': photo_data['file_unique_id'],
                'file_size': photo_data.get('file_size'),
                'width': photo_data.get('width'),
                'height': photo_data.get('height'),
                'download_url': photo_data.get('download_url'),
                'file_name': f"photo_{photo_data['file_id'][:10]}.jpg",
                'telegram_data': photo_data,
                'is_downloaded': False
            }
            
            logging.info(f"📤 Sending photo payload: {media_payload}")
            result = backend_post("/api/rental-media-files/", media_payload)
            if result:
                media_files_saved += 1
                logging.info(f"✅ Saved photo media file: {photo_data['file_id']}")
            else:
                logging.error(f"❌ Failed to save photo: {photo_data['file_id']}")
        
        # Videos ni saqlash
        for video_data in merged_media_info.get('videos', []):
            total_media_files += 1
            logging.info(f"🎥 Saving video {video_data['file_id']}")
            
            media_payload = {
                'announcement': announcement_id,
                'media_type': 'video',
                'file_id': video_data['file_id'],
                'file_unique_id': video_data['file_unique_id'],
                'file_size': video_data.get('file_size'),
                'width': video_data.get('width'),
                'height': video_data.get('height'),
                'duration': video_data.get('duration'),
                'mime_type': video_data.get('mime_type'),
                'download_url': video_data.get('download_url'),
                'file_name': f"video_{video_data['file_id'][:10]}.mp4",
                'telegram_data': video_data,
                'is_downloaded': False
            }
            
            logging.info(f"📤 Sending video payload: {media_payload}")
            result = backend_post("/api/rental-media-files/", media_payload)
            if result:
                media_files_saved += 1
                logging.info(f"✅ Saved video media file: {video_data['file_id']}")
            else:
                logging.error(f"❌ Failed to save video: {video_data['file_id']}")
        
        # Documents ni saqlash
        for doc_data in merged_media_info.get('documents', []):
            total_media_files += 1
            logging.info(f"📄 Saving document {doc_data['file_id']}")
            
            media_payload = {
                'announcement': announcement_id,
                'media_type': 'document',
                'file_id': doc_data['file_id'],
                'file_unique_id': doc_data['file_unique_id'],
                'file_size': doc_data.get('file_size'),
                'mime_type': doc_data.get('mime_type'),
                'download_url': doc_data.get('download_url'),
                'file_name': doc_data.get('file_name') or f"document_{doc_data['file_id'][:10]}",
                'telegram_data': doc_data,
                'is_downloaded': False
            }
            
            logging.info(f"📤 Sending document payload: {media_payload}")
            result = backend_post("/api/rental-media-files/", media_payload)
            if result:
                media_files_saved += 1
                logging.info(f"✅ Saved document media file: {doc_data['file_id']}")
            else:
                logging.error(f"❌ Failed to save document: {doc_data['file_id']}")

        # Audio files ni saqlash
        for audio_data in merged_media_info.get('audio_files', []):
            total_media_files += 1
            logging.info(f"🎵 Saving audio {audio_data['file_id']}")
            
            media_payload = {
                'announcement': announcement_id,
                'media_type': 'audio',
                'file_id': audio_data['file_id'],
                'file_unique_id': audio_data['file_unique_id'],
                'file_size': audio_data.get('file_size'),
                'duration': audio_data.get('duration'),
                'performer': audio_data.get('performer'),
                'title': audio_data.get('title'),
                'download_url': audio_data.get('download_url'),
                'file_name': f"audio_{audio_data['file_id'][:10]}.mp3",
                'telegram_data': audio_data,
                'is_downloaded': False
            }
            
            logging.info(f"📤 Sending audio payload: {media_payload}")
            result = backend_post("/api/rental-media-files/", media_payload)
            if result:
                media_files_saved += 1
                logging.info(f"✅ Saved audio media file: {audio_data['file_id']}")
            else:
                logging.error(f"❌ Failed to save audio: {audio_data['file_id']}")

        # Voice messages ni saqlash
        for voice_data in merged_media_info.get('voice_messages', []):
            total_media_files += 1
            logging.info(f"🎤 Saving voice {voice_data['file_id']}")
            
            media_payload = {
                'announcement': announcement_id,
                'media_type': 'voice',
                'file_id': voice_data['file_id'],
                'file_unique_id': voice_data['file_unique_id'],
                'file_size': voice_data.get('file_size'),
                'duration': voice_data.get('duration'),
                'download_url': voice_data.get('download_url'),
                'file_name': f"voice_{voice_data['file_id'][:10]}.ogg",
                'telegram_data': voice_data,
                'is_downloaded': False
            }
            
            logging.info(f"📤 Sending voice payload: {media_payload}")
            result = backend_post("/api/rental-media-files/", media_payload)
            if result:
                media_files_saved += 1
                logging.info(f"✅ Saved voice media file: {voice_data['file_id']}")
            else:
                logging.error(f"❌ Failed to save voice: {voice_data['file_id']}")

        # Video notes ni saqlash
        for video_note_data in merged_media_info.get('video_notes', []):
            total_media_files += 1
            logging.info(f"🎬 Saving video note {video_note_data['file_id']}")
            
            media_payload = {
                'announcement': announcement_id,
                'media_type': 'video_note',
                'file_id': video_note_data['file_id'],
                'file_unique_id': video_note_data['file_unique_id'],
                'file_size': video_note_data.get('file_size'),
                'length': video_note_data.get('length'),
                'duration': video_note_data.get('duration'),
                'download_url': video_note_data.get('download_url'),
                'file_name': f"video_note_{video_note_data['file_id'][:10]}.mp4",
                'telegram_data': video_note_data,
                'is_downloaded': False
            }
            
            logging.info(f"📤 Sending video note payload: {media_payload}")
            result = backend_post("/api/rental-media-files/", media_payload)
            if result:
                media_files_saved += 1
                logging.info(f"✅ Saved video note media file: {video_note_data['file_id']}")
            else:
                logging.error(f"❌ Failed to save video note: {video_note_data['file_id']}")
        
        logging.info(f"🎯 FINAL RESULT: Saved announcement {announcement_id} with {media_files_saved}/{total_media_files} media files")
        
        if total_media_files > 0 and media_files_saved == 0:
            logging.error("❌ CRITICAL: No media files were saved!")
            return False
        
        return True
        
    except Exception as e:
        logging.error(f"❌ Save rental announcement error: {e}", exc_info=True)
        return False


async def process_media_group(media_group_id: str):
    """Media groupni qayta ishlash"""
    if media_group_id not in media_groups:
        return
    
    group_data = media_groups[media_group_id]
    messages = group_data['messages']
    
    if not messages:
        return
    
    try:
        logging.info(f"🔄 Processing media group {media_group_id} with {len(messages)} messages")
        
        # Birinchi xabarni asosiy deb hisoblaymiz
        main_message = messages[0]
        
        # Guruhni ro'yxatga olish yoki yangilash
        group_pk = await upsert_group(main_message.chat)
        if not group_pk:
            logging.error("❌ Failed to upsert group")
            return
        
        # Barcha media ma'lumotlarini yig'ish
        all_media_infos = []
        all_texts = []
        
        for i, message in enumerate(messages):
            logging.info(f"📋 Processing message {i+1}/{len(messages)} (ID: {message.message_id})")
            media_info = await extract_media_info_with_urls(message)
            all_media_infos.append(media_info)
            
            # Text yoki caption ni yig'ish
            text_content = message.text or message.caption or ""
            if text_content.strip():
                all_texts.append(text_content.strip())
                logging.info(f"📝 Added text: {text_content[:50]}...")
        
        # Media ma'lumotlarini birlashtirish
        merged_media_info = merge_media_info(*all_media_infos)
        
        # Barcha textlarni birlashtirish
        combined_text = "\n".join(all_texts)
        
        # Foydalanuvchi ma'lumotlari
        user_data = {
            'username': main_message.from_user.username,
            'first_name': main_message.from_user.first_name,
            'last_name': main_message.from_user.last_name,
            'user_id': main_message.from_user.id
        }
        
        # Media soni
        total_media_count = sum(len(merged_media_info.get(key, [])) for key in merged_media_info.keys())
        
        logging.info(f"📊 Media group summary: {total_media_count} media files, text length: {len(combined_text)}")
        
        # Ijara eloni ehtimolligini tahlil qilish
        analysis = analyze_rental_content(combined_text, user_data, total_media_count)
        
        logging.info(f"🔍 Analysis result: confidence={analysis['confidence_score']:.2f}, is_rental={analysis['is_likely_rental']}")
        
        # Agar ijara eloni bo'lishi mumkin bo'lsa, saqlash
        if analysis['is_likely_rental'] or analysis['confidence_score'] > 0.15:
            logging.info("💾 Starting to save media group announcement...")
            success = save_rental_announcement_and_media(
                group_pk, main_message, analysis, merged_media_info, all_texts
            )
            
            if success:
                confidence_percent = int(analysis['confidence_score'] * 100)
                keywords_str = ", ".join(analysis['keywords_found'][:5])
                
                logging.info(
                    f"🏠 MEDIA GROUP RENTAL SAVED [{confidence_percent}%] in «{main_message.chat.title}» "
                    f"by {user_data['first_name']} (@{user_data['username']}) "
                    f"- {total_media_count} files, Keywords: {keywords_str}"
                )
            else:
                logging.error("❌ Failed to save media group announcement")
        else:
            logging.info(f"ℹ️ Media group confidence too low: {int(analysis['confidence_score'] * 100)}%")
    
    except Exception as e:
        logging.error(f"❌ Process media group error: {e}", exc_info=True)
    finally:
        # Media group ma'lumotlarini tozalash
        if media_group_id in media_groups:
            del media_groups[media_group_id]


async def handle_single_message(message: types.Message):
    """Yagona xabarni qayta ishlash"""
    try:
        logging.info(f"📝 Processing single message {message.message_id} from {message.chat.title}")
        
        # Guruhni ro'yxatga olish yoki yangilash
        group_pk = await upsert_group(message.chat)
        if not group_pk:
            logging.error("❌ Failed to upsert group")
            return
        
        # Media ma'lumotlarini ajratib olish
        media_info = await extract_media_info_with_urls(message)
        
        # Xabar matnini olish (text yoki caption)
        text_content = message.text or message.caption or ""
        
        # Foydalanuvchi ma'lumotlari
        user_data = {
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name,
            'user_id': message.from_user.id
        }
        
        # Media soni
        total_media_count = sum(len(media_info.get(key, [])) for key in media_info.keys())
        
        logging.info(f"📊 Single message summary: {total_media_count} media files, text length: {len(text_content)}")
        
        # Ijara eloni ehtimolligini tahlil qilish
        analysis = analyze_rental_content(text_content, user_data, total_media_count)
        
        logging.info(f"🔍 Analysis result: confidence={analysis['confidence_score']:.2f}, is_rental={analysis['is_likely_rental']}")
        
        # Agar ijara eloni bo'lishi mumkin bo'lsa, saqlash
        if analysis['is_likely_rental'] or analysis['confidence_score'] > 0.15:
            logging.info("💾 Starting to save single message announcement...")
            success = save_rental_announcement_and_media(
                group_pk, message, analysis, media_info, [text_content] if text_content else []
            )
            
            if success:
                confidence_percent = int(analysis['confidence_score'] * 100)
                keywords_str = ", ".join(analysis['keywords_found'][:5])
                
                logging.info(
                    f"🏠 SINGLE RENTAL SAVED [{confidence_percent}%] in «{message.chat.title}» "
                    f"by {user_data['first_name']} (@{user_data['username']}) "
                    f"- {total_media_count} files, Keywords: {keywords_str}"
                )
            else:
                logging.error("❌ Failed to save single message announcement")
        else:
            logging.info(f"ℹ️ Single message confidence too low: {int(analysis['confidence_score'] * 100)}%")
    
    except Exception as e:
        logging.error(f"❌ Handle single message error: {e}", exc_info=True)


@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def monitor_group_messages(message: types.Message):
    """Guruh xabarlarini kuzatish va ijara elonlarini aniqlash"""
    try:
        logging.info(f"📨 Received message {message.message_id} in {message.chat.title}")
        
        # Media group bor-yo'qligini tekshirish
        media_group_id = getattr(message, 'media_group_id', None)
        
        if media_group_id:
            logging.info(f"📁 Message is part of media group: {media_group_id}")
            
            # Media group xabari
            if media_group_id not in media_groups:
                media_groups[media_group_id] = {
                    'messages': [],
                    'timer': None
                }
                logging.info(f"🆕 Created new media group storage for: {media_group_id}")
            
            # Xabarni qo'shish
            media_groups[media_group_id]['messages'].append(message)
            logging.info(f"➕ Added message to group {media_group_id}, total messages: {len(media_groups[media_group_id]['messages'])}")
            
            # Agar timer mavjud bo'lsa, bekor qilish
            if media_groups[media_group_id]['timer']:
                media_groups[media_group_id]['timer'].cancel()
                logging.debug("⏰ Cancelled previous timer")
            
            # Yangi timer o'rnatish
            async def delayed_process():
                await asyncio.sleep(MEDIA_GROUP_TIMEOUT)
                await process_media_group(media_group_id)
            
            media_groups[media_group_id]['timer'] = asyncio.create_task(delayed_process())
            logging.debug(f"⏰ Set {MEDIA_GROUP_TIMEOUT}s timer for media group {media_group_id}")
            
        else:
            logging.info("📄 Message is not part of media group, processing as single message")
            # Oddiy xabar (media group emas)
            await handle_single_message(message)
    
    except Exception as e:
        logging.error(f"❌ Monitor group messages error: {e}", exc_info=True)


# Bot ishga tushirish
async def main():
    logging.info("🤖 Rental monitoring bot starting...")
    logging.info(f"📊 Monitoring keywords: {len(RENTAL_KEYWORDS)} keywords")
    logging.info(f"⏱️  Media group timeout: {MEDIA_GROUP_TIMEOUT} seconds")
    logging.info(f"🔗 API Base: {API_BASE}")
    logging.info(f"📥 Media download enabled: True")
    
    # Bot ma'lumotlarini olish
    try:
        bot_info = await bot.get_me()
        logging.info(f"🤖 Bot username: @{bot_info.username}")
    except Exception as e:
        logging.error(f"❌ Failed to get bot info: {e}")
    
    # Backend ulanishini tekshirish
    try:
        test_response = await backend_get("/api/monitoredgroup/")
        if test_response is not None:
            logging.info("✅ Backend connection successful")
        else:
            logging.error("❌ Backend connection failed")
    except Exception as e:
        logging.error(f"❌ Backend connection error: {e}")
    
    logging.info("🚀 Bot is ready and listening for messages...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())