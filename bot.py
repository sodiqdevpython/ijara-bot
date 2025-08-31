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

MEDIA_GROUP_TIMEOUT = 2

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

PRICE_PATTERNS = [
    r'\b\d+[\s]*(?:so\'m|sum|сум|руб|rub|\$|usd|€|eur)\b',
    r'\b\d+[\s]*(?:ming|тыс|k|thousand)\b',
    r'\b\d+[\s]*(?:million|mln|млн)\b',
    r'\$\s*\d+',
    r'\d+\s*\$',
    r'\b\d{3,}\b'
]

CONTACT_PATTERNS = [
    r'\+?\d{1,4}[\s\-\(\)]*\d{2,3}[\s\-\(\)]*\d{3,4}[\s\-\(\)]*\d{2,4}',  # Telefon raqamlari
    r'@\w+',  # Username
    r't\.me/\w+',  # Telegram link
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

media_groups: Dict[str, Dict] = {}

def backend_post(endpoint: str, payload: dict):
    try:
        response = requests.post(f"{API_BASE}{endpoint}", json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Backend POST error: {e}")
        return None

async def backend_get(endpoint: str) -> list | dict:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(f"{API_BASE}{endpoint}")
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logging.error(f"Backend GET error: {e}")
        return None


def analyze_rental_content(text: str, user_data: dict, media_count: int) -> dict:
    if not text:
        text = ""
    
    text_lower = text.lower()
    
    found_keywords = []
    for keyword in RENTAL_KEYWORDS:
        if keyword.lower() in text_lower:
            found_keywords.append(keyword)
    
    prices_found = []
    for pattern in PRICE_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        prices_found.extend(matches)
    
    contacts_found = []
    for pattern in CONTACT_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        contacts_found.extend(matches)
    
    confidence = 0.0
    
    if found_keywords:
        confidence += min(len(found_keywords) * 0.15, 0.6)
    
    if prices_found:
        confidence += 0.25
    
    if contacts_found:
        confidence += 0.2
    
    if media_count > 0:
        confidence += min(media_count * 0.05, 0.3)

    if user_data.get('username') or any('phone' in str(contact).lower() for contact in contacts_found):
        confidence += 0.1
    
    confidence = min(confidence, 1.0)
    
    return {
        'keywords_found': found_keywords,
        'prices_found': prices_found,
        'contacts_found': contacts_found,
        'confidence_score': confidence,
        'is_likely_rental': confidence >= 0.3
    }


def extract_media_info(message: types.Message) -> dict:
    media_info = {
        'photos': [],
        'videos': [],
        'documents': [],
        'audio_files': [],
        'voice_messages': [],
        'video_notes': []
    }
    
    try:
        if message.photo:
            largest_photo = max(message.photo, key=lambda x: x.width * x.height)
            media_info['photos'].append({
                'file_id': largest_photo.file_id,
                'file_unique_id': largest_photo.file_unique_id,
                'width': largest_photo.width,
                'height': largest_photo.height,
                'file_size': getattr(largest_photo, 'file_size', None)
            })
        
        if message.video:
            media_info['videos'].append({
                'file_id': message.video.file_id,
                'file_unique_id': message.video.file_unique_id,
                'width': message.video.width,
                'height': message.video.height,
                'duration': message.video.duration,
                'file_size': getattr(message.video, 'file_size', None),
                'mime_type': getattr(message.video, 'mime_type', None)
            })
        
        if message.document:
            media_info['documents'].append({
                'file_id': message.document.file_id,
                'file_unique_id': message.document.file_unique_id,
                'file_name': getattr(message.document, 'file_name', None),
                'mime_type': getattr(message.document, 'mime_type', None),
                'file_size': getattr(message.document, 'file_size', None)
            })
        
        if message.audio:
            media_info['audio_files'].append({
                'file_id': message.audio.file_id,
                'file_unique_id': message.audio.file_unique_id,
                'duration': message.audio.duration,
                'performer': getattr(message.audio, 'performer', None),
                'title': getattr(message.audio, 'title', None),
                'file_size': getattr(message.audio, 'file_size', None)
            })
        
        if message.voice:
            media_info['voice_messages'].append({
                'file_id': message.voice.file_id,
                'file_unique_id': message.voice.file_unique_id,
                'duration': message.voice.duration,
                'file_size': getattr(message.voice, 'file_size', None)
            })
        
        if message.video_note:
            media_info['video_notes'].append({
                'file_id': message.video_note.file_id,
                'file_unique_id': message.video_note.file_unique_id,
                'length': message.video_note.length,
                'duration': message.video_note.duration,
                'file_size': getattr(message.video_note, 'file_size', None)
            })
    
    except Exception as e:
        logging.error(f"Media extraction error: {e}")
    
    return media_info


def merge_media_info(*media_infos) -> dict:
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


def save_rental_announcement(group_pk: int, main_message: types.Message, analysis_result: dict, merged_media_info: dict, all_texts: List[str]):
    try:
        location_data = {}
        if main_message.location:
            location_data = {
                'location_latitude': main_message.location.latitude,
                'location_longitude': main_message.location.longitude,
                'location_address': getattr(main_message.location, 'address', None)
            }

        contact_info = {
            'telegram_username': main_message.from_user.username,
            'found_contacts': analysis_result.get('contacts_found', []),
            'user_id': main_message.from_user.id
        }
        
        combined_text = "\n".join(filter(None, all_texts))
        
        payload = {
            "group": group_pk,
            "user_id": main_message.from_user.id,
            "username": main_message.from_user.username,
            "first_name": main_message.from_user.first_name,
            "last_name": main_message.from_user.last_name,
            "message_text": combined_text,
            "message_id": main_message.message_id,
            
            "photos": merged_media_info.get('photos', []),
            "videos": merged_media_info.get('videos', []),
            "documents": merged_media_info.get('documents', []),
            "audio_files": merged_media_info.get('audio_files', []),
            "voice_messages": merged_media_info.get('voice_messages', []),
            
            "rental_keywords_found": analysis_result.get('keywords_found', []),
            "confidence_score": analysis_result.get('confidence_score', 0.0),
            
            "contact_info": contact_info,
            **location_data,
            
            "raw_telegram_data": json.loads(main_message.model_dump_json()),
            
            "is_processed": False,
            "is_verified": False
        }
        
        result = backend_post("/api/rental-announcements/", payload)
        return result is not None
        
    except Exception as e:
        logging.error(f"Save rental announcement error: {e}")
        return False


async def process_media_group(media_group_id: str):
    if media_group_id not in media_groups:
        return
    
    group_data = media_groups[media_group_id]
    messages = group_data['messages']
    
    if not messages:
        return
    
    try:
        main_message = messages[0]
        group_pk = await upsert_group(main_message.chat)
        if not group_pk:
            logging.error("Failed to upsert group")
            return
        all_media_infos = []
        all_texts = []
        
        for message in messages:
            media_info = extract_media_info(message)
            all_media_infos.append(media_info)
            
            text_content = message.text or message.caption or ""
            if text_content.strip():
                all_texts.append(text_content.strip())
        
        merged_media_info = merge_media_info(*all_media_infos)
        
        combined_text = "\n".join(all_texts)
        
        user_data = {
            'username': main_message.from_user.username,
            'first_name': main_message.from_user.first_name,
            'last_name': main_message.from_user.last_name,
            'user_id': main_message.from_user.id
        }
        
        total_media_count = (
            len(merged_media_info.get('photos', [])) +
            len(merged_media_info.get('videos', [])) +
            len(merged_media_info.get('documents', [])) +
            len(merged_media_info.get('audio_files', [])) +
            len(merged_media_info.get('voice_messages', []))
        )
        
        analysis = analyze_rental_content(combined_text, user_data, total_media_count)
        
        if analysis['is_likely_rental'] or analysis['confidence_score'] > 0.15:
            success = save_rental_announcement(
                group_pk, main_message, analysis, merged_media_info, all_texts
            )
            
            if success:
                confidence_percent = int(analysis['confidence_score'] * 100)
                keywords_str = ", ".join(analysis['keywords_found'][:5])
                
                logging.info(
                    f"🏠 Rental found [{confidence_percent}%] in «{main_message.chat.title}» "
                    f"by {user_data['first_name']} (@{user_data['username']}) "
                    f"- Media: {total_media_count} files, Keywords: {keywords_str}"
                )
            else:
                logging.error("Failed to save rental announcement")
        else:
            if analysis['confidence_score'] > 0:
                logging.debug(f"Low confidence rental message [{int(analysis['confidence_score'] * 100)}%] in {main_message.chat.title}")
    
    except Exception as e:
        logging.error(f"Process media group error: {e}")
    finally:
        if media_group_id in media_groups:
            del media_groups[media_group_id]


async def handle_single_message(message: types.Message):
    try:
        group_pk = await upsert_group(message.chat)
        if not group_pk:
            logging.error("Failed to upsert group")
            return
        
        media_info = extract_media_info(message)

        text_content = message.text or message.caption or ""
        
        user_data = {
            'username': message.from_user.username,
            'first_name': message.from_user.first_name,
            'last_name': message.from_user.last_name,
            'user_id': message.from_user.id
        }
        
        total_media_count = (
            len(media_info.get('photos', [])) +
            len(media_info.get('videos', [])) +
            len(media_info.get('documents', [])) +
            len(media_info.get('audio_files', [])) +
            len(media_info.get('voice_messages', []))
        )
        
        analysis = analyze_rental_content(text_content, user_data, total_media_count)
        
        if analysis['is_likely_rental'] or analysis['confidence_score'] > 0.15:
            success = save_rental_announcement(
                group_pk, message, analysis, media_info, [text_content] if text_content else []
            )
            
            if success:
                confidence_percent = int(analysis['confidence_score'] * 100)
                keywords_str = ", ".join(analysis['keywords_found'][:5])
                
                logging.info(
                    f"🏠 Single rental found [{confidence_percent}%] in «{message.chat.title}» "
                    f"by {user_data['first_name']} (@{user_data['username']}) "
                    f"- Media: {total_media_count} files, Keywords: {keywords_str}"
                )
            else:
                logging.error("Failed to save rental announcement")
        else:
            if analysis['confidence_score'] > 0:
                logging.debug(f"Low confidence rental message [{int(analysis['confidence_score'] * 100)}%] in {message.chat.title}")
    
    except Exception as e:
        logging.error(f"Handle single message error: {e}")


@dp.message(F.chat.type.in_({ChatType.GROUP, ChatType.SUPERGROUP}))
async def monitor_group_messages(message: types.Message):
    """Guruh xabarlarini kuzatish va ijara elonlarini aniqlash"""
    try:
        media_group_id = getattr(message, 'media_group_id', None)
        
        if media_group_id:
            if media_group_id not in media_groups:
                media_groups[media_group_id] = {
                    'messages': [],
                    'timer': None
                }
            
            media_groups[media_group_id]['messages'].append(message)
            
            if media_groups[media_group_id]['timer']:
                media_groups[media_group_id]['timer'].cancel()
            
            async def delayed_process():
                await asyncio.sleep(MEDIA_GROUP_TIMEOUT)
                await process_media_group(media_group_id)
            
            media_groups[media_group_id]['timer'] = asyncio.create_task(delayed_process())
            
        else:
            await handle_single_message(message)
    
    except Exception as e:
        logging.error(f"Monitor group messages error: {e}")


async def main():
    logging.info(f"Monitoring keywords: {len(RENTAL_KEYWORDS)} keywords")
    logging.info(f"Media group timeout: {MEDIA_GROUP_TIMEOUT} seconds")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())