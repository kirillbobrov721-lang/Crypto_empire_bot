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

# Токен из переменных окружения
TOKEN = os.environ.get('BOT_TOKEN')

# ========== БИЗНЕСЫ (10 УРОВНЕЙ!) ==========
BUSINESSES = {
    1: {"name": "🏪 Ларёк", "income": 50, "upgrade_cost": 500, "emoji": "🏪", "defense": 5},
    2: {"name": "🏬 Магазин", "income": 150, "upgrade_cost": 2000, "emoji": "🏬", "defense": 10},
    3: {"name": "🏢 Супермаркет", "income": 400, "upgrade_cost": 8000, "emoji": "🏢", "defense": 15},
    4: {"name": "🏙️ Торговый центр", "income": 1000, "upgrade_cost": 30000, "emoji": "🏙️", "defense": 20},
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

# ========== ДОСТИЖЕНИЯ ==========
ACHIEVEMENTS = {
    1: {"name": "💰 Новичок", "desc": "Заработать 10,000", "reward": 5000, "required": 10000},
    2: {"name": "💎 Миллионер", "desc": "Заработать 1,000,000", "reward": 100000, "required": 1000000},
    3: {"name": "⚡ Трудоголик", "desc": "Собрать доход 100 раз", "reward": 50000, "required": 100},
    4: {"name": "👑 Император", "desc": "10 уровень бизнеса", "reward": 1000000, "required": 10},
    5: {"name": "🔫 Мафиози", "desc": "Ограбить 50 игроков", "reward": 200000, "required": 50},
    6: {"name": "🛡️ Неуязвимый", "desc": "Отбить 30 атак", "reward": 150000, "required": 30},
    7: {"name": "💀 Киллер", "desc": "Уничтожить бизнес", "reward": 500000, "required": 10}
}

# Инициализация БД
def init_db():
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    
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
                  protection_until TIMESTAMP)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (user_id INTEGER, item_type TEXT, quantity INTEGER DEFAULT 0,
                  PRIMARY KEY (user_id, item_type))''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_achievements
                 (user_id INTEGER, achievement_id INTEGER, completed BOOLEAN DEFAULT FALSE,
                  PRIMARY KEY (user_id, achievement_id))''')
    
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
    c.execute("INSERT OR IGNORE INTO users (user_id, last_collect, last_daily, last_work, last_attack, protection_until) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, now, now, now, now, now))
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

def calculate_defense(user):
    level = user[2]
    base_defense = BUSINESSES[level]["defense"]
    
    if user[5]: base_defense += 5   # Менеджер
    if user[7]: base_defense += 20  # Охрана
    if user[9]: base_defense += 40  # Бронированный
    
    # Проверка защиты (временная)
    if user[20] and datetime.fromisoformat(user[20]) > datetime.now():
        base_defense *= 2
    
    return base_defense

def calculate_attack(user):
    attack = 10 + (user[2] * 3)  # Базовая атака от уровня
    if user[10]: attack += 30     # Хакер
    return attack

def calculate_income(user):
    level = user[2]
    base_income = BUSINESSES[level]["income"]
    multiplier = 1.0
    
    if user[5]: multiplier += 0.20   # Менеджер
    if user[6]: multiplier += 0.15   # Реклама
    if user[8]: multiplier += 0.25   # Маркетинг
    
    return int(base_income * multiplier)

def attack_business(attacker_id, target_id):
    attacker = get_user(attacker_id)
    target = get_user(target_id)
    
    if not target:
        return "not_found"
    
    # Проверка кулдауна (15 минут)
    last_attack = datetime.fromisoformat(attacker[19]) if attacker[19] else datetime.now() - timedelta(minutes=15)
    if (datetime.now() - last_attack).total_seconds() < 900:
        remaining = int(900 - (datetime.now() - last_attack).total_seconds())
        return f"cooldown|{remaining}"
    
    # Расчет шанса
    attack_power = calculate_attack(attacker)
    defense_power = calculate_defense(target)
    
    win_chance = attack_power / (attack_power + defense_power) * 100
    win = random.random() * 100 < win_chance
    
    if win:
        # Кража 10-30% от баланса жертвы
        stolen = int(target[1] * random.uniform(0.1, 0.3))
        stolen = min(stolen, 100000)  # Максимум 100к за раз
        
        update_balance(attacker_id, stolen)
        update_balance(target_id, -stolen)
        
        # Обновляем статистику
        conn = sqlite3.connect('business.db')
        c = conn.cursor()
        c.execute("UPDATE users SET attacks_won = attacks_won + 1, last_attack = ? WHERE user_id = ?", 
                  (datetime.now(), attacker_id))
        
        # Шанс уничтожить уровень бизнеса (5%)
        if random.random() < 0.05 and target[2] > 1:
            c.execute("UPDATE users SET business_level = business_level - 1 WHERE user_id = ?", (target_id,))
            c.execute("UPDATE users SET businesses_destroyed = businesses_destroyed + 1 WHERE user_id = ?", (attacker_id,))
            destroyed = True
        else:
            destroyed = False
        
        conn.commit()
        conn.close()
        
        check_achievements(attacker_id)
        return f"win|{stolen}|{destroyed}"
    else:
        # Штраф за провал (теряем 5-15% своих денег)
        penalty = int(attacker[1] * random.uniform(0.05, 0.15))
        update_balance(attacker_id, -penalty)
        
        conn = sqlite3.connect('business.db')
        c = conn.cursor()
        c.execute("UPDATE users SET defenses_won = defenses_won + 1, last_attack = ? WHERE user_id = ?", 
                  (datetime.now(), attacker_id))
        conn.commit()
        conn.close()
        
        check_achievements(target_id)
        return f"lose|{penalty}"

def buy_protection(user_id, hours=24):
    cost = hours * 1000
    user = get_user(user_id)
    
    if user[1] < cost:
        return False
    
    protection_until = datetime.now() + timedelta(hours=hours)
    
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance - ?, protection_until = ? WHERE user_id = ?",
              (cost, protection_until, user_id))
    conn.commit()
    conn.close()
    
    return protection_until

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
            elif ach_id == 3 and user[6] >= 100:
                achieved = True
            elif ach_id == 4 and user[2] >= 10:
                achieved = True
            elif ach_id == 5 and user[16] >= 50:
                achieved = True
            elif ach_id == 6 and user[17] >= 30:
                achieved = True
            elif ach_id == 7 and user[18] >= 10:
                achieved = True
            
            if achieved:
                c.execute("INSERT OR REPLACE INTO user_achievements (user_id, achievement_id, completed) VALUES (?, ?, TRUE)", 
                         (user_id, ach_id))
                update_balance(user_id, ach_data['reward'])
    
    conn.commit()
    conn.close()

def get_daily_reward(streak):
    return 1000 + (streak * 500)

def claim_daily(user_id):
    user = get_user(user_id)
    last_daily = datetime.fromisoformat(user[12]) if user[12] else datetime.now() - timedelta(days=1)
    today = datetime.now().date()
    last_date = last_daily.date()
    
    if last_date == today:
        return None, 0
    
    if (today - last_date).days == 1:
        streak = user[13] + 1
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

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance"),
         InlineKeyboardButton("🏪 Бизнес", callback_data="business")],
        [InlineKeyboardButton("💼 Собрать", callback_data="collect"),
         InlineKeyboardButton("📈 Магазин", callback_data="upgrades")],
        [InlineKeyboardButton("⚔️ АТАКА", callback_data="attack_menu"),
         InlineKeyboardButton("🛡️ Защита", callback_data="protection")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="daily"),
         InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton("🏆 Достижения", callback_data="achievements"),
         InlineKeyboardButton("📊 Статистика", callback_data="stats")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== ОБРАБОТЧИКИ ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    
    text = ("🔥 *CRYPTO EMPIRE: БИТВЫ БИЗНЕСОВ* 🔥\n\n"
            "💎 *МЕГА-СИСТЕМЫ:*\n"
            "💰 Пассивный доход каждые 15 минут\n"
            "📈 10 уровней бизнеса (до Абсолюта!)\n"
            "⚔️ **АТАКУЙ** других игроков и воруй деньги!\n"
            "🛡️ **ЗАЩИЩАЙСЯ** с помощью брони и охраны\n"
            "💀 **УНИЧТОЖАЙ** бизнесы конкурентов\n"
            "🎰 Казино с 3 играми\n"
            "💼 Работа с 4 профессиями\n"
            "🎁 Подарки друзьям\n"
            "🏆 7 достижений\n\n"
            "👇 *НАЧНИ СВОЙ КРИМИНАЛЬНЫЙ БИЗНЕС!*")
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())

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
        text = (f"💰 *БАЛАНС:* `{user[1]:,}` монет\n\n"
                f"📈 Всего заработано: `{user[4]:,}`\n"
                f"⚔️ Атак выиграно: {user[16]}\n"
                f"🛡️ Атак отбито: {user[17]}\n"
                f"💀 Бизнесов уничтожено: {user[18]}")
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== БИЗНЕС =====
    elif action == "business":
        level = user[2]
        business = BUSINESSES[level]
        income = calculate_income(user)
        defense = calculate_defense(user)
        attack = calculate_attack(user)
        
        text = (f"{business['emoji']} *{business['name']}* (Уровень {level}/10)\n\n"
                f"💵 Доход: `{income:,}` монет\n"
                f"⚔️ Сила атаки: {attack}\n"
                f"🛡️ Защита: {defense}\n\n"
                f"📈 *Множители:*\n"
                f"  👔 Менеджер: +20% {'✅' if user[5] else '❌'}\n"
                f"  📢 Реклама: +15% {'✅' if user[6] else '❌'}\n"
                f"  🛡️ Охрана: +20 защиты {'✅' if user[7] else '❌'}\n"
                f"  📊 Маркетинг: +25% {'✅' if user[8] else '❌'}\n"
                f"  🚛 Бронированный: +40 защиты {'✅' if user[9] else '❌'}\n"
                f"  💻 Хакер: +30 атаки {'✅' if user[10] else '❌'}")
        
        if level < 10:
            text += f"\n\n⬆️ *Апгрейд:* `{business['upgrade_cost']:,}` монет"
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== СБОР =====
    elif action == "collect":
        last_collect = datetime.fromisoformat(user[3]) if user[3] else datetime.now()
        time_passed = (datetime.now() - last_collect).total_seconds()
        
        if time_passed >= 900:
            income = calculate_income(user)
            update_balance(user_id, income)
            
            conn = sqlite3.connect('business.db')
            c = conn.cursor()
            c.execute("UPDATE users SET last_collect = ?, total_collects = total_collects + 1 WHERE user_id = ?", 
                      (datetime.now(), user_id))
            conn.commit()
            conn.close()
            
            text = (f"✅ *ДОХОД СОБРАН!*\n💵 `+{income:,}` монет\n💰 Баланс: `{user[1] + income:,}`")
        else:
            minutes_left = int((900 - time_passed) // 60)
            text = f"⏳ *Следующий сбор через:* {minutes_left} мин"
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== МАГАЗИН УЛУЧШЕНИЙ =====
    elif action == "upgrades":
        text = ("🏪 *МАГАЗИН УЛУЧШЕНИЙ*\n\n"
                "1️⃣ Менеджер - +20% дохода, +5 защиты (2000💰)\n"
                "2️⃣ Реклама - +15% дохода (1500💰)\n"
                "3️⃣ Охрана - +20 защиты (3000💰)\n"
                "4️⃣ Маркетинг - +25% дохода (5000💰)\n"
                "5️⃣ Бронированный - +40 защиты (10000💰)\n"
                "6️⃣ Хакер - +30 атаки (15000💰)")
        
        keyboard = []
        if not user[5]:
            keyboard.append([InlineKeyboardButton("👔 Менеджер (2000💰)", callback_data="buy_manager")])
        if not user[6]:
            keyboard.append([InlineKeyboardButton("📢 Реклама (1500💰)", callback_data="buy_advertising")])
        if not user[7]:
            keyboard.append([InlineKeyboardButton("🛡️ Охрана (3000💰)", callback_data="buy_security")])
        if not user[8]:
            keyboard.append([InlineKeyboardButton("📊 Маркетинг (5000💰)", callback_data="buy_marketing")])
        if not user[9]:
            keyboard.append([InlineKeyboardButton("🚛 Бронированный (10000💰)", callback_data="buy_armored")])
        if not user[10]:
            keyboard.append([InlineKeyboardButton("💻 Хакер (15000💰)", callback_data="buy_hacker")])
        if user[2] < 10:
            cost = BUSINESSES[user[2]]["upgrade_cost"]
            keyboard.append([InlineKeyboardButton(f"⬆️ Апгрейд бизнеса ({cost:,}💰)", callback_data="upgrade_business")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Покупки улучшений
    elif action in ["buy_manager", "buy_advertising", "buy_security", "buy_marketing", "buy_armored", "buy_hacker"]:
        upgrade_key = action.replace("buy_", "")
        upgrade = UPGRADES[upgrade_key]
        
        if user[1] >= upgrade["cost"]:
            update_balance(user_id, -upgrade["cost"])
            conn = sqlite3.connect('business.db')
            c = conn.cursor()
            c.execute(f"UPDATE users SET {upgrade_key} = TRUE WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            await query.answer(f"✅ {upgrade['name']} куплено!", show_alert=True)
            await query.edit_message_text("✅ Улучшение приобретено!", reply_markup=get_main_keyboard())
        else:
            await query.answer(f"❌ Нужно {upgrade['cost'] - user[1]:,} монет", show_alert=True)
    
    # Апгрейд бизнеса
    elif action == "upgrade_business":
        level = user[2]
        if level < 10:
            cost = BUSINESSES[level]["upgrade_cost"]
            if user[1] >= cost:
                update_balance(user_id, -cost)
                conn = sqlite3.connect('business.db')
                c = conn.cursor()
                c.execute("UPDATE users SET business_level = business_level + 1 WHERE user_id = ?", (user_id,))
                conn.commit()
                conn.close()
                
                text = (f"🎉 *АПГРЕЙД!* {BUSINESSES[level]['emoji']} → {BUSINESSES[level+1]['emoji']}\n"
                       f"🏪 {BUSINESSES[level+1]['name']}\n"
                       f"💵 Доход: `{BUSINESSES[level+1]['income']:,}` монет")
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
            else:
                await query.answer(f"❌ Нужно {cost - user[1]:,} монет", show_alert=True)
        else:
            await query.answer("🎉 У вас максимальный уровень!", show_alert=True)
    
    # ===== АТАКА =====
    elif action == "attack_menu":
        text = ("⚔️ *АТАКА НА БИЗНЕС*\n\n"
                "Введи в чат:\n"
                "`/attack @username`\n\n"
                "📊 *Правила:*\n"
                "• Кулдаун 15 минут\n"
                "• Шанс победы зависит от атаки/защиты\n"
                "• При победе крадешь 10-30% денег\n"
                "• 5% шанс уничтожить уровень бизнеса\n"
                "• При провале теряешь 5-15% своих денег")
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== ЗАЩИТА =====
    elif action == "protection":
        protection_time = datetime.fromisoformat(user[20]) if user[20] else datetime.now()
        if protection_time > datetime.now():
            hours_left = (protection_time - datetime.now()).total_seconds() / 3600
            text = (f"🛡️ *ЗАЩИТА АКТИВНА*\n\n"
                   f"⏰ Осталось: {hours_left:.1f} часов\n"
                   f"✨ Вы защищены от атак!")
        else:
            text = ("🛡️ *КУПИТЬ ЗАЩИТУ*\n\n"
                   "💰 1000 монет за час\n"
                   "🛡️ Защита удваивает оборону\n\n"
                   "Введи в чат:\n"
                   "`/protect 24` (часы)")
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== ЕЖЕДНЕВНЫЙ БОНУС =====
    elif action == "daily":
        result = claim_daily(user_id)
        if result[0] is None:
            text = "⚠️ *Бонус уже получен!* Загляни завтра!"
        else:
            streak, reward = result
            text = (f"🎁 *ЕЖЕДНЕВНЫЙ БОНУС!*\n\n"
                   f"🔥 Серия: {streak} дней\n"
                   f"💰 +{reward:,} монет")
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== ИНВЕНТАРЬ =====
    elif action == "inventory":
        text = "🎒 *ИНВЕНТАРЬ*\n\n💡 Скоро здесь будут бонусные предметы!"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== ДОСТИЖЕНИЯ =====
    elif action == "achievements":
        text = "🏆 *ДОСТИЖЕНИЯ*\n\n"
        conn = sqlite3.connect('business.db')
        c = conn.cursor()
        
        completed_count = 0
        for ach_id, ach_data in ACHIEVEMENTS.items():
            c.execute("SELECT completed FROM user_achievements WHERE user_id = ? AND achievement_id = ?", (user_id, ach_id))
            completed = c.fetchone()
            status = "✅" if (completed and completed[0]) else "❌"
            if completed and completed[0]:
                completed_count += 1
            text += f"{status} *{ach_data['name']}* - {ach_data['desc']}\n   🏆 {ach_data['reward']:,}\n\n"
        
        text += f"\n📊 Прогресс: {completed_count}/{len(ACHIEVEMENTS)}"
        conn.close()
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # ===== СТАТИСТИКА =====
    elif action == "stats":
        text = (f"📊 *ПОЛНАЯ СТАТИСТИКА*\n\n"
               f"💰 Баланс: `{user[1]:,}`\n"
               f"🏪 Бизнес: {BUSINESSES[user[2]]['name']} (ур. {user[2]}/10)\n"
               f"💵 Доход за сбор: `{calculate_income(user):,}`\n"
               f"⚔️ Сила атаки: {calculate_attack(user)}\n"
               f"🛡️ Защита: {calculate_defense(user)}\n"
               f"📊 Собрано раз: {user[6]}\n"
               f"⚔️ Атак выиграно: {user[16]}\n"
               f"🛡️ Атак отбито: {user[17]}\n"
               f"💀 Бизнесов уничтожено: {user[18]}\n"
               f"🔥 Ежедневная серия: {user[13]} дней")
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    elif action == "back":
        await query.edit_message_text("🏪 *ГЛАВНОЕ МЕНЮ*", parse_mode='Markdown', reply_markup=get_main_keyboard())

async def attack_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 1:
        await update.message.reply_text("❌ *Использование:* `/attack @username`", parse_mode='Markdown')
        return
    
    username = args[0].replace('@', '')
    
    # Поиск цели
    try:
        chat = await context.bot.get_chat(f"@{username}")
        target_id = chat.id
    except:
        await update.message.reply_text("❌ *Пользователь не найден!*", parse_mode='Markdown')
        return
    
    if target_id == user_id:
        await update.message.reply_text("❌ *Нельзя атаковать себя!*", parse_mode='Markdown')
        return
    
    result = attack_business(user_id, target_id)
    
    if result == "not_found":
        text = "❌ *Игрок не зарегистрирован в игре!*"
    elif result.startswith("cooldown"):
        remaining = int(result.split("|")[1])
        text = f"⏳ *Кулдаун!* Следующая атака через {remaining//60} мин"
    elif result.startswith("win"):
        _, stolen, destroyed = result.split("|")
        text = f"✅ *ПОБЕДА!* Вы украли `{stolen:,}` монет!"
        if destroyed == "True":
            text += "\n💀 *БИЗНЕС УНИЧТОЖЕН!* Уровень цели понижен!"
    else:
        _, penalty = result.split("|")
        text = f"😢 *ПРОВАЛ!* Вы потеряли `{penalty:,}` монет"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def protect_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 1:
        await update.message.reply_text("❌ *Использование:* `/protect 24` (часы)", parse_mode='Markdown')
        return
    
    try:
        hours = int(args[0])
        if hours < 1 or hours > 168:
            await update.message.reply_text("❌ *Часы должны быть от 1 до 168*", parse_mode='Markdown')
            return
    except ValueError:
        await update.message.reply_text("❌ *Введи число!*", parse_mode='Markdown')
        return
    
    result = buy_protection(user_id, hours)
    
    if result:
        text = f"🛡️ *ЗАЩИТА АКТИВИРОВАНА!*\n\n⏰ Действует {hours} часов\n✨ Ваша оборона удвоена!"
    else:
        text = f"❌ *Недостаточно монет!* Нужно {hours * 1000:,}"
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def gift_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text("❌ *Использование:* `/gift @username сумма`", parse_mode='Markdown')
        return
    
    username = args[0].replace('@', '')
    try:
        amount = int(args[1])
        if amount < 1000:
            await update.message.reply_text("❌ *Минимум 1000 монет*", parse_mode='Markdown')
            return
    except ValueError:
        await update.message.reply_text("❌ *Сумма должна быть числом!*", parse_mode='Markdown')
        return
    
    try:
        chat = await context.bot.get_chat(f"@{username}")
        to_user_id = chat.id
    except:
        await update.message.reply_text("❌ *Пользователь не найден!*", parse_mode='Markdown')
        return
    
    user = get_user(user_id)
    if user[1] < amount:
        await update.message.reply_text(f"❌ *Недостаточно!* Нужно {amount:,}", parse_mode='Markdown')
        return
    
    update_balance(user_id, -amount)
    update_balance(to_user_id, amount)
    
    await update.message.reply_text(f"🎁 *Подарок отправлен!* {amount:,} монет для @{username}", parse_mode='Markdown')
    
    try:
        await context.bot.send_message(to_user_id, f"🎉 *Вам отправили подарок!*\n💰 +{amount:,} монет", parse_mode='Markdown')
    except:
        pass

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("attack", attack_command))
    app.add_handler(CommandHandler("protect", protect_command))
    app.add_handler(CommandHandler("gift", gift_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("🤖 CRYPTO EMPIRE БОТ ЗАПУЩЕН!")
    app.run_polling()

if __name__ == "__main__":
    main()
