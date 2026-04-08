import os
import logging
import sqlite3
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен из переменных окружения Render
TOKEN = os.environ.get('BOT_TOKEN')

# Данные бизнесов (6 уровней)
BUSINESSES = {
    1: {"name": "🏪 Ларёк", "income": 50, "upgrade_cost": 500, "emoji": "🏪"},
    2: {"name": "🏬 Магазин", "income": 150, "upgrade_cost": 2000, "emoji": "🏬"},
    3: {"name": "🏢 Супермаркет", "income": 400, "upgrade_cost": 8000, "emoji": "🏢"},
    4: {"name": "🏙️ ТЦ", "income": 1000, "upgrade_cost": 30000, "emoji": "🏙️"},
    5: {"name": "🌆 Корпорация", "income": 2500, "upgrade_cost": 100000, "emoji": "🌆"},
    6: {"name": "🌍 Империя", "income": 6000, "upgrade_cost": None, "emoji": "🌍"}
}

# Достижения
ACHIEVEMENTS = {
    1: {"name": "💰 Первый миллион", "description": "Заработать 1,000,000 монет", "reward": 50000, "required": 1000000},
    2: {"name": "🚀 Магнат", "description": "Купить 5 улучшений", "reward": 25000, "required": 5},
    3: {"name": "⚡ Трудоголик", "description": "Собрать доход 100 раз", "reward": 30000, "required": 100},
    4: {"name": "👑 Император", "description": "Достичь 6 уровня бизнеса", "reward": 100000, "required": 6}
}

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    
    # Таблица пользователей
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
                  last_daily TIMESTAMP,
                  streak INTEGER DEFAULT 0)''')
    
    # Таблица инвентаря
    c.execute('''CREATE TABLE IF NOT EXISTS inventory
                 (user_id INTEGER,
                  item_type TEXT,
                  quantity INTEGER DEFAULT 0,
                  PRIMARY KEY (user_id, item_type))''')
    
    # Таблица достижений
    c.execute('''CREATE TABLE IF NOT EXISTS user_achievements
                 (user_id INTEGER,
                  achievement_id INTEGER,
                  completed BOOLEAN DEFAULT FALSE,
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
    c.execute("INSERT OR IGNORE INTO users (user_id, last_collect, last_daily) VALUES (?, ?, ?)",
              (user_id, datetime.now(), datetime.now()))
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

def get_upgrade_status(user_id):
    user = get_user(user_id)
    return {
        'manager': user[5] if user else False,
        'advertising': user[6] if user else False,
        'security': user[7] if user else False
    }

def calculate_income(user):
    level = user[2]
    base_income = BUSINESSES[level]["income"]
    multiplier = 1.0
    
    if user[5]:  # Менеджер
        multiplier += 0.2
    if user[6]:  # Реклама
        multiplier += 0.15
    if user[7]:  # Охрана
        multiplier += 0.1
    
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
        # Проверяем, не получено ли уже
        c.execute("SELECT completed FROM user_achievements WHERE user_id = ? AND achievement_id = ?", (user_id, ach_id))
        completed = c.fetchone()
        
        if not completed or not completed[0]:
            achieved = False
            
            if ach_id == 1 and user[4] >= 1000000:  # Миллион
                achieved = True
            elif ach_id == 2:  # Улучшения
                upgrades = sum([1 for x in [user[5], user[6], user[7]] if x])
                if upgrades >= 5:
                    achieved = True
            elif ach_id == 3 and user[8] >= 100:  # 100 сборов
                achieved = True
            elif ach_id == 4 and user[2] >= 6:  # Макс уровень
                achieved = True
            
            if achieved:
                c.execute("INSERT OR REPLACE INTO user_achievements (user_id, achievement_id, completed) VALUES (?, ?, TRUE)", 
                         (user_id, ach_id))
                update_balance(user_id, ach_data['reward'])
                
    conn.commit()
    conn.close()

def get_daily_reward(streak):
    base_reward = 1000
    streak_bonus = streak * 200
    return base_reward + streak_bonus

def claim_daily(user_id):
    user = get_user(user_id)
    last_daily = datetime.fromisoformat(user[9]) if user[9] else datetime.now() - timedelta(days=1)
    today = datetime.now().date()
    last_date = last_daily.date()
    
    if last_date == today:
        return None, 0
    
    # Проверяем непрерывность
    if (today - last_date).days == 1:
        streak = user[10] + 1
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

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance"),
         InlineKeyboardButton("🏪 Бизнес", callback_data="business")],
        [InlineKeyboardButton("💼 Собрать доход", callback_data="collect"),
         InlineKeyboardButton("📈 Магазин", callback_data="upgrades")],
        [InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="daily"),
         InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory")],
        [InlineKeyboardButton("🏆 Достижения", callback_data="achievements"),
         InlineKeyboardButton("📊 Статистика", callback_data="stats")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    
    text = ("🏆 *ДОБРО ПОЖАЛОВАТЬ В БИЗНЕС ИМПЕРИЮ!* 🏆\n\n"
            "Ты начинаешь с *1000 монет* и маленького ларька.\n"
            "💰 *Зарабатывай* каждые 15 минут\n"
            "📈 *Прокачивай* бизнес до Империи\n"
            "🎁 *Забирай* ежедневные бонусы\n"
            "🏆 *Получай* достижения\n\n"
            "👇 *Используй кнопки для управления!*")
    
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
    
    # Баланс
    if action == "balance":
        text = (f"💰 *Ваш баланс:* `{user[1]:,}` монет\n"
                f"📈 *Всего заработано:* `{user[4]:,}` монет\n"
                f"📊 *Собрано раз:* {user[8]}")
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # Бизнес
    elif action == "business":
        level = user[2]
        business = BUSINESSES[level]
        income = calculate_income(user)
        
        last_collect = datetime.fromisoformat(user[3]) if user[3] else datetime.now()
        time_passed = (datetime.now() - last_collect).total_seconds()
        time_left = max(0, 900 - time_passed)
        minutes_left = int(time_left // 60)
        seconds_left = int(time_left % 60)
        
        text = (f"{business['emoji']} *{business['name']}*\n"
                f"📊 *Уровень:* {level}/6\n"
                f"💵 *Доход за сбор:* `{income:,}` монет\n"
                f"⏰ *До сбора:* {minutes_left} мин {seconds_left} сек\n\n"
                f"📈 *Множители:*\n"
                f"  👔 Менеджер: +20% {'✅' if user[5] else '❌'}\n"
                f"  📢 Реклама: +15% {'✅' if user[6] else '❌'}\n"
                f"  🛡️ Охрана: +10% {'✅' if user[7] else '❌'}")
        
        if level < 6:
            text += f"\n\n⬆️ *До апгрейда:* `{business['upgrade_cost']:,}` монет"
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # Сбор дохода
    elif action == "collect":
        last_collect = datetime.fromisoformat(user[3]) if user[3] else datetime.now()
        time_passed = (datetime.now() - last_collect).total_seconds()
        
        if time_passed >= 900:
            income = calculate_income(user)
            update_balance(user_id, income)
            update_last_collect(user_id)
            
            # Шанс на бонусный предмет (10%)
            if random.random() < 0.1:
                bonus_items = ["💎 Алмаз", "⭐ Звезда", "🎫 Лотерейный билет"]
                item = random.choice(bonus_items)
                add_inventory_item(user_id, item)
                bonus_text = f"\n\n🎁 *Бонус!* Получен {item}!"
            else:
                bonus_text = ""
            
            text = (f"✅ *Вы собрали доход!*\n"
                   f"💵 Получено: `+{income:,}` монет\n"
                   f"💰 Новый баланс: `{user[1] + income:,}` монет{bonus_text}")
        else:
            minutes_left = int((900 - time_passed) // 60)
            seconds_left = int((900 - time_passed) % 60)
            text = f"⏳ *До следующего сбора:* {minutes_left} мин {seconds_left} сек"
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # Магазин улучшений
    elif action == "upgrades":
        text = ("🏪 *МАГАЗИН УЛУЧШЕНИЙ*\n\n"
                "1️⃣ *Менеджер* - +20% к доходу\n"
                "   💰 Цена: `2,000` монет\n\n"
                "2️⃣ *Реклама* - +15% к доходу\n"
                "   💰 Цена: `1,500` монет\n\n"
                "3️⃣ *Охрана* - +10% к доходу\n"
                "   💰 Цена: `3,000` монет\n\n"
                "4️⃣ *Апгрейд бизнеса* - следующий уровень\n"
                "   💰 Цена: зависит от уровня")
        
        keyboard = []
        if not user[5]:
            keyboard.append([InlineKeyboardButton("👔 Нанять менеджера (2000💰)", callback_data="buy_manager")])
        if not user[6]:
            keyboard.append([InlineKeyboardButton("📢 Реклама (1500💰)", callback_data="buy_advertising")])
        if not user[7]:
            keyboard.append([InlineKeyboardButton("🛡️ Охрана (3000💰)", callback_data="buy_security")])
        if user[2] < 6:
            cost = BUSINESSES[user[2]]["upgrade_cost"]
            keyboard.append([InlineKeyboardButton(f"⬆️ Апгрейд бизнеса ({cost:,}💰)", callback_data="upgrade_business")])
        keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
        
        await query.edit_message_text(text, parse_mode='Markdown', 
                                    reply_markup=InlineKeyboardMarkup(keyboard))
    
    # Покупка менеджера
    elif action == "buy_manager":
        if user[1] >= 2000:
            buy_upgrade(user_id, "manager", 2000)
            await query.answer("✅ Менеджер нанят! Доход +20%", show_alert=True)
            await query.edit_message_text("✅ Улучшение приобретено!", reply_markup=get_main_keyboard())
        else:
            await query.answer(f"❌ Не хватает {2000 - user[1]:,} монет", show_alert=True)
    
    # Покупка рекламы
    elif action == "buy_advertising":
        if user[1] >= 1500:
            buy_upgrade(user_id, "advertising", 1500)
            await query.answer("✅ Реклама запущена! Доход +15%", show_alert=True)
            await query.edit_message_text("✅ Улучшение приобретено!", reply_markup=get_main_keyboard())
        else:
            await query.answer(f"❌ Не хватает {1500 - user[1]:,} монет", show_alert=True)
    
    # Покупка охраны
    elif action == "buy_security":
        if user[1] >= 3000:
            buy_upgrade(user_id, "security", 3000)
            await query.answer("✅ Охрана нанята! Доход +10%", show_alert=True)
            await query.edit_message_text("✅ Улучшение приобретено!", reply_markup=get_main_keyboard())
        else:
            await query.answer(f"❌ Не хватает {3000 - user[1]:,} монет", show_alert=True)
    
    # Апгрейд бизнеса
    elif action == "upgrade_business":
        level = user[2]
        if level < 6:
            cost = BUSINESSES[level]["upgrade_cost"]
            if user[1] >= cost:
                update_balance(user_id, -cost)
                upgrade_business(user_id)
                new_level = level + 1
                text = (f"🎉 *ПОЗДРАВЛЯЮ!*\n"
                       f"Бизнес улучшен до {BUSINESSES[new_level]['name']} {BUSINESSES[new_level]['emoji']}\n"
                       f"💵 Новый доход: `{BUSINESSES[new_level]['income']:,}` монет")
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
            else:
                await query.answer(f"❌ Не хватает {cost - user[1]:,} монет", show_alert=True)
        else:
            await query.answer("🎉 У вас максимальный уровень!", show_alert=True)
    
    # Ежедневный бонус
    elif action == "daily":
        result = claim_daily(user_id)
        if result[0] is None:
            text = "⚠️ *Вы уже получили сегодняшний бонус!*\nЗагляните завтра!"
        else:
            streak, reward = result
            text = (f"🎁 *ЕЖЕДНЕВНЫЙ БОНУС!*\n\n"
                   f"🔥 *Серия:* {streak} дней\n"
                   f"💰 *Награда:* `+{reward:,}` монет\n"
                   f"✨ *Завтра вас ждёт ещё больше!*")
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # Инвентарь
    elif action == "inventory":
        items = get_inventory(user_id)
        if not items:
            text = "🎒 *Ваш инвентарь пуст*\n\nЗарабатывайте предметы при сборе дохода!"
        else:
            text = "🎒 *ВАШ ИНВЕНТАРЬ*\n\n"
            for item, quantity in items.items():
                text += f"• {item}: {quantity} шт\n"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # Достижения
    elif action == "achievements":
        text = "🏆 *ВАШИ ДОСТИЖЕНИЯ*\n\n"
        conn = sqlite3.connect('business.db')
        c = conn.cursor()
        
        for ach_id, ach_data in ACHIEVEMENTS.items():
            c.execute("SELECT completed FROM user_achievements WHERE user_id = ? AND achievement_id = ?", (user_id, ach_id))
            completed = c.fetchone()
            status = "✅" if (completed and completed[0]) else "❌"
            text += f"{status} *{ach_data['name']}*\n   {ach_data['description']}\n   🏆 Награда: `{ach_data['reward']:,}`\n\n"
        
        conn.close()
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # Статистика
    elif action == "stats":
        level = user[2]
        income = calculate_income(user)
        upgrades_count = sum([user[5], user[6], user[7]])
        
        text = (f"📊 *ПОДРОБНАЯ СТАТИСТИКА*\n\n"
               f"💰 Баланс: `{user[1]:,}`\n"
               f"💹 Всего заработано: `{user[4]:,}`\n"
               f"🏪 Бизнес: {BUSINESSES[level]['emoji']} {BUSINESSES[level]['name']}\n"
               f"📈 Уровень: {level}/6\n"
               f"💵 Доход за сбор: `{income:,}`\n"
               f"🔧 Улучшений куплено: {upgrades_count}/3\n"
               f"📊 Собрано раз: {user[8]}\n"
               f"🔥 Ежедневная серия: {user[10]} дней")
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    # Назад
    elif action == "back":
        await query.edit_message_text("🏪 *Главное меню*\nВыберите действие:", 
                                    parse_mode='Markdown', 
                                    reply_markup=get_main_keyboard())

async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=context.job.chat_id, 
                                 text="🎁 *Напоминание!* Не забудьте забрать ежедневный бонус в меню!",
                                 parse_mode='Markdown')

def main():
    init_db()
    
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("🤖 Бизнес Империя успешно запущена!")
    app.run_polling()

if __name__ == "__main__":
    main()    conn.commit()
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
    c.execute("INSERT OR IGNORE INTO users (user_id, last_collect) VALUES (?, ?)",
              (user_id, datetime.now()))
    conn.commit()
    conn.close()

def update_balance(user_id, amount):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?",
              (amount, max(amount, 0), user_id))
    conn.commit()
    conn.close()

def upgrade_business(user_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("UPDATE users SET business_level = business_level + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def update_last_collect(user_id):
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute("UPDATE users SET last_collect = ? WHERE user_id = ?", (datetime.now(), user_id))
    conn.commit()
    conn.close()

def calculate_income(user):
    level = user[2]
    base_income = BUSINESSES[level]["income"]
    multiplier = 1.0
    if user[5]:
        multiplier += 0.2
    if user[6]:
        multiplier += 0.1
    return int(base_income * multiplier)

def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance"),
         InlineKeyboardButton("🏪 Бизнес", callback_data="business")],
        [InlineKeyboardButton("💼 Заработать", callback_data="collect"),
         InlineKeyboardButton("📈 Улучшения", callback_data="upgrades")],
        [InlineKeyboardButton("📋 Задания", callback_data="tasks"),
         InlineKeyboardButton("📊 Статистика", callback_data="stats")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id)
    
    text = ("🏆 *Добро пожаловать в Деловой Магнат!* 🏆\n\n"
            "Ты начинающий предприниматель с 1000 монет.\n"
            "Каждые 15 минут собирай доход и развивай бизнес!\n\n"
            "👇 *Используй кнопки ниже*")
    
    await update.message.reply_text(text, parse_mode='Markdown', 
                                   reply_markup=get_main_keyboard())

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    action = query.data
    user = get_user(user_id)
    
    if action == "balance":
        text = f"💰 *Ваш баланс:* {user[1]} монет\n📈 *Всего заработано:* {user[4]} монет"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    elif action == "business":
        level = user[2]
        business = BUSINESSES[level]
        income = calculate_income(user)
        
        last_collect = datetime.fromisoformat(user[3]) if user[3] else datetime.now()
        time_passed = (datetime.now() - last_collect).total_seconds()
        time_left = max(0, 900 - time_passed)
        minutes_left = int(time_left // 60)
        seconds_left = int(time_left % 60)
        
        text = (f"🏪 *{business['name']}*\n"
                f"📊 Уровень: {level}/5\n"
                f"💵 Доход: {income} монет\n"
                f"⏰ До сбора: {minutes_left} мин {seconds_left} сек")
        
        if level < 5:
            text += f"\n⬆️ Апгрейд: {business['upgrade_cost']} монет"
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    elif action == "collect":
        last_collect = datetime.fromisoformat(user[3]) if user[3] else datetime.now()
        time_passed = (datetime.now() - last_collect).total_seconds()
        
        if time_passed >= 900:
            income = calculate_income(user)
            update_balance(user_id, income)
            update_last_collect(user_id)
            text = f"✅ +{income} монет!\n💰 Новый баланс: {user[1] + income}"
        else:
            minutes_left = int((900 - time_passed) // 60)
            text = f"⏳ Еще {minutes_left} мин до сбора!"
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    elif action == "upgrades":
        level = user[2]
        if level < 5:
            text = ("📈 *Улучшения*\n\n"
                   f"👔 Менеджер: {'✅' if user[5] else '❌'} (+20% дохода, 2000💰)\n"
                   f"📢 Реклама: {'✅' if user[6] else '❌'} (+10% дохода, 1500💰)\n"
                   f"⬆️ Апгрейд бизнеса: {BUSINESSES[level]['upgrade_cost']}💰")
            
            keyboard = []
            if not user[5]:
                keyboard.append([InlineKeyboardButton("👔 Нанять менеджера (2000💰)", callback_data="buy_manager")])
            if not user[6]:
                keyboard.append([InlineKeyboardButton("📢 Реклама (1500💰)", callback_data="buy_advertising")])
            if level < 5:
                keyboard.append([InlineKeyboardButton("⬆️ Апгрейд бизнеса", callback_data="upgrade_business")])
            keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
            
            await query.edit_message_text(text, parse_mode='Markdown', 
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await query.answer("🎉 Максимальный уровень!", show_alert=True)
    
    elif action == "upgrade_business":
        level = user[2]
        if level < 5:
            cost = BUSINESSES[level]["upgrade_cost"]
            if user[1] >= cost:
                update_balance(user_id, -cost)
                upgrade_business(user_id)
                await query.answer("✅ Бизнес улучшен!", show_alert=True)
                await query.edit_message_text("🎉 Поздравляю с апгрейдом!", 
                                            reply_markup=get_main_keyboard())
            else:
                await query.answer(f"❌ Не хватает {cost - user[1]}💰", show_alert=True)
    
    elif action == "buy_manager":
        if user[1] >= 2000:
            conn = sqlite3.connect('business.db')
            c = conn.cursor()
            c.execute("UPDATE users SET balance = balance - 2000, manager = TRUE WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            await query.answer("✅ Менеджер нанят! +20% к доходу", show_alert=True)
            # Обновляем сообщение
            await query.edit_message_text("✅ Улучшение куплено!", reply_markup=get_main_keyboard())
        else:
            await query.answer(f"❌ Не хватает {2000 - user[1]}💰", show_alert=True)
    
    elif action == "buy_advertising":
        if user[1] >= 1500:
            conn = sqlite3.connect('business.db')
            c = conn.cursor()
            c.execute("UPDATE users SET balance = balance - 1500, advertising = TRUE WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()
            await query.answer("✅ Реклама запущена! +10% к доходу", show_alert=True)
            await query.edit_message_text("✅ Улучшение куплено!", reply_markup=get_main_keyboard())
        else:
            await query.answer(f"❌ Не хватает {1500 - user[1]}💰", show_alert=True)
    
    elif action == "tasks":
        text = ("📋 *Ежедневное задание*\n\n"
                "✅ Собрать доход 3 раза\n\n"
                "🏆 Награда: 500 монет")
        keyboard = [[InlineKeyboardButton("💰 Забрать награду", callback_data="claim_reward")],
                   [InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        await query.edit_message_text(text, parse_mode='Markdown', 
                                    reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif action == "claim_reward":
        update_balance(user_id, 500)
        await query.answer("🎉 +500 монет!", show_alert=True)
        await query.edit_message_text("✅ Награда получена!", reply_markup=get_main_keyboard())
    
    elif action == "stats":
        level = user[2]
        income = calculate_income(user)
        text = (f"📊 *Статистика*\n\n"
                f"💰 Баланс: {user[1]}\n"
                f"🏪 Бизнес: {BUSINESSES[level]['name']}\n"
                f"📈 Уровень: {level}/5\n"
                f"💵 Доход: {income}\n"
                f"💹 Всего: {user[4]}\n"
                f"👔 Менеджер: {'✅' if user[5] else '❌'}\n"
                f"📢 Реклама: {'✅' if user[6] else '❌'}")
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_keyboard())
    
    elif action == "back":
        await query.edit_message_text("🏪 *Главное меню*\nВыберите действие:", 
                                    parse_mode='Markdown', 
                                    reply_markup=get_main_keyboard())

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("🤖 Бот успешно запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
