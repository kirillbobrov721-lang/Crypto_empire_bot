import os
import logging
import sqlite3
import random
import re
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('BOT_TOKEN')

# ========== АДМИНЫ С ДОЛЖНОСТЯМИ ==========
ADMIN_ROLES = {
    "owner": {
        "name": "👑 Владелец",
        "level": 5,
        "permissions": ["all"],
        "users": [5005387093]
    },
    "admin": {
        "name": "⚙️ Администратор",
        "level": 4,
        "permissions": ["ban", "unban", "give_money", "clear_inventory", "announce", "set_vip", "set_admin"],
        "users": []
    },
    "moderator": {
        "name": "🛡️ Модератор",
        "level": 3,
        "permissions": ["ban", "unban", "warn", "mute"],
        "users": []
    },
    "support": {
        "name": "🎧 Поддержка",
        "level": 2,
        "permissions": ["help_users", "warn"],
        "users": []
    },
    "helper": {
        "name": "🌟 Хелпер",
        "level": 1,
        "permissions": ["help_users"],
        "users": []
    }
}

# ========== VIP СТАТУСЫ ==========
VIP_STATUSES = {
    "bronze": {"name": "🥉 Бронза", "price": 50000, "duration": 30, "bonus_income": 5, "bonus_defense": 10, "emoji": "🥉"},
    "silver": {"name": "🥈 Серебро", "price": 150000, "duration": 30, "bonus_income": 10, "bonus_defense": 20, "emoji": "🥈"},
    "gold": {"name": "🥇 Золото", "price": 500000, "duration": 30, "bonus_income": 20, "bonus_defense": 35, "emoji": "🥇"},
    "platinum": {"name": "💎 Платина", "price": 1500000, "duration": 30, "bonus_income": 35, "bonus_defense": 50, "emoji": "💎"},
    "diamond": {"name": "✨ Алмаз", "price": 5000000, "duration": 30, "bonus_income": 50, "bonus_defense": 75, "emoji": "✨"}
}

# ========== БИЗНЕСЫ (10 УРОВНЕЙ) ==========
BUSINESSES = {
    1: {"name": "🏪 Ларёк", "income": 50, "upgrade_cost": 500, "emoji": "🏪", "defense": 5},
    2: {"name": "🏬 Магазин", "income": 150, "upgrade_cost": 2000, "emoji": "🏬", "defense": 10},
    3: {"name": "🏢 Супермаркет", "income": 400, "upgrade_cost": 8000, "emoji": "🏢", "defense": 15},
    4: {"name": "🏙️ ТЦ", "income": 1000, "upgrade_cost": 30000, "emoji": "🏙️", "defense": 20},
    5: {"name": "🌆 Корпорация", "income": 2500, "upgrade_cost": 100000, "emoji": "🌆", "defense": 30},
    6: {"name": "🌍 Империя", "income": 6000, "upgrade_cost": 500000, "emoji": "🌍", "defense": 40},
    7: {"name": "🚀 Космическая", "income": 15000, "upgrade_cost": 2000000, "emoji": "🚀", "defense": 50},
    8: {"name": "✨ Божественная", "income": 50000, "upgrade_cost": 5000000, "emoji": "✨", "defense": 70},
    9: {"name": "👑 Легендарная", "income": 150000, "upgrade_cost": 15000000, "emoji": "👑", "defense": 100},
    10: {"name": "💎 Абсолют", "income": 500000, "upgrade_cost": None, "emoji": "💎", "defense": 150}
}

# ========== УЛУЧШЕНИЯ ==========
UPGRADES = {
    "manager": {"name": "👔 Менеджер", "cost": 2000, "income_bonus": 0.20, "defense_bonus": 5},
    "advertising": {"name": "📢 Реклама", "cost": 1500, "income_bonus": 0.15, "defense_bonus": 0},
    "security": {"name": "🛡️ Охрана", "cost": 3000, "income_bonus": 0, "defense_bonus": 20},
    "marketing": {"name": "📊 Маркетинг", "cost": 5000, "income_bonus": 0.25, "defense_bonus": 0},
    "armored": {"name": "🚛 Бронированный", "cost": 10000, "income_bonus": 0, "defense_bonus": 40},
    "hacker": {"name": "💻 Хакер", "cost": 15000, "income_bonus": 0, "attack_bonus": 30}
}

# ========== КВЕСТЫ ==========
QUESTS = {
    1: {"name": "📦 Первый доход", "desc": "Собрать доход 1 раз", "target": 1, "reward": 500, "type": "collect"},
    2: {"name": "💪 Начинающий", "desc": "Собрать доход 10 раз", "target": 10, "reward": 5000, "type": "collect"},
    3: {"name": "⚔️ Первая атака", "desc": "Атаковать игрока 1 раз", "target": 1, "reward": 1000, "type": "attack"},
    4: {"name": "🛡️ Первая защита", "desc": "Отразить атаку 1 раз", "target": 1, "reward": 1000, "type": "defense"},
    5: {"name": "💰 Первый миллион", "desc": "Накопить 1,000,000 монет", "target": 1000000, "reward": 100000, "type": "balance"}
}

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    
    # Пользователи с AUTOINCREMENT ID
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER UNIQUE,
                  balance INTEGER DEFAULT 1000,
                  business_level INTEGER DEFAULT 1,
                  last_collect TIMESTAMP,
                  total_earned INTEGER DEFAULT 0,
                  total_collects INTEGER DEFAULT 0,
                  manager BOOLEAN DEFAULT FALSE,
                  advertising BOOLEAN DEFAULT FALSE,
                  security BOOLEAN DEFAULT FALSE,
                  marketing BOOLEAN DEFAULT FALSE,
                  armored BOOLEAN DEFAULT FALSE,
                  hacker BOOLEAN DEFAULT FALSE,
                  last_daily TIMESTAMP,
                  streak INTEGER DEFAULT 0,
                  last_work TIMESTAMP,
                  casino_wins INTEGER DEFAULT 0,
                  gifts_sent INTEGER DEFAULT 0,
                  attacks_won INTEGER DEFAULT 0,
                  defenses_won INTEGER DEFAULT 0,
                  businesses_destroyed INTEGER DEFAULT 0,
                  last_attack TIMESTAMP,
                  protection_until TIMESTAMP,
                  vip_level TEXT DEFAULT 'none',
                  vip_until TIMESTAMP,
                  clan_id INTEGER DEFAULT 0,
                  banned BOOLEAN DEFAULT FALSE,
                  warn_count INTEGER DEFAULT 0,
                  register_date TIMESTAMP)''')
    
    # Админы
    c.execute('''CREATE TABLE IF NOT EXISTS admins
                 (user_id INTEGER PRIMARY KEY,
                  role TEXT DEFAULT 'helper',
                  appointed_by INTEGER,
                  appointed_at TIMESTAMP)''')
    
    # Инвентарь
    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (user_id INTEGER, item_type TEXT, quantity INTEGER DEFAULT 0,
                  PRIMARY KEY (user_id, item_type))''')
    
    # Квесты
    c.execute('''CREATE TABLE IF NOT EXISTS user_quests
                 (user_id INTEGER, quest_id INTEGER, progress INTEGER DEFAULT 0, completed BOOLEAN DEFAULT FALSE,
                  PRIMARY KEY (user_id, quest_id))''')
    
    conn.commit()
    conn.close()
    
    # Добавляем владельца в админы
    add_admin(5005387093, "owner")

def get_user_by_id(user_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_user_by_game_id(game_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (game_id,))
    user = c.fetchone()
    conn.close()
    return user

def get_game_id(user_id):
    user = get_user_by_id(user_id)
    return user[0] if user else None

def register_user(user_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    now = datetime.now()
    
    # Проверяем, есть ли уже пользователь
    c.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
    existing = c.fetchone()
    
    if not existing:
        c.execute("""INSERT INTO users 
                     (user_id, last_collect, last_daily, last_work, last_attack, protection_until, vip_until, register_date) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                  (user_id, now, now, now, now, now, now, now))
        conn.commit()
        
        # Получаем присвоенный ID
        c.execute("SELECT id FROM users WHERE user_id = ?", (user_id,))
        game_id = c.fetchone()[0]
        
        # Если это первый пользователь (владелец), даём особый статус
        if game_id == 1:
            c.execute("UPDATE users SET balance = 1000000 WHERE user_id = ?", (user_id,))
            conn.commit()
    else:
        game_id = existing[0]
    
    conn.close()
    
    # Инициализация квестов
    init_user_quests(user_id)
    
    return game_id

def init_user_quests(user_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    for quest_id in QUESTS:
        c.execute("INSERT OR IGNORE INTO user_quests (user_id, quest_id, progress, completed) VALUES (?, ?, 0, FALSE)",
                  (user_id, quest_id))
    conn.commit()
    conn.close()

def add_admin(user_id, role):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO admins (user_id, role, appointed_by, appointed_at) VALUES (?, ?, ?, ?)",
              (user_id, role, 5005387093, datetime.now()))
    conn.commit()
    conn.close()

def get_admin_role(user_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("SELECT role FROM admins WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def has_permission(user_id, permission):
    role = get_admin_role(user_id)
    if not role:
        return False
    admin_data = ADMIN_ROLES.get(role)
    if not admin_data:
        return False
    return permission in admin_data["permissions"] or "all" in admin_data["permissions"]

def update_balance(user_id, amount):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?",
              (amount, max(amount, 0), user_id))
    conn.commit()
    conn.close()

def calculate_income(user):
    level = user[3]
    base_income = BUSINESSES[level]["income"]
    multiplier = 1.0
    
    if user[6]: multiplier += 0.20
    if user[7]: multiplier += 0.15
    if user[9]: multiplier += 0.25
    
    # VIP бонус
    vip = user[23]
    if vip in VIP_STATUSES:
        multiplier += VIP_STATUSES[vip]["bonus_income"] / 100
    
    return int(base_income * multiplier)

def calculate_defense(user):
    level = user[3]
    base_defense = BUSINESSES[level]["defense"]
    
    if user[6]: base_defense += 5
    if user[8]: base_defense += 20
    if user[10]: base_defense += 40
    
    # VIP бонус
    vip = user[23]
    if vip in VIP_STATUSES:
        base_defense += VIP_STATUSES[vip]["bonus_defense"]
    
    return base_defense

def calculate_attack(user):
    attack = 10 + (user[3] * 3)
    if user[11]:
        attack += 30
    return attack

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance"),
         InlineKeyboardButton("🏪 Бизнес", callback_data="business")],
        [InlineKeyboardButton("💼 Собрать", callback_data="collect"),
         InlineKeyboardButton("📈 Магазин", callback_data="upgrades")],
        [InlineKeyboardButton("⚔️ Атака", callback_data="attack_menu"),
         InlineKeyboardButton("🛡️ Защита", callback_data="protection")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="daily"),
         InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton("👑 VIP", callback_data="vip_shop"),
         InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("🏆 Квесты", callback_data="quests"),
         InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== ОБРАБОТЧИКИ КОМАНД ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    game_id = register_user(user_id)
    user = get_user_by_id(user_id)
    
    text = (f"🔥 *CRYPTO EMPIRE* 🔥\n\n"
            f"✨ *Твой ID:* `#{game_id}`\n"
            f"💰 *Стартовый баланс:* 1000 монет\n\n"
            f"📌 *Доступные команды:*\n"
            f"• `/start` - запуск\n"
            f"• `/баланс` или `/б` - баланс\n"
            f"• `/бизнес` или `/биз` - бизнес\n"
            f"• `/собрать` - собрать доход\n"
            f"• `/атака @ник` - атаковать\n"
            f"• `/защита 24` - купить защиту\n"
            f"• `/подарок @ник 1000` - подарок\n"
            f"• `/топ` - топ игроков\n"
            f"• `/гет @ник` - информация\n"
            f"• `/агет ID` - информация по ID\n\n"
            f"👇 *Используй кнопки ниже!*")
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user_by_id(user_id)
    game_id = get_game_id(user_id)
    
    if not user:
        await update.message.reply_text("❌ Ты не зарегистрирован! Напиши /start")
        return
    
    text = (f"💰 *ТВОЙ БАЛАНС*\n\n"
            f"🆔 ID: `#{game_id}`\n"
            f"💵 Монет: `{user[2]:,}`\n"
            f"📈 Всего заработано: `{user[5]:,}`\n"
            f"⚔️ Побед в атаках: {user[18]}\n"
            f"🛡️ Защит: {user[19]}")
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def get_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация об игроке по @username или ID"""
    args = context.args
    
    if not args:
        await update.message.reply_text("❌ Использование: `/get @username` или `/get 15`", parse_mode='Markdown')
        return
    
    target = args[0]
    
    if target.startswith('@'):
        username = target[1:]
        try:
            chat = await context.bot.get_chat(f"@{username}")
            target_id = chat.id
            user = get_user_by_id(target_id)
            if not user:
                await update.message.reply_text("❌ Игрок не найден в игре!", parse_mode='Markdown')
                return
            game_id = get_game_id(target_id)
        except:
            await update.message.reply_text("❌ Пользователь не найден!", parse_mode='Markdown')
            return
    elif target.isdigit():
        game_id = int(target)
        user = get_user_by_game_id(game_id)
        if not user:
            await update.message.reply_text("❌ Игрок с таким ID не найден!", parse_mode='Markdown')
            return
        target_id = user[1]
        game_id = user[0]
    else:
        await update.message.reply_text("❌ Использование: `/get @username` или `/get 15`", parse_mode='Markdown')
        return
    
    level = user[3]
    business = BUSINESSES[level]
    income = calculate_income(user)
    
    text = (f"📊 *ИНФОРМАЦИЯ ОБ ИГРОКЕ*\n\n"
            f"🆔 ID: `#{game_id}`\n"
            f"👤 Ник: @{username if target.startswith('@') else 'скрыт'}\n"
            f"🏪 Бизнес: {business['emoji']} {business['name']} (ур. {level}/10)\n"
            f"💰 Баланс: `{user[2]:,}` монет\n"
            f"💵 Доход за сбор: `{income:,}`\n"
            f"⚔️ Сила атаки: {calculate_attack(user)}\n"
            f"🛡️ Защита: {calculate_defense(user)}\n"
            f"📊 Собрано раз: {user[6]}\n"
            f"⚔️ Атак выиграно: {user[18]}\n"
            f"🛡️ Атак отбито: {user[19]}")
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def aget_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Информация об игроке по ID (только для админов)"""
    user_id = update.effective_user.id
    
    if not has_permission(user_id, "help_users"):
        await update.message.reply_text("❌ У тебя нет прав на эту команду!", parse_mode='Markdown')
        return
    
    args = context.args
    
    if not args or not args[0].isdigit():
        await update.message.reply_text("❌ Использование: `/aget ID`", parse_mode='Markdown')
        return
    
    game_id = int(args[0])
    user = get_user_by_game_id(game_id)
    
    if not user:
        await update.message.reply_text("❌ Игрок с таким ID не найден!", parse_mode='Markdown')
        return
    
    target_id = user[1]
    vip = user[23] if user[23] != 'none' else 'Нет'
    
    text = (f"🔍 *ПОЛНАЯ ИНФОРМАЦИЯ* (ID: #{game_id})\n\n"
            f"🆔 Telegram ID: `{target_id}`\n"
            f"💰 Баланс: `{user[2]:,}`\n"
            f"🏪 Бизнес: ур.{user[3]}\n"
            f"📈 Всего заработано: `{user[5]:,}`\n"
            f"📊 Собрано раз: {user[6]}\n"
            f"⚔️ Атак выиграно: {user[18]}\n"
            f"🛡️ Защит: {user[19]}\n"
            f"💀 Уничтожено бизнесов: {user[20]}\n"
            f"👑 VIP статус: {vip}\n"
            f"🚫 Бан: {'✅' if user[26] else '❌'}\n"
            f"⚠️ Варнов: {user[27]}")
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("SELECT id, user_id, balance FROM users ORDER BY balance DESC LIMIT 10")
    top = c.fetchall()
    conn.close()
    
    text = "🏆 *ТОП 10 БОГАЧЕЙ* 🏆\n\n"
    for i, (game_id, uid, balance) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
        text += f"{medal} #{game_id} — `{balance:,}` монет\n"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def ahelp_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает доступные админ команды"""
    user_id = update.effective_user.id
    role = get_admin_role(user_id)
    
    if not role:
        await update.message.reply_text("❌ У тебя нет прав администратора!", parse_mode='Markdown')
        return
    
    role_data = ADMIN_ROLES.get(role, {})
    role_name = role_data.get("name", role)
    level = role_data.get("level", 0)
    
    text = f"🛡️ *АДМИН ПАНЕЛЬ* 🛡️\n\n"
    text += f"👑 Твоя роль: {role_name} (уровень {level})\n\n"
    text += f"📋 *Доступные команды:*\n"
    
    for cmd_name, cmd_data in ADMIN_COMMANDS.items():
        if level >= cmd_data["min_level"]:
            text += f"\n• `/{cmd_name}`\n   {cmd_data['desc']}\n   💡 {cmd_data['usage']}"
    
    text += "\n\n⚡ *Русские команды:*\n• `/админ` - это меню\n• `/выдать @ник сумма`\n• `/забанить @ник`\n• `/объявить текст`"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых команд без / (алиасы)"""
    text = update.message.text.lower().strip()
    user_id = update.effective_user.id
    
    # Русские алиасы
    aliases = {
        "баланс": balance_command,
        "б": balance_command,
        "деньги": balance_command,
        "денег": balance_command,
        "бизнес": business_command,
        "биз": business_command,
        "собрать": collect_command,
        "сбор": collect_command,
        "топ": top_command,
        "атака": attack_command,
        "защита": protection_command,
        "помощь": help_command,
        "хелп": help_command,
        "админ": ahelp_command,
        "ахелп": ahelp_command,
        "ahelp": ahelp_command,
        "акмд": ahelp_command
    }
    
    # Проверяем, начинается ли сообщение с одной из команд
    for alias, handler in aliases.items():
        if text.startswith(alias):
            # Если команда с аргументами (атака @ник)
            parts = text.split()
            if len(parts) > 1:
                context.args = parts[1:]
            else:
                context.args = []
            await handler(update, context)
            return

# Заглушки для недостающих функций
async def business_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏪 Информация о бизнесе (в разработке)")

async def collect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💼 Сбор дохода (в разработке)")

async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚔️ Атака (в разработке)")

async def protection_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛡️ Защита (в разработке)")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Помощь (в разработке)")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "help":
        text = ("📚 *ПОМОЩЬ*\n\n"
                "💰 *Баланс* - твои деньги\n"
                "🏪 *Бизнес* - прокачка\n"
                "💼 *Собрать* - доход каждые 15 мин\n"
                "⚔️ *Атака* - `/attack @ник`\n"
                "🛡️ *Защита* - `/protect 24`\n"
                "🎁 *Подарок* - `/gift @ник сумма`\n"
                "📊 *Топ* - `/top`\n"
                "🔍 *Гет* - `/get @ник` или `/get 15`\n\n"
                "🔥 *Русские команды:*\n"
                "• `/баланс` или `/б`\n"
                "• `/бизнес` или `/биз`\n"
                "• `/собрать`\n"
                "• `/топ`\n"
                "• `/атака @ник`\n"
                "• `/защита 24`\n"
                "• `/подарок @ник 1000`\n"
                "• `/гет @ник`\n"
                "• `/агет 15` - админ команда")
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    else:
        await query.edit_message_text("🔄 В разработке...", reply_markup=get_main_keyboard())

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    # Команды с /
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler(["balance", "bal", "b"], balance_command))
    app.add_handler(CommandHandler(["get", "info", "гет"], get_command))
    app.add_handler(CommandHandler(["aget", "агет"], aget_command))
    app.add_handler(CommandHandler(["top", "топ"], top_command))
    app.add_handler(CommandHandler(["ahelp", "админ", "ахелп", "акмд"], ahelp_command))
    app.add_handler(CommandHandler(["help", "помощь", "хелп"], help_command))
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Обработка текста без / (алиасы)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    logger.info("🤖 CRYPTO EMPIRE ЗАПУЩЕН!")
    app.run_polling()

if __name__ == "__main__":
    main()
