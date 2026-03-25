# schedules_sync.py - إصدار مصحح
import json
from datetime import datetime, date, timedelta
from sqlalchemy import or_
import hashlib
from sqlalchemy.orm import joinedload

def calculate_structure_hash(structure_json):
    """حساب بصمة الهيكل للتتبع"""
    if structure_json:
        return hashlib.sha256(structure_json.encode('utf-8')).hexdigest()
    return None

def get_department_structure(department_id):
    """الحصول على هيكل القسم"""
    from database import db_session
    from models import Department
    
    department = db_session.query(Department).get(department_id)
    if department and department.schedule_structure:
        return json.loads(department.schedule_structure)
    return None

def analyze_schedule_structure(schedule):
    """تحليل هيكل الجدول"""
    try:
        if not schedule.schedule_data:
            return 'empty', None
        
        data = json.loads(schedule.schedule_data)
        
        if isinstance(data, dict):
            if 'schedule' in data:
                return 'new_format', data
            else:
                return 'old_dict_format', data
        elif isinstance(data, list):
            return 'list_format', data
        else:
            return 'invalid', None
            
    except Exception as e:
        print(f"Error analyzing schedule {schedule.id}: {str(e)}")
        return 'error', None

def is_schedule_already_synced(schedule, department):
    """التحقق مما إذا كان الجدول مزامن بالفعل"""
    try:
        if not hasattr(schedule, 'is_generated_from_structure'):
            return False
        
        if not schedule.is_generated_from_structure:
            return False
        
        if not department.schedule_structure:
            return False  # تغيير: إذا لم يكن هناك هيكل، فهو ليس مزامناً
        
        # حساب البصمة الحالية
        current_hash = calculate_structure_hash(department.schedule_structure)
        
        if hasattr(schedule, 'structure_hash') and schedule.structure_hash:
            return schedule.structure_hash == current_hash
        
        return False
        
    except Exception as e:
        print(f"Error checking sync status for schedule {schedule.id}: {str(e)}")
        return False

def normalize_schedule_to_structure(schedule, department):
    """توحيد الجدول ليطابق هيكل القسم"""
    try:
        if not department.schedule_structure:
            print(f"القسم {department.name} ليس لديه هيكل")
            return None
        
        # تحليل هيكل القسم
        structure_data = json.loads(department.schedule_structure)
        
        # أيام الأسبوع
        days_of_week = ['السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
        
        # إنشاء الهيكل الجديد الموحد
        new_structure = {
            'department': department.name,
            'week_start_date': schedule.week_start_date.strftime('%Y-%m-%d'),
            'week_end_date': schedule.week_end_date.strftime('%Y-%m-%d'),
            'source': 'department_structure_v3',
            'structure_version': department.schedule_structure_version if hasattr(department, 'schedule_structure_version') else 1,
            'structure_hash': calculate_structure_hash(department.schedule_structure),
            'schedule': []
        }
        
        # تحليل البيانات الحالية للجدول
        current_data = {}
        if schedule.schedule_data:
            try:
                current_data = json.loads(schedule.schedule_data)
            except:
                current_data = {}
        
        # تعبئة الأيام من هيكل القسم
        for i, day_name in enumerate(days_of_week):
            current_date = schedule.week_start_date + timedelta(days=i)
            
            # البحث عن اليوم في هيكل القسم
            day_structure = find_day_in_department_structure(structure_data, day_name)
            
            if day_structure:
                # نسخ اليوم من هيكل القسم
                day_entry = day_structure.copy()
                day_entry['date'] = current_date.strftime('%Y-%m-%d')
                day_entry['day'] = day_name
                day_entry['department'] = department.name
            else:
                # إنشاء يوم افتراضي
                day_entry = {
                    'day': day_name,
                    'date': current_date.strftime('%Y-%m-%d'),
                    'department': department.name,
                    'morning_shift': '',
                    'evening_shift': '',
                    'night_shift': '',
                    'job': 'موظف'
                }
            
            # محاولة استخراج بيانات الموظفين من الجدول الحالي
            old_data = extract_shifts_from_current_schedule(current_data, day_name, department.id)
            if old_data:
                day_entry.update(old_data)
            
            new_structure['schedule'].append(day_entry)
        
        return new_structure
        
    except Exception as e:
        print(f"Error normalizing schedule {schedule.id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def find_day_in_department_structure(structure_data, day_name):
    """البحث عن يوم في هيكل القسم"""
    try:
        if isinstance(structure_data, dict) and 'schedule' in structure_data:
            for day in structure_data['schedule']:
                if isinstance(day, dict) and day.get('day') == day_name:
                    return day
        elif isinstance(structure_data, list):
            for day in structure_data:
                if isinstance(day, dict) and day.get('day') == day_name:
                    return day
        return None
    except:
        return None

def extract_shifts_from_current_schedule(current_data, day_name, department_id):
    """استخراج بيانات الموظفين من الجدول الحالي"""
    try:
        if not current_data:
            return {}
        
        extracted = {
            'morning_shift': '',
            'evening_shift': '',
            'night_shift': ''
        }
        
        # استخراج من الهيكل الجديد
        if isinstance(current_data, dict) and 'schedule' in current_data:
            for day_entry in current_data['schedule']:
                if isinstance(day_entry, dict) and day_entry.get('day') == day_name:
                    # نسخ بيانات الشيفتات إذا كانت موجودة
                    for field in ['morning_shift', 'evening_shift', 'night_shift', 'job']:
                        if field in day_entry and day_entry[field]:
                            extracted[field] = day_entry[field]
                    return extracted
        
        # استخراج من الهيكل القديم
        if isinstance(current_data, dict):
            morning_shifts = []
            evening_shifts = []
            night_shifts = []
            
            for emp_id, emp_schedule in current_data.items():
                if isinstance(emp_schedule, dict):
                    arabic_days = ['السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
                    day_index = arabic_days.index(day_name) if day_name in arabic_days else -1
                    
                    if day_index >= 0:
                        shift = emp_schedule.get(arabic_days[day_index], '')
                        if shift:
                            # الحصول على اسم الموظف
                            from database import db_session
                            from models import User
                            
                            try:
                                emp = db_session.query(User).get(int(emp_id))
                                emp_name = emp.name if emp else f"مستخدم {emp_id}"
                            except:
                                emp_name = f"مستخدم {emp_id}"
                            
                            if 'صباحي' in str(shift):
                                morning_shifts.append(emp_name)
                            elif 'مسائي' in str(shift):
                                evening_shifts.append(emp_name)
                            elif 'ليلي' in str(shift):
                                night_shifts.append(emp_name)
            
            # تجميع النتائج
            if morning_shifts:
                extracted['morning_shift'] = ', '.join(morning_shifts)
            if evening_shifts:
                extracted['evening_shift'] = ', '.join(evening_shifts)
            if night_shifts:
                extracted['night_shift'] = ', '.join(night_shifts)
        
        return extracted
        
    except Exception as e:
        print(f"Error extracting from current schedule: {str(e)}")
        return {}

def normalize_schedule_with_cached_data(schedule, department, cached_employee_data):
    """
    تطبيع الجدول مع البيانات المخزنة مؤقتاً
    """
    try:
        if not schedule.schedule_data:
            return None
        
        # تحليل بيانات الجدول الحالي
        schedule_data = json.loads(schedule.schedule_data)
        
        # الحصول على اسم القسم بشكل آمن
        department_name = department
        if isinstance(department, dict):
            department_name = department.get('name', f"القسم {schedule.department_id}")
        elif hasattr(department, 'name'):
            department_name = department.name
        else:
            department_name = f"القسم {schedule.department_id}"
        
        # تحديد نوع الهيكل وتحويله إلى الهيكل الموحد
        normalized_structure = {
            'department': department_name,
            'week_start_date': schedule.week_start_date.strftime('%Y-%m-%d'),
            'week_end_date': schedule.week_end_date.strftime('%Y-%m-%d'),
            'source': 'normalized_from_mixed',
            'schedule': []
        }
        
        # أيام الأسبوع
        days_of_week = ['السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
        
        for i, day_name in enumerate(days_of_week):
            current_date = schedule.week_start_date + timedelta(days=i)
            
            day_entry = {
                'day': day_name,
                'date': current_date.strftime('%Y-%m-%d'),
                'department': department_name,
                'morning_shift': '',
                'evening_shift': '',
                'night_shift': '',
                'job': 'موظف'
            }
            
            # استخراج البيانات من الهيكل القديم
            if isinstance(schedule_data, dict):
                # الهيكل القديم: {employee_id: {day: shift, ...}}
                morning_shifts = []
                evening_shifts = []
                night_shifts = []
                
                for emp_id, emp_schedule in schedule_data.items():
                    if isinstance(emp_schedule, dict):
                        # الحصول على اسم اليوم العربي
                        arabic_days = ['السبت', 'الأحد', 'الأثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
                        if i < len(arabic_days):
                            arabic_day = arabic_days[i]
                            shift = emp_schedule.get(arabic_day, '')
                            
                            if shift:
                                # الحصول على اسم الموظف من البيانات المخزنة مؤقتاً
                                emp_name = cached_employee_data.get(str(emp_id), f"مستخدم {emp_id}")
                                
                                if 'صباحي' in str(shift):
                                    morning_shifts.append(emp_name)
                                elif 'مسائي' in str(shift):
                                    evening_shifts.append(emp_name)
                                elif 'ليلي' in str(shift) or 'سهر' in str(shift):
                                    night_shifts.append(emp_name)
                
                if morning_shifts:
                    day_entry['morning_shift'] = ', '.join(morning_shifts)
                if evening_shifts:
                    day_entry['evening_shift'] = ', '.join(evening_shifts)
                if night_shifts:
                    day_entry['night_shift'] = ', '.join(night_shifts)
                    
            elif isinstance(schedule_data, list):
                # الهيكل القديم: [{day: ..., shift: ...}]
                for item in schedule_data:
                    if isinstance(item, dict):
                        item_day = item.get('day') or item.get('اليوم')
                        if item_day == day_name:
                            # استخراج الشيفتات
                            if item.get('morning_shift'):
                                day_entry['morning_shift'] = item['morning_shift']
                            if item.get('evening_shift'):
                                day_entry['evening_shift'] = item['evening_shift']
                            if item.get('night_shift'):
                                day_entry['night_shift'] = item['night_shift']
                            if item.get('job'):
                                day_entry['job'] = item['job']
                            break
            
            normalized_structure['schedule'].append(day_entry)
        
        return normalized_structure
        
    except Exception as e:
        print(f"خطأ في تطبيع الجدول {schedule.id}: {str(e)}")
        return None

def sync_all_schedules_with_department_structures(force=False):
    """مزامنة جميع الجداول مع هياكل الأقسام - نسخة محسنة"""
    from database import db_session
    from models import WeeklySchedule, Department, User
    
    try:
        print("=== بدء مزامنة جميع الجداول مع هياكل الأقسام ===")
        
        # تحسين: جلب البيانات في دفعات
        all_schedules = db_session.query(WeeklySchedule).options(
            joinedload(WeeklySchedule.department)
        ).all()
        
        # تجميع بيانات الأقسام مسبقاً
        department_map = {}
        departments = db_session.query(Department).all()
        for dept in departments:
            if dept.schedule_structure:
                department_map[dept.id] = {
                    'department': dept,
                    'structure_hash': calculate_structure_hash(dept.schedule_structure),
                    'structure_data': json.loads(dept.schedule_structure)
                }
        
        # تجميع بيانات الموظفين مسبقاً
        users = db_session.query(User).all()
        cached_employee_data = {str(user.id): user.name for user in users}
        
        synced_count = 0
        skipped_count = 0
        failed_count = 0
        
        for schedule in all_schedules:
            try:
                dept_id = schedule.department_id
                
                if dept_id not in department_map:
                    print(f"⚠️ قسم غير موجود للجدول {schedule.id}")
                    failed_count += 1
                    continue
                
                dept_info = department_map[dept_id]
                department = dept_info['department']
                current_hash = dept_info['structure_hash']
                
                # التحقق مما إذا كان الجدول مزامن بالفعل
                if not force and is_schedule_already_synced(schedule, department):
                    # تحسين: تحديث الهاش فقط إذا تغير
                    if (hasattr(schedule, 'structure_hash') and 
                        schedule.structure_hash != current_hash):
                        schedule.structure_hash = current_hash
                        db_session.flush()
                    
                    skipped_count += 1
                    continue
                
                # استخدام البيانات المحملة مسبقاً
                new_structure = normalize_schedule_with_cached_data(
                    schedule, 
                    department,  # تمرير كائن القسم وليس البيانات
                    cached_employee_data
                )
                
                if new_structure:
                    schedule.schedule_data = json.dumps(new_structure, ensure_ascii=False)
                    schedule.structure_hash = current_hash
                    schedule.is_generated_from_structure = True
                    
                    if hasattr(schedule, 'structure_version'):
                        schedule.structure_version = (
                            department.schedule_structure_version 
                            if hasattr(department, 'schedule_structure_version') 
                            else 1
                        )
                    
                    synced_count += 1
                    print(f"✓ تم مزامنة الجدول {schedule.id}")
                
            except Exception as e:
                print(f"❌ خطأ في مزامنة الجدول {schedule.id}: {str(e)}")
                failed_count += 1
                continue
        
        db_session.commit()
        print(f"=== تم مزامنة {synced_count} جدول، تخطي {skipped_count}، فشل {failed_count} جدول ===")
        return synced_count
        
    except Exception as e:
        db_session.rollback()
        print(f"❌ خطأ عام في المزامنة: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0

def create_future_schedules_from_structure():
    """إنشاء جداول مستقبلية من هياكل الأقسام"""
    from database import db_session
    from models import Department, WeeklySchedule
    
    try:
        print("=== بدء إنشاء الجداول المستقبلية من هياكل الأقسام ===")
        
        departments = db_session.query(Department).filter_by(auto_generate_schedule=True).all()
        created_count = 0
        
        # استخدام datetime بدلاً من date للمقارنة
        from datetime import datetime  # إضافة هذا الاستيراد
        
        # تاريخ بداية الأسبوع الحالي (السبت)
        today = datetime.now().date()  # تأكد من استخدام date() للحصول على التاريخ فقط
        days_since_saturday = (today.weekday() - 5) % 7
        current_week_start = today - timedelta(days=days_since_saturday)
        
        for department in departments:
            # التحقق من وجود هيكل
            if not department.schedule_structure:
                print(f"⚠️ القسم {department.name} ليس لديه هيكل")
                continue
            
            # إنشاء جداول للأسابيع القادمة
            for week_offset in range(1, 5):  # 4 أسابيع قادمة
                week_start_date = current_week_start + timedelta(days=7 * week_offset)
                week_end_date = week_start_date + timedelta(days=6)
                
                # التحقق من أن الأسبوع المستقبلي فقط (بعد اليوم)
                if week_start_date <= today:
                    continue  # تخطي الأسابيع الماضية أو الحالية
                
                # التحقق من عدم وجود جدول لهذا الأسبوع
                existing_schedule = db_session.query(WeeklySchedule).filter_by(
                    department_id=department.id,
                    week_start_date=week_start_date
                ).first()
                
                if not existing_schedule:
                    # إنشاء الجدول الجديد من هيكل القسم
                    schedule_data = create_schedule_from_structure(department, week_start_date)
                    
                    if schedule_data:
                        new_schedule = WeeklySchedule(
                            department_id=department.id,
                            week_start_date=week_start_date,
                            week_end_date=week_end_date,
                            schedule_data=json.dumps(schedule_data, ensure_ascii=False),
                            created_by=1,  # النظام
                            status='draft',
                            is_locked=False,
                            is_approved=False,
                            is_generated_from_structure=True,
                            structure_hash=calculate_structure_hash(department.schedule_structure)
                        )
                        
                        if hasattr(department, 'schedule_structure_version'):
                            new_schedule.structure_version = department.schedule_structure_version
                        
                        db_session.add(new_schedule)
                        created_count += 1
                        print(f"✓ تم إنشاء جدول للقسم {department.name} للأسبوع {week_start_date}")
        
        db_session.commit()
        print(f"=== تم إنشاء {created_count} جدول مستقبلي ===")
        return created_count
        
    except Exception as e:
        db_session.rollback()
        print(f"❌ خطأ في إنشاء الجداول المستقبلية: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0

def create_schedule_from_structure(department, week_start_date):
    """إنشاء جدول جديد من هيكل القسم"""
    try:
        if not department.schedule_structure:
            return None
        
        # تحليل هيكل القسم
        structure_data = json.loads(department.schedule_structure)
        days_of_week = ['السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
        
        # إنشاء الهيكل الجديد
        new_structure = {
            'department': department.name,
            'week_start_date': week_start_date.strftime('%Y-%m-%d'),
            'week_end_date': (week_start_date + timedelta(days=6)).strftime('%Y-%m-%d'),
            'source': 'structure_generated_v2',
            'structure_version': department.schedule_structure_version if hasattr(department, 'schedule_structure_version') else 1,
            'structure_hash': calculate_structure_hash(department.schedule_structure),
            'schedule': []
        }
        
        # تعبئة الأيام من هيكل القسم
        for i, day_name in enumerate(days_of_week):
            current_date = week_start_date + timedelta(days=i)
            
            # البحث عن اليوم في الهيكل
            day_structure = find_day_in_department_structure(structure_data, day_name)
            
            if day_structure:
                day_entry = day_structure.copy()
                day_entry['date'] = current_date.strftime('%Y-%m-%d')
                day_entry['day'] = day_name
                day_entry['department'] = department.name
            else:
                day_entry = {
                    'day': day_name,
                    'date': current_date.strftime('%Y-%m-%d'),
                    'department': department.name,
                    'morning_shift': '',
                    'evening_shift': '',
                    'night_shift': '',
                    'job': 'موظف'
                }
            
            new_structure['schedule'].append(day_entry)
        
        return new_structure
        
    except Exception as e:
        print(f"Error creating schedule from structure: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def force_sync_all_schedules():
    """إجبار مزامنة جميع الجداول"""
    return sync_all_schedules_with_department_structures(force=True)

def sync_department_schedules(dept_id, force=False):
    """مزامنة جداول قسم معين"""
    from database import db_session
    from models import Department, WeeklySchedule
    
    try:
        department = db_session.query(Department).get(dept_id)
        if not department:
            return False, "القسم غير موجود"
        
        if not department.schedule_structure:
            return False, f"القسم {department.name} ليس لديه هيكل"
        
        schedules = db_session.query(WeeklySchedule).filter_by(
            department_id=dept_id
        ).all()
        
        synced_count = 0
        
        for schedule in schedules:
            # التحقق مما إذا كان مزامن بالفعل
            if not force and is_schedule_already_synced(schedule, department):
                continue
            
            new_structure = normalize_schedule_to_structure(schedule, department)
            if new_structure:
                schedule.schedule_data = json.dumps(new_structure, ensure_ascii=False)
                
                # تحديث معلومات الهيكل
                new_hash = calculate_structure_hash(department.schedule_structure)
                
                if hasattr(schedule, 'structure_hash'):
                    schedule.structure_hash = new_hash
                
                schedule.is_generated_from_structure = True
                synced_count += 1
        
        db_session.commit()
        return True, f"تم مزامنة {synced_count} جدول للقسم {department.name}"
        
    except Exception as e:
        db_session.rollback()
        return False, f"خطأ في المزامنة: {str(e)}"