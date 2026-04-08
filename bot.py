import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен из переменных окружения Render
TOKEN = os.environ.get('BOT_TOKEN', '7600712318:AAFjjLpGJk4NcGk5ZqW2rX8vY7tU3sP1oM9')

# Данные бизнесов
BUSINESSES = {
    1: {"name": "🏪 Ларек", "income": 50, "upgrade_cost": 500},
    2: {"name": "🏬 Магазин", "income": 150, "upgrade_cost": 2000},
    3: {"name": "🏢 Супермаркет", "income": 400, "upgrade_cost": 8000},
    4: {"name": "🏙️ Торговый центр", "income": 1000, "upgrade_cost": 30000},
    5: {"name": "🌍 Корпорация", "income": 3000, "upgrade_cost": None}
}

def init_db():
    conn = sqlite3.connect('business.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  balance INTEGER DEFAULT 1000,
                  business_level INTEGER DEFAULT 1,
                  last_collect TIMESTAMP,
                  total_earned INTEGER DEFAULT 0,
                  manager BOOLEAN DEFAULT FALSE,
                  advertising BOOLEAN DEFAULT FALSE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS daily_tasks
                 (user_id INTEGER, task_date DATE, task_completed BOOLEAN DEFAULT FALSE)''')
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
