
import asyncio
import sqlite3
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command


# =========================================================
# НАСТРОЙКИ
# =========================================================

# Токен, который выдал @BotFather
BOT_TOKEN = os.getenv("8970777640:AAG3EUAmmYzXGP20eePkDNzE81jwweH9p5c")

# ТВОЙ Telegram ID
# Например: 123456789
ADMIN_ID = 7346162876

# Ссылка, которую увидит пользователь,
# если введёт неправильный ключ
ACCESS_LINK = "@gryaznost"


# =========================================================
# БАЗА ДАННЫХ SQLITE
# =========================================================

db = sqlite3.connect("bot.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS videos (
    keyword TEXT PRIMARY KEY,
    file_id TEXT NOT NULL
)
""")

db.commit()


# =========================================================
# BOT / DISPATCHER
# =========================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# СОСТОЯНИЕ АДМИНИСТРАТОРА
# =========================================================

# Здесь временно хранится:
#
# Telegram ID администратора -> ключ
#
# Например:
# 123456789 -> "pantera79"
#
# Это означает, что сейчас бот ждёт видео
# для ключа pantera79.

waiting_for_video = {}


# =========================================================
# ПРОВЕРКА АДМИНИСТРАТОРА
# =========================================================

def is_admin(message: types.Message) -> bool:
    return message.from_user.id == ADMIN_ID


# =========================================================
# /START
# =========================================================

@dp.message(CommandStart())
async def start_handler(message: types.Message):

    if is_admin(message):

        await message.answer(
            "👋 Панель администратора\n\n"
            "Добавить видео:\n"
            "/addvideo ключ\n\n"
            "Удалить видео:\n"
            "/delete ключ\n\n"
            "Список видео:\n"
            "/list"
        )

    else:

        await message.answer(
            "Отправьте ключевое слово."
        )


# =========================================================
# /ADDVIDEO
# =========================================================

@dp.message(Command("addvideo"))
async def add_video_handler(message: types.Message):

    # Обычным пользователям команда недоступна
    if not is_admin(message):
        return

    # Получаем аргумент после команды
    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:

        await message.answer(
            "❌ Укажи ключевое слово.\n\n"
            "Пример:\n"
            "/addvideo pantera79"
        )

        return

    keyword = parts[1]

    # Убираем пробелы по краям
    keyword = keyword.strip()

    # Проверяем, есть ли уже такой ключ
    cursor.execute(
        "SELECT keyword FROM videos WHERE keyword = ?",
        (keyword,)
    )

    existing = cursor.fetchone()

    # Запоминаем, для какого ключа ждём видео
    waiting_for_video[message.from_user.id] = keyword

    if existing:

        await message.answer(
            f"🔄 Ключ «{keyword}» уже существует.\n\n"
            f"Отправь новое видео — старое будет заменено."
        )

    else:

        await message.answer(
            f"✅ Ключ: {keyword}\n\n"
            f"Теперь отправь мне видео."
        )


# =========================================================
# /DELETE
# =========================================================

@dp.message(Command("delete"))
async def delete_handler(message: types.Message):

    if not is_admin(message):
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:

        await message.answer(
            "Использование:\n"
            "/delete pantera79"
        )

        return

    keyword = parts[1].strip()

    cursor.execute(
        "DELETE FROM videos WHERE keyword = ?",
        (keyword,)
    )

    db.commit()

    if cursor.rowcount > 0:

        await message.answer(
            f"🗑 Ключ «{keyword}» удалён."
        )

    else:

        await message.answer(
            f"❌ Ключ «{keyword}» не найден."
        )


# =========================================================
# /LIST
# =========================================================

@dp.message(Command("list"))
async def list_handler(message: types.Message):

    if not is_admin(message):
        return

    cursor.execute(
        "SELECT keyword FROM videos ORDER BY keyword"
    )

    rows = cursor.fetchall()

    if not rows:

        await message.answer(
            "📭 В базе пока нет видео."
        )

        return

    text = "📹 Добавленные видео:\n\n"

    for number, row in enumerate(rows, start=1):

        text += f"{number}. {row[0]}\n"

    await message.answer(text)


# =========================================================
# ОБРАБОТКА ВСЕХ СООБЩЕНИЙ
# =========================================================

@dp.message()
async def message_handler(message: types.Message):

    user_id = message.from_user.id

    # =====================================================
    # АДМИН СЕЙЧАС ДОБАВЛЯЕТ ВИДЕО
    # =====================================================

    if user_id == ADMIN_ID and user_id in waiting_for_video:

        # Проверяем, действительно ли это видео
        if not message.video:

            await message.answer(
                "❌ Я жду видео.\n\n"
                "Отправь именно видеофайл."
            )

            return

        # Получаем ключ
        keyword = waiting_for_video[user_id]

        # Получаем Telegram file_id
        file_id = message.video.file_id

        # Сохраняем видео
        # Если ключ уже существует — заменяем его
        cursor.execute("""
            INSERT OR REPLACE INTO videos (keyword, file_id)
            VALUES (?, ?)
        """, (keyword, file_id))

        db.commit()

        # Удаляем состояние ожидания
        del waiting_for_video[user_id]

        await message.answer(
            "✅ Видео успешно сохранено!\n\n"
            f"🔑 Ключ: {keyword}"
        )

        return

    # =====================================================
    # ЕСЛИ ПОЛЬЗОВАТЕЛЬ ОТПРАВИЛ НЕ ТЕКСТ
    # =====================================================

    if not message.text:

        await message.answer(
            f"Необходимо купить доступ: {ACCESS_LINK}"
        )

        return

    # =====================================================
    # КЛЮЧЕВОЕ СЛОВО
    # =====================================================

    keyword = message.text

    # ВАЖНО:
    # Здесь используется обычное сравнение строки.
    #
    # Поэтому:
    #
    # pantera79     -> найдено
    # Pantera79     -> НЕ найдено
    # pantera79     -> найдено
    # pantera79     -> найдено
    # pantera790    -> НЕ найдено
    #
    # Никакого поиска по частичному совпадению нет.

    cursor.execute(
        "SELECT file_id FROM videos WHERE keyword = ?",
        (keyword,)
    )

    result = cursor.fetchone()

    # =====================================================
    # КЛЮЧ НАЙДЕН
    # =====================================================

    if result:

        file_id = result[0]

        await message.answer_video(
            video=file_id
        )

        return

    # =====================================================
    # КЛЮЧ НЕ НАЙДЕН
    # =====================================================

    await message.answer(
        f"Необходимо купить доступ: {ACCESS_LINK}"
    )


# =========================================================
# ЗАПУСК БОТА
# =========================================================

async def main():

    print("================================")
    print("Telegram-бот запущен!")
    print("================================")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

