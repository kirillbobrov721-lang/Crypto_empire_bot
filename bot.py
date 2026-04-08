import os
import logging
import sqlite3
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен из переменных окружения Render
TOKEN = os.environ.get('BOT_TOKEN')

# ========== БИЗНЕСЫ (8 УРОВНЕЙ!) ==========
BUSINESSES = {
    1: {"name": "🏪 Ларёк", "income": 50, "upgrade_cost": 500, "emoji": "🏪"},
    2: {"name": "🏬 Магазин", "income": 150, "upgrade_cost": 2000, "emoji": "🏬"},
    3: {"name": "🏢 Супермаркет", "income": 400, "upgrade_cost": 8000, "emoji": "🏢"},
    4: {"name": "🏙️ Торговый центр", "income": 1000, "upgrade_cost": 30000, "emoji": "🏙️"},
    5: {"name": "🌆 Корпорация", "income": 2500, "upgrade_cost": 100000, "emoji": "🌆"},
    6: {"name": "🌍 Империя", "income": 6000, "upgrade_cost": 500000, "emoji": "🌍"},
    7: {"name": "🚀 Космическая", "income": 15000, "upgrade_cost": 2000000, "emoji": "🚀"},
    8: {"name": "✨ Божественная", "income": 50000, "upgrade_cost": None, "emoji": "✨"}
}

# ========== ДОСТИЖЕНИЯ ==========
ACHIEVEMENTS = {
    1: {"name": "💰 Новичок", "desc": "Заработать 10,000 монет", "reward": 5000, "required": 10000},
    2: {"name": "💎 Миллионер", "desc": "Заработать 1,000,000 монет", "reward": 100000, "required": 1000000},
    3: {"name": "⚡ Трудоголик", "desc": "Собрать доход 100 раз", "reward": 50000, "required": 100},
    4: {"name": "🔧 Коллекционер", "desc": "Купить все улучшения", "reward": 75000, "required": 3},
    5: {"name": "👑 Император", "desc": "Достичь 8 уровня бизнеса", "reward": 500000, "required": 8},
    6: {"name": "🎲 Везунчик", "desc": "Выиграть в казино 10 раз", "reward": 25000, "required": 10},
    7: {"name": "🤝 Меценат", "desc": "Отправить подарок другу", "reward": 15000, "required": 1}
}

# ========== КАЗИНО ==========
CASINO_GAMES = {
    "🎰 Слоты": {"min_bet": 100, "max_bet": 10000, "win_chance": 0.3, "multiplier": 2.5},
    "🎲 Кости": {"min_bet": 50, "max_bet": 5000, "win_chance": 0.5, "multiplier": 1.8},
    "🏆 Рулетка": {"min_bet": 200, "max_bet": 20000, "win_chance": 0.4, "multiplier": 2.2}
}

# ========== РАБОТЫ ==========
JOBS = {
    1: {"name": "📦 Курьер", "income": 300, "duration": 30, "cooldown": 60},
    2: {"name": "💻 Программист", "income": 800, "duration": 60, "cooldown": 120},
    3: {"name": "👨‍💼 Менеджер", "income": 1500, "duration": 120, "cooldown": 240},
    4: {"name": "🏦 Банкир", "income": 3000, "duration": 180, "cooldown": 360}
}

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    
    # Основная таблица пользователей
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  balance INTEGER DEFAULT 1000,
                  business_level INTEGER DEFAULT 1,
                  last_collect TIMESTAMP,
                  total_earned INTEGER DEFAULT 0,
                  total_collects INTEGER DEFAULT 0,
                  manager BOOLEAN DEFAULT FALSE,
                  advertising BOOLEAN DEFAULT FALSE,
                  security BOOLEAN DEFAULT FALSE,
                  marketing BOOLEAN DEFAULT FALSE,
                  last_daily TIMESTAMP,
                  streak INTEGER DEFAULT 0,
                  last_work TIMESTAMP,
                  casino_wins INTEGER DEFAULT 0,
                  gifts_sent INTEGER DEFAULT 0)''')
    
    # Инвентарь
    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (user_id INTEGER,
                  item_type TEXT,
                  quantity INTEGER DEFAULT 0,
                  PRIMARY KEY (user_id, item_type))''')
    
    # Достижения
    c.execute('''CREATE TABLE IF NOT EXISTS user_achievements
                 (user_id INTEGER,
                  achievement_id INTEGER,
                  completed BOOLEAN DEFAULT FALSE,
                  PRIMARY KEY (user_id, achievement_id))''')
    
    # Работа
    c.execute('''CREATE TABLE IF NOT EXISTS user_work
                 (user_id INTEGER PRIMARY KEY,
                  last_job_time TIMESTAMP,
                  current_job INTEGER)''')
    
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def register_user(user_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    now = datetime.now()
    c.execute("INSERT OR IGNORE INTO users (user_id, last_collect, last_daily, last_work) VALUES (?, ?, ?, ?)",
              (user_id, now, now, now))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?",
              (amount, max(amount, 0), user_id))
    conn.commit()
    conn.close()
    check_achievements(user_id)

def upgrade_business(user_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("UPDATE users SET business_level = business_level + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def update_last_collect(user_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("UPDATE users SET last_collect = ?, total_collects = total_collects + 1 WHERE user_id = ?", 
              (datetime.now(), user_id))
    conn.commit()
    conn.close()
    check_achievements(user_id)

def buy_upgrade(user_id, upgrade_type, cost):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute(f"UPDATE users SET balance = balance - ?, {upgrade_type} = TRUE WHERE user_id = ? AND balance >= ?", 
              (cost, user_id, cost))
    conn.commit()
    conn.close()
    check_achievements(user_id)

def calculate_income(user):
    level = user[2]
    base_income = BUSINESSES[level]["income"]
    multiplier = 1.0
    
    if user[5]: multiplier += 0.2    # Менеджер
    if user[6]: multiplier += 0.15   # Реклама
    if user[7]: multiplier += 0.1    # Охрана
    if user[8]: multiplier += 0.25   # Маркетинг
    
    return int(base_income * multiplier)

def add_inventory_item(user_id, item_type, quantity=1):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO inventory (user_id, item_type, quantity) VALUES (?, ?, COALESCE((SELECT quantity FROM inventory WHERE user_id = ? AND item_type = ?), 0) + ?)",
              (user_id, item_type, user_id, item_type, quantity))
    conn.commit()
    conn.close()

def get_inventory(user_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("SELECT item_type, quantity FROM inventory WHERE user_id = ?", (user_id,))
    items = c.fetchall()
    conn.close()
    return dict(items)

def check_achievements(user_id):
    user = get_user(user_id)
    if not user:
        return
    
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    
    for ach_id, ach_data in ACHIEVEMENTS.items():
        c.execute("SELECT completed FROM user_achievements WHERE user_id = ? AND achievement_id = ?", (user_id, ach_id))
        completed = c.fetchone()
        
        if not completed or not completed[0]:
            achieved = False
            
            if ach_id == 1 and user[4] >= 10000:
                achieved = True
            elif ach_id == 2 and user[4] >= 1000000:
                achieved = True
            elif ach_id == 3 and user[9] >= 100:
                achieved = True
            elif ach_id == 4:  # Все улучшения
                upgrades = sum([user[5], user[6], user[7], user[8]])
                if upgrades >= 4:
                    achieved = True
            elif ach_id == 5 and user[2] >= 8:
                achieved = True
            elif ach_id == 6 and user[13] >= 10:
                achieved = True
            elif ach_id == 7 and user[14] >= 1:
                achieved = True
            
            if achieved:
                c.execute("INSERT OR REPLACE INTO user_achievements (user_id, achievement_id, completed) VALUES (?, ?, TRUE)", 
                         (user_id, ach_id))
                update_balance(user_id, ach_data['reward'])
                
    conn.commit()
    conn.close()

def get_daily_reward(streak):
    base_reward = 1000
    streak_bonus = streak * 300
    return base_reward + streak_bonus

def claim_daily(user_id):
    user = get_user(user_id)
    last_daily = datetime.fromisoformat(user[10]) if user[10] else datetime.now() - timedelta(days=1)
    today = datetime.now().date()
    last_date = last_daily.date()
    
    if last_date == today:
        return None, 0
    
    if (today - last_date).days == 1:
        streak = user[11] + 1
    else:
        streak = 1
    
    reward = get_daily_reward(streak)
    update_balance(user_id, reward)
    
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("UPDATE users SET last_daily = ?, streak = ? WHERE user_id = ?", 
              (datetime.now(), streak, user_id))
    conn.commit()
    conn.close()
    
    return streak, reward

def send_gift(from_user_id, to_user_id, amount):
    from_user = get_user(from_user_id)
    to_user = get_user(to_user_id)
    
    if not to_user:
        return "not_found"
    
    if from_user[1] < amount:
        return "no_money"
    
    update_balance(from_user_id, -amount)
    update_balance(to_user_id, amount)
    
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("UPDATE users SET gifts_sent = gifts_sent + 1 WHERE user_id = ?", (from_user_id,))
    conn.commit()
    conn.close()
    
    check_achievements(from_user_id)
    return "success"

def casino_game(user_id, game_name, bet):
    user = get_user(user_id)
    if user[1] < bet:
        return None, "no_money"
    
    game = CASINO_GAMES[game_name]
    if bet < game["min_bet"] or bet > game["max_bet"]:
        return None, "invalid_bet"
    
    win = random.random() < game["win_chance"]
    
    if win:
        winnings = int(bet * game["multiplier"])
        update_balance(user_id, winnings)
        
        conn = sqlite3.connect('business.db')
        c = conn.cursor()
        c.execute("UPDATE users SET casino_wins = casino_wins + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        check_achievements(user_id)
        return winnings, "win"
    else:
        update_balance(user_id, -bet)
        return 0, "lose"

def do_work(user_id, job_id):
    user = get_user(user_id)
    job = JOBS[job_id]
    
    last_work = datetime.fromisoformat(user[12]) if user[12] else datetime.now()
    time_since = (datetime.now() - last_work).total_seconds()
    
    if time_since < job["cooldown"] * 60:
        remaining = int((job["cooldown"] * 60 - time_since) // 60)
        return None, remaining
    
    update_balance(user_id, job["income"])
    
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("UPDATE users SET last_work = ? WHERE user_id = ?", (datetime.now(), user_id))
    conn.commit()
    conn.close()
    
    return job["income"], 0

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance"),
         InlineKeyboardButton("🏪 Бизнес", callback_data="business")],
        [InlineKeyboardButton("💼 Собрать доход", callback_data="collect"),
         InlineKeyboardButton("📈 Магазин", callback_data="upgrades")],
        [InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="daily"),
         InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton("🎰 Казино", callback_data="casino"),
         InlineKeyboardButton("💼 Работа", callback_data="work")],
        [InlineKeyboardButton("🎁 Подарок другу", callback_data="gift"),
         InlineKeyboardButton("🏆 Достижения", callback_data="achievements")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_casino_keyboard():
    keyboard = []
    for game in CASINO_GAMES.keys():
        keyboard.append([InlineKeyboardButton(game, callback_data=f"casino_{game}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

def get_work_keyboard():
    keyboard = []
    for job_id, job in JOBS.items():
        keyboard.append([InlineKeyboardButton(f"{job['name']} (+{job['income']}💰)", callback_data=f"work_{job_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    return InlineKeyboardMarkup(keyboard)

# ========== ОБРАБОТЧИКИ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    
    text = ("🏆 *ДОБРО ПОЖАЛОВАТЬ В CRYPTO EMPIRE!* 🏆\n\n"
            "🌍 *Мега-системы:*\n"
            "💰 Пассивный доход каждые 15 минут\n"
            "📈 8 уровней бизнеса (до Божественного!)\n"
            "🎰 Казино с 3 играми\n"
            "💼 Работа с 4 профессиями\n"
            "🎁 Подарки друзьям\n"
            "🏆 7 достижений\n"
            "🔥 Ежедневные бонусы с серией\n\n"
            "👇 *НАЧНИ СВОЙ ПУТЬ К ИМПЕРИИ!*")
    
    await update.message.reply_text(text, parse_mode='Markdown', 
                                   reply_markup=get_main_keyboard())

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    user = get_user(user_id)
    
    if not user:
        register_user(user_id)
        user = get_user(user_id)
    
    # ===== БАЛАНС =====
    if action == "balance":
        text = (f"💰 *ВАШ БАЛАНС:* `{user[1]:,}` монет\n\n"
                f"📈 *Всего заработано:* `{user[4]:,}`\n"
                f"📊 *Собрано раз:* {user[9]}\n"
                f"🎰 *Побед в казино:* {user[13]}\n"
                f"🎁 *Подарков отправлено:* {user[14]}")
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== БИЗНЕС =====
    elif action == "business":
        level = user[2]
        business = BUSINESSES[level]
        income = calculate_income(user)
        
        last_collect = datetime.fromisoformat(user[3]) if user[3] else datetime.now()
        time_passed = (datetime.now() - last_collect).total_seconds()
        time_left = max(0, 900 - time_passed)
        minutes_left = int(time_left // 60)
        seconds_left = int(time_left % 60)
        
        text = (f"{business['emoji']} *{business['name']}* (Уровень {level}/8)\n\n"
                f"💵 *Доход за сбор:* `{income:,}` монет\n"
                f"⏰ *До сбора:* {minutes_left} мин {seconds_left} сек\n\n"
                f"📈 *Множители:*\n"
                f"  👔 Менеджер: +20% {'✅' if user[5] else '❌'}\n"
                f"  📢 Реклама: +15% {'✅' if user[6] else '❌'}\n"
                f"  🛡️ Охрана: +10% {'✅' if user[7] else '❌'}\n"
                f"  📊 Маркетинг: +25% {'✅' if user[8] else '❌'}")
        
        if level < 8:
            text += f"\n\n⬆️ *Апгрейд:* `{business['upgrade_cost']:,}` монет"
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== СБОР =====
    elif action == "collect":
        last_collect = datetime.fromisoformat(user[3]) if user[3] else datetime.now()
        time_passed = (datetime.now() - last_collect).total_seconds()
        
        if time_passed >= 900:
            income = calculate_income(user)
            update_balance(user_id, income)
            update_last_collect(user_id)
            
            # Бонусные предметы
            if random.random() < 0.15:
                items = ["💎 Алмаз", "⭐ Звезда", "🎫 Лотерейный билет", "🍀 Четырёхлистный клевер"]
                item = random.choice(items)
                add_inventory_item(user_id, item)
                bonus_text = f"\n\n🎁 *Бонус!* +{item} в инвентарь!"
            else:
                bonus_text = ""
            
            text = (f"✅ *ДОХОД СОБРАН!*\n"
                   f"💵 `+{income:,}` монет\n"
                   f"💰 Баланс: `{user[1] + income:,}`{bonus_text}")
        else:
            minutes_left = int((900 - time_passed) // 60)
            seconds_left = int((900 - time_passed) % 60)
            text = f"⏳ *Следующий сбор через:* {minutes_left} мин {seconds_left} сек"
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== МАГАЗИН =====
    elif action == "upgrades":
        text = ("🏪 *МАГАЗИН УЛУЧШЕНИЙ*\n\n"
                "1️⃣ *Менеджер* - +20% к доходу\n"
                "   💰 `2,000` монет\n\n"
                "2️⃣ *Реклама* - +15% к доходу\n"
                "   💰 `1,500` монет\n\n"
                "3️⃣ *Охрана* - +10% к доходу\n"
                "   💰 `3,000` монет\n\n"
                "4️⃣ *Маркетинг* - +25% к доходу\n"
                "   💰 `5,000` монет\n\n"
                "5️⃣ *Апгрейд бизнеса* - следующий уровень")
        
        keyboard = []
        if not user[5]:
            keyboard.append([InlineKeyboardButton("👔 Менеджер (2000💰)", callback_data="buy_manager")])
        if not user[6]:
            keyboard.append([InlineKeyboardButton("📢 Реклама (1500💰)", callback_data="buy_advertising")])
        if not user[7]:
            keyboard.append([InlineKeyboardButton("🛡️ Охрана (3000💰)", callback_data="buy_security")])
        if not user[8]:
            keyboard.append([InlineKeyboardButton("📊 Маркетинг (5000💰)", callback_data="buy_marketing")])
        if user[2] < 8:
            cost = BUSINESSES[user[2]]["upgrade_cost"]
            keyboard.append([InlineKeyboardButton(f"⬆️ Апгрейд ({cost:,}💰)", callback_data="upgrade_business")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        
        await query.edit_message_text(text, parse_mode='Markdown', 
                                    reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Покупки улучшений
    elif action == "buy_manager":
        if user[1] >= 2000:
            buy_upgrade(user_id, "manager", 2000)
            await query.answer("✅ Менеджер нанят! +20% к доходу", show_alert=True)
            await query.edit_message_text("✅ Улучшение куплено!", reply_markup=get_main_keyboard())
        else:
            await query.answer(f"❌ Нужно {2000 - user[1]:,} монет", show_alert=True)
    
    elif action == "buy_advertising":
        if user[1] >= 1500:
            buy_upgrade(user_id, "advertising", 1500)
            await query.answer("✅ Реклама запущена! +15% к доходу", show_alert=True)
            await query.edit_message_text("✅ Улучшение куплено!", reply_markup=get_main_keyboard())
        else:
            await query.answer(f"❌ Нужно {1500 - user[1]:,} монет", show_alert=True)
    
    elif action == "buy_security":
        if user[1] >= 3000:
            buy_upgrade(user_id, "security", 3000)
            await query.answer("✅ Охрана нанята! +10% к доходу", show_alert=True)
            await query.edit_message_text("✅ Улучшение куплено!", reply_markup=get_main_keyboard())
        else:
            await query.answer(f"❌ Нужно {3000 - user[1]:,} монет", show_alert=True)
    
    elif action == "buy_marketing":
        if user[1] >= 5000:
            buy_upgrade(user_id, "marketing", 5000)
            await query.answer("✅ Маркетинг запущен! +25% к доходу", show_alert=True)
            await query.edit_message_text("✅ Улучшение куплено!", reply_markup=get_main_keyboard())
        else:
            await query.answer(f"❌ Нужно {5000 - user[1]:,} монет", show_alert=True)
    
    # Апгрейд бизнеса
    elif action == "upgrade_business":
        level = user[2]
        if level < 8:
            cost = BUSINESSES[level]["upgrade_cost"]
            if user[1] >= cost:
                update_balance(user_id, -cost)
                upgrade_business(user_id)
                new_level = level + 1
                text = (f"🎉 *АПГРЕЙД!* {BUSINESSES[level]['emoji']} → {BUSINESSES[new_level]['emoji']}\n"
                       f"🏪 {BUSINESSES[new_level]['name']}\n"
                       f"💵 Доход: `{BUSINESSES[new_level]['income']:,}` монет")
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
            else:
                await query.answer(f"❌ Нужно {cost - user[1]:,} монет", show_alert=True)
        else:
            await query.answer("🎉 У вас максимальный уровень!", show_alert=True)
    
    # ===== ЕЖЕДНЕВНЫЙ БОНУС =====
    elif action == "daily":
        result = claim_daily(user_id)
        if result[0] is None:
            text = "⚠️ *Вы уже получили бонус сегодня!*\nЗагляните завтра!"
        else:
            streak, reward = result
            text = (f"🎁 *ЕЖЕДНЕВНЫЙ БОНУС!*\n\n"
                   f"🔥 *Серия:* {streak} дней\n"
                   f"💰 *Награда:* `+{reward:,}` монет\n"
                   f"✨ *Завтра будет ещё больше!*")
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== ИНВЕНТАРЬ =====
    elif action == "inventory":
        items = get_inventory(user_id)
        if not items:
            text = "🎒 *Инвентарь пуст*\n\n💡 *Совет:* Собирайте доход для получения предметов!"
        else:
            text = "🎒 *ИНВЕНТАРЬ*\n\n"
            for item, quantity in items.items():
                text += f"• {item}: {quantity} шт\n"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== КАЗИНО =====
    elif action == "casino":
        await query.edit_message_text("🎰 *ВЫБЕРИ ИГРУ*\n\n"
                                     "🎡 Слоты: шанс 30%, множитель x2.5\n"
                                     "🎲 Кости: шанс 50%, множитель x1.8\n"
                                     "🏆 Рулетка: шанс 40%, множитель x2.2",
                                     parse_mode='Markdown', reply_markup=get_casino_keyboard())
    
    elif action.startswith("casino_"):
        game_name = action.replace("casino_", "")
        context.user_data['casino_game'] = game_name
        game = CASINO_GAMES[game_name]
        text = (f"🎰 *{game_name}*\n\n"
               f"💰 Минимальная ставка: `{game['min_bet']:,}`\n"
               f"💎 Максимальная ставка: `{game['max_bet']:,}`\n"
               f"🎲 Шанс победы: {game['win_chance']*100}%\n"
               f"✨ Множитель: x{game['multiplier']}\n\n"
               f"📝 *Введите сумму ставки в чат*\n"
               f"(например: 1000)")
        
        await query.edit_message_text(text, parse_mode='Markdown')
        context.user_data['waiting_bet'] = True
    
    # ===== РАБОТА =====
    elif action == "work":
        await query.edit_message_text("💼 *ВЫБЕРИ РАБОТУ*\n\n"
                                     "📦 Курьер: 300💰 (30 мин, кд 60 мин)\n"
                                     "💻 Программист: 800💰 (60 мин, кд 120 мин)\n"
                                     "👨‍💼 Менеджер: 1500💰 (120 мин, кд 240 мин)\n"
                                     "🏦 Банкир: 3000💰 (180 мин, кд 360 мин)",
                                     parse_mode='Markdown', reply_markup=get_work_keyboard())
    
    elif action.startswith("work_"):
        job_id = int(action.split("_")[1])
        result, remaining = do_work(user_id, job_id)
        
        if result is None:
            text = f"⏳ *Отдыхай!* Следующая работа через {remaining} минут"
        else:
            text = f"✅ *Работа выполнена!*\n💵 `+{result:,}` монет"
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== ПОДАРКИ =====
    elif action == "gift":
        text = ("🎁 *ОТПРАВИТЬ ПОДАРОК*\n\n"
               "Введи в чат:\n"
               "`/gift @username сумма`\n\n"
               "💰 *Минимальная сумма:* 1000 монет\n"
               "🏆 *Достижение:* Меценат (за первый подарок)")
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== ДОСТИЖЕНИЯ =====
    elif action == "achievements":
        text = "🏆 *ВАШИ ДОСТИЖЕНИЯ*\n\n"
        conn = sqlite3.connect('business.db')
        c = conn.cursor()
        
        completed_count = 0
        for ach_id, ach_data in ACHIEVEMENTS.items():
            c.execute("SELECT completed FROM user_achievements WHERE user_id = ? AND achievement_id = ?", (user_id, ach_id))
            completed = c.fetchone()
            status = "✅" if (completed and completed[0]) else "❌"
            if completed and completed[0]:
                completed_count += 1
            text += f"{status} *{ach_data['name']}*\n   {ach_data['desc']}\n   🏆 `{ach_data['reward']:,}`\n\n"
        
        text += f"\n📊 *Прогресс:* {completed_count}/{len(ACHIEVEMENTS)}"
        conn.close()
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== СТАТИСТИКА =====
    elif action == "stats":
        level = user[2]
        income = calculate_income(user)
        upgrades_count = sum([user[5], user[6], user[7], user[8]])
        
        text = (f"📊 *ПОДРОБНАЯ СТАТИСТИКА*\n\n"
               f"💰 Баланс: `{user[1]:,}`\n"
               f"💹 Всего заработано: `{user[4]:,}`\n"
               f"🏪 Бизнес: {BUSINESSES[level]['emoji']} {BUSINESSES[level]['name']}\n"
               f"📈 Уровень: {level}/8\n"
               f"💵 Доход за сбор: `{income:,}`\n"
               f"🔧 Улучшений: {upgrades_count}/4\n"
               f"📊 Собрано раз: {user[9]}\n"
               f"🔥 Ежедневная серия: {user[11]} дней\n"
               f"🎰 Побед в казино: {user[13]}\n"
               f"🎁 Подарков отправлено: {user[14]}")
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    elif action == "back":
        await query.edit_message_text("🏪 *ГЛАВНОЕ МЕНЮ*", parse_mode='Markdown', 
                                    reply_markup=get_main_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting_bet'):
        try:
            bet = int(update.message.text)
            game_name = context.user_data.get('casino_game')
            
            if game_name:
                result, status = casino_game(update.effective_user.id, game_name, bet)
                
                if status == "no_money":
                    text = "❌ *Недостаточно монет!*"
                elif status == "invalid_bet":
                    game = CASINO_GAMES[game_name]
                    text = f"❌ *Ставка должна быть от {game['min_bet']} до {game['max_bet']}*"
                elif status == "win":
                    text = f"🎉 *ПОБЕДА!* Вы выиграли `{result:,}` монет! 🎉"
                else:
                    text = f"😢 *ПРОИГРЫШ!* Вы проиграли `{bet:,}` монет..."
                
                await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
                context.user_data['waiting_bet'] = False
                
        except ValueError:
            await update.message.reply_text("❌ *Введи число!*", parse_mode='Markdown')

async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text("❌ *Использование:* `/gift @username сумма`", parse_mode='Markdown')
        return
    
    username = args[0].replace('@', '')
    try:
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ *Сумма должна быть числом!*", parse_mode='Markdown')
        return
    
    if amount < 1000:
        await update.message.reply_text("❌ *Минимальная сумма подарка:* 1000 монет", parse_mode='Markdown')
        return
    
    # Поиск пользователя по username
    try:
        chat = await context.bot.get_chat(f"@{username}")
        to_user_id = chat.id
    except:
        await update.message.reply_text("❌ *Пользователь не найден!*", parse_mode='Markdown')
        return
    
    result = send_gift(user_id, to_user_id, amount)
    
    if result == "not_found":
        text = "❌ *Пользователь не найден в игре!*"
    elif result == "no_money":
        text = f"❌ *Недостаточно монет!* Нужно {amount:,}"
    else:
        text = f"🎁 *Подарок отправлен!* {amount:,} монет получил @{username}"
        try:
            await context.bot.send_message(to_user_id, f"🎉 *Вам отправили подарок!*\n💰 +{amount:,} монет", parse_mode='Markdown')
        except:
            pass
    
    await update.message.reply_text(text, parse_mode='Markdown')

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gift", gift_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("🤖 CRYPTO EMPIRE БОТ ЗАПУЩЕН!")
    app.run_polling()

if __name__ == "__main__":
    main()
