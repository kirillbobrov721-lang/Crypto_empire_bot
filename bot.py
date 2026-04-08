import logging
import random
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import *
from database import Database

# Настройка
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()

# ============ КЛАВИАТУРЫ ============
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("💰 Баланс", callback_data="balance"),
         InlineKeyboardButton("📊 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🎰 Казино", callback_data="casino"),
         InlineKeyboardButton("🏎️ Гонка", callback_data="race")],
        [InlineKeyboardButton("🎁 Кейсы", callback_data="cases"),
         InlineKeyboardButton("👑 VIP", callback_data="vip")],
        [InlineKeyboardButton("🏪 Бизнес", callback_data="business"),
         InlineKeyboardButton("📈 Топы", callback_data="tops")],
        [InlineKeyboardButton("🚗 Машины", callback_data="cars"),
         InlineKeyboardButton("📋 Репорт", callback_data="report")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ============ ОСНОВНЫЕ КОМАНДЫ ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    db.register_user(user_id, username)
    user = db.get_user(user_id)
    
    # Добавляем стартовые кейсы
    db.add_case(user_id, 1, 1)
    
    await update.message.reply_text(
        f"🏦 *CRYPTO EMPIRE* 🏦\n\n"
        f"👋 Привет, {user[3]}!\n"
        f"📋 Твой ID: #{user[0]}\n"
        f"💰 Баланс: {db.format_number(user[1])}£\n"
        f"⭐ Рейтинг: {user[7]}\n\n"
        f"🎁 Тебе выдан стартовый кейс!\n\n"
        f"*Команды без /:*\n"
        f"баланс, профиль, казино 1000, гонка, кейс 1",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    user_id = update.effective_user.id
    
    if text in ["баланс", "деньги", "б"]:
        user = db.get_user(user_id)
        await update.message.reply_text(f"💰 *Баланс:* {db.format_number(user[1])}£", parse_mode="Markdown")
    
    elif text in ["профиль", "проф", "я"]:
        user = db.get_user(user_id)
        vip_bonus = VIP_PRICES.get(user[5], {"bonus": 1.0})["bonus"]
        await update.message.reply_text(
            f"👤 *ПРОФИЛЬ #{user[0]}*\n\n"
            f"📝 Ник: {user[3]}\n"
            f"💰 Баланс: {db.format_number(user[1])}£\n"
            f"💎 CryptoCoin: {db.format_number(user[2])}\n"
            f"⭐ Рейтинг: {user[7]}\n"
            f"👑 VIP: {VIP_PRICES.get(user[5], {'name': 'Нет'})['name']}\n"
            f"🚗 Машина: {CARS.get(user[8], {'name': 'Нет'})['name']}\n"
            f"🏆 Кубки: {user[9]}\n"
            f"🏁 Гонок: {user[10]}\n"
            f"🎉 Побед: {user[11]}",
            parse_mode="Markdown"
        )
    
    elif text.startswith("казино "):
        await casino_bet(update, context)
    
    elif text == "гонка":
        await race_start(update, context)
    
    elif text.startswith("кейс "):
        await open_case_text(update, context)

# ============ КАЗИНО ============
async def casino_bet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    try:
        bet_text = update.message.text.split()[1]
        
        # Парсим сумму с K, M
        bet_text_upper = bet_text.upper()
        multiplier = 1
        if bet_text_upper.endswith("K"):
            multiplier = 1000
            bet_text = bet_text[:-1]
        elif bet_text_upper.endswith("M"):
            multiplier = 1000000
            bet_text = bet_text[:-1]
        elif bet_text_upper.endswith("KK"):
            multiplier = 1000000
            bet_text = bet_text[:-2]
        
        bet = int(float(bet_text) * multiplier)
        
        if bet < 100:
            await update.message.reply_text("❌ Минимальная ставка: 100£")
            return
        
        if bet > user[1]:
            await update.message.reply_text(f"❌ Не хватает! У вас {db.format_number(user[1])}£")
            return
        
        # Выбор множителя
        rand = random.random() * 100
        cumulative = 0
        selected = CASINO_MULTIPLIERS[0]
        
        for mult in CASINO_MULTIPLIERS:
            cumulative += mult["chance"]
            if rand <= cumulative:
                selected = mult
                break
        
        win_amount = int(bet * selected["x"])
        
        if win_amount > 0:
            db.update_balance(user_id, win_amount - bet)
            result = f"🎉 *{selected['name']}* x{selected['x']}\n💰 +{db.format_number(win_amount)}£"
        else:
            db.update_balance(user_id, -bet)
            result = f"💀 *{selected['name']}*\n💸 -{db.format_number(bet)}£"
        
        new_user = db.get_user(user_id)
        result += f"\n\n💰 Новый баланс: {db.format_number(new_user[1])}£"
        
        await update.message.reply_text(result, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text("❌ Использование: казино 1000 или казино 1к")

# ============ ГОНКИ ============
race_queue = {}

async def race_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if user[1] < RACE_ENTRY_FEE:
        await update.message.reply_text(f"❌ Нужно {db.format_number(RACE_ENTRY_FEE)}£ для участия!")
        return
    
    # Проверяем очередь
    opponent = db.get_race_opponent(user_id)
    
    if opponent:
        # Найден соперник - проводим гонку
        db.remove_from_race_queue(opponent)
        await race_fight(update, context, user_id, opponent)
    else:
        # Добавляем в очередь
        db.add_to_race_queue(user_id)
        await update.message.reply_text(
            "🏁 *Вы в очереди на гонку!*\n"
            "Ожидайте соперника...\n\n"
            "Через 100 секунд вы сразитесь с ботом",
            parse_mode="Markdown"
        )
        
        # Таймер для гонки с ботом
        await asyncio.sleep(100)
        
        # Проверяем, всё ещё в очереди?
        still_in_queue = db.get_race_opponent(user_id)
        if still_in_queue:
            db.remove_from_race_queue(user_id)
            await race_with_bot(update, context, user_id)

async def race_fight(update: Update, context: ContextTypes.DEFAULT_TYPE, user1_id, user2_id):
    user1 = db.get_user(user1_id)
    user2 = db.get_user(user2_id)
    
    # Списываем взнос
    db.update_balance(user1_id, -RACE_ENTRY_FEE)
    db.update_balance(user2_id, -RACE_ENTRY_FEE)
    
    # Сила машин
    car1_power = CARS.get(user1[8], {"power": 100})["power"]
    car2_power = CARS.get(user2[8], {"power": 100})["power"]
    
    # Шанс победы зависит от силы машины
    total_power = car1_power + car2_power
    user1_chance = (car1_power / total_power) * 100
    
    rand = random.random() * 100
    
    if rand < user1_chance:
        winner_id = user1_id
        loser_id = user2_id
        winner_power = car1_power
    else:
        winner_id = user2_id
        loser_id = user1_id
        winner_power = car2_power
    
    # Награда победителю
    cups_earned = RACE_BASE_CUPS + int(winner_power / 100)
    vip_bonus = VIP_PRICES.get(user1[5] if winner_id == user1_id else user2[5], {"bonus": 1.0})["bonus"]
    cups_earned = int(cups_earned * vip_bonus)
    
    db.update_race_stats(winner_id, True, cups_earned)
    db.update_race_stats(loser_id, False, 0)
    
    # Денежная награда
    prize = RACE_ENTRY_FEE * 2 + random.randint(500, 2000)
    db.update_balance(winner_id, prize)
    
    winner_user = db.get_user(winner_id)
    loser_user = db.get_user(loser_id)
    
    # Отправляем результат
    await context.bot.send_message(
        winner_id,
        f"🏆 *ПОБЕДА В ГОНКЕ!* 🏆\n\n"
        f"Противник: {loser_user[3]}\n"
        f"🎁 Награда: +{db.format_number(prize)}£\n"
        f"🏆 Кубков: +{cups_earned}\n"
        f"💰 Баланс: {db.format_number(winner_user[1])}£",
        parse_mode="Markdown"
    )
    
    await context.bot.send_message(
        loser_id,
        f"💨 *ПОРАЖЕНИЕ В ГОНКЕ!* 💨\n\n"
        f"Победитель: {winner_user[3]}\n"
        f"💰 Баланс: {db.format_number(loser_user[1])}£",
        parse_mode="Markdown"
    )
    
    # Даём гоночный кейс победителю
    db.add_case(winner_id, 3, 1)

async def race_with_bot(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    user = db.get_user(user_id)
    
    db.update_balance(user_id, -RACE_ENTRY_FEE)
    
    # Шанс победы над ботом - 50%
    win = random.choice([True, False])
    
    if win:
        cups_earned = RACE_BASE_CUPS
        vip_bonus = VIP_PRICES.get(user[5], {"bonus": 1.0})["bonus"]
        cups_earned = int(cups_earned * vip_bonus)
        
        prize = RACE_ENTRY_FEE * 2 + random.randint(200, 1000)
        db.update_balance(user_id, prize)
        db.update_race_stats(user_id, True, cups_earned)
        
        new_user = db.get_user(user_id)
        
        await context.bot.send_message(
            user_id,
            f"🏆 *ПОБЕДА НАД БОТОМ!* 🏆\n\n"
            f"🎁 Награда: +{db.format_number(prize)}£\n"
            f"🏆 Кубков: +{cups_earned}\n"
            f"💰 Баланс: {db.format_number(new_user[1])}£",
            parse_mode="Markdown"
        )
        
        db.add_case(user_id, 3, 1)
    else:
        db.update_race_stats(user_id, False, 0)
        new_user = db.get_user(user_id)
        
        await context.bot.send_message(
            user_id,
            f"💨 *ПОРАЖЕНИЕ ОТ БОТА!* 💨\n\n"
            f"💰 Баланс: {db.format_number(new_user[1])}£",
            parse_mode="Markdown"
        )

# ============ КЕЙСЫ ============
async def open_case_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    try:
        case_num = int(update.message.text.split()[1])
        
        if case_num not in CASES:
            await update.message.reply_text("❌ Доступны кейсы: 1, 2, 3")
            return
        
        case = CASES[case_num]
        
        if case["price"] > 0 and user[1] < case["price"]:
            await update.message.reply_text(f"❌ Не хватает {db.format_number(case['price'])}£!")
            return
        
        # Проверяем наличие кейса
        user_cases = db.get_user_cases(user_id)
        has_case = any(c[0] == case_num for c in user_cases)
        
        if case_num == 3 and not has_case:
            await update.message.reply_text("❌ У вас нет гоночных кейсов!")
            return
        
        if case["price"] > 0:
            db.update_balance(user_id, -case["price"])
        else:
            db.remove_case(user_id, case_num)
        
        # Награды
        if case_num == 1:
            rewards = [500, 1000, 2000, 5000]
            reward = random.choice(rewards)
            db.update_balance(user_id, reward)
            await update.message.reply_text(
                f"🎁 *{case['name']} кейс открыт!*\n"
                f"💰 Получено: +{db.format_number(reward)}£",
                parse_mode="Markdown"
            )
        elif case_num == 2:
            rewards = [2000, 5000, 10000, 25000, 50000]
            reward = random.choice(rewards)
            db.update_balance(user_id, reward)
            await update.message.reply_text(
                f"🎁 *{case['name']} кейс открыт!*\n"
                f"💰 Получено: +{db.format_number(reward)}£",
                parse_mode="Markdown"
            )
        elif case_num == 3:
            rewards = [1000, 2000, 5000, 10000]
            reward = random.choice(rewards)
            db.update_balance(user_id, reward)
            await update.message.reply_text(
                f"🎁 *{case['name']} кейс открыт!*\n"
                f"💰 Получено: +{db.format_number(reward)}£\n"
                f"🏆 +5 кубков",
                parse_mode="Markdown"
            )
            db.update_race_stats(user_id, True, 5)
        
        new_user = db.get_user(user_id)
        await update.message.reply_text(f"💰 Новый баланс: {db.format_number(new_user[1])}£")
        
    except:
        await update.message.reply_text("❌ Использование: кейс 1, кейс 2 или кейс 3")

# ============ ТОПЫ ============
async def show_tops(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 По деньгам", callback_data="top_balance"),
         InlineKeyboardButton("⭐ По рейтингу", callback_data="top_rating")],
        [InlineKeyboardButton("🏆 По гонкам", callback_data="top_race"),
         InlineKeyboardButton("🔙 Назад", callback_data="back")]
    ])
    
    await query.edit_message_text(
        "📊 *Выберите категорию топа:*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def top_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    top = db.get_top_balance(10)
    text = "💰 *Топ богатейших игроков:*\n\n"
    
    for i, (name, balance, uid) in enumerate(top, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += f"{medal} {name} — {db.format_number(balance)}£\n"
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def top_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    top = db.get_top_rating(10)
    text = "⭐ *Топ по рейтингу:*\n\n"
    
    for i, (name, rating, uid) in enumerate(top, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += f"{medal} {name} — {rating}⭐\n"
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def top_race(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    top = db.get_top_racers(10)
    text = "🏆 *Топ гонщиков:*\n\n"
    
    for i, (name, cups, uid) in enumerate(top, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        text += f"{medal} {name} — {cups}🏆\n"
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

# ============ CALLBACK HANDLERS ============
async def callback_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = db.get_user(query.from_user.id)
    await query.edit_message_text(
        f"💰 *Ваш баланс:* {db.format_number(user[1])}£\n"
        f"💎 *CryptoCoin:* {db.format_number(user[2])}",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def callback_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = db.get_user(query.from_user.id)
    vip_bonus = VIP_PRICES.get(user[5], {"bonus": 1.0})["bonus"]
    
    await query.edit_message_text(
        f"👤 *ПРОФИЛЬ #{user[0]}*\n\n"
        f"📝 Ник: {user[3]}\n"
        f"💰 Баланс: {db.format_number(user[1])}£\n"
        f"💎 CryptoCoin: {db.format_number(user[2])}\n"
        f"⭐ Рейтинг: {user[7]}\n"
        f"👑 VIP: {VIP_PRICES.get(user[5], {'name': 'Нет'})['name']}\n"
        f"🚗 Машина: {CARS.get(user[8], {'name': 'Нет'})['name']}\n"
        f"🏆 Кубки: {user[9]}\n"
        f"🏁 Гонок: {user[10]}\n"
        f"🎉 Побед: {user[11]}",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def callback_casino(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🎰 *КАЗИНО*\n\n"
        "Используйте команду:\n"
        "`казино <сумма>`\n\n"
        "Примеры: `казино 1000` или `казино 1к`\n\n"
        "Множители: x0, x0.25, x0.5, x0.75, x1, x1.5, x2, x3, x5, x10",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def callback_race(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        f"🏁 *ГОНКИ*\n\n"
        f"💰 Вступительный взнос: {db.format_number(RACE_ENTRY_FEE)}£\n"
        f"🏆 Кубков за победу: от {RACE_BASE_CUPS}\n"
        f"🎁 Награда: кейс + деньги\n\n"
        f"Используйте команду: `гонка`",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def callback_cases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = db.get_user(query.from_user.id)
    user_cases = db.get_user_cases(query.from_user.id)
    
    text = "🎁 *ДОСТУПНЫЕ КЕЙСЫ*\n\n"
    
    for case_id, case in CASES.items():
        if case["price"] > 0:
            text += f"{case_id}. {case['name']} - {db.format_number(case['price'])}£\n"
        else:
            user_case = next((c for c in user_cases if c[0] == case_id), None)
            quantity = user_case[1] if user_case else 0
            text += f"{case_id}. {case['name']} - {quantity} шт.\n"
    
    text += "\n💡 Используйте: `кейс 1`, `кейс 2` или `кейс 3`"
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def callback_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = "👑 *VIP СТАТУСЫ*\n\n"
    for level, vip in VIP_PRICES.items():
        if level > 0:
            text += f"{vip['name']} - {db.format_number(vip['price'])}£\n"
            text += f"└ Бонус: x{vip['bonus']} к доходу\n\n"
    
    text += "💡 Для покупки: `/buy_vip <уровень>`\n"
    text += "Пример: `/buy_vip бронза`"
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def callback_business(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = "🏪 *БИЗНЕСЫ*\n\n"
    for biz_id, biz in BUSINESSES.items():
        text += f"{biz['name']}\n"
        text += f"└ Доход: {db.format_number(biz['income'])}£\n"
        text += f"└ Цена: {db.format_number(biz['price'])}£\n\n"
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def callback_cars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = db.get_user(query.from_user.id)
    
    text = "🚗 *МАШИНЫ ДЛЯ ГОНОК*\n\n"
    for car_id, car in CARS.items():
        check = "✅" if user[8] == car_id else "❌"
        text += f"{check} {car['name']}\n"
        text += f"└ Сила: {car['power']} | Цена: {db.format_number(car['price'])}£\n\n"
    
    text += "💡 Для покупки: `/buy_car <номер>`\nПример: `/buy_car 3`"
    
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def callback_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📋 *СИСТЕМА РЕПОРТОВ*\n\n"
        "Для жалобы на игрока используйте:\n"
        "`/report <ID> <причина>`\n\n"
        "Пример: `/report 15 Оскорбления в чате`",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

async def callback_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = db.get_user(query.from_user.id)
    await query.edit_message_text(
        f"🏦 *CRYPTO EMPIRE* 🏦\n\n"
        f"👋 Привет, {user[3]}!\n"
        f"💰 Баланс: {db.format_number(user[1])}£\n"
        f"⭐ Рейтинг: {user[7]}\n\n"
        f"Используйте кнопки для навигации!",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# ============ АДМИН КОМАНДЫ ============
async def give_case(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != DEVELOPER_ID:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    try:
        target_id = int(context.args[0])
        case_id = int(context.args[1])
        quantity = int(context.args[2]) if len(context.args) > 2 else 1
        
        db.add_case(target_id, case_id, quantity)
        await update.message.reply_text(f"✅ Выдал {quantity} кейс(ов) #{case_id} игроку #{target_id}")
    except:
        await update.message.reply_text("❌ Использование: /give_case <ID> <кейс> <кол-во>")

async def give_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != DEVELOPER_ID:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        
        db.update_balance(target_id, amount)
        await update.message.reply_text(f"✅ Выдал {db.format_number(amount)}£ игроку #{target_id}")
    except:
        await update.message.reply_text("❌ Использование: /give_money <ID> <сумма>")

async def give_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != DEVELOPER_ID:
        await update.message.reply_text("❌ Нет прав!")
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        
        db.update_rating(target_id, amount)
        await update.message.reply_text(f"✅ Выдал {amount}⭐ рейтинга игроку #{target_id}")
    except:
        await update.message.reply_text("❌ Использование: /give_rating <ID> <количество>")

# ============ ЗАПУСК ============
def main():
    print("🤖 Бот CRYPTO EMPIRE запущен!")
    print(f"👑 Разработчик: {DEVELOPER_ID}")
    print("📋 Доступные команды:")
    print("   - баланс, профиль, казино 1000, гонка, кейс 1")
    print("   - /start - перезапуск")
    print("   - /give_case - админ")
    print("   - /give_money - админ")
    print("   - /give_rating - админ")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("give_case", give_case))
    app.add_handler(CommandHandler("give_money", give_money))
    app.add_handler(CommandHandler("give_rating", give_rating))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(callback_balance, pattern="balance"))
    app.add_handler(CallbackQueryHandler(callback_profile, pattern="profile"))
    app.add_handler(CallbackQueryHandler(callback_casino, pattern="casino"))
    app.add_handler(CallbackQueryHandler(callback_race, pattern="race"))
    app.add_handler(CallbackQueryHandler(callback_cases, pattern="cases"))
    app.add_handler(CallbackQueryHandler(callback_vip, pattern="vip"))
    app.add_handler(CallbackQueryHandler(callback_business, pattern="business"))
    app.add_handler(CallbackQueryHandler(show_tops, pattern="tops"))
    app.add_handler(CallbackQueryHandler(callback_cars, pattern="cars"))
    app.add_handler(CallbackQueryHandler(callback_report, pattern="report"))
    app.add_handler(CallbackQueryHandler(callback_back, pattern="back"))
    app.add_handler(CallbackQueryHandler(top_balance, pattern="top_balance"))
    app.add_handler(CallbackQueryHandler(top_rating, pattern="top_rating"))
    app.add_handler(CallbackQueryHandler(top_race, pattern="top_race"))
    
    # Текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()