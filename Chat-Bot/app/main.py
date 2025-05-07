import httpx

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import os
import sqlite3
import uuid

app = FastAPI()

# === БАЗА ДАННЫХ ===
DB_FILE = "bot_data.db"
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    message TEXT,
    response TEXT
)''')
conn.commit()

# === МОДЕЛИ ===
class Message(BaseModel):
    user_id: str
    message: str

# === ФУНКЦИЯ С РЕАЛЬНЫМ ПОГОДНЫМ API ===
async def get_weather():
    # Координаты Санкт-Петербурга
    url = "https://api.open-meteo.com/v1/forecast?latitude=59.93&longitude=30.31&current_weather=true"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        weather = data.get("current_weather", {})
        temp = weather.get("temperature")
        wind = weather.get("windspeed")
        return f"В Санкт-Петербурге сейчас {temp}°C, ветер {wind} м/с."

# === ОБРАБОТКА СООБЩЕНИЙ ===
@app.post("/chat")
async def chat(message: Message):
    if "погода" in message.message.lower():
        response = await get_weather()
    else:
        response = "Извините, я пока не понимаю этот запрос."

    msg_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?)", (msg_id, message.user_id, message.message, response))
    conn.commit()
    return {"response": response, "id": msg_id}

# === ЗАГРУЗКА ФАЙЛОВ ===
UPLOAD_FOLDER = "static"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.post("/upload")
def upload(file: UploadFile = File(...), user_id: str = Form(...)):
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_{file.filename}")
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    return {"file_id": file_id, "filename": file.filename, "url": f"/static/{file_id}_{file.filename}"}

@app.get("/static/{file_name}")
def get_file(file_name: str):
    file_path = os.path.join(UPLOAD_FOLDER, file_name)
    return FileResponse(file_path)

# === ПРОВЕРКА: ВСЕ СООБЩЕНИЯ ===
@app.get("/history/{user_id}")
def get_history(user_id: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.execute("SELECT message, response FROM messages WHERE user_id=?", (user_id,))
    return [{"message": row[0], "response": row[1]} for row in cursor.fetchall()]
