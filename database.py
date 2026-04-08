import sqlite3
from datetime import datetime

class Database:
    def __init__(self):
        self.conn = sqlite3.connect("crypto_empire.db", check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                username TEXT,
                nickname TEXT,
                balance INTEGER DEFAULT 5000,
                cryptocoins INTEGER DEFAULT 0,
                vip_level INTEGER DEFAULT 0,
                rating INTEGER DEFAULT 0,
                car_id INTEGER DEFAULT 1,
                cups INTEGER DEFAULT 0,
                total_races INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                register_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                user_id INTEGER,
                business_id INTEGER,
                level INTEGER DEFAULT 1,
                last_collect TIMESTAMP,
                PRIMARY KEY (user_id, business_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS cases (
                user_id INTEGER,
                case_id INTEGER,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, case_id)
            )
        """)
        
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS race_queue (
                user_id INTEGER PRIMARY KEY,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.conn.commit()
    
    def format_number(self, num):
        return f"{num:,}".replace(",", ".")
    
    def register_user(self, user_id, username):
        self.cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, nickname)
            VALUES (?, ?, ?)
        """, (user_id, username, username))
        self.conn.commit()
        return self.get_user(user_id)[0]
    
    def get_user(self, user_id):
        self.cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone()
    
    def get_user_by_id(self, db_id):
        self.cursor.execute("SELECT * FROM users WHERE id = ?", (db_id,))
        return self.cursor.fetchone()
    
    def update_balance(self, user_id, amount):
        self.cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        self.conn.commit()
    
    def update_rating(self, user_id, amount):
        self.cursor.execute("UPDATE users SET rating = rating + ? WHERE user_id = ?", (amount, user_id))
        self.conn.commit()
    
    def update_vip(self, user_id, level):
        self.cursor.execute("UPDATE users SET vip_level = ? WHERE user_id = ?", (level, user_id))
        self.conn.commit()
    
    def update_car(self, user_id, car_id):
        self.cursor.execute("UPDATE users SET car_id = ? WHERE user_id = ?", (car_id, user_id))
        self.conn.commit()
    
    def update_race_stats(self, user_id, won, cups_earned):
        if won:
            self.cursor.execute("""
                UPDATE users SET wins = wins + 1, total_races = total_races + 1, cups = cups + ?
                WHERE user_id = ?
            """, (cups_earned, user_id))
        else:
            self.cursor.execute("""
                UPDATE users SET total_races = total_races + 1
                WHERE user_id = ?
            """, (user_id,))
        self.conn.commit()
    
    def add_to_race_queue(self, user_id):
        self.cursor.execute("INSERT OR REPLACE INTO race_queue (user_id) VALUES (?)", (user_id,))
        self.conn.commit()
    
    def remove_from_race_queue(self, user_id):
        self.cursor.execute("DELETE FROM race_queue WHERE user_id = ?", (user_id,))
        self.conn.commit()
    
    def get_race_opponent(self, user_id):
        self.cursor.execute("""
            SELECT user_id FROM race_queue 
            WHERE user_id != ? 
            ORDER BY joined_at LIMIT 1
        """, (user_id,))
        result = self.cursor.fetchone()
        return result[0] if result else None
    
    def add_case(self, user_id, case_id, quantity=1):
        self.cursor.execute("""
            INSERT INTO cases (user_id, case_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, case_id) DO UPDATE SET
            quantity = quantity + ?
        """, (user_id, case_id, quantity, quantity))
        self.conn.commit()
    
    def remove_case(self, user_id, case_id):
        self.cursor.execute("""
            UPDATE cases SET quantity = quantity - 1
            WHERE user_id = ? AND case_id = ? AND quantity > 0
        """, (user_id, case_id))
        self.conn.commit()
    
    def get_user_cases(self, user_id):
        self.cursor.execute("""
            SELECT c.case_id, c.quantity
            FROM cases c
            WHERE c.user_id = ? AND c.quantity > 0
        """, (user_id,))
        return self.cursor.fetchall()
    
    def get_top_balance(self, limit=10):
        self.cursor.execute("""
            SELECT nickname, balance, user_id
            FROM users
            ORDER BY balance DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()
    
    def get_top_rating(self, limit=10):
        self.cursor.execute("""
            SELECT nickname, rating, user_id
            FROM users
            ORDER BY rating DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()
    
    def get_top_racers(self, limit=10):
        self.cursor.execute("""
            SELECT nickname, cups, user_id
            FROM users
            ORDER BY cups DESC
            LIMIT ?
        """, (limit,))
        return self.cursor.fetchall()
    
    def close(self):
        self.conn.close()