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

# === ИМИТАЦИЯ QRM-МОДЕЛИ ===
def dummy_model_response(text):
    # Здесь можно заменить на реальную ML-модель
    if "погода" in text.lower():
        return "Сегодня солнечно."
    return "Извините, я пока не понимаю этот запрос."

# === ОБРАБОТКА СООБЩЕНИЙ ===
@app.post("/chat")
def chat(message: Message):
    response = dummy_model_response(message.message)
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
