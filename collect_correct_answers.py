import asyncio
import json
import os
from telethon import TelegramClient

API_ID = int(os.environ.get("API_ID", 1234567))
API_HASH = os.environ.get("API_HASH", "твой_api_hash")
CHANNEL = "@trassa993"
PHONE_NUMBER = "+79625231378"  # ЗАМЕНИ НА СВОЙ НОМЕР

async def main():
    client = TelegramClient("session", API_ID, API_HASH)
    await client.start(phone=PHONE_NUMBER)
    
    print("🔍 Собираю правильные ответы...")
    
    try:
        with open("quizzes.json", "r", encoding="utf-8") as f:
            quizzes = json.load(f)
    except:
        quizzes = []
    
    existing_links = {q.get("link") for q in quizzes}
    new_quizzes = []
    
    async for msg in client.iter_messages(CHANNEL, limit=500):
        if msg.poll and msg.poll.quiz:
            link = f"https://t.me/{CHANNEL[1:]}/{msg.id}"
            
            if link in existing_links:
                continue
            
            correct_idx = msg.poll.correct_option_id
            if correct_idx is None:
                continue
            
            quiz_data = {
                "link": link,
                "date": msg.date.strftime("%Y-%m-%d"),
                "question": msg.poll.question,
                "options": [ans.text for ans in msg.poll.answers],
                "correct": correct_idx
            }
            new_quizzes.append(quiz_data)
            print(f"✅ {msg.date.strftime('%Y-%m-%d')}: {msg.poll.question[:40]}...")
            
            await asyncio.sleep(0.5)
    
    if new_quizzes:
        quizzes.extend(new_quizzes)
        with open("quizzes.json", "w", encoding="utf-8") as f:
            json.dump(quizzes, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Добавлено {len(new_quizzes)} новых викторин")
    else:
        print("❌ Новых викторин не найдено")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
