import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import User, Department, Base
from werkzeug.security import generate_password_hash
import sys
import os

# إضافة المسار الحالي إلى sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def import_departments_from_excel(file_path):
    """
    استيراد الأقسام من ملف Excel
    
    Args:
        file_path (str): مسار ملف Excel
        
    Returns:
        dict: نتائج الاستيراد
    """
    
    try:
        # قراءة ملف Excel للأقسام - استخدام الورقة الأولى افتراضياً
        df = pd.read_excel(file_path, sheet_name=0)  # الورقة الأولى
        
        # التحقق من العناوين - استخدام العناوين العربية من بياناتك
        required_headers = ['اسم القسم']
        
        # التحقق من وجود العناوين المطلوبة (بأي لغة)
        available_headers = df.columns.tolist()
        missing_headers = []
        
        for req_header in required_headers:
            if req_header not in available_headers:
                # البحث عن مرادفات محتملة
                if 'القسم' in str(available_headers):
                    # إذا كان هناك عمود يحتوي على كلمة "القسم"، اعتبره العمود المطلوب
                    continue
                missing_headers.append(req_header)
        
        if missing_headers:
            return {
                'success': False,
                'message': f'عناوين مفقودة في ورقة الأقسام: {", ".join(missing_headers)}',
                'available_headers': available_headers
            }
        
        # الاتصال بقاعدة البيانات
        from database import engine
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # إحصائيات
        stats = {
            'total': len(df),
            'success': 0,
            'failed': 0,
            'errors': [],
            'department_map': {}  # خريطة أسماء الأقسام إلى IDs
        }
        
        # تحديد اسم عمود الأقسام
        dept_column = 'اسم القسم'
        for col in df.columns:
            if 'القسم' in str(col):
                dept_column = col
                break
        
        # معالجة كل قسم
        for index, row in df.iterrows():
            try:
                department_name = str(row[dept_column]).strip()
                
                # تخطي الصفوف الفارغة
                if not department_name or department_name == 'nan':
                    continue
                
                # التحقق من أن اسم القسم غير مكرر
                existing_dept = session.query(Department).filter_by(name=department_name).first()
                if existing_dept:
                    stats['department_map'][department_name] = existing_dept.id
                    print(f"✓ القسم موجود مسبقاً: {department_name}")
                    stats['success'] += 1
                    continue
                
                # إنشاء كائن القسم
                department = Department(
                    name=department_name,
                    created_by=1  # يمكن تعديله حسب المستخدم المسؤول
                )
                
                # إضافة القسم إلى قاعدة البيانات
                session.add(department)
                session.flush()  # للحصول على ID
                
                stats['department_map'][department_name] = department.id
                stats['success'] += 1
                print(f"✓ تم إضافة القسم: {department.name} (ID: {department.id})")
                
            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append(f"الصف {index + 2}: {str(e)}")
                print(f"✗ خطأ في الصف {index + 2}: {str(e)}")
        
        # حفظ التغييرات
        session.commit()
        session.close()
        
        return {
            'success': True,
            'message': f'تم استيراد {stats["success"]} من أصل {stats["total"]} قسم',
            'stats': stats
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f'خطأ في قراءة ورقة الأقسام: {str(e)}'
        }

def import_users_from_excel(file_path, department_map):
    """
    استيراد المستخدمين من ملف Excel باستخدام خريطة الأقسام
    
    Args:
        file_path (str): مسار ملف Excel
        department_map (dict): خريطة أسماء الأقسام إلى IDs
        
    Returns:
        dict: نتائج الاستيراد
    """
    
    try:
        # قراءة ملف Excel للمستخدمين - استخدام الورقة الثانية
        try:
            df = pd.read_excel(file_path, sheet_name=1)  # الورقة الثانية
        except:
            df = pd.read_excel(file_path, sheet_name='المستخدمين')
        
        print(f"العناوين المتاحة في ورقة المستخدمين: {df.columns.tolist()}")
        
        # التعرف على العناوين تلقائياً بناء على البيانات
        header_mapping = {}
        available_headers = df.columns.tolist()
        
        for header in available_headers:
            header_str = str(header)
            if 'المستخدم' in header_str:
                header_mapping['username'] = header
            elif 'الاسم' in header_str and 'الكامل' in header_str:
                header_mapping['name'] = header
            elif 'كلمة' in header_str and 'المرور' in header_str:
                header_mapping['password'] = header
            elif 'نظام' in header_str:
                header_mapping['is_admin'] = header
            elif 'قسم' in header_str and 'مدير' in header_str:
                header_mapping['is_manager'] = header
            elif 'القسم' in header_str:
                header_mapping['department_name'] = header
        
        # إذا لم يتم التعرف على العناوين، استخدم الفهرس
        if not header_mapping.get('username'):
            header_mapping['username'] = available_headers[0] if len(available_headers) > 0 else 0
        if not header_mapping.get('name'):
            header_mapping['name'] = available_headers[1] if len(available_headers) > 1 else 1
        if not header_mapping.get('password'):
            header_mapping['password'] = available_headers[2] if len(available_headers) > 2 else 2
        if not header_mapping.get('department_name'):
            header_mapping['department_name'] = available_headers[5] if len(available_headers) > 5 else 5
        
        print(f"تعيين العناوين: {header_mapping}")
        
        # الاتصال بقاعدة البيانات
        from database import engine
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # إحصائيات
        stats = {
            'total': len(df),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        # معالجة كل صف
        for index, row in df.iterrows():
            try:
                # الحصول على البيانات باستخدام التعيين الصحيح
                username = str(row[header_mapping['username']]).strip()
                name = str(row[header_mapping['name']]).strip()
                password = str(row[header_mapping['password']]).strip()
                
                # تخطي الصفوف الفارغة
                if pd.isna(username) or pd.isna(name) or not username or not name:
                    continue
                
                # إذا كان كلمة المرور فارغة، استخدم اسم المستخدم ككلمة مرور
                if pd.isna(password) or not password:
                    password = username
                
                # التحقق من أن اسم المستخدم غير مكرر
                existing_user = session.query(User).filter_by(username=username).first()
                if existing_user:
                    stats['errors'].append(f"الصف {index + 2}: اسم المستخدم '{username}' موجود مسبقاً")
                    stats['failed'] += 1
                    continue
                
                # الحصول على department_id من اسم القسم
                department_id = None
                department_name = ""
                
                if header_mapping['department_name'] in row:
                    dept_value = row[header_mapping['department_name']]
                    if not pd.isna(dept_value):
                        department_name = str(dept_value).strip()
                        if department_name in department_map:
                            department_id = department_map[department_name]
                        else:
                            stats['errors'].append(f"الصف {index + 2}: القسم '{department_name}' غير موجود")
                            stats['failed'] += 1
                            continue
                
                # الحصول على is_admin و is_manager
                is_admin = False
                is_manager = False
                
                if header_mapping.get('is_admin') in row:
                    admin_value = row[header_mapping['is_admin']]
                    is_admin = convert_to_boolean(admin_value)
                
                if header_mapping.get('is_manager') in row:
                    manager_value = row[header_mapping['is_manager']]
                    is_manager = convert_to_boolean(manager_value)
                
                # إنشاء كائن المستخدم
                user = User(
                    username=username,
                    name=name,
                    password_hash=generate_password_hash(password),
                    is_admin=is_admin,
                    is_manager=is_manager,
                    department_id=department_id
                )
                
                # إضافة المستخدم إلى قاعدة البيانات
                session.add(user)
                session.flush()
                
                stats['success'] += 1
                print(f"✓ تم إضافة المستخدم: {user.username} - {user.name} - القسم: {department_name or 'لا يوجد'}")
                
            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append(f"الصف {index + 2}: {str(e)}")
                print(f"✗ خطأ في الصف {index + 2}: {str(e)}")
                import traceback
                print(traceback.format_exc())
        
        # حفظ التغييرات
        session.commit()
        session.close()
        
        return {
            'success': True,
            'message': f'تم استيراد {stats["success"]} من أصل {stats["total"]} مستخدم',
            'stats': stats
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f'خطأ في قراءة ورقة المستخدمين: {str(e)}'
        }

def convert_to_boolean(value):
    """تحويل القيمة إلى boolean"""
    if pd.isna(value) or value is None:
        return False
    
    if isinstance(value, bool):
        return value
    
    value_str = str(value).strip().lower()
    true_values = ['نعم', 'yes', 'true', '1', 'y', '✓', 'true']
    return value_str in true_values

def convert_to_int(value):
    """تحويل القيمة إلى integer"""
    if pd.isna(value) or value is None:
        return None
    
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def create_template_from_your_data():
    """إنشاء ملف Excel بناء على البيانات التي قدمتها"""
    
    # بيانات الأقسام من طلبك
    departments_data = {
        'اسم القسم': [
            'الاطباء الاستشاريين',
            'أطباء السونار',
            'أطباء المركز',
            'الفنيين',
            'التمريض',
            'مساعدات التمريض',
            'التقارير',
            'التسويق',
            'الاستقبال',
            'الموارد البشرية',
            'الحسابات',
            'الخدمات المعاونة'
        ],
        'اسم المدير': ['', '', '', '', '', '', '', '', '', '', '', '']
    }
    
    # بيانات المستخدمين من طلبك (عينة صغيرة)
    users_data = {
        'اسم المستخدم': ['3', '9', '12', '13', '14'],
        'الاسم الكامل': [
            'د/ رامى إدوارد أبراهيم',
            'د/ سميح شكرى صبحى شاروبيم', 
            'د/ أحمد عبدالمعز السيد جمعه',
            'د/ شريف علي زكي علي عمر',
            'د/ أحمد بدر الدين عباس البهائى'
        ],
        'كلمة المرور': ['273010', '272122', '278010', '272030', '280070'],
        'مدير نظام': ['لا', 'لا', 'لا', 'لا', 'لا'],
        'مدير قسم': ['لا', 'لا', 'لا', 'لا', 'لا'],
        'اسم القسم': [
            'الاطباء الاستشاريين',
            'أطباء السونار',
            'أطباء السونار',
            'أطباء السونار', 
            'أطباء المركز'
        ]
    }
    
    # حفظ الملف
    file_name = "بيانات_الموظفين_الجاهزة.xlsx"
    with pd.ExcelWriter(file_name, engine='openpyxl') as writer:
        # ورقة الأقسام
        df_dept = pd.DataFrame(departments_data)
        df_dept.to_excel(writer, sheet_name='الأقسام', index=False)
        
        # ورقة المستخدمين
        df_users = pd.DataFrame(users_data)
        df_users.to_excel(writer, sheet_name='المستخدمين', index=False)
    
    print(f"✓ تم إنشاء الملف: {file_name}")
    print("  - يحتوي على هيكل البيانات الذي قدمته")

def main_import_process(file_path):
    """عملية الاستيراد الرئيسية"""
    print("جاري استيراد الأقسام أولاً...")
    dept_result = import_departments_from_excel(file_path)
    
    if not dept_result['success']:
        print(f"✗ فشل استيراد الأقسام: {dept_result['message']}")
        if 'available_headers' in dept_result:
            print(f"   العناوين المتاحة: {dept_result['available_headers']}")
        return dept_result
    
    print(f"✓ {dept_result['message']}")
    
    # الحصول على خريطة الأقسام
    department_map = dept_result['stats']['department_map']
    print(f"   الأقسام المستوردة: {list(department_map.keys())}")
    
    print("\nجاري استيراد المستخدمين...")
    users_result = import_users_from_excel(file_path, department_map)
    
    print(f"\n{'='*50} النتائج النهائية {'='*50}")
    print(f"الأقسام: {dept_result['message']}")
    print(f"المستخدمين: {users_result['message']}")
    
    # عرض الأخطاء إذا وجدت
    all_errors = dept_result['stats']['errors'] + users_result['stats']['errors']
    if all_errors:
        print(f"\nالأخطاء ({len(all_errors)}):")
        for error in all_errors[:15]:  # عرض أول 15 خطأ فقط
            print(f"  - {error}")
        if len(all_errors) > 15:
            print(f"  ... و{len(all_errors) - 15} خطأ آخر")
    
    return {
        'success': users_result['success'],
        'departments': dept_result,
        'users': users_result
    }

if __name__ == "__main__":
    print("=" * 70)
    print("أداة استيراد الأقسام والمستخدمين من Excel - النسخة المعدلة")
    print("=" * 70)
    
    while True:
        print("\nاختر الخيار:")
        print("1 - استيراد الأقسام والمستخدمين من ملف Excel")
        print("2 - إنشاء ملف قالب بناء على بياناتك")
        print("3 - الخروج")
        
        choice = input("\nادخل رقم الخيار: ").strip()
        
        if choice == '1':
            file_path = input("ادخل مسار ملف Excel: ").strip()
            
            if not os.path.exists(file_path):
                print("✗ الملف غير موجود!")
                continue
            
            main_import_process(file_path)
        
        elif choice == '2':
            create_template_from_your_data()
        
        elif choice == '3':
            print("مع السلامة!")
            break
        
        else:
            print("✗ خيار غير صحيح!")