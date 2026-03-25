# update_existing_schedules.py
from database import db_session
from models import Department, WeeklySchedule
import json
from datetime import datetime, timedelta

def update_all_existing_schedules():
    """تحديث جميع الجداول الحالية لتصبح بنفس هيكل القسم"""
    try:
        print("=== بدء تحديث جميع الجداول الحالية ===")
        
        departments = db_session.query(Department).all()
        updated_count = 0
        
        for department in departments:
            if not department.schedule_structure:
                print(f"⚠️ القسم {department.name} ليس لديه هيكل")
                continue
            
            # الحصول على جميع جداول القسم
            schedules = db_session.query(WeeklySchedule).filter_by(
                department_id=department.id
            ).all()
            
            print(f"معالجة {len(schedules)} جدول للقسم {department.name}")
            
            for schedule in schedules:
                try:
                    # إنشاء جدول جديد من هيكل القسم
                    new_schedule_data = create_schedule_from_department_structure(
                        department, schedule.week_start_date
                    )
                    
                    if new_schedule_data:
                        # استبدال البيانات القديمة
                        schedule.schedule_data = json.dumps(new_schedule_data, ensure_ascii=False)
                        
                        # تحديث معلومات المزامنة
                        schedule.is_generated_from_structure = True
                        schedule.structure_version = department.schedule_structure_version
                        schedule.structure_hash = calculate_structure_hash(department.schedule_structure)
                        schedule.is_auto_synced = True
                        schedule.last_sync_check = datetime.now()
                        schedule.sync_status = 'synced'
                        
                        updated_count += 1
                        print(f"  ✓ تم تحديث الجدول {schedule.id} للفترة {schedule.week_start_date}")
                        
                except Exception as e:
                    print(f"  ❌ خطأ في تحديث الجدول {schedule.id}: {str(e)}")
                    continue
        
        db_session.commit()
        print(f"=== تم تحديث {updated_count} جدول ===")
        return updated_count
        
    except Exception as e:
        db_session.rollback()
        print(f"❌ خطأ في التحديث: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0

def create_schedule_from_department_structure(department, week_start_date):
    """إنشاء جدول من هيكل القسم"""
    try:
        if not department.schedule_structure:
            return None
        
        # تحليل هيكل القسم
        structure_data = json.loads(department.schedule_structure)
        
        # أيام الأسبوع
        days_of_week = ['السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
        
        # إنشاء هيكل الجدول
        schedule_data = {
            'department': department.name,
            'week_start_date': week_start_date.strftime('%Y-%m-%d'),
            'week_end_date': (week_start_date + timedelta(days=6)).strftime('%Y-%m-%d'),
            'source': 'department_structure',
            'structure_version': department.schedule_structure_version,
            'schedule': []
        }
        
        # تعبئة الأيام من الهيكل
        for i, day_name in enumerate(days_of_week):
            current_date = week_start_date + timedelta(days=i)
            
            day_entry = {
                'day': day_name,
                'date': current_date.strftime('%Y-%m-%d'),
                'department': department.name,
                'morning_shift': '',
                'evening_shift': '',
                'night_shift': '',
                'job': 'موظف'
            }
            
            # إذا كان هناك هيكل محدد، استخدمه
            if isinstance(structure_data, dict) and 'schedule' in structure_data:
                for template_day in structure_data['schedule']:
                    if isinstance(template_day, dict) and template_day.get('day') == day_name:
                        # نسخ البيانات من الهيكل
                        day_entry.update({
                            'morning_shift': template_day.get('morning_shift', ''),
                            'evening_shift': template_day.get('evening_shift', ''),
                            'night_shift': template_day.get('night_shift', ''),
                            'job': template_day.get('job', 'موظف')
                        })
                        break
            
            schedule_data['schedule'].append(day_entry)
        
        return schedule_data
        
    except Exception as e:
        print(f"❌ خطأ في إنشاء الجدول: {str(e)}")
        return None

def calculate_structure_hash(structure_json):
    """حساب بصمة الهيكل"""
    import hashlib
    if structure_json:
        return hashlib.sha256(structure_json.encode('utf-8')).hexdigest()
    return None

if __name__ == '__main__':
    update_all_existing_schedules()