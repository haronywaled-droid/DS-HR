from database import init_db, db_session
from sqlalchemy import inspect, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_job_code_column():
    """إضافة عمود job_code إلى جدول schedule_structure_rows"""
    try:
        # استخدام inspect بدلاً من run_callable
        inspector = inspect(db_session.bind)
        
        # الحصول على أسماء الأعمدة في الجدول
        columns = inspector.get_columns('schedule_structure_rows')
        column_names = [col['name'] for col in columns]
        
        logger.info(f"الأعمدة الموجودة: {column_names}")
        
        if 'job_code' not in column_names:
            logger.info("جاري إضافة عمود job_code...")
            
            # إضافة العمود باستخدام SQL مباشر
            db_session.execute(text(
                "ALTER TABLE schedule_structure_rows ADD COLUMN job_code VARCHAR(20)"
            ))
            db_session.commit()
            logger.info("✅ تم إضافة عمود job_code بنجاح")
        else:
            logger.info("✅ عمود job_code موجود بالفعل")
            
    except Exception as e:
        logger.error(f"❌ خطأ في إضافة العمود: {e}")
        db_session.rollback()
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    init_db()
    add_job_code_column()
    print("تم الانتهاء من تحديث قاعدة البيانات")