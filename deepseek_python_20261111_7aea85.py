import os
import asyncio
import logging
import feedparser
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

# ---------- Конфиг ----------
BOT_TOKEN   = os.environ["BOT_TOKEN"]
CHAT_ID     = os.environ["CHAT_ID"]
CHANNEL_ID  = os.environ["YOUTUBE_CHANNEL_ID"]
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 300))

STATE_FILE = "/data/last_video.txt"   # Railway Volume; без Volume — "last_video.txt"
RSS_URL = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("yt-notifier")


def load_last_video_id() -> str | None:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except FileNotFoundError:
        return None


def save_last_video_id(video_id: str) -> None:
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            f.write(video_id)
    except OSError as e:
        log.warning("Не удалось сохранить state: %s", e)


async def send_notification(bot: Bot, entry) -> None:
    title = entry.title
    link = entry.link
    video_id = entry.yt_videoid
    thumbnail = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
    caption = f"🎬 <b>{title}</b>\n\n▶️ <a href='{link}'>Смотреть на YouTube</a>"

    try:
        await bot.send_photo(chat_id=CHAT_ID, photo=thumbnail,
                             caption=caption, parse_mode=ParseMode.HTML)
        log.info("Отправлено: %s", title)
    except TelegramError as e:
        log.warning("maxres не сработал (%s), пробую hqdefault", e)
        await bot.send_photo(
            chat_id=CHAT_ID,
            photo=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            caption=caption,
            parse_mode=ParseMode.HTML,
        )


async def main_loop() -> None:
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    log.info("Бот запущен: @%s", me.username)
    log.info("Канал YouTube: %s | Чат: %s | Интервал: %s сек",
             CHANNEL_ID, CHAT_ID, CHECK_INTERVAL)

    last_video_id = load_last_video_id()
    if last_video_id is None:
        feed = feedparser.parse(RSS_URL)
        if feed.entries:
            last_video_id = feed.entries[0].yt_videoid
            save_last_video_id(last_video_id)
            log.info("Инициализация: последнее видео = %s", last_video_id)
        else:
            log.warning("Пустая лента. Проверьте YOUTUBE_CHANNEL_ID.")

    while True:
        try:
            feed = feedparser.parse(RSS_URL)
            if feed.entries:
                new_entries = []
                for entry in feed.entries:
                    if entry.yt_videoid == last_video_id:
                        break
                    new_entries.append(entry)

                for entry in reversed(new_entries):
                    await send_notification(bot, entry)
                    last_video_id = entry.yt_videoid
                    save_last_video_id(last_video_id)
        except Exception as e:
            log.exception("Ошибка в цикле: %s", e)

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main_loop())