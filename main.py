import json
import random
import sqlite3
import os
import time
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ===== НАСТРОЙКИ =====
TOKEN = "8798378718:AAGRxt_IwUR0m8a2M97l-5TPn8PhWpcNL9s"
CACHE_CHAT_ID = -1002546333211
ADMIN_ID = 5206039766
QUIZ_FILE = "quizzes.json"
MEMES_FILE = "memes.json"

# ===== АНТИСПАМ =====
antispam = {}

def check_antispam(user_id):
    now = time.time()
    user = antispam.get(user_id, {"blocked_until": 0, "last_command": 0, "count": 0})
    
    if user["blocked_until"] > now:
        wait = int(user["blocked_until"] - now)
        return False, f"🚫 *Стоп!* Ты в спам-бане `{wait}` сек.\n📖 Найди викторину в канале."
    
    if now - user["last_command"] < 2.0:
        user["count"] += 1
        user["last_command"] = now
        antispam[user_id] = user
        
        if user["count"] >= 2:
            user["blocked_until"] = now + 20
            user["count"] = 0
            antispam[user_id] = user
            return False, "🚫 *Спам-детект!* Ты слишком часто жмёшь команды.\n⏳ Блокировка `20` сек.\n📖 Полистай канал с викторинами."
        else:
            return False, ""
    
    user["count"] = 0
    user["last_command"] = now
    antispam[user_id] = user
    return True, ""

user_quiz_timers = {}

# ===== БАЗА ДАННЫХ =====
def init_db():
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  total INTEGER DEFAULT 0,
                  rank TEXT DEFAULT "Новичок")''')
    c.execute('''CREATE TABLE IF NOT EXISTS completions
                 (user_id INTEGER,
                  quiz_id TEXT,
                  completed_at TIMESTAMP,
                  PRIMARY KEY (user_id, quiz_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS rebus_solves
                 (user_id INTEGER PRIMARY KEY,
                  user_name TEXT,
                  solves INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()
    print("✅ База данных инициализирована")

def has_completed(user_id, quiz_id):
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    c.execute("SELECT 1 FROM completions WHERE user_id = ? AND quiz_id = ?", (user_id, quiz_id))
    result = c.fetchone()
    conn.close()
    return result is not None

def add_rebus_solve(user_id, user_name):
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    c.execute('''INSERT INTO rebus_solves (user_id, user_name, solves)
                 VALUES (?, ?, 1)
                 ON CONFLICT(user_id) DO UPDATE SET
                 solves = solves + 1,
                 user_name = excluded.user_name''',
              (user_id, user_name))
    conn.commit()
    conn.close()

def add_completion(user_id, first_name, quiz_id):
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    
    c.execute("INSERT OR IGNORE INTO completions (user_id, quiz_id, completed_at) VALUES (?, ?, ?)",
              (user_id, quiz_id, datetime.now()))
    
    c.execute("SELECT total, first_name FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if user:
        new_total = user[0] + 1
        rank = get_rank_by_score(new_total)
        c.execute("UPDATE users SET first_name = ?, total = ?, rank = ? WHERE user_id = ?",
                  (first_name, new_total, rank, user_id))
    else:
        rank = get_rank_by_score(1)
        c.execute("INSERT INTO users (user_id, first_name, total, rank) VALUES (?, ?, ?, ?)",
                  (user_id, first_name, 1, rank))
    
    conn.commit()
    conn.close()
    return get_user_stats(user_id)

def update_user(user_id, first_name):
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    c.execute("UPDATE users SET first_name = ? WHERE user_id = ?", (first_name, user_id))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    c.execute("SELECT total, rank FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {"total": result[0], "rank": result[1]}
    return {"total": 0, "rank": "Новичок"}

def get_user_by_id(user_id):
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    c.execute("SELECT first_name, total, rank FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result:
        return {"first_name": result[0], "total": result[1], "rank": result[2]}
    return None

def get_rank_by_score(total):
    if total >= 100:
        return "Гендиректор Организации"
    elif total >= 45:
        return "Первый"
    elif total >= 20:
        return "Багрянник"
    elif total >= 10:
        return "Мироходец"
    else:
        return "Новичок"

# ===== ЗАГРУЗКА ВИКТОРИН =====
def load_quizzes():
    if not os.path.exists(QUIZ_FILE):
        print(f"⚠️ Файл {QUIZ_FILE} не найден, создаю тестовые данные")
        return []
    try:
        with open(QUIZ_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list) and len(data) > 0:
                print(f"✅ Загружено викторин: {len(data)}")
                return data
            else:
                print(f"⚠️ Файл {QUIZ_FILE} пуст")
                return []
    except Exception as e:
        print(f"❌ Ошибка загрузки {QUIZ_FILE}: {e}")
        return []

def save_quizzes(quizzes):
    with open(QUIZ_FILE, "w", encoding="utf-8") as f:
        json.dump(quizzes, f, ensure_ascii=False, indent=2)

# ===== ЗАГРУЗКА МЕМОВ =====
def load_memes():
    if not os.path.exists('memes.json'):
        print("⚠️ Файл memes.json не найден")
        return []
    with open('memes.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        return []

def save_memes(memes):
    with open(MEMES_FILE, "w", encoding="utf-8") as f:
        json.dump(memes, f, ensure_ascii=False, indent=2)

# ===== ДЕКОРАТОР АНТИСПАМА =====
def antispam_decorator(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        allowed, msg = check_antispam(user_id)
        if not allowed:
            if msg:
                await update.message.reply_text(msg, parse_mode="Markdown")
            return
        return await func(update, context)
    return wrapper

# ===== НОВЫЕ ФУНКЦИИ ВИКТОРИН =====
@antispam_decorator
async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quizzes = load_quizzes()
    if not quizzes:
        await update.message.reply_text("❌ Викторин пока нет")
        return

    q = random.choice(quizzes)
    
    # Проверяем, что викторина в правильном формате
    if "question" not in q or "options" not in q or "correct" not in q:
        await update.message.reply_text("❌ Эта викторина не готова (нет вопросов/ответов)")
        return
    
    # Сохраняем текущий вопрос
    context.user_data["current_quiz"] = q
    
    keyboard = []
    for i, opt in enumerate(q["options"]):
        keyboard.append([InlineKeyboardButton(opt, callback_data=f"quiz_ans_{i}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"❓ *{q['question']}*\n\n_Выбери правильный вариант:_",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

@antispam_decorator
async def fastqz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quizzes = load_quizzes()
    if not quizzes:
        await update.message.reply_text("❌ Викторин пока нет")
        return

    q = random.choice(quizzes)
    
    if "question" not in q or "options" not in q or "correct" not in q:
        await update.message.reply_text("❌ Эта викторина не готова")
        return
    
    # Для быстрой викторины рейтинг не начисляется, поэтому сохраняем с пометкой
    context.user_data["current_quiz_fast"] = q
    
    keyboard = []
    for i, opt in enumerate(q["options"]):
        keyboard.append([InlineKeyboardButton(opt, callback_data=f"fastqz_ans_{i}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"⚡ *Быстрая викторина (без рейтинга)*\n\n"
        f"❓ *{q['question']}*\n\n_Выбери правильный вариант:_",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def handle_quiz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    first_name = query.from_user.first_name
    
    q = context.user_data.get("current_quiz")
    if not q:
        await query.edit_message_text("❌ Викторина не найдена. Попробуй /quiz заново")
        return
    
    selected = int(query.data.split("_")[-1])
    correct = q["correct"]
    
    if selected == correct:
        stats_data = add_completion(user_id, first_name, q["link"].split("/")[-1])
        response = (
            f"✅ *Правильно!* +1 балл!\n\n"
            f"📊 Всего викторин пройдено: {stats_data['total']}\n"
            f"🎖️ Твой ранг: {stats_data['rank']}"
        )
    else:
        correct_answer = q["options"][correct]
        response = f"❌ *Неправильно!*\n\nПравильный ответ: *{correct_answer}*"
    
    await query.edit_message_text(response, parse_mode="Markdown")
    del context.user_data["current_quiz"]

async def handle_fastqz_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    q = context.user_data.get("current_quiz_fast")
    if not q:
        await query.edit_message_text("❌ Викторина не найдена. Попробуй /fastqz заново")
        return
    
    selected = int(query.data.split("_")[-1])
    correct = q["correct"]
    
    if selected == correct:
        response = f"✅ *Правильно!* (без рейтинга)"
    else:
        correct_answer = q["options"][correct]
        response = f"❌ *Неправильно!*\n\nПравильный ответ: *{correct_answer}*"
    
    await query.edit_message_text(response, parse_mode="Markdown")
    del context.user_data["current_quiz_fast"]

# ===== ОСТАЛЬНЫЕ КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name
    update_user(user_id, first_name)
    
    await update.message.reply_text(
        "🎯 *Бот викторин и ребусов*\n\n"
        "/quiz — случайная викторина (рейтинг)\n"
        "/fastqz — быстрая викторина (без рейтинга)\n"
        "/rebus — отгадай ребус (рейтинг)\n"
        "/mm — случайный мем\n"
        "/stats — моя статистика\n"
        "/top — топ игроков\n"
        "/rebustop — топ ребусников\n"
        "/base — количество викторин и мемов\n"
        "/donate — поддержать разработку\n"
        "/help — помощь",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Помощь по командам:*\n\n"
        "/quiz — викторина с рейтингом (выбери вариант)\n"
        "/fastqz — быстрая викторина (без рейтинга)\n"
        "/rebus — отгадай ребус (изображение + слово)\n"
        "/mm — случайный мем\n"
        "/stats — моя статистика (аватарка + рейтинг)\n"
        "/top — топ-10 игроков по викторинам\n"
        "/rebustop — топ-10 по ребусам\n"
        "/base — сколько викторин и мемов в базе\n"
        "/donate — поддержать разработку\n"
        "/help — это сообщение\n\n"
        "🎯 *Как получить рейтинг в викторинах:*\n"
        "Напиши /quiz и выбери правильный ответ.\n\n"
        "🧩 *Как отгадать ребус:*\n"
        "Напиши /rebus, посмотри на картинку и напиши слово в чат.",
        parse_mode="Markdown"
    )

@antispam_decorator
async def donate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 Поддержать разработку", url="https://finance.ozon.ru/apps/sbp/ozonbankpay/019da166-0117-7486-83c4-ba6b6a587f43")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "💸 *Поддержать разработку бота*\n\n"
        "Если тебе нравятся викторины — можешь отправить донат.\n\n"
        "Спасибо за поддержку! ❤️",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stats_data = get_user_stats(user.id)
    
    photo = None
    try:
        photos = await context.bot.get_user_profile_photos(user.id, limit=1)
        if photos.total_count > 0:
            photo = photos.photos[0][-1].file_id
    except:
        pass
    
    text = (
        f"📊 *Статистика {user.first_name}*:\n\n"
        f"🎯 Викторин пройдено: {stats_data['total']}\n"
        f"🎖️ Ранг: *{stats_data['rank']}*"
    )
    
    if photo:
        await update.message.reply_photo(
            photo=photo,
            caption=text,
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(text, parse_mode="Markdown")

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    c.execute("SELECT first_name, total, rank FROM users ORDER BY total DESC LIMIT 10")
    top_users = c.fetchall()
    conn.close()
    
    if not top_users:
        await update.message.reply_text("❌ Пока никого нет в рейтинге")
        return
    
    message = "🏆 *Топ-10 игроков:*\n\n"
    for i, (name, total, rank) in enumerate(top_users, 1):
        message += f"{i}. *{name}* — {total} викторин ({rank})\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def mm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memes = load_memes()
    if not memes:
        await update.message.reply_text("❌ Мемов пока нет")
        return
    
    m = random.choice(memes)
    
    if 'img_url' in m and m['img_url']:
        await update.message.reply_photo(
            photo=m['img_url'],
            caption=f"😂 *Мем от {m['date']}*",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"😂 *Мем от {m['date']}*\n\n👉 [Смотреть мем]({m['link']})",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )

async def base(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quizzes = load_quizzes()
    quiz_count = len(quizzes)
    
    memes = load_memes()
    meme_count = len(memes)
    
    oldest_quiz = None
    newest_quiz = None
    if quiz_count > 0:
        dates = [q.get("date", "") for q in quizzes if q.get("date")]
        if dates:
            oldest_quiz = min(dates)
            newest_quiz = max(dates)
    
    text = (
        f"📦 *База данных бота:*\n\n"
        f"🎯 *Викторин:* {quiz_count}\n"
        f"😂 *Мемов:* {meme_count}\n"
    )
    
    if oldest_quiz and newest_quiz:
        text += f"\n📅 *Викторины:* с {oldest_quiz} по {newest_quiz}"
    
    text += f"\n\n💡 *Совет:* играй в викторины через /quiz, а мемы через /mm"
    
    await update.message.reply_text(text, parse_mode="Markdown")

# ===== АДМИН-КОМАНДЫ =====
@antispam_decorator
async def editstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет прав")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "📝 *Использование:* `/editstats <user_id> количество`\n"
            "Пример: `/editstats 123456789 15`\n\n"
            "⚠️ Используй числовой ID пользователя (можно получить через @userinfobot).",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        new_total = int(context.args[1])
    except:
        await update.message.reply_text("❌ Оба аргумента должны быть числами: ID пользователя и количество")
        return
    
    new_rank = get_rank_by_score(new_total)
    
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    
    user_data = get_user_by_id(target_user_id)
    if user_data:
        user_name = user_data['first_name']
        c.execute("UPDATE users SET total = ?, rank = ? WHERE user_id = ?", (new_total, new_rank, target_user_id))
        await update.message.reply_text(f"🔄 Обновлён пользователь {user_name} (ID: {target_user_id})")
    else:
        c.execute("INSERT INTO users (user_id, first_name, total, rank) VALUES (?, ?, ?, ?)",
                  (target_user_id, "Неизвестный", new_total, new_rank))
        await update.message.reply_text(f"✅ Создан пользователь с ID {target_user_id}")
    
    c.execute("DELETE FROM completions WHERE user_id = ?", (target_user_id,))
    
    quizzes = load_quizzes()
    added = 0
    for i, q in enumerate(quizzes):
        if i >= new_total:
            break
        quiz_id = q["link"].split("/")[-1]
        c.execute("INSERT OR IGNORE INTO completions (user_id, quiz_id, completed_at) VALUES (?, ?, ?)",
                  (target_user_id, quiz_id, datetime.now()))
        added += 1
    
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ *Статистика обновлена:*\n\n"
        f"🆔 *ID:* {target_user_id}\n"
        f"🎯 *Викторин:* {new_total}\n"
        f"🎖️ *Ранг:* {new_rank}\n"
        f"📚 *Защита:* {added} викторин отмечены пройденными.",
        parse_mode="Markdown"
    )

@antispam_decorator
async def edittop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет прав")
        return
    
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    c.execute("SELECT user_id, first_name, total, rank FROM users ORDER BY total DESC LIMIT 10")
    top_users = c.fetchall()
    conn.close()
    
    if not top_users:
        await update.message.reply_text("❌ Топ пуст")
        return
    
    message = "🏆 *Топ-10 игроков (для админа):*\n\n"
    for user_id, name, total, rank in top_users:
        message += f"🆔 `{user_id}` — *{name}* — {total} викторин ({rank})\n"
    
    message += "\n📝 *Изменить статистику:* `/editstats <user_id> количество`\n"
    message += "📌 Пример: `/editstats 123456789 15`\n\n"
    message += "💡 *Как узнать ID?* Напиши пользователю в Telegram: `@userinfobot`"
    
    await update.message.reply_text(message, parse_mode="Markdown")

@antispam_decorator
async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет прав")
        return
    
    if os.path.exists('quiz_users.db'):
        with open('quiz_users.db', 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename='quiz_users.db',
                caption="📦 Резервная копия базы данных"
            )
    else:
        await update.message.reply_text("❌ Файл базы данных не найден")

# ===== РЕБУСЫ =====
active_rebuses = {}

async def rebus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from rebus import load_dictionary, split_into_parts, expression_to_blocks, draw_rebus_from_blocks, find_image_case_insensitive
    from io import BytesIO
    import random
    
    dictionary = load_dictionary("words.txt")
    if not dictionary:
        await update.message.reply_text("❌ База слов пуста")
        return
    
    candidates = [w for w in dictionary if 3 <= len(w) <= 6]
    if not candidates:
        candidates = list(dictionary)
    
    random.shuffle(candidates)
    
    for target_word in candidates[:30]:
        variants = split_into_parts(target_word, dictionary, max_parts=2)
        if not variants:
            continue
        
        variant = variants[0]
        expression = variant["expression"]
        blocks_data = expression_to_blocks(expression)
        
        missing = False
        for block in blocks_data:
            if find_image_case_insensitive(block["word"]) is None:
                missing = True
                break
        if missing:
            continue
        
        try:
            img = draw_rebus_from_blocks(
                blocks_data,
                images_dir="images",
                font_path="fonts/minecraft.ttf",
                frame_text="ТРЯСЛО993",
                frame_padding=30,
                letter_spacing_h=5,
                letter_spacing_v=7
            )
            
            if img:
                bio = BytesIO()
                img.save(bio, format='PNG')
                bio.seek(0)
                
                sent_message = await update.message.reply_photo(
                    photo=bio,
                    caption=f"🧩 *Отгадай слово ({len(target_word)} букв)*\n\nПодсказка: первая буква — «{target_word[0]}»",
                    parse_mode="Markdown"
                )
                
                active_rebuses[update.effective_user.id] = {
                    "word": target_word,
                    "message_id": sent_message.message_id,
                    "chat_id": update.message.chat_id
                }
                
                return
        except Exception as e:
            print(f"Ошибка при {target_word}: {e}")
            continue
    
    await update.message.reply_text(
        "❌ *Не удалось собрать ребус*\n\n"
        "Попробуй позже.",
        parse_mode="Markdown"
    )

async def rebus_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    c.execute('''SELECT user_name, solves FROM rebus_solves
                 ORDER BY solves DESC LIMIT 10''')
    top = c.fetchall()
    conn.close()
    
    if not top:
        await update.message.reply_text("❌ Пока никто не отгадал ни одного ребуса")
        return
    
    message = "🏆 *Топ ребусников:*\n\n"
    for i, (name, solves) in enumerate(top, 1):
        word = "ребус" if solves == 1 else "ребусов"
        message += f"{i}. *{name}* — {solves} {word}\n"
    
    await update.message.reply_text(message, parse_mode="Markdown")

async def check_rebus_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    answer = update.message.text.strip().lower()
    
    active = active_rebuses.get(user_id)
    if not active:
        return
    
    if answer == active["word"].lower():
        user_name = update.effective_user.first_name
        add_rebus_solve(user_id, user_name)
        
        await update.message.reply_text(
            f"✅ *{user_name}*, правильно! +1 очко!\n🎉 Загаданное слово: *{active['word']}*",
            parse_mode="Markdown"
        )
        del active_rebuses[user_id]
    else:
        await update.message.reply_text(
            f"❌ Неправильно. Попробуй ещё раз или напиши /rebus для нового ребуса.",
            parse_mode="Markdown"
        )

@antispam_decorator
async def editrebusstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет прав")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "📝 *Использование:* `/editrebusstats <user_id> количество`\n"
            "Пример: `/editrebusstats 123456789 15`\n\n"
            "⚠️ Используй числовой ID пользователя.",
            parse_mode="Markdown"
        )
        return
    
    try:
        target_user_id = int(context.args[0])
        new_solves = int(context.args[1])
    except:
        await update.message.reply_text("❌ Оба аргумента должны быть числами")
        return
    
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    
    c.execute("SELECT user_name FROM rebus_solves WHERE user_id = ?", (target_user_id,))
    result = c.fetchone()
    
    if result:
        user_name = result[0]
        c.execute("UPDATE rebus_solves SET solves = ? WHERE user_id = ?", (new_solves, target_user_id))
        await update.message.reply_text(f"🔄 Обновлён пользователь {user_name} (ID: {target_user_id}) → {new_solves} ребусов")
    else:
        await update.message.reply_text(
            f"❌ Пользователь с ID {target_user_id} не найден в топе ребусов.\n"
            f"Сначала он должен отгадать хотя бы один ребус через /rebus"
        )
        conn.close()
        return
    
    conn.commit()
    conn.close()

@antispam_decorator
async def rebus_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет прав")
        return
    
    conn = sqlite3.connect('quiz_users.db')
    c = conn.cursor()
    c.execute("SELECT user_id, user_name, solves FROM rebus_solves ORDER BY solves DESC")
    data = c.fetchall()
    conn.close()
    
    if not data:
        await update.message.reply_text("❌ Нет данных о ребусах")
        return
    
    backup_data = [{"user_id": row[0], "user_name": row[1], "solves": row[2]} for row in data]
    
    with open("rebus_backup.json", "w", encoding="utf-8") as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    
    with open("rebus_backup.json", "rb") as f:
        await update.message.reply_document(
            document=f,
            filename="rebus_backup.json",
            caption="📦 Резервная копия топа ребусов"
        )
    
    os.remove("rebus_backup.json")

@antispam_decorator
async def restore_rebus_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Нет прав")
        return
    
    reply = update.message.reply_to_message
    if not reply or not reply.document:
        await update.message.reply_text(
            "❌ *Как восстановить:*\n"
            "1. Отправь файл `rebus_backup.json`\n"
            "2. Нажми на него → 'Ответить'\n"
            "3. Напиши `/restorerebusstats`\n\n"
            "📌 Команда должна быть ответом на сообщение с файлом!",
            parse_mode="Markdown"
        )
        return
    
    file = await reply.document.get_file()
    file_path = "restore_rebus.json"
    await file.download_to_drive(file_path)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        conn = sqlite3.connect('quiz_users.db')
        c = conn.cursor()
        
        restored = 0
        for item in data:
            user_id = item["user_id"]
            user_name = item["user_name"]
            solves = item["solves"]
            c.execute('''INSERT INTO rebus_solves (user_id, user_name, solves)
                         VALUES (?, ?, ?)
                         ON CONFLICT(user_id) DO UPDATE SET
                         solves = excluded.solves,
                         user_name = excluded.user_name''',
                      (user_id, user_name, solves))
            restored += 1
        
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ Восстановлено {restored} записей в топе ребусов")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка восстановления: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

# ===== ДИАГНОСТИЧЕСКИЕ КОМАНДЫ =====
async def check_dict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from rebus import load_dictionary
    import os
    
    msg = "📁 *Диагностика словарей*\n\n"
    
    if os.path.exists("words.txt"):
        msg += "✅ `words.txt` существует\n"
    else:
        msg += "❌ `words.txt` НЕ найден\n"
    
    if os.path.exists("letters.txt"):
        msg += "✅ `letters.txt` существует\n"
    else:
        msg += "❌ `letters.txt` НЕ найден\n"
    
    dictionary = load_dictionary("words.txt")
    msg += f"\n📚 Загружено слов: {len(dictionary)}\n"
    
    if dictionary:
        word_list = list(dictionary)
        msg += f"🔹 Первые 5: `{', '.join(list(word_list)[:5])}`\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def test_rebus_logic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from rebus import load_dictionary, split_into_parts
    import random
    import os
    
    msg = ""
    
    dictionary = load_dictionary("words.txt")
    msg += f"📚 Загружено слов из words.txt: {len(dictionary)}\n"
    
    if os.path.exists("letters.txt"):
        with open("letters.txt", "r", encoding="utf-8") as f:
            letters = [line.strip() for line in f if line.strip()]
        msg += f"🔤 Загружено букв из letters.txt: {len(letters)}\n"
        msg += f"🔹 Первые 10 букв: {', '.join(letters[:10])}\n"
    else:
        msg += "❌ Файл letters.txt НЕ НАЙДЕН\n"
    
    if dictionary:
        short_words = [w for w in dictionary if len(w) <= 6]
        msg += f"📏 Коротких слов (до 6 букв): {len(short_words)}\n"
        
        if short_words:
            target_word = random.choice(short_words)
            msg += f"🎯 Выбрано слово: {target_word}\n"
            
            try:
                variants = split_into_parts(target_word, dictionary, max_parts=2)
                msg += f"🧩 Вариантов разбиения: {len(variants)}\n"
                if variants:
                    msg += f"✅ Пример: {variants[0]['expression']}\n"
            except Exception as e:
                msg += f"❌ Ошибка разбиения: {e}\n"
    
    await update.message.reply_text(msg)

async def check_rebus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        import rebus
        await update.message.reply_text(f"✅ rebus найден! Функции: {', '.join([x for x in dir(rebus) if not x.startswith('_')][:10])}")
    except ImportError as e:
        await update.message.reply_text(f"❌ rebus НЕ загружен: {e}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def test_pillow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from io import BytesIO
    from PIL import Image, ImageDraw
    
    img = Image.new('RGB', (200, 100), color='white')
    draw = ImageDraw.Draw(img)
    draw.text((10, 40), "Тест Pillow", fill='black')
    
    bio = BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    await update.message.reply_photo(bio, caption="Pillow работает!")

async def debug_rebus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from rebus import load_dictionary, split_into_parts, expression_to_blocks, draw_rebus_from_blocks, find_image_case_insensitive
    from io import BytesIO
    import random
    import os
    import traceback
    
    msg = "🔍 *Диагностика ребуса*\n\n"
    
    dictionary = load_dictionary("words.txt")
    msg += f"📚 Слов в словаре: {len(dictionary)}\n"
    
    candidates = [w for w in dictionary if 3 <= len(w) <= 6]
    msg += f"📏 Коротких слов: {len(candidates)}\n"
    
    if not candidates:
        await update.message.reply_text(msg + "❌ Нет коротких слов")
        return
    
    target_word = random.choice(candidates)
    msg += f"🎯 Пробуем слово: {target_word}\n"
    
    variants = split_into_parts(target_word, dictionary, max_parts=2)
    msg += f"🧩 Вариантов разбиения: {len(variants)}\n"
    
    if not variants:
        await update.message.reply_text(msg + "❌ Нет вариантов разбиения")
        return
    
    variant = variants[0]
    expression = variant["expression"]
    msg += f"📝 Выражение: {expression}\n"
    
    blocks_data = expression_to_blocks(expression)
    msg += f"🧱 Блоков: {len(blocks_data)}\n"
    
    all_good = True
    for block in blocks_data:
        word = block["word"]
        img_path = find_image_case_insensitive(word)
        msg += f"  {'✅' if img_path else '❌'} {word} → {img_path if img_path else 'НЕ НАЙДЕН'}\n"
        if not img_path:
            all_good = False
    
    if not all_good:
        await update.message.reply_text(msg + "❌ Не хватает картинок")
        return
    
    try:
        img = draw_rebus_from_blocks(
            blocks_data,
            images_dir="images",
            font_path="fonts/minecraft.ttf",
            frame_text="ТРЯСЛО993",
            frame_padding=30,
            letter_spacing_h=5,
            letter_spacing_v=7
        )
        
        if img is None:
            msg += "❌ draw_rebus_from_blocks вернула None\n"
            await update.message.reply_text(msg)
            return
        
        msg += "✅ Картинка сгенерирована, отправляю...\n"
        await update.message.reply_text(msg)
        
        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)
        await update.message.reply_photo(
            photo=bio,
            caption=f"🧩 *Отгадай слово ({len(target_word)} букв)*\n\nПодсказка: первая буква — «{target_word[0]}»",
            parse_mode="Markdown"
        )
    except Exception as e:
        msg += f"❌ Ошибка генерации: {str(e)[:200]}\n{traceback.format_exc()[:500]}"
        await update.message.reply_text(msg)

async def test_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from rebus import expression_to_blocks, draw_rebus_from_blocks
    from io import BytesIO

    test_expr = "акула"
    blocks = expression_to_blocks(test_expr)
    
    if not blocks:
        await update.message.reply_text("❌ Не удалось разобрать выражение")
        return
    
    img = draw_rebus_from_blocks(
        blocks,
        images_dir="images",
        font_path="fonts/minecraft.ttf",
        frame_text="ТРЯСЛО993",
        frame_padding=30,
        letter_spacing_h=5,
        letter_spacing_v=7
    )
    
    if img is None:
        await update.message.reply_text("❌ draw_rebus_from_blocks вернула None")
        return
    
    if img.width == 0 or img.height == 0:
        await update.message.reply_text(f"❌ Картинка имеет нулевой размер: {img.width}x{img.height}")
        return
    
    bio = BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    
    await update.message.reply_photo(bio, caption="Тестовая картинка")

async def test_complex(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from rebus import expression_to_blocks, draw_rebus_from_blocks
    from io import BytesIO

    test_expr = "саша^1$2 + шрам$1"
    
    await update.message.reply_text(f"Пробуем: {test_expr}")
    
    blocks = expression_to_blocks(test_expr)
    if not blocks:
        await update.message.reply_text("❌ Не удалось разобрать выражение")
        return
    
    for block in blocks:
        await update.message.reply_text(f"Блок: {block['word']}, удаление слева: {block['removals_left']}, справа: {block['removals_right']}")
    
    img = draw_rebus_from_blocks(
        blocks,
        images_dir="images",
        font_path="fonts/minecraft.ttf",
        frame_text="ТРЯСЛО993",
        frame_padding=30,
        letter_spacing_h=5,
        letter_spacing_v=7
    )
    
    if img is None:
        await update.message.reply_text("❌ draw_rebus_from_blocks вернула None")
        return
    
    bio = BytesIO()
    img.save(bio, format='PNG')
    bio.seek(0)
    await update.message.reply_photo(bio, caption="Сложный ребус")

async def check_bytes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import os
    word = "шрам"
    for ext in ['.webrp', '.webp']:
        path = os.path.join("images", f"{word}{ext}")
        if os.path.exists(path):
            with open(path, 'rb') as f:
                header = f.read(12)
            await update.message.reply_text(f"{path}: {header.hex()}")
            return
    await update.message.reply_text("Файл не найден")

async def list_all_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import os
    msg = "📁 *Все файлы в images:*\n"
    if os.path.exists("images"):
        files = os.listdir("images")
        for f in sorted(files)[:30]:
            msg += f"• `{f}`\n"
        if len(files) > 30:
            msg += f"\n... и ещё {len(files) - 30} файлов"
    else:
        msg += "❌ Папка images не найдена"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ===== ОБРАБОТЧИК ПЕРЕСЛАННЫХ ПОСТОВ =====
async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.forward_origin:
        await update.message.reply_text("❌ Перешлите пост из канала")
        return
    
    try:
        origin = update.message.forward_origin
        if hasattr(origin, 'chat') and origin.chat:
            channel = origin.chat
            channel_username = channel.username
            post_id = origin.message_id
        else:
            await update.message.reply_text("❌ Не могу определить канал")
            return
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)[:50]}")
        return
    
    if not channel_username:
        await update.message.reply_text("❌ У канала нет username, не могу создать ссылку")
        return
    
    link = f"https://t.me/{channel_username}/{post_id}"
    date = datetime.now().strftime("%Y-%m-%d")
    text = update.message.caption or ""
    
    quizzes = load_quizzes()
    if link not in [q["link"] for q in quizzes]:
        quizzes.append({"link": link, "date": date})
        save_quizzes(quizzes)
        await update.message.reply_text(f"✅ Викторина добавлена!\n{link}")
    else:
        await update.message.reply_text("⚠️ Такая викторина уже есть")

# ===== ЗАПУСК =====
if __name__ == "__main__":
    init_db()
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("donate", donate))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("fastqz", fastqz))
    app.add_handler(CallbackQueryHandler(handle_quiz_answer, pattern="quiz_ans_"))
    app.add_handler(CallbackQueryHandler(handle_fastqz_answer, pattern="fastqz_ans_"))
    app.add_handler(CommandHandler("mm", mm))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("base", base))
    app.add_handler(CommandHandler("editstats", editstats))
    app.add_handler(CommandHandler("edittop", edittop))
    app.add_handler(CommandHandler("backup", backup))
    app.add_handler(CommandHandler("rebus", rebus))
    app.add_handler(CommandHandler("checkdict", check_dict))
    app.add_handler(CommandHandler("testrb", test_rebus_logic))
    app.add_handler(CommandHandler("checkrebus", check_rebus))
    app.add_handler(CommandHandler("testpillow", test_pillow))
    app.add_handler(CommandHandler("debugrebus", debug_rebus))
    app.add_handler(CommandHandler("testgen", test_gen))
    app.add_handler(CommandHandler("testcomplex", test_complex))
    app.add_handler(CommandHandler("checkbytes", check_bytes))
    app.add_handler(CommandHandler("allimg", list_all_images))
    app.add_handler(CommandHandler("rebustop", rebus_top))
    app.add_handler(CommandHandler("rebusbackup", rebus_backup))
    app.add_handler(CommandHandler("editrebusstats", editrebusstats))
    app.add_handler(CommandHandler("restorerebusstats", restore_rebus_stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, check_rebus_answer))
    app.add_handler(MessageHandler(filters.FORWARDED, handle_forward))
    
    print("✅ Бот запущен!")
    app.run_polling()
