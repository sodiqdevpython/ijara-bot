import requests

TELEGRAM_BOT_TOKEN = "7413765945:AAHqyNsG2tvyUt0XgBd5OT0FuTA94t1SpEc"

def get_photo_urls(announcement):
    """Berilgan RentalAnnouncement ichidagi barcha rasmlar uchun URL qaytaradi"""
    urls = []
    for photo in announcement.photos:  # JSONField ichidagi ro‘yxat
        file_id = photo.get("file_id")
        if not file_id:
            continue

        file_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
        r = requests.get(file_info_url)
        result = r.json().get("result")

        if not result:
            continue

        file_path = result["file_path"]
        file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        urls.append(file_url)

    return urls
