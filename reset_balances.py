import os
import sys
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# تأكد من ضبط مسار المشروع لاستيراد النماذج
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from models import EmployeeBalance, Notification, User
from database import db_session, init_db  # أو أي طريقة تستخدمها للاتصال

def reset_permission_balances(force=False):
    """
    إعادة تعيين رصيد الإذونات إلى 2 لجميع الموظفين.
    
    Args:
        force (bool): إذا كان True يتم الإعادة بغض النظر عن اليوم، 
                      وإلا يتم الإعادة فقط إذا كان اليوم 26 من الشهر.
    
    Returns:
        int: عدد الموظفين الذين تم تحديث أرصدتهم.
    """
    try:
        today = date.today()
        
        if force or today.day == 26:
            print(f"=== إعادة تعيين أرصدة الإذونات لشهر {today.strftime('%Y-%m')} (force={force}) ===")
            
            employee_balances = db_session.query(EmployeeBalance).all()
            reset_count = 0
            
            for balance in employee_balances:
                if balance.permission_balance != 2:
                    old_balance = balance.permission_balance
                    balance.permission_balance = 2
                    balance.last_updated = datetime.now()
                    reset_count += 1
                    
                    print(f"تم إعادة تعيين رصيد المستخدم {balance.user_id}: {old_balance} -> 2")
                    
                    # إرسال إشعار للموظف
                    notification = Notification(
                        user_id=balance.user_id,
                        title='تم تجديد رصيد الإذونات',
                        message=f'تم تجديد رصيد الإذونات الخاص بك إلى 2 إذن لشهر {today.strftime("%Y-%m")}',
                        notification_type='balance_reset',
                        action_url='/user/dashboard'  # يمكن تعديل الرابط
                    )
                    db_session.add(notification)
            
            db_session.commit()
            print(f"تم تحديث {reset_count} موظف.")
            return reset_count
        else:
            print(f"اليوم {today.day} ليس 26، لم يتم تنفيذ إعادة التعيين.")
            return 0
            
    except Exception as e:
        print(f"خطأ: {e}")
        db_session.rollback()
        return 0

if __name__ == '__main__':
    # تهيئة قاعدة البيانات إذا لزم الأمر
    init_db()
    # تنفيذ الإعادة (force=True لتجاوز شرط اليوم)
    reset_permission_balances(force=True)