BOT_TOKEN = "8693908580:AAHLkw25kJrc3Z6eXrUgVtFFEeJQMWShGTw"
DEVELOPER_ID = 5005387093

# VIP статусы
VIP_PRICES = {
    0: {"name": "👤 Обычный", "price": 0, "bonus": 1.0},
    1: {"name": "🥉 Bronze VIP", "price": 10000, "bonus": 1.2},
    2: {"name": "🥈 Silver VIP", "price": 50000, "bonus": 1.5},
    3: {"name": "🥇 Gold VIP", "price": 200000, "bonus": 2.0},
    4: {"name": "💎 Platinum VIP", "price": 1000000, "bonus": 3.0},
    5: {"name": "👑 Diamond VIP", "price": 5000000, "bonus": 5.0}
}

# Бизнесы
BUSINESSES = {
    1: {"name": "🍔 Фастфуд", "price": 25000, "income": 150},
    2: {"name": "🏨 Отель", "price": 150000, "income": 600},
    3: {"name": "🏢 ТРЦ", "price": 750000, "income": 2500},
    4: {"name": "💻 IT-компания", "price": 3000000, "income": 10000},
    5: {"name": "✈️ Авиакомпания", "price": 15000000, "income": 45000},
    6: {"name": "🏦 Банк", "price": 75000000, "income": 200000}
}

# Машины для гонок
CARS = {
    1: {"name": "🚗 Lada Vesta", "price": 5000, "power": 100},
    2: {"name": "🚕 Toyota Camry", "price": 15000, "power": 200},
    3: {"name": "🏎️ BMW M5", "price": 50000, "power": 400},
    4: {"name": "🦅 Porsche 911", "price": 100000, "power": 600},
    5: {"name": "🐎 Ferrari F8", "price": 250000, "power": 900},
    6: {"name": "🚀 Bugatti Chiron", "price": 1000000, "power": 1500}
}

# Кейсы
CASES = {
    1: {"name": "🎋 Бамбуковый", "price": 1000},
    2: {"name": "💎 Нефритовый", "price": 5000},
    3: {"name": "🏆 Гоночный", "price": 0}
}

# Казино множители
CASINO_MULTIPLIERS = [
    {"x": 0, "chance": 10, "name": "💀 БАНКРОТСТВО"},
    {"x": 0.25, "chance": 25, "name": "😢 Плохо"},
    {"x": 0.5, "chance": 20, "name": "😐 Неудача"},
    {"x": 0.75, "chance": 15, "name": "🙁 Обидно"},
    {"x": 1, "chance": 12, "name": "👍 Вернул"},
    {"x": 1.5, "chance": 8, "name": "🎉 Хорошо"},
    {"x": 2, "chance": 5, "name": "🎊 Отлично"},
    {"x": 3, "chance": 3, "name": "🤯 Удача"},
    {"x": 5, "chance": 1.5, "name": "⚡ ДЖЕКПОТ"},
    {"x": 10, "chance": 0.5, "name": "💎 МЕГА ДЖЕКПОТ"}
]

RACE_ENTRY_FEE = 500
RACE_BASE_CUPS = 10