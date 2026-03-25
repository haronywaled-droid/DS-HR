#!/usr/bin/env python3
"""
Telegram Bot for HR System
Complete rewrite with phone+password login, deep linking, and web integration
"""

import os
import sys
import json
import logging
import sqlite3
import requests
import threading
import hashlib
import hmac
import base64
import urllib.parse
from datetime import datetime, timedelta
from time import sleep
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass
from enum import Enum

# Configuration
BOT_TOKEN = "8778522922:AAHs7vMPrbX6bLFm1GYEAwpqVbznnvQZjHU"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
DATABASE_PATH = "hr_system.db"
FLASK_APP_URL = "http://196.218.2.70:5551"
WEBHOOK_SECRET = "hr-system-telegram-secret-key-change-in-production"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles in the system"""
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class MenuState(Enum):
    """User menu states"""
    MAIN = "main"
    AWAITING_PHONE = "awaiting_phone"
    AWAITING_PASSWORD = "awaiting_password"
    AWAITING_LEAVE_TYPE = "awaiting_leave_type"
    AWAITING_LEAVE_DATE = "awaiting_leave_date"
    AWAITING_PERMISSION_TYPE = "awaiting_permission_type"
    AWAITING_PERMISSION_DATE = "awaiting_permission_date"
    AWAITING_SALARY_MONTH = "awaiting_salary_month"
    AWAITING_SCHEDULE_WEEK = "awaiting_schedule_week"


@dataclass
class UserSession:
    """User session data"""
    user_id: int
    telegram_id: int
    username: str
    name: str
    role: UserRole
    department_id: Optional[int] = None
    department_name: Optional[str] = None
    menu_state: MenuState = MenuState.MAIN
    temp_data: Dict[str, Any] = None
    last_activity: datetime = None
    
    def __post_init__(self):
        if self.temp_data is None:
            self.temp_data = {}
        if self.last_activity is None:
            self.last_activity = datetime.now()


class DatabaseManager:
    """Enhanced database operations"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def get_connection(self):
        """Get database connection"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            return None
    
    def authenticate_user(self, phone: str, password: str) -> Optional[Dict]:
        """
        Authenticate user with phone and password
        Returns user data if authentication successful
        """
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            
            # Find user by phone number
            cursor.execute("""
                SELECT u.id, u.username, u.name, u.is_admin, u.is_manager,
                       u.password_hash, ed.phone, ed.whatsapp,
                       ed.job_title, d.id as department_id, d.name as department_name
                FROM users u
                LEFT JOIN employee_data ed ON u.id = ed.user_id
                LEFT JOIN departments d ON u.department_id = d.id
                WHERE ed.phone = ? OR ed.whatsapp = ? OR ed.phone = ? OR ed.whatsapp = ?
            """, (phone, phone, phone.replace('+', ''), phone.replace('+', '')))
            
            user = cursor.fetchone()
            if not user:
                return None
            
            user_dict = dict(user)
            
            # Verify password
            from werkzeug.security import check_password_hash
            if not check_password_hash(user_dict['password_hash'], password):
                return None
            
            # Determine role
            if user_dict['is_admin']:
                role = UserRole.ADMIN
            elif user_dict['is_manager']:
                role = UserRole.MANAGER
            else:
                role = UserRole.EMPLOYEE
            
            return {
                'id': user_dict['id'],
                'username': user_dict['username'],
                'name': user_dict['name'],
                'role': role,
                'department_id': user_dict['department_id'],
                'department_name': user_dict['department_name'],
                'job_title': user_dict['job_title'],
                'phone': user_dict['phone'] or user_dict['whatsapp']
            }
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Get user by Telegram ID from mapping"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT u.id, u.username, u.name, u.is_admin, u.is_manager,
                       u.department_id, ed.job_title, d.name as department_name,
                       tm.telegram_id, tm.phone_number
                FROM users u
                JOIN telegram_mapping tm ON u.id = tm.user_id
                LEFT JOIN employee_data ed ON u.id = ed.user_id
                LEFT JOIN departments d ON u.department_id = d.id
                WHERE tm.telegram_id = ? AND tm.is_active = 1
            """, (telegram_id,))
            
            user = cursor.fetchone()
            return dict(user) if user else None
            
        except sqlite3.Error as e:
            logger.error(f"Error querying user by telegram_id: {e}")
            return None
        finally:
            conn.close()
    
    def save_telegram_mapping(self, user_id: int, telegram_id: int, 
                             phone: str, session_token: str = None) -> bool:
        """Save Telegram mapping to database with session token"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            
            # Create telegram_mapping table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telegram_mapping (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    telegram_id INTEGER NOT NULL UNIQUE,
                    phone_number TEXT NOT NULL,
                    session_token TEXT,
                    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_telegram_mapping_user 
                ON telegram_mapping(user_id)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_telegram_mapping_telegram 
                ON telegram_mapping(telegram_id)
            """)
            
            # Check if mapping exists
            cursor.execute(
                "SELECT id FROM telegram_mapping WHERE user_id = ?",
                (user_id,)
            )
            existing = cursor.fetchone()
            
            now = datetime.now().isoformat()
            
            if existing:
                # Update existing mapping
                cursor.execute("""
                    UPDATE telegram_mapping 
                    SET telegram_id = ?, phone_number = ?, session_token = ?,
                        last_activity = ?, verified_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (telegram_id, phone, session_token, now, user_id))
            else:
                # Insert new mapping
                cursor.execute("""
                    INSERT INTO telegram_mapping 
                    (user_id, telegram_id, phone_number, session_token, last_activity)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, telegram_id, phone, session_token, now))
            
            conn.commit()
            logger.info(f"Saved Telegram mapping for user {user_id}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Error saving telegram mapping: {e}")
            return False
        finally:
            conn.close()
    
    def update_last_activity(self, telegram_id: int) -> bool:
        """Update user's last activity timestamp"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE telegram_mapping 
                SET last_activity = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            """, (telegram_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error updating last activity: {e}")
            return False
        finally:
            conn.close()
    
    def get_user_pending_notifications(self, user_id: int) -> List[Dict]:
        """Get pending notifications for user"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, title, message, notification_type, created_at, action_url
                FROM notifications
                WHERE user_id = ? AND is_read = 0
                ORDER BY created_at DESC
                LIMIT 20
            """, (user_id,))
            
            notifications = cursor.fetchall()
            return [dict(n) for n in notifications]
            
        except sqlite3.Error as e:
            logger.error(f"Error getting pending notifications: {e}")
            return []
        finally:
            conn.close()
    
    def mark_notification_read(self, notification_id: int) -> bool:
        """Mark notification as read"""
        conn = self.get_connection()
        if not conn:
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE notifications SET is_read = 1 WHERE id = ?",
                (notification_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            logger.error(f"Error marking notification read: {e}")
            return False
        finally:
            conn.close()
    
    def get_user_leave_requests(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's leave requests"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, leave_type, start_date, end_date, total_days,
                       status, reason, created_at
                FROM leave_requests
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
            
            requests = cursor.fetchall()
            return [dict(r) for r in requests]
            
        except sqlite3.Error as e:
            logger.error(f"Error getting leave requests: {e}")
            return []
        finally:
            conn.close()
    
    def get_user_permission_requests(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get user's permission requests"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, permission_type, date, time, reason, status,
                       extra_data, created_at
                FROM permission_requests
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
            
            requests = cursor.fetchall()
            return [dict(r) for r in requests]
            
        except sqlite3.Error as e:
            logger.error(f"Error getting permission requests: {e}")
            return []
        finally:
            conn.close()
    
    def get_user_salary_slips(self, user_id: int, limit: int = 5) -> List[Dict]:
        """Get user's salary slips"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, month, arabic_month, file_name, is_viewed
                FROM salary_slips
                WHERE user_id = ?
                ORDER BY month DESC
                LIMIT ?
            """, (user_id, limit))
            
            slips = cursor.fetchall()
            return [dict(s) for s in slips]
            
        except sqlite3.Error as e:
            logger.error(f"Error getting salary slips: {e}")
            return []
        finally:
            conn.close()
    
    def get_user_balance(self, user_id: int) -> Optional[Dict]:
        """Get user's leave and permission balance"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT leave_balance, permission_balance, advance_balance,
                       last_updated
                FROM employee_balances
                WHERE user_id = ?
            """, (user_id,))
            
            balance = cursor.fetchone()
            return dict(balance) if balance else None
            
        except sqlite3.Error as e:
            logger.error(f"Error getting user balance: {e}")
            return None
        finally:
            conn.close()
    
    def get_current_week_schedule(self, department_id: int) -> Optional[Dict]:
        """Get current week schedule for department"""
        conn = self.get_connection()
        if not conn:
            return None
        
        try:
            cursor = conn.cursor()
            today = datetime.now().date().isoformat()
            
            cursor.execute("""
                SELECT ws.id, ws.week_start_date, ws.week_end_date,
                       sd.day_date, sd.day_name, sd.job_title,
                       sd.morning_shift, sd.evening_shift, sd.night_shift
                FROM weekly_schedules ws
                JOIN schedule_details sd ON ws.id = sd.weekly_schedule_id
                WHERE ws.department_id = ? AND ws.is_approved = 1
                  AND ws.week_start_date <= ? AND ws.week_end_date >= ?
                ORDER BY sd.day_date, sd.row_order
            """, (department_id, today, today))
            
            details = cursor.fetchall()
            
            if not details:
                return None
            
            result = {
                'schedule_id': details[0]['id'],
                'week_start': details[0]['week_start_date'],
                'week_end': details[0]['week_end_date'],
                'details': [dict(d) for d in details]
            }
            
            return result
            
        except sqlite3.Error as e:
            logger.error(f"Error getting schedule: {e}")
            return None
        finally:
            conn.close()
    
    def get_department_employees(self, department_id: int) -> List[Dict]:
        """Get employees in department"""
        conn = self.get_connection()
        if not conn:
            return []
        
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT u.id, u.name, u.username, ed.job_title
                FROM users u
                LEFT JOIN employee_data ed ON u.id = ed.user_id
                WHERE u.department_id = ? AND u.is_admin = 0 AND u.is_active = 1
                ORDER BY u.name
            """, (department_id,))
            
            employees = cursor.fetchall()
            return [dict(e) for e in employees]
            
        except sqlite3.Error as e:
            logger.error(f"Error getting department employees: {e}")
            return []
        finally:
            conn.close()
    
    def get_manager_pending_requests(self, manager_id: int) -> Dict[str, int]:
        """Get counts of pending requests for manager"""
        conn = self.get_connection()
        if not conn:
            return {'leaves': 0, 'permissions': 0, 'advances': 0}
        
        try:
            cursor = conn.cursor()
            
            # Get departments managed by this user
            cursor.execute("""
                SELECT department_id FROM department_managers
                WHERE user_id = ?
            """, (manager_id,))
            
            dept_rows = cursor.fetchall()
            dept_ids = [d['department_id'] for d in dept_rows]
            
            if not dept_ids:
                return {'leaves': 0, 'permissions': 0, 'advances': 0}
            
            dept_placeholders = ','.join(['?'] * len(dept_ids))
            
            # Count pending leaves
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM leave_requests
                WHERE department_id IN ({dept_placeholders})
                  AND status = 'pending'
            """, dept_ids)
            leaves = cursor.fetchone()['count']
            
            # Count pending permissions
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM permission_requests
                WHERE department_id IN ({dept_placeholders})
                  AND status = 'pending'
            """, dept_ids)
            permissions = cursor.fetchone()['count']
            
            # Count pending advances
            cursor.execute(f"""
                SELECT COUNT(*) as count FROM advance_requests
                WHERE department_id IN ({dept_placeholders})
                  AND status = 'pending'
            """, dept_ids)
            advances = cursor.fetchone()['count']
            
            return {
                'leaves': leaves,
                'permissions': permissions,
                'advances': advances
            }
            
        except sqlite3.Error as e:
            logger.error(f"Error getting pending requests: {e}")
            return {'leaves': 0, 'permissions': 0, 'advances': 0}
        finally:
            conn.close()


class DeepLinkGenerator:
    """Generate deep links for automatic login to web interface"""
    
    @staticmethod
    def generate_token(user_id: int, telegram_id: int) -> str:
        """Generate a secure token for automatic login"""
        timestamp = int(datetime.now().timestamp())
        data = f"{user_id}:{telegram_id}:{timestamp}"
        
        # Create HMAC signature
        signature = hmac.new(
            WEBHOOK_SECRET.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        
        token = base64.urlsafe_b64encode(
            f"{user_id}:{telegram_id}:{timestamp}:{signature}".encode()
        ).decode().rstrip('=')
        
        return token
    
    @staticmethod
    def verify_token(token: str) -> Optional[Dict]:
        """Verify a login token"""
        try:
            # Add padding if needed
            padding = 4 - (len(token) % 4)
            if padding < 4:
                token += '=' * padding
            
            decoded = base64.urlsafe_b64decode(token).decode()
            user_id, telegram_id, timestamp, signature = decoded.split(':')
            
            # Check if token is expired (24 hours)
            if int(timestamp) < int(datetime.now().timestamp()) - 86400:
                return None
            
            # Verify signature
            data = f"{user_id}:{telegram_id}:{timestamp}"
            expected = hmac.new(
                WEBHOOK_SECRET.encode(),
                data.encode(),
                hashlib.sha256
            ).hexdigest()[:16]
            
            if signature != expected:
                return None
            
            return {
                'user_id': int(user_id),
                'telegram_id': int(telegram_id),
                'timestamp': int(timestamp)
            }
            
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None
    
    @staticmethod
    def get_login_url(user_id: int, telegram_id: int, page: str = 'dashboard') -> str:
        """Get login URL for a specific page"""
        token = DeepLinkGenerator.generate_token(user_id, telegram_id)
        params = urllib.parse.urlencode({
            'token': token,
            'telegram_id': telegram_id
        })
        return f"{FLASK_APP_URL}/telegram_login/{page}?{params}"
    
    @staticmethod
    def get_page_urls(user_id: int, telegram_id: int) -> Dict[str, str]:
        """Get URLs for all main pages"""
        base_token = DeepLinkGenerator.generate_token(user_id, telegram_id)
        
        pages = {
            'dashboard': f"{FLASK_APP_URL}/telegram_login/dashboard?token={base_token}",
            'schedule': f"{FLASK_APP_URL}/telegram_login/schedule?token={base_token}",
            'leave': f"{FLASK_APP_URL}/telegram_login/leave_requests?token={base_token}",
            'salary': f"{FLASK_APP_URL}/telegram_login/salary_slips?token={base_token}",
            'profile': f"{FLASK_APP_URL}/telegram_login/profile?token={base_token}"
        }
        
        return pages


class MessageFormatter:
    """Format messages for Telegram"""
    
    @staticmethod
    def escape_markdown(text: str) -> str:
        """Escape special characters for Markdown"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
    
    @staticmethod
    def format_welcome(user: Dict, pages: Dict[str, str]) -> str:
        """Format welcome message with deep links"""
        name = user.get('name', '')
        role = user.get('role', UserRole.EMPLOYEE).value
        
        text = f"""
🎉 <b>مرحباً {name}!</b>

تم ربط حسابك بنجاح. يمكنك الآن:
• استلام الإشعارات مباشرة
• تصفح النظام عبر الروابط أدناه
• إدارة طلباتك بسهولة

<b>🔗 روابط سريعة (دخول تلقائي):</b>
• <a href="{pages['dashboard']}">🏠 الرئيسية</a>
• <a href="{pages['schedule']}">📅 جدول العمل</a>
• <a href="{pages['leave']}">📋 طلباتي</a>
• <a href="{pages['salary']}">💰 المرتبات</a>
• <a href="{pages['profile']}">👤 ملفي الشخصي</a>

<b>📌 الأوامر المتاحة:</b>
/start - القائمة الرئيسية
/notifications - آخر الإشعارات
/schedule - جدول العمل
/balance - الرصيد المتبقي
/requests - طلباتي
/help - المساعدة
"""
        return text
    
    @staticmethod
    def format_notification(notification: Dict) -> str:
        """Format a single notification"""
        n_type = notification.get('notification_type', 'general')
        title = notification.get('title', 'إشعار')
        message = notification.get('message', '')
        created = notification.get('created_at', '')
        n_id = notification.get('id')
        
        # Parse date
        if isinstance(created, str):
            try:
                dt = datetime.strptime(created, '%Y-%m-%d %H:%M:%S.%f')
                date_str = dt.strftime('%Y-%m-%d %H:%M')
            except:
                date_str = created[:16]
        else:
            date_str = ''
        
        # Emoji based on type
        emoji_map = {
            'leave_approved': '✅',
            'leave_rejected': '❌',
            'leave_request': '📋',
            'permission_approved': '✅',
            'permission_rejected': '❌',
            'permission_request': '📋',
            'salary': '💰',
            'schedule': '📅',
            'advance_approved': '✅',
            'advance_rejected': '❌',
            'advance_request': '💰',
            'general': '🔔'
        }
        
        emoji = emoji_map.get(n_type, '🔔')
        
        # Build message
        formatted = f"{emoji} <b>{title}</b>\n\n{message}\n\n📅 {date_str}"
        
        if n_id:
            formatted += f"\n\n<i>لتعليم كمقروء:</i> /read_{n_id}"
        
        return formatted
    
    @staticmethod
    def format_balance(balance: Dict) -> str:
        """Format user balance"""
        leave = balance.get('leave_balance', 0)
        permission = balance.get('permission_balance', 0)
        advance = balance.get('advance_balance', 0)
        updated = balance.get('last_updated', '')
        
        if updated:
            try:
                dt = datetime.strptime(updated, '%Y-%m-%d %H:%M:%S.%f')
                updated_str = dt.strftime('%Y-%m-%d')
            except:
                updated_str = updated[:10]
        else:
            updated_str = 'غير معروف'
        
        text = f"""
📊 <b>رصيدك الحالي</b>

🏖️ <b>إجازات:</b> {leave} يوم
🔑 <b>أذونات:</b> {permission} إذن
💰 <b>سلف:</b> {advance} جنيه

📅 <b>آخر تحديث:</b> {updated_str}

<i>ملاحظة: يتم تجديد الأذونات في 26 من كل شهر</i>
"""
        return text
    
    @staticmethod
    def format_leave_requests(requests: List[Dict]) -> str:
        """Format leave requests list"""
        if not requests:
            return "📭 لا توجد طلبات إجازة سابقة"
        
        text = "📋 <b>طلبات الإجازة الأخيرة</b>\n\n"
        
        for i, req in enumerate(requests[:5], 1):
            r_type = req.get('leave_type', 'غير محدد')
            start = req.get('start_date', '')[:10]
            status = req.get('status', '')
            days = req.get('total_days', 1)
            
            # Status emoji
            status_emoji = {
                'pending': '⏳',
                'approved': '✅',
                'rejected': '❌'
            }.get(status, '❓')
            
            text += f"{i}. {r_type} - {start} ({days} يوم) {status_emoji}\n"
        
        text += f"\n📌 لعرض التفاصيل: /leave_details"
        
        return text
    
    @staticmethod
    def format_permission_requests(requests: List[Dict]) -> str:
        """Format permission requests list"""
        if not requests:
            return "📭 لا توجد طلبات إذن سابقة"
        
        text = "📋 <b>طلبات الإذن الأخيرة</b>\n\n"
        
        for i, req in enumerate(requests[:5], 1):
            p_type = req.get('permission_type', 'غير محدد')
            date = req.get('date', '')[:10]
            status = req.get('status', '')
            
            # Status emoji
            status_emoji = {
                'pending': '⏳',
                'approved': '✅',
                'rejected': '❌'
            }.get(status, '❓')
            
            text += f"{i}. {p_type} - {date} {status_emoji}\n"
        
        text += f"\n📌 لعرض التفاصيل: /permission_details"
        
        return text
    
    @staticmethod
    def format_salary_slips(slips: List[Dict]) -> str:
        """Format salary slips list"""
        if not slips:
            return "📭 لا توجد شيتات مرتب سابقة"
        
        text = "💰 <b>شيتات المرتب</b>\n\n"
        
        for i, slip in enumerate(slips[:5], 1):
            month = slip.get('arabic_month', slip.get('month', ''))
            viewed = slip.get('is_viewed', False)
            viewed_emoji = '✅' if viewed else '🆕'
            
            text += f"{i}. {month} {viewed_emoji}\n"
            text += f"   /download_{slip['id']} - تحميل\n"
        
        return text
    
    @staticmethod
    def format_schedule(schedule: Dict, user_name: str = None) -> str:
        """Format weekly schedule"""
        details = schedule.get('details', [])
        
        if not details:
            return "📅 لا يوجد جدول للأسبوع الحالي"
        
        week_start = schedule.get('week_start', '')
        week_end = schedule.get('week_end', '')
        
        text = f"📅 <b>جدول العمل</b>\n"
        text += f"من {week_start[:10]} إلى {week_end[:10]}\n\n"
        
        # Group by day
        days = {}
        for d in details:
            day = d.get('day_name', '')
            if day not in days:
                days[day] = []
            days[day].append(d)
        
        # Display each day
        for day_name in ['السبت', 'الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']:
            if day_name in days:
                text += f"<b>{day_name}</b>\n"
                for d in days[day_name]:
                    job = d.get('job_title', '')
                    morning = d.get('morning_shift', '')
                    evening = d.get('evening_shift', '')
                    night = d.get('night_shift', '')
                    
                    # Highlight if user name matches
                    if user_name:
                        if user_name in morning:
                            morning = f"✅ {morning}"
                        if user_name in evening:
                            evening = f"✅ {evening}"
                        if user_name in night:
                            night = f"✅ {night}"
                    
                    text += f"  • {job}\n"
                    if morning:
                        text += f"    صباحي: {morning}\n"
                    if evening:
                        text += f"    مسائي: {evening}\n"
                    if night:
                        text += f"    سهر: {night}\n"
                text += "\n"
        
        return text
    
    @staticmethod
    def format_help(role: UserRole) -> str:
        """Format help message based on user role"""
        base_commands = """
<b>📚 الأوامر الأساسية</b>

/start - القائمة الرئيسية
/notifications - عرض الإشعارات
/read_all - تعليم الكل كمقروء
/balance - رصيد الإجازات والأذونات
/schedule - جدول العمل
/requests - طلباتي
/help - هذه المساعدة

<b>🔗 روابط النظام</b>
/dashboard - لوحة التحكم
/profile - ملفي الشخصي
"""

        employee_commands = """
<b>👤 أوامر الموظف</b>
/leave - طلب إجازة جديد
/permission - طلب إذن جديد
/leave_list - طلبات الإجازة
/permission_list - طلبات الإذن
/salary - شيتات المرتب
"""

        manager_commands = """
<b>👥 أوامر المدير</b>
/pending_leaves - الإجازات المعلقة
/pending_permissions - الأذونات المعلقة
/team - فريق العمل
/reports - تقارير سريعة
"""

        admin_commands = """
<b>⚙️ أوامر المسؤول</b>
/users - قائمة المستخدمين
/departments - الأقسام
/stats - إحصائيات النظام
/broadcast - إرسال رسالة للجميع
"""

        text = base_commands
        
        if role == UserRole.EMPLOYEE:
            text += employee_commands
        elif role == UserRole.MANAGER:
            text += employee_commands + manager_commands
        elif role == UserRole.ADMIN:
            text += employee_commands + manager_commands + admin_commands
        
        text += "\n<i>يمكنك استخدام الأزرار أسفل الشاشة للتنقل السريع</i>"
        
        return text


class TelegramBot:
    """Main Telegram Bot class with enhanced features"""
    
    def __init__(self, token: str, db_manager: DatabaseManager):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.db = db_manager
        self.offset = 0
        self.running = True
        
        # In-memory user sessions
        self.sessions: Dict[int, UserSession] = {}
        
        # Session timeout (30 minutes)
        self.session_timeout = 1800
        
        # Keyboard templates
        self.keyboards = self._create_keyboards()
    
    def _create_keyboards(self) -> Dict:
        """Create keyboard templates"""
        return {
            'main_employee': {
                'keyboard': [
                    [{'text': '📋 طلباتي'}, {'text': '📅 الجدول'}],
                    [{'text': '💰 المرتب'}, {'text': '📊 الرصيد'}],
                    [{'text': '🔔 الإشعارات'}, {'text': '🌐 الدخول للنظام'}],
                    [{'text': '❓ مساعدة'}]
                ],
                'resize_keyboard': True
            },
            'main_manager': {
                'keyboard': [
                    [{'text': '📋 طلباتي'}, {'text': '📅 الجدول'}],
                    [{'text': '⏳ الطلبات المعلقة'}, {'text': '👥 فريقي'}],
                    [{'text': '💰 المرتب'}, {'text': '📊 الرصيد'}],
                    [{'text': '🔔 الإشعارات'}, {'text': '🌐 الدخول للنظام'}],
                    [{'text': '❓ مساعدة'}]
                ],
                'resize_keyboard': True
            },
            'main_admin': {
                'keyboard': [
                    [{'text': '📋 طلباتي'}, {'text': '📅 الجدول'}],
                    [{'text': '⏳ الطلبات المعلقة'}, {'text': '👥 المستخدمين'}],
                    [{'text': '📊 إحصائيات'}, {'text': '📢 بث'}],
                    [{'text': '💰 المرتب'}, {'text': '📊 الرصيد'}],
                    [{'text': '🔔 الإشعارات'}, {'text': '🌐 الدخول للنظام'}],
                    [{'text': '❓ مساعدة'}]
                ],
                'resize_keyboard': True
            },
            'requests': {
                'keyboard': [
                    [{'text': '📋 الإجازات'}, {'text': '🔑 الأذونات'}],
                    [{'text': '💰 السلف'}, {'text': '🔙 رجوع'}]
                ],
                'resize_keyboard': True
            },
            'back': {
                'keyboard': [
                    [{'text': '🔙 رجوع'}]
                ],
                'resize_keyboard': True
            },
            'cancel': {
                'keyboard': [
                    [{'text': '❌ إلغاء'}]
                ],
                'resize_keyboard': True
            },
            'confirm': {
                'keyboard': [
                    [{'text': '✅ تأكيد'}, {'text': '❌ إلغاء'}]
                ],
                'resize_keyboard': True
            },
            'remove': {
                'remove_keyboard': True
            }
        }
    
    def _get_session(self, telegram_id: int) -> Optional[UserSession]:
        """Get or create user session"""
        # Clean expired sessions
        now = datetime.now()
        expired = [tid for tid, sess in self.sessions.items() 
                  if (now - sess.last_activity).total_seconds() > self.session_timeout]
        for tid in expired:
            del self.sessions[tid]
        
        # Get session
        session = self.sessions.get(telegram_id)
        
        # If not in memory, try to load from database
        if not session:
            user_data = self.db.get_user_by_telegram_id(telegram_id)
            if user_data:
                # Determine role
                if user_data.get('is_admin'):
                    role = UserRole.ADMIN
                elif user_data.get('is_manager'):
                    role = UserRole.MANAGER
                else:
                    role = UserRole.EMPLOYEE
                
                session = UserSession(
                    user_id=user_data['id'],
                    telegram_id=telegram_id,
                    username=user_data.get('username', ''),
                    name=user_data.get('name', ''),
                    role=role,
                    department_id=user_data.get('department_id'),
                    department_name=user_data.get('department_name')
                )
                self.sessions[telegram_id] = session
        
        if session:
            session.last_activity = datetime.now()
        
        return session
    
    def send_message(self, chat_id: int, text: str, 
                    parse_mode: str = "HTML",
                    keyboard: Optional[Dict] = None,
                    disable_web_page_preview: bool = True) -> bool:
        """Send message with optional keyboard"""
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview
            }
            
            if keyboard:
                payload["reply_markup"] = json.dumps(keyboard)
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Message sent to {chat_id}")
                return True
            else:
                logger.error(f"Failed to send message: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def send_photo(self, chat_id: int, photo_url: str, caption: str = "") -> bool:
        """Send photo"""
        try:
            url = f"{self.api_url}/sendPhoto"
            payload = {
                "chat_id": chat_id,
                "photo": photo_url,
                "caption": caption,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending photo: {e}")
            return False
    
    def send_document(self, chat_id: int, document_url: str, caption: str = "") -> bool:
        """Send document"""
        try:
            url = f"{self.api_url}/sendDocument"
            payload = {
                "chat_id": chat_id,
                "document": document_url,
                "caption": caption,
                "parse_mode": "HTML"
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending document: {e}")
            return False
    
    def answer_callback_query(self, callback_id: str, text: str = "", show_alert: bool = False) -> bool:
        """Answer callback query"""
        try:
            url = f"{self.api_url}/answerCallbackQuery"
            payload = {
                "callback_query_id": callback_id,
                "text": text,
                "show_alert": show_alert
            }
            response = requests.post(url, json=payload, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error answering callback: {e}")
            return False
    
    def edit_message_text(self, chat_id: int, message_id: int, text: str,
                         parse_mode: str = "HTML", keyboard: Optional[Dict] = None) -> bool:
        """Edit message text"""
        try:
            url = f"{self.api_url}/editMessageText"
            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": parse_mode
            }
            
            if keyboard:
                payload["reply_markup"] = json.dumps(keyboard)
            
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            return False
    
    # ==================== Command Handlers ====================
    
    def handle_start(self, chat_id: int, session: Optional[UserSession] = None, args: str = "") -> None:
        """Handle /start command"""
        if session:
            # Already logged in - show main menu
            self.show_main_menu(chat_id, session)
        else:
            # Not logged in - start login flow
            self.sessions[chat_id] = UserSession(
                user_id=0,
                telegram_id=chat_id,
                username="",
                name="",
                role=UserRole.EMPLOYEE,
                menu_state=MenuState.AWAITING_PHONE,
                temp_data={}
            )
            
            text = """
<b>مرحباً بك في بوت النظام 🎯</b>

للاستفادة من جميع الخدمات، يرجى تسجيل الدخول باستخدام:
• رقم الهاتف المسجل في النظام
• كلمة المرور الخاصة بك

<i>مثال:</i>
01012345678
كلمة المرور
"""
            self.send_message(chat_id, text, keyboard=self.keyboards['cancel'])
    
    def handle_help(self, chat_id: int, session: UserSession) -> None:
        """Handle /help command"""
        text = MessageFormatter.format_help(session.role)
        self.send_message(chat_id, text, keyboard=self.keyboards['main_employee'])
    
    def handle_notifications(self, chat_id: int, session: UserSession) -> None:
        """Handle /notifications command"""
        notifications = self.db.get_user_pending_notifications(session.user_id)
        
        if not notifications:
            text = "📭 لا توجد إشعارات جديدة"
            self.send_message(chat_id, text)
            return
        
        text = f"📬 لديك {len(notifications)} إشعار غير مقروء:\n\n"
        self.send_message(chat_id, text)
        
        for notif in notifications:
            msg = MessageFormatter.format_notification(notif)
            self.send_message(chat_id, msg)
            sleep(0.5)  # Rate limiting
    
    def handle_read_all(self, chat_id: int, session: UserSession) -> None:
        """Handle /read_all command"""
        notifications = self.db.get_user_pending_notifications(session.user_id)
        
        if not notifications:
            self.send_message(chat_id, "📭 لا توجد إشعارات غير مقروءة")
            return
        
        read_count = 0
        for notif in notifications:
            if self.db.mark_notification_read(notif['id']):
                read_count += 1
        
        self.send_message(chat_id, f"✅ تم تعليم {read_count} إشعار كمقروء")
    
    def handle_balance(self, chat_id: int, session: UserSession) -> None:
        """Handle /balance command"""
        balance = self.db.get_user_balance(session.user_id)
        
        if not balance:
            text = "❌ لا توجد معلومات عن الرصيد"
        else:
            text = MessageFormatter.format_balance(balance)
        
        self.send_message(chat_id, text)
    
    def handle_schedule(self, chat_id: int, session: UserSession) -> None:
        """Handle /schedule command"""
        if not session.department_id:
            self.send_message(chat_id, "❌ لم يتم تحديد القسم الخاص بك")
            return
        
        schedule = self.db.get_current_week_schedule(session.department_id)
        
        if not schedule:
            text = "📅 لا يوجد جدول معتمد للأسبوع الحالي"
        else:
            text = MessageFormatter.format_schedule(schedule, session.name)
        
        self.send_message(chat_id, text)
    
    def handle_requests(self, chat_id: int, session: UserSession) -> None:
        """Handle /requests command"""
        text = "📋 <b>اختر نوع الطلبات:</b>"
        self.send_message(chat_id, text, keyboard=self.keyboards['requests'])
    
    def handle_leave_requests(self, chat_id: int, session: UserSession) -> None:
        """Handle leave requests list"""
        requests = self.db.get_user_leave_requests(session.user_id)
        text = MessageFormatter.format_leave_requests(requests)
        self.send_message(chat_id, text)
    
    def handle_permission_requests(self, chat_id: int, session: UserSession) -> None:
        """Handle permission requests list"""
        requests = self.db.get_user_permission_requests(session.user_id)
        text = MessageFormatter.format_permission_requests(requests)
        self.send_message(chat_id, text)
    
    def handle_salary(self, chat_id: int, session: UserSession) -> None:
        """Handle salary command"""
        slips = self.db.get_user_salary_slips(session.user_id)
        text = MessageFormatter.format_salary_slips(slips)
        self.send_message(chat_id, text)
    
    def handle_dashboard_link(self, chat_id: int, session: UserSession) -> None:
        """Send dashboard link with auto-login"""
        pages = DeepLinkGenerator.get_page_urls(session.user_id, chat_id)
        
        text = f"""
🌐 <b>الدخول إلى النظام</b>

انقر على الرابط المناسب للدخول التلقائي:

🏠 <a href="{pages['dashboard']}">لوحة التحكم الرئيسية</a>
📅 <a href="{pages['schedule']}">جدول العمل</a>
📋 <a href="{pages['leave']}">طلبات الإجازات والأذونات</a>
💰 <a href="{pages['salary']}">شيتات المرتب</a>
👤 <a href="{pages['profile']}">الملف الشخصي</a>

<i>ملاحظة: الروابط صالحة لمدة 24 ساعة</i>
"""
        self.send_message(chat_id, text, disable_web_page_preview=False)
    
    def handle_read(self, chat_id: int, notification_id: str, session: UserSession) -> None:
        """Handle /read_123 command"""
        try:
            nid = int(notification_id)
            
            if self.db.mark_notification_read(nid):
                self.send_message(chat_id, f"✅ تم تعليم الإشعار {nid} كمقروء")
            else:
                self.send_message(chat_id, f"❌ لم يتم العثور على إشعار برقم {nid}")
        except ValueError:
            self.send_message(chat_id, "❌ رقم الإشعار غير صحيح")
    
    def handle_download(self, chat_id: int, slip_id: str, session: UserSession) -> None:
        """Handle /download_123 command"""
        try:
            slip_id = int(slip_id)
            
            # Get salary slip info
            # You would need to implement this in DatabaseManager
            # For now, send a placeholder
            self.send_message(chat_id, f"🔗 رابط التحميل:\n{FLASK_APP_URL}/download_salary_slip/{slip_id}")
            
        except ValueError:
            self.send_message(chat_id, "❌ رقم الشيت غير صحيح")
    
    def handle_manager_pending(self, chat_id: int, session: UserSession) -> None:
        """Handle pending requests for manager"""
        if session.role not in [UserRole.MANAGER, UserRole.ADMIN]:
            self.send_message(chat_id, "❌ هذه الخدمة للمديرين فقط")
            return
        
        pending = self.db.get_manager_pending_requests(session.user_id)
        
        text = f"""
⏳ <b>الطلبات المعلقة</b>

📋 إجازات: {pending['leaves']}
🔑 أذونات: {pending['permissions']}
💰 سلف: {pending['advances']}

📌 للاطلاع على التفاصيل:
<a href="{FLASK_APP_URL}/manager/leave_requests">الإجازات</a>
<a href="{FLASK_APP_URL}/manager/permission_requests">الأذونات</a>
<a href="{FLASK_APP_URL}/manager/advance_requests">السلف</a>
"""
        self.send_message(chat_id, text, disable_web_page_preview=False)
    
    def handle_team(self, chat_id: int, session: UserSession) -> None:
        """Handle team list for manager"""
        if session.role not in [UserRole.MANAGER, UserRole.ADMIN]:
            self.send_message(chat_id, "❌ هذه الخدمة للمديرين فقط")
            return
        
        if not session.department_id:
            self.send_message(chat_id, "❌ لم يتم تحديد القسم")
            return
        
        employees = self.db.get_department_employees(session.department_id)
        
        if not employees:
            text = "👥 لا يوجد موظفين في القسم"
        else:
            text = f"👥 <b>فريق العمل - {session.department_name}</b>\n\n"
            for i, emp in enumerate(employees[:10], 1):
                text += f"{i}. {emp['name']} - {emp.get('job_title', 'موظف')}\n"
        
        self.send_message(chat_id, text)
    
    def show_main_menu(self, chat_id: int, session: UserSession) -> None:
        """Show main menu based on user role"""
        name = session.name
        
        text = f"""
<b>مرحباً {name}! 👋</b>

اختر من القائمة أدناه:
"""
        if session.role == UserRole.ADMIN:
            keyboard = self.keyboards['main_admin']
        elif session.role == UserRole.MANAGER:
            keyboard = self.keyboards['main_manager']
        else:
            keyboard = self.keyboards['main_employee']
        
        self.send_message(chat_id, text, keyboard=keyboard)
    
    # ==================== Login Flow ====================
    
    def handle_login_phone(self, chat_id: int, phone: str, session: UserSession) -> None:
        """Handle phone number input during login"""
        # Clean phone number
        phone = phone.strip().replace(' ', '').replace('+', '')
        
        if not phone or len(phone) < 10:
            self.send_message(
                chat_id,
                "❌ رقم الهاتف غير صحيح. يرجى إدخال رقم صحيح (10 أرقام على الأقل)"
            )
            return
        
        # Store phone in session
        session.temp_data['phone'] = phone
        session.menu_state = MenuState.AWAITING_PASSWORD
        
        self.send_message(
            chat_id,
            "🔐 الآن أدخل كلمة المرور الخاصة بك:",
            keyboard=self.keyboards['cancel']
        )
    
    def handle_login_password(self, chat_id: int, password: str, session: UserSession) -> None:
        """Handle password input during login"""
        phone = session.temp_data.get('phone')
        
        if not phone:
            # Something went wrong, restart login
            session.menu_state = MenuState.AWAITING_PHONE
            self.send_message(
                chat_id,
                "❌ حدث خطأ. يرجى إدخال رقم الهاتف مرة أخرى:"
            )
            return
        
        # Authenticate
        user_data = self.db.authenticate_user(phone, password)
        
        if not user_data:
            self.send_message(
                chat_id,
                "❌ رقم الهاتف أو كلمة المرور غير صحيحة.\n"
                "يرجى المحاولة مرة أخرى باستخدام /start"
            )
            session.menu_state = MenuState.MAIN
            return
        
        # Save mapping
        session_token = DeepLinkGenerator.generate_token(user_data['id'], chat_id)
        self.db.save_telegram_mapping(
            user_data['id'], 
            chat_id, 
            phone,
            session_token
        )
        
        # Update session
        session.user_id = user_data['id']
        session.username = user_data['username']
        session.name = user_data['name']
        session.role = user_data['role']
        session.department_id = user_data.get('department_id')
        session.department_name = user_data.get('department_name')
        session.menu_state = MenuState.MAIN
        session.temp_data = {}
        
        # Generate login URLs
        pages = DeepLinkGenerator.get_page_urls(session.user_id, chat_id)
        
        # Welcome message
        welcome = MessageFormatter.format_welcome(user_data, pages)
        self.send_message(chat_id, welcome, disable_web_page_preview=False)
        
        # Show main menu
        self.show_main_menu(chat_id, session)
        
        # Check for pending notifications
        pending = self.db.get_user_pending_notifications(session.user_id)
        if pending:
            self.send_message(
                chat_id,
                f"📬 لديك {len(pending)} إشعار غير مقروء.\n"
                "استخدم /notifications لعرضها"
            )
    
    # ==================== Button Handlers ====================
    
    def handle_button_click(self, chat_id: int, text: str, session: UserSession) -> None:
        """Handle button clicks from custom keyboards"""
        
        # Cancel button
        if text == '❌ إلغاء':
            session.menu_state = MenuState.MAIN
            session.temp_data = {}
            self.show_main_menu(chat_id, session)
            return
        
        # Back button
        if text == '🔙 رجوع':
            session.menu_state = MenuState.MAIN
            self.show_main_menu(chat_id, session)
            return
        
        # Main menu buttons
        if text == '🔔 الإشعارات':
            self.handle_notifications(chat_id, session)
        elif text == '📊 الرصيد':
            self.handle_balance(chat_id, session)
        elif text == '📅 الجدول':
            self.handle_schedule(chat_id, session)
        elif text == '💰 المرتب':
            self.handle_salary(chat_id, session)
        elif text == '🌐 الدخول للنظام':
            self.handle_dashboard_link(chat_id, session)
        elif text == '❓ مساعدة':
            self.handle_help(chat_id, session)
        elif text == '📋 طلباتي':
            self.handle_requests(chat_id, session)
        elif text == '⏳ الطلبات المعلقة':
            self.handle_manager_pending(chat_id, session)
        elif text == '👥 فريقي':
            self.handle_team(chat_id, session)
        elif text == '📋 الإجازات':
            self.handle_leave_requests(chat_id, session)
        elif text == '🔑 الأذونات':
            self.handle_permission_requests(chat_id, session)
        else:
            # Unknown button
            self.send_message(chat_id, f"❌ أمر غير معروف: {text}")
    
    # ==================== Main Processing ====================
    
    def process_update(self, update: Dict) -> None:
        """Process a single Telegram update"""
        try:
            # Check message type
            if 'message' in update:
                self._process_message(update['message'])
            elif 'callback_query' in update:
                self._process_callback(update['callback_query'])
                
        except Exception as e:
            logger.error(f"Error processing update: {e}")
    
    def _process_message(self, message: Dict) -> None:
        """Process a message update"""
        chat_id = message['chat']['id']
        
        # Get or create session
        session = self._get_session(chat_id)
        
        # Check if it's a text message
        if 'text' not in message:
            self.send_message(chat_id, "❌ يرجى إرسال نص فقط")
            return
        
        text = message['text'].strip()
        
        # Handle commands
        if text.startswith('/'):
            self._process_command(chat_id, text, session)
        else:
            # Handle based on menu state
            if session and session.menu_state == MenuState.AWAITING_PHONE:
                self.handle_login_phone(chat_id, text, session)
            elif session and session.menu_state == MenuState.AWAITING_PASSWORD:
                self.handle_login_password(chat_id, text, session)
            elif session:
                # Treat as button click
                self.handle_button_click(chat_id, text, session)
            else:
                # No session - start login
                self.handle_start(chat_id)
    
    def _process_command(self, chat_id: int, command: str, session: Optional[UserSession]) -> None:
        """Process a command"""
        # Parse command and args
        parts = command.split(' ', 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # Commands that don't require login
        if cmd == '/start' and not session:
            self.handle_start(chat_id)
            return
        
        # All other commands require login
        if not session:
            self.handle_start(chat_id)
            return
        
        # Handle special commands with args
        if cmd.startswith('/read_'):
            notif_id = cmd.replace('/read_', '')
            self.handle_read(chat_id, notif_id, session)
            return
        
        if cmd.startswith('/download_'):
            slip_id = cmd.replace('/download_', '')
            self.handle_download(chat_id, slip_id, session)
            return
        
        # Regular commands
        command_map = {
            '/start': lambda: self.show_main_menu(chat_id, session),
            '/help': lambda: self.handle_help(chat_id, session),
            '/notifications': lambda: self.handle_notifications(chat_id, session),
            '/read_all': lambda: self.handle_read_all(chat_id, session),
            '/balance': lambda: self.handle_balance(chat_id, session),
            '/schedule': lambda: self.handle_schedule(chat_id, session),
            '/requests': lambda: self.handle_requests(chat_id, session),
            '/leave_list': lambda: self.handle_leave_requests(chat_id, session),
            '/permission_list': lambda: self.handle_permission_requests(chat_id, session),
            '/salary': lambda: self.handle_salary(chat_id, session),
            '/dashboard': lambda: self.handle_dashboard_link(chat_id, session),
            '/pending_leaves': lambda: self.handle_manager_pending(chat_id, session),
            '/team': lambda: self.handle_team(chat_id, session),
        }
        
        handler = command_map.get(cmd)
        if handler:
            handler()
        else:
            self.send_message(chat_id, "❌ أمر غير معروف. استخدم /help للمساعدة")
    
    def _process_callback(self, callback: Dict) -> None:
        """Process a callback query"""
        callback_id = callback['id']
        chat_id = callback['message']['chat']['id']
        message_id = callback['message']['message_id']
        data = callback['data']
        
        # Answer callback to remove loading state
        self.answer_callback_query(callback_id)
        
        # Get session
        session = self._get_session(chat_id)
        if not session:
            self.edit_message_text(
                chat_id, message_id,
                "❌ الرجاء تسجيل الدخول أولاً باستخدام /start"
            )
            return
        
        # Process callback data
        if data.startswith('approve_'):
            # Approve request
            req_id = data.replace('approve_', '')
            self.send_message(chat_id, f"✅ تمت الموافقة على الطلب {req_id}")
        
        elif data.startswith('reject_'):
            # Reject request
            req_id = data.replace('reject_', '')
            self.send_message(chat_id, f"❌ تم رفض الطلب {req_id}")
        
        elif data == 'refresh':
            # Refresh data
            self.edit_message_text(
                chat_id, message_id,
                "🔄 جاري التحديث...",
                keyboard={'inline_keyboard': []}
            )
    
    def run(self) -> None:
        """Main bot loop"""
        logger.info("Starting Telegram bot...")
        
        while self.running:
            try:
                # Get updates
                url = f"{self.api_url}/getUpdates"
                params = {
                    "offset": self.offset,
                    "timeout": 30,
                    "allowed_updates": ["message", "callback_query"]
                }
                
                response = requests.get(url, params=params, timeout=35)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if data.get('ok') and data.get('result'):
                        for update in data['result']:
                            self.process_update(update)
                            self.offset = update['update_id'] + 1
                
                sleep(1)
                
            except requests.exceptions.Timeout:
                continue
                
            except requests.exceptions.ConnectionError:
                logger.error("Connection error, retrying in 10 seconds...")
                sleep(10)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                self.running = False
                break
                
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                sleep(5)
    
    def stop(self):
        """Stop the bot"""
        self.running = False
        logger.info("Bot stopped")


class WebhookServer:
    """Webhook server to receive notifications from Flask app"""
    
    def __init__(self, bot: TelegramBot, db_manager: DatabaseManager, port: int = 5002):
        self.bot = bot
        self.db = db_manager
        self.port = port
        self.running = False
    
    def start(self):
        """Start the webhook server"""
        from flask import Flask, request, jsonify
        
        app = Flask(__name__)
        
        @app.route('/webhook/notification', methods=['POST'])
        def notification_webhook():
            """Receive notification from Flask app"""
            try:
                data = request.json
                
                if not data:
                    return jsonify({'error': 'No data provided'}), 400
                
                notification_id = data.get('notification_id')
                
                if not notification_id:
                    return jsonify({'error': 'notification_id required'}), 400
                
                # Get notification details from database
                conn = self.db.get_connection()
                if not conn:
                    return jsonify({'error': 'Database error'}), 500
                
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT n.id, n.user_id, n.title, n.message, 
                               n.notification_type, n.created_at,
                               tm.telegram_id
                        FROM notifications n
                        JOIN telegram_mapping tm ON n.user_id = tm.user_id
                        WHERE n.id = ? AND tm.is_active = 1
                    """, (notification_id,))
                    
                    notification = cursor.fetchone()
                    
                    if not notification:
                        return jsonify({'status': 'no_telegram_user'}), 404
                    
                    notif_dict = dict(notification)
                    
                    # Send via bot
                    msg = MessageFormatter.format_notification(notif_dict)
                    success = self.bot.send_message(
                        notif_dict['telegram_id'],
                        msg
                    )
                    
                    if success:
                        return jsonify({'status': 'sent'}), 200
                    else:
                        return jsonify({'status': 'failed'}), 500
                        
                finally:
                    conn.close()
                    
            except Exception as e:
                logger.error(f"Webhook error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @app.route('/webhook/broadcast', methods=['POST'])
        def broadcast_webhook():
            """Broadcast message to all users"""
            try:
                data = request.json
                
                if not data:
                    return jsonify({'error': 'No data provided'}), 400
                
                message = data.get('message')
                notification_type = data.get('type', 'broadcast')
                
                if not message:
                    return jsonify({'error': 'message required'}), 400
                
                # Get all active Telegram users
                conn = self.db.get_connection()
                if not conn:
                    return jsonify({'error': 'Database error'}), 500
                
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT u.id, u.name, tm.telegram_id
                        FROM telegram_mapping tm
                        JOIN users u ON tm.user_id = u.id
                        WHERE tm.is_active = 1
                    """)
                    
                    users = cursor.fetchall()
                    
                    sent_count = 0
                    for user in users:
                        formatted_msg = f"📢 <b>إشعار عام</b>\n\n{message}"
                        if self.bot.send_message(user['telegram_id'], formatted_msg):
                            sent_count += 1
                        sleep(0.5)
                    
                    return jsonify({
                        'status': 'broadcast_sent',
                        'total_users': len(users),
                        'sent_count': sent_count
                    }), 200
                    
                finally:
                    conn.close()
                    
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @app.route('/health', methods=['GET'])
        def health():
            """Health check endpoint"""
            return jsonify({
                'status': 'running',
                'timestamp': datetime.now().isoformat()
            }), 200
        
        logger.info(f"Starting webhook server on port {self.port}")
        app.run(host='0.0.0.0', port=self.port, debug=False, threaded=True)


def create_required_tables(db_path: str):
    """Create required tables if they don't exist"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create telegram_mapping table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telegram_mapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            telegram_id INTEGER NOT NULL UNIQUE,
            phone_number TEXT NOT NULL,
            session_token TEXT,
            verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Add index for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_telegram_mapping_user 
        ON telegram_mapping(user_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_telegram_mapping_telegram 
        ON telegram_mapping(telegram_id)
    """)
    
    # Create telegram_sessions table for storing session data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telegram_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            telegram_id INTEGER NOT NULL,
            session_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (telegram_id) REFERENCES telegram_mapping(telegram_id)
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("Database tables created/verified")


def main():
    """Main entry point"""
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     Telegram Bot for HR System - Enhanced Version        ║
    ║                                                          ║
    ║     Features:                                            ║
    ║     • Phone + Password Login                             ║
    ║     • Deep Links with Auto-Login                         ║
    ║     • Interactive Menus                                  ║
    ║     • Real-time Notifications                            ║
    ║     • Salary Slips Download                              ║
    ║     • Schedule Viewing                                   ║
    ║     • Leave/Permission Requests                          ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Create required tables
    create_required_tables(DATABASE_PATH)
    
    # Initialize components
    db_manager = DatabaseManager(DATABASE_PATH)
    bot = TelegramBot(BOT_TOKEN, db_manager)
    
    # Start webhook server in a separate thread
    import threading
    webhook_server = WebhookServer(bot, db_manager, port=5002)
    webhook_thread = threading.Thread(target=webhook_server.start, daemon=True)
    webhook_thread.start()
    
    try:
        # Start bot polling
        bot.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        bot.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()