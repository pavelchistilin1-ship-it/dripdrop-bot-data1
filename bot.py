import logging
import sqlite3
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Константы
DB_NAME = "dripdrop.db"
ADMIN_USERNAME = "Emagjii"
SUPPORT_BOT_URL = "https://t.me/DripDropSupport_bot"
WELCOME_PHOTO_URL = "https://i.postimg.cc/Dwyx5HHG/IMG-4225.jpg"

# Состояния для ConversationHandler
ADD_REQUISITE = 1
REPLENISH_AMOUNT = 2
TRAFFIC_INTERVAL = 4
MOD_SEARCH_USER = 5
MOD_REPLENISH_TYPE = 6
MOD_REPLENISH_AMOUNT = 7
MOD_PAYMENT_DATA = 9
APPROVE_PAYMENT_NUMBER = 10
PROMOTE_MODERATOR = 11
MOD_REPLY_USER = 12 # Новое состояние для ответа пользователю

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            role TEXT DEFAULT 'trader',
            insurance_balance REAL DEFAULT 0,
            working_balance REAL DEFAULT 0,
            turnover REAL DEFAULT 0,
            earned REAL DEFAULT 0
        )
    ''')
    # Проверка наличия колонки earned (для существующих БД)
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'earned' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN earned REAL DEFAULT 0")
        
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requisites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            data TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trader_id INTEGER,
            moderator_id INTEGER,
            data TEXT,
            amount REAL,
            status TEXT DEFAULT 'pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Вспомогательные функции для БД
def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_identifier(identifier):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if identifier.isdigit():
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (int(identifier),))
    else:
        username = identifier.replace("@", "")
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
    conn.commit()
    conn.close()

def get_moderators():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE role IN ('moderator', 'super_moderator')")
    mods = [row[0] for row in cursor.fetchall()]
    conn.close()
    return mods

# Расчет комиссии
def calculate_commission(amount):
    if amount < 100: return 0
    if amount < 1000: return 0.12
    if amount < 5000: return 0.10
    if amount < 10000: return 0.08
    return 0.055

# Клавиатуры
def get_main_keyboard(role):
    if role in ['moderator', 'super_moderator']:
        keyboard = [
            [KeyboardButton("📤 Платежи"), KeyboardButton("👥 Пользователи")]
        ]
        if role == 'super_moderator':
            keyboard.append([KeyboardButton("🛡️ Назначить модератора")])
        keyboard.append([KeyboardButton("🔄 Режим Трейдера")])
    else:
        keyboard = [
            [KeyboardButton("💎 Баланс"), KeyboardButton("🏦 Реквизиты")],
            [KeyboardButton("🧊 Пополнить"), KeyboardButton("🚦 Трафик")],
            [KeyboardButton("📋 Платежи"), KeyboardButton("🆘 Поддержка")]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# Обработчики команд
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    create_user(user_id, username)
    user = get_user(user_id)
    
    if username == ADMIN_USERNAME and user[2] != 'super_moderator':
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET role = 'super_moderator' WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        user = get_user(user_id)

    role_map = {'trader': 'Трейдер', 'moderator': 'Модератор', 'super_moderator': 'Супер-модератор'}
    role_name = role_map.get(user[2], 'Трейдер')
    
    welcome_text = (
        f"⠀ ⠀ ⠀ ⠀ 🌊 **DripDropPay** 🌊\n"
        f"       ━━━━━━━━━━━━\n"
        f"👤 Вы вошли как **{role_name} #{user_id}**\n\n"
        f"> Используйте меню ниже для работы."
    )
    
    try:
        await update.message.reply_photo(
            photo=WELCOME_PHOTO_URL,
            caption=welcome_text,
            reply_markup=get_main_keyboard(user[2]),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error sending photo: {e}")
        await update.message.reply_text(
            welcome_text,
            reply_markup=get_main_keyboard(user[2]),
            parse_mode='Markdown'
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    if not user: return

    if text == "🔄 Режим Трейдера" and user[2] in ['moderator', 'super_moderator']:
        keyboard = [
            [KeyboardButton("💎 Баланс"), KeyboardButton("🏦 Реквизиты")],
            [KeyboardButton("🧊 Пополнить"), KeyboardButton("🚦 Трафик")],
            [KeyboardButton("📋 Платежи"), KeyboardButton("🆘 Поддержка")],
            [KeyboardButton("🔄 Режим Модератора")]
        ]
        await update.message.reply_text("🔄 Переключено в режим Трейдера.", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return

    if text == "🔄 Режим Модератора" and user[2] in ['moderator', 'super_moderator']:
        await update.message.reply_text("🔄 Переключено в режим Модератора.", reply_markup=get_main_keyboard(user[2]))
        return

    if text in ["💎 Баланс", "💰 Баланс"]:
        # user[6] - это поле earned
        earned_val = user[6] if len(user) > 6 else 0
        await update.message.reply_text(
            f"🧊 **Ваши счета**\n"
            f"━━━━━━━━━━━━\n"
            f"🔹 Страховой: `{user[3]:.2f} ₽`\n"
            f"🔸 Рабочий: `{user[4]:.2f} ₽`\n"
            f"📈 Оборот: `{user[5]:.2f} ₽`\n"
            f"💸 Заработано: `{earned_val:.2f} ₽`\n"
            f"━━━━━━━━━━━━\n"
            f"🌐 *Статус: Активен*",
            parse_mode='Markdown'
        )

    elif text == "🏦 Реквизиты":
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, data FROM requisites WHERE user_id = ?", (user_id,))
        reqs = cursor.fetchall()
        conn.close()
        
        if not reqs:
            msg = "❕ У вас пока нет реквизитов."
        else:
            msg = "📋 **Ваши реквизиты**\n━━━━━━━━━━━━\n"
            for r in reqs:
                msg += f"💧 `{r[1]}`\n"
        
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Добавить", callback_data="add_req"),
             InlineKeyboardButton("🗑️ Удалить", callback_data="del_req")]
        ]), parse_mode='Markdown')

    elif text in ["🧊 Пополнить", "💳 Пополнить"]:
        keyboard = [
            [InlineKeyboardButton("🤖 CryptoBot", callback_data="repl_crypto")],
            [InlineKeyboardButton("🌐 TRC20", callback_data="repl_trc20")]
        ]
        await update.message.reply_text("💎 Выберите способ пополнения:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text in ["🚦 Трафик", "🚦 Запросить трафик"]:
        if user[3] < 5000:
            await update.message.reply_text("❌ **Ошибка:** Страховой баланс должен быть не менее 5000 ₽.")
            return
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM requisites WHERE user_id = ?", (user_id,))
        reqs = cursor.fetchall()
        conn.close()
        
        if not reqs:
            await update.message.reply_text("❌ Сначала добавьте реквизиты.")
            return
            
        keyboard = [[InlineKeyboardButton(f"💧 {r[0]}", callback_data=f"traf_req_{r[0][:20]}")] for r in reqs]
        await update.message.reply_text("🚦 Выберите реквизит для трафика:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "📋 Платежи":
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, data, amount FROM payments WHERE trader_id = ? AND status = 'pending'", (user_id,))
        pays = cursor.fetchall()
        conn.close()
        
        if not pays:
            await update.message.reply_text("❕ У вас нет активных платежей.")
        else:
            for p in pays:
                msg = (
                    f"📦 **Платёж #{p[0]}**\n"
                    f"━━━━━━━━━━━━\n"
                    f"💰 Сумма: `{p[2]:.2f} ₽`\n"
                    f"🏦 Данные: `{p[1]}`\n"
                    f"━━━━━━━━━━━━\n"
                    f"> Ожидает подтверждения"
                )
                await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Одобрить", callback_data=f"appr_pay_{p[0]}")]
                ]), parse_mode='Markdown')

    elif text == "🆘 Поддержка":
        await update.message.reply_text(
            "🆘 **Служба поддержки**\n\n> Если у вас возникли вопросы, обратитесь к нашему боту поддержки.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔴 СВЯЗАТЬСЯ С ПОДДЕРЖКОЙ", url=SUPPORT_BOT_URL)]
            ]),
            parse_mode='Markdown'
        )

    elif text == "📤 Платежи" and user[2] in ['moderator', 'super_moderator']:
        await update.message.reply_text("🔍 Введите Username или ID трейдера для отправки платежа:")
        context.user_data['mod_action'] = 'payment'
        return MOD_SEARCH_USER

    elif text == "👥 Пользователи" and user[2] in ['moderator', 'super_moderator']:
        await update.message.reply_text("🔍 Введите Username или ID пользователя:")
        context.user_data['mod_action'] = 'profile'
        return MOD_SEARCH_USER

    elif text == "🛡️ Назначить модератора" and user[2] == 'super_moderator':
        await update.message.reply_text("🛡️ Введите Username или ID будущего модератора:")
        return PROMOTE_MODERATOR

# Conversation Handlers
async def add_req_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💧 Введите реквизиты в формате: `номер-банк-фио` (например: `+79516768798-Альфа-Иван И.`)", parse_mode='Markdown')
    return ADD_REQUISITE

async def add_req_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.message.text
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO requisites (user_id, data) VALUES (?, ?)", (user_id, data))
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Реквизит успешно добавлен!")
    return ConversationHandler.END

async def del_req_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, data FROM requisites WHERE user_id = ?", (user_id,))
    reqs = cursor.fetchall()
    conn.close()
    
    if not reqs:
        await query.edit_message_text("У вас нет реквизитов для удаления.")
        return ConversationHandler.END
        
    keyboard = [[InlineKeyboardButton(f"🗑️ {r[1]}", callback_data=f"del_id_{r[0]}")] for r in reqs]
    await query.edit_message_text("Выберите реквизит для удаления:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def del_req_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    req_id = query.data.split("_")[2]
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM requisites WHERE id = ?", (req_id,))
    conn.commit()
    conn.close()
    await query.edit_message_text("✅ Реквизит удален.")
    return ConversationHandler.END

async def repl_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = "CryptoBot" if "crypto" in query.data else "TRC20"
    context.user_data['repl_method'] = method
    await query.edit_message_text(f"🧊 Введите сумму пополнения в **$** ({method}):", parse_mode='Markdown')
    return REPLENISH_AMOUNT

async def repl_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    amount = update.message.text
    user_id = update.effective_user.id
    username = update.effective_user.username
    method = context.user_data.get('repl_method', 'Неизвестно')
    
    mods = get_moderators()
    for mod_id in mods:
        try:
            msg = (
                f"💰 **Заявка на пополнение**\n"
                f"━━━━━━━━━━━━\n"
                f"👤 Пользователь: @{username} (#{user_id})\n"
                f"💵 Сумма: `{amount} $`\n"
                f"💳 Метод: `{method}`"
            )
            await context.bot.send_message(mod_id, msg, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Ответить", callback_data=f"reply_user_{user_id}")]
            ]), parse_mode='Markdown')
        except: pass
        
    await update.message.reply_text("✅ Заявка отправлена модераторам. Ожидайте подтверждения.")
    return ConversationHandler.END

# Обработка ответов модератора
async def mod_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = query.data.split("_")[2]
    context.user_data['reply_target_id'] = target_id
    await query.message.reply_text(f"💬 Введите сообщение для пользователя #{target_id}:")
    return MOD_REPLY_USER

async def mod_reply_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    target_id = context.user_data.get('reply_target_id')
    
    try:
        await context.bot.send_message(target_id, f"✉️ **Сообщение от модератора:**\n\n> {text}", parse_mode='Markdown')
        await update.message.reply_text("✅ Сообщение отправлено пользователю.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при отправке: {e}")
        
    return ConversationHandler.END

# Обработка трафика
async def traf_req_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['traf_req'] = query.data.replace("traf_req_", "")
    keyboard = [
        [InlineKeyboardButton("15 мин", callback_data="int_15"), InlineKeyboardButton("30 мин", callback_data="int_30")],
        [InlineKeyboardButton("1 час", callback_data="int_60"), InlineKeyboardButton("2 часа", callback_data="int_120")]
    ]
    await query.edit_message_text("⏱ Выберите интервал трафика:", reply_markup=InlineKeyboardMarkup(keyboard))
    return TRAFFIC_INTERVAL

async def traf_req_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    interval = query.data.replace("int_", "")
    user_id = update.effective_user.id
    username = update.effective_user.username
    req_data = context.user_data.get('traf_req')
    
    mods = get_moderators()
    for mod_id in mods:
        try:
            msg = (
                f"🚦 **Запрос трафика**\n"
                f"━━━━━━━━━━━━\n"
                f"👤 Трейдер: @{username} (#{user_id})\n"
                f"🏦 Реквизит: `{req_data}`\n"
                f"⏱ Интервал: `{interval} мин`"
            )
            await context.bot.send_message(mod_id, msg, reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Принять", callback_data=f"traf_acc_{user_id}"),
                 InlineKeyboardButton("❌ Отклонить", callback_data=f"traf_rej_{user_id}")]
            ]), parse_mode='Markdown')
        except: pass
        
    await query.edit_message_text("✅ Запрос на трафик отправлен.")
    return ConversationHandler.END

# Функции модератора (поиск и действия)
async def mod_search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identifier = update.message.text
    target = get_user_by_identifier(identifier)
    
    if not target:
        await update.message.reply_text("❌ Пользователь не найден.")
        return ConversationHandler.END
        
    context.user_data['target_id'] = target[0]
    
    if context.user_data.get('mod_action') == 'profile':
        earned_val = target[6] if len(target) > 6 else 0
        msg = (
            f"👤 **Профиль пользователя**\n"
            f"━━━━━━━━━━━━\n"
            f"🆔 ID: `{target[0]}`\n"
            f"👤 Username: @{target[1]}\n"
            f"🎖 Роль: `{target[2]}`\n"
            f"🔹 Страховой: `{target[3]:.2f} ₽`\n"
            f"🔸 Рабочий: `{target[4]:.2f} ₽`\n"
            f"📈 Оборот: `{target[5]:.2f} ₽`\n"
            f"💸 Заработано: `{earned_val:.2f} ₽`"
        )
        keyboard = [
            [InlineKeyboardButton("➕ Пополнить баланс", callback_data="mod_repl")],
            [InlineKeyboardButton("➖ Снять с баланса", callback_data="mod_withdraw")]
        ]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return MOD_REPLENISH_TYPE
    else:
        await update.message.reply_text("📦 Введите данные платежа в формате: `номер реквизит сумма` (через пробел)")
        return MOD_PAYMENT_DATA

async def mod_repl_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['mod_repl_action'] = 'add' if 'repl' in query.data else 'sub'
    keyboard = [
        [InlineKeyboardButton("Страховой", callback_data="bal_ins"), InlineKeyboardButton("Рабочий", callback_data="bal_work")]
    ]
    await query.edit_message_text("💎 Выберите тип баланса:", reply_markup=InlineKeyboardMarkup(keyboard))
    return MOD_REPLENISH_AMOUNT

async def mod_repl_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['mod_bal_type'] = 'insurance' if 'ins' in query.data else 'working'
    await query.edit_message_text("💰 Введите сумму:")
    return MOD_REPLENISH_AMOUNT

async def mod_repl_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text)
    except:
        await update.message.reply_text("❌ **Ошибка:** Введите число.")
        return ConversationHandler.END
        
    target_id = context.user_data['target_id']
    action = context.user_data['mod_repl_action']
    bal_type = context.user_data['mod_bal_type']
    
    field = "insurance_balance" if bal_type == "insurance" else "working_balance"
    op = "+" if action == "add" else "-"
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {field} = {field} {op} ? WHERE user_id = ?", (amount, target_id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Баланс успешно обновлен.")
    try:
        await context.bot.send_message(target_id, f"🔔 Ваш {'страховой' if bal_type == 'insurance' else 'рабочий'} баланс изменен на {op}{amount} ₽.")
    except: pass
    return ConversationHandler.END

async def mod_payment_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        data = update.message.text.split()
        amount = float(data[-1])
        pay_info = " ".join(data[:-1])
    except:
        await update.message.reply_text("❌ **Ошибка формата.** Используйте: `номер реквизит сумма`")
        return ConversationHandler.END
        
    target_id = context.user_data['target_id']
    mod_id = update.effective_user.id
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO payments (trader_id, moderator_id, data, amount) VALUES (?, ?, ?, ?)", 
                   (target_id, mod_id, pay_info, amount))
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ Платёж отправлен трейдеру.")
    try:
        await context.bot.send_message(target_id, f"📦 Получен новый платёж на сумму {amount} ₽. Проверьте раздел «📋 Платежи».")
    except: pass
    return ConversationHandler.END

# Одобрение платежа трейдером
async def approve_pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pay_id = query.data.split("_")[2]
    context.user_data['approve_pay_id'] = pay_id
    await query.edit_message_text("📱 Введите номер, с которого был совершен платёж:")
    return APPROVE_PAYMENT_NUMBER

async def approve_pay_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text
    pay_id = context.user_data['approve_pay_id']
    user_id = update.effective_user.id
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT amount, moderator_id FROM payments WHERE id = ?", (pay_id,))
    pay = cursor.fetchone()
    
    if not pay:
        await update.message.reply_text("❌ Платёж не найден.")
        conn.close()
        return ConversationHandler.END
        
    amount = pay[0]
    mod_id = pay[1]
    comm_rate = calculate_commission(amount)
    profit = amount * comm_rate
    
    # Обновляем балансы: списываем сумму, начисляем процент, обновляем оборот и заработано
    cursor.execute("UPDATE users SET working_balance = working_balance - ?, turnover = turnover + ?, earned = earned + ? WHERE user_id = ?", 
                   (amount, amount, profit, user_id))
    cursor.execute("UPDATE users SET working_balance = working_balance + ? WHERE user_id = ?", (profit, user_id))
    cursor.execute("UPDATE payments SET status = 'approved' WHERE id = ?", (pay_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Платёж одобрен! Вам начислено {profit:.2f} ₽ ({comm_rate*100}%).")
    try:
        await context.bot.send_message(mod_id, f"✅ Трейдер #{user_id} одобрил платёж #{pay_id} на сумму {amount} ₽. Номер отправителя: {number}")
    except: pass
    return ConversationHandler.END

# Назначение модератора
async def promote_mod_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    identifier = update.message.text
    target = get_user_by_identifier(identifier)
    
    if not target:
        await update.message.reply_text("❌ Пользователь не найден.")
        return ConversationHandler.END
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = 'moderator' WHERE user_id = ?", (target[0],))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Пользователь @{target[1]} назначен модератором.")
    try:
        await context.bot.send_message(target[0], "🎉 Вам назначена роль Модератора! Перезапустите бота /start")
    except: pass
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❕ Действие отменено.")
    return ConversationHandler.END

# Главная функция
def main():
    init_db()
    TOKEN = "8619908903:AAE5Ds0ts3rhViOw0AIzwGLEOGSzfEja0_k"
    application = Application.builder().token(TOKEN).build()

    # Conversation Handlers
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_req_start, pattern="^add_req$"),
            CallbackQueryHandler(repl_start, pattern="^repl_"),
            CallbackQueryHandler(mod_reply_start, pattern="^reply_user_"),
            CallbackQueryHandler(traf_req_select, pattern="^traf_req_"),
            CallbackQueryHandler(approve_pay_start, pattern="^appr_pay_"),
            MessageHandler(filters.Regex("^(📤 Платежи|👥 Пользователи)$"), handle_message),
            MessageHandler(filters.Regex("^🛡️ Назначить модератора$"), handle_message)
        ],
        states={
            ADD_REQUISITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_req_save)],
            REPLENISH_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, repl_finish)],
            MOD_REPLY_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, mod_reply_finish)],
            TRAFFIC_INTERVAL: [CallbackQueryHandler(traf_req_finish, pattern="^int_")],
            MOD_SEARCH_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, mod_search_user)],
            MOD_REPLENISH_TYPE: [CallbackQueryHandler(mod_repl_type, pattern="^mod_")],
            MOD_REPLENISH_AMOUNT: [
                CallbackQueryHandler(mod_repl_amount, pattern="^bal_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, mod_repl_finish)
            ],
            MOD_PAYMENT_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, mod_payment_save)],
            APPROVE_PAYMENT_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, approve_pay_finish)],
            PROMOTE_MODERATOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, promote_mod_finish)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(del_req_start, pattern="^del_req$"))
    application.add_handler(CallbackQueryHandler(del_req_confirm, pattern="^del_id_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🌊 DripDropPay Bot запущен!")
    application.run_polling()

if __name__ == '__main__':
    main()
