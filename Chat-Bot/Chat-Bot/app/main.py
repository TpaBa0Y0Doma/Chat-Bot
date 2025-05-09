import math
import httpx
import re

from fastapi.responses import RedirectResponse
from sympy import sympify, sqrt
from sympy.parsing.sympy_parser import standard_transformations, implicit_multiplication_application, parse_expr
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
    url = "https://api.open-meteo.com/v1/forecast?latitude=59.93&longitude=30.31&current_weather=true"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        weather = data.get("current_weather", {})
        temp = weather.get("temperature")
        wind = weather.get("windspeed")
        if temp is not None and wind is not None:
            return f"В Санкт-Петербурге сейчас {temp}°C, ветер {wind} м/с."
        return "Не удалось получить данные о погоде."

transformations = (standard_transformations + (implicit_multiplication_application,))

def evaluate_expression(expr: str):
    try:
        # Поддержка sqrt и других функций
        allowed_names = {"sqrt": math.sqrt}
        result = eval(expr, {"__builtins__": {}}, allowed_names)
        return f"Ответ: {result}"
    except Exception:
        return "Извините, я не смог обработать выражение."

# === ОБРАБОТКА СООБЩЕНИЙ ===
def preprocess_expression(expr: str):
    expr = expr.replace("^", "**")
    expr = re.sub(r'√(\d+(\.\d+)?)', r'sqrt(\1)', expr)
    expr = re.sub(r'√\(([^)]+)\)', r'sqrt(\1)', expr)

    # Обработка процентов: заменяем "число - процент%" на "число - (число * процент / 100)"
    expr = re.sub(
        r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*%',
        lambda m: f"{m.group(1)} - ({m.group(1)} * {float(m.group(2)) / 100})",
        expr
    )
    
    # Обработка процентов в других выражениях, например 25% → 0.25
    expr = re.sub(r'(\d+(\.\d+)?)\s*%', lambda m: str(float(m.group(1)) / 100), expr)

    return expr

def advanced_calculator(expr: str):
    try:
        expr = preprocess_expression(expr)
        parsed_expr = parse_expr(expr, transformations=transformations)
        result = parsed_expr.evalf()
        return f"Ответ: {result}"
    except Exception:
        return "Извините, я не смог обработать выражение."

# === ОБРАБОТКА СООБЩЕНИЙ ===
@app.post("/chat")
async def chat(message: Message):
    text = message.message.lower()

    if "погода" in text:
        response = await get_weather()
    else:
        response = advanced_calculator(message.message)

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

@app.get("/")
def root():
    return RedirectResponse(url="/docs")