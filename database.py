#Secondary bot file that is responsible for working with the database: loading, and so on. 

import sqlite3
from typing import Optional, Tuple

class Database:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.create_tables()
    
    def create_tables(self):
        """Create necessary tables if they don't exist"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        # Create users table
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                telegram_id INTEGER UNIQUE,
                name TEXT,
                contact TEXT,
                password TEXT,
                registration_complete BOOLEAN DEFAULT FALSE,
                is_blocked BOOLEAN DEFAULT FALSE,
                last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def user_exists(self, telegram_id: int) -> bool:
        """Check if user exists and has completed registration"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute('SELECT registration_complete FROM users WHERE telegram_id = ?', (telegram_id,))
        result = c.fetchone()
        
        conn.close()
        return result is not None and result[0]
    
    def get_user_data(self, telegram_id: int) -> Optional[Tuple]:
        """Get user registration data"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute('SELECT name, contact, password FROM users WHERE telegram_id = ?', (telegram_id,))
        result = c.fetchone()
        
        conn.close()
        return result
    
    def create_user(self, telegram_id: int):
        """Create new user entry"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute('INSERT OR IGNORE INTO users (telegram_id) VALUES (?)', (telegram_id,))
        
        conn.commit()
        conn.close()
    
    def update_user_field(self, telegram_id: int, field: str, value: str):
        """Update specific user field"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        query = f'UPDATE users SET {field} = ? WHERE telegram_id = ?'
        c.execute(query, (value, telegram_id))
        
        conn.commit()
        conn.close()
    
    def complete_registration(self, telegram_id: int):
        """Mark user registration as complete and update last login"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute('''
            UPDATE users 
            SET registration_complete = TRUE, 
                last_login = CURRENT_TIMESTAMP 
            WHERE telegram_id = ?
        ''', (telegram_id,))
        
        conn.commit()
        conn.close()
    
    def update_last_login(self, telegram_id: int):
        """Update user's last login timestamp"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute('''
            UPDATE users 
            SET last_login = CURRENT_TIMESTAMP 
            WHERE telegram_id = ?
        ''', (telegram_id,))
        
        conn.commit()
        conn.close()
    
    def check_auth(self, telegram_id: int) -> bool:
        """Check if user is registered and not blocked"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute('''
            SELECT registration_complete, is_blocked 
            FROM users 
            WHERE telegram_id = ?
        ''', (telegram_id,))
        
        result = c.fetchone()
        conn.close()
        
        if result:
            is_registered, is_blocked = result
            return is_registered and not is_blocked
        return False
    
    def block_user(self, telegram_id: int):
        """Block user by setting is_blocked flag"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute('''
            UPDATE users 
            SET is_blocked = TRUE 
            WHERE telegram_id = ?
        ''', (telegram_id,))
        
        conn.commit()
        conn.close()
    
    def is_blocked(self, telegram_id: int) -> bool:
        """Check if user is blocked"""
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        
        c.execute('SELECT is_blocked FROM users WHERE telegram_id = ?', (telegram_id,))
        result = c.fetchone()
        
        conn.close()
        return bool(result and result[0]) 
