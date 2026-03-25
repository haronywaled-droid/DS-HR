import pandas as pd
from datetime import datetime, date
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import database configuration
try:
    from database import engine, SessionLocal
    session = SessionLocal()
except ImportError:
    # Create database connection if database.py doesn't exist
    DATABASE_URL = "sqlite:///hr_system.db"  # Change this to your database URL
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

# Import models
try:
    from models import User, EmployeeData
    print("✅ تم استيراد النماذج بنجاح")
except ImportError as e:
    print(f"❌ خطأ في استيراد النماذج: {e}")
    print("🔧 جاري محاولة استيراد بديلة...")
    # Try to import directly by executing the models file
    import importlib.util
    import types
    
    # Create a temporary module to avoid conflicts
    models_module = types.ModuleType('models_module')
    
    # Read and execute the models file with a different module name
    with open('models.py', 'r', encoding='utf-8') as f:
        models_code = f.read()
    
    # Replace the module name to avoid conflicts
    models_code = models_code.replace('from database import Base', 'from sqlalchemy.ext.declarative import declarative_base\nBase = declarative_base()')
    
    # Execute the code in the temporary module
    exec(models_code, models_module.__dict__)
    
    # Get the classes we need
    User = models_module.User
    EmployeeData = models_module.EmployeeData
    print("✅ تم استيراد النماذج باستخدام الطريقة البديلة")

def safe_date_conversion(date_str):
    """Convert string to date object safely"""
    if pd.isna(date_str) or date_str is None:
        return None
    
    if isinstance(date_str, (datetime, date)):
        return date_str.date() if isinstance(date_str, datetime) else date_str
    
    date_str = str(date_str).strip()
    if not date_str or date_str.lower() in ['nan', 'nat', 'null', 'none']:
        return None
    
    # Try different date formats
    date_formats = [
        '%Y-%m-%d',
        '%d/%m/%Y', 
        '%d-%m-%Y',
        '%Y/%m/%d',
        '%m/%d/%Y'
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    # If all parsing fails, return None
    return None

def fix_numeric_string(value):
    """Fix numeric strings that Excel corrupted with decimal points"""
    if pd.isna(value) or value is None:
        return None
    
    # Convert to string first
    value_str = str(value).strip()
    
    # Remove any decimal points and zeros after decimal
    if '.' in value_str:
        value_str = value_str.split('.')[0]
    
    # Remove any non-digit characters (keep only numbers)
    value_str = ''.join(filter(str.isdigit, value_str))
    
    return value_str if value_str else None

def import_employee_data_from_excel(excel_file_path):
    """
    Import employee data from Excel file with Arabic headers into the database
    """
    
    # Mapping from Arabic headers to database field names
    header_mapping = {
        'اسم المستخدم': 'username',
        'الاسم بالعربية': 'arabic_name',
        'الاسم بالإنجليزية': 'english_name',
        'الرقم القومي': 'national_id',
        'تاريخ إصدار البطاقة': 'id_issue_date',
        'تاريخ الميلاد': 'birth_date',
        'العمر': 'age',
        'رقم الواتساب': 'whatsapp',
        'رقم الهاتف': 'phone',
        'العنوان': 'address',
        'الحالة العسكرية': 'military_status',
        'الحالة الاجتماعية': 'marital_status',
        'المؤهل الدراسي': 'qualification',
        'سنة التخرج': 'graduation_year',
        'الدرجة': 'grade',
        'يعمل حالياً': 'has_work',
        'مكان العمل': 'workplace',
        'المسمى الوظيفي': 'job_title',
        'رقم التأمين': 'insurance_number',
        'الرقم الضريبي': 'tax_number',
        'اسم جهة الاتصال الأولى': 'emergency1_name',
        'هاتف جهة الاتصال الأولى': 'emergency1_phone',
        'عنوان جهة الاتصال الأولى': 'emergency1_address',
        'صلة القرابة للاتصال الأول': 'emergency1_relation',
        'اسم جهة الاتصال الثانية': 'emergency2_name',
        'هاتف جهة الاتصال الثانية': 'emergency2_phone',
        'عنوان جهة الاتصال الثانية': 'emergency2_address',
        'صلة القرابة للاتصال الثاني': 'emergency2_relation',
        'ترخيص المهنة': 'profession_license',
        'بطاقة النقابة': 'union_card'
    }
    
    try:
        # Read Excel file - specify ALL columns as strings to prevent Excel corruption
        print(f"📖 جاري قراءة الملف: {excel_file_path}")
        df = pd.read_excel(excel_file_path, dtype=str)
        
        print(f"✅ تم قراءة {len(df)} سجل من الملف")
        print(f"📊 الأعمدة الموجودة: {list(df.columns)}")
        
        # Check if required columns exist
        required_columns = ['اسم المستخدم', 'الاسم بالعربية']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"❌ الأعمدة المطلوبة مفقودة: {missing_columns}")
            return 0, len(df), 0
        
        # Rename columns to English for processing
        df_english = df.rename(columns=header_mapping)
        
        # Keep only columns that exist in our mapping
        available_columns = [col for col in df_english.columns if col in header_mapping.values()]
        df_english = df_english[available_columns]
        
        success_count = 0
        error_count = 0
        skipped_count = 0
        missing_users_count = 0
        
        print("\n🔄 بدء استيراد البيانات إلى قاعدة البيانات...")
        
        for index, row in df_english.iterrows():
            try:
                username = row['username']
                
                if pd.isna(username) or str(username).strip() == '':
                    print(f"⚠️  السطر {index+2}: اسم المستخدم فارغ - تم تخطي السجل")
                    skipped_count += 1
                    continue
                
                username = str(username).strip()
                
                # Get user by username
                user = session.query(User).filter_by(username=username).first()
                
                if not user:
                    print(f"⏭️  السطر {index+2}: المستخدم '{username}' غير موجود في قاعدة البيانات - تم تخطي السجل")
                    missing_users_count += 1
                    continue
                
                # Check if employee data already exists for this user
                employee_data = session.query(EmployeeData).filter_by(user_id=user.id).first()
                
                if employee_data:
                    print(f"🔄 السطر {index+2}: تحديث بيانات المستخدم الحالي: {username}")
                    action = "updated"
                else:
                    print(f"➕ السطر {index+2}: إضافة بيانات جديدة للمستخدم: {username}")
                    employee_data = EmployeeData(user_id=user.id)
                    action = "created"
                
                # Update all fields - handle each field type appropriately
                for field in available_columns:
                    if field != 'username' and hasattr(employee_data, field):
                        value = row[field]
                        
                        # Handle empty values
                        if pd.isna(value) or value == 'nan' or value == 'None':
                            value = None
                        else:
                            # Handle different field types
                            if field in ['id_issue_date', 'birth_date']:
                                # Convert date fields to date objects
                                value = safe_date_conversion(value)
                            elif field in ['age', 'graduation_year']:
                                # Convert numeric fields to integers
                                try:
                                    value = int(float(value)) if value and value != 'nan' else None
                                except (ValueError, TypeError):
                                    value = None
                            elif field == 'has_work':
                                # Convert boolean field
                                value_str = str(value).strip().lower()
                                value = value_str in ['نعم', 'yes', 'true', '1', 'y']
                            elif field in ['national_id', 'whatsapp', 'phone', 'emergency1_phone', 'emergency2_phone']:
                                # Fix numeric strings corrupted by Excel
                                value = fix_numeric_string(value)
                            else:
                                # All other fields as strings
                                value = str(value).strip() if value and value != 'nan' else None
                        
                        setattr(employee_data, field, value)
                
                # Set update information
                employee_data.last_updated = datetime.now()
                employee_data.updated_by = "excel_import"
                
                # Calculate completion percentage
                completion_before = employee_data.completion_percentage
                employee_data.calculate_completion()
                completion_after = employee_data.completion_percentage
                
                if action == "created":
                    session.add(employee_data)
                
                success_count += 1
                print(f"✅ السطر {index+2}: تم {action} بيانات {username} (نسبة الإكمال: {completion_before}% → {completion_after}%)")
                
            except Exception as e:
                print(f"❌ السطر {index+2}: خطأ في معالجة السجل: {str(e)}")
                error_count += 1
                session.rollback()  # Rollback for this record
                continue
        
        # Commit all changes
        session.commit()
        
        print("\n" + "="*60)
        print("📊 تقرير الاستيراد النهائي:")
        print(f"✅ السجلات الناجحة: {success_count}")
        print(f"⏭️  المستخدمون المفقودون: {missing_users_count}")
        print(f"⚠️  السجلات المتخطاة: {skipped_count}")
        print(f"❌ السجلات الفاشلة: {error_count}")
        print(f"📄 إجمالي السجلات في الملف: {len(df)}")
        print("="*60)
        
        # Show some examples of fixed data
        if success_count > 0:
            print("\n🔍 أمثلة على البيانات التي تم تصحيحها:")
            sample_count = 0
            for index, row in df_english.iterrows():
                if sample_count >= 3:
                    break
                username = row['username']
                if username and session.query(User).filter_by(username=str(username).strip()).first():
                    # Show national ID fix
                    original_national_id = row['national_id']
                    fixed_national_id = fix_numeric_string(original_national_id)
                    if original_national_id != fixed_national_id:
                        print(f"   {username} - الرقم القومي: {original_national_id} → {fixed_national_id}")
                    
                    # Show phone fix
                    original_phone = row['phone']
                    fixed_phone = fix_numeric_string(original_phone)
                    if original_phone != fixed_phone:
                        print(f"   {username} - الهاتف: {original_phone} → {fixed_phone}")
                    
                    sample_count += 1
        
        return success_count, error_count, missing_users_count
        
    except Exception as e:
        session.rollback()
        print(f"❌ خطأ عام في استيراد البيانات: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0, len(df), 0

def validate_excel_structure(excel_file_path):
    """
    Validate the Excel file structure before import
    """
    try:
        # Read with ALL columns as strings to see the raw data
        df = pd.read_excel(excel_file_path, dtype=str)
        
        print("🔍 التحقق من هيكل الملف...")
        print(f"عدد السجلات: {len(df)}")
        print(f"الأعمدة: {list(df.columns)}")
        
        # Check for required columns
        required_columns = ['اسم المستخدم', 'الاسم بالعربية']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"❌ الأعمدة المطلوبة مفقودة: {missing_columns}")
            return False
        
        # Check for empty usernames
        empty_usernames = df['اسم المستخدم'].isna().sum()
        if empty_usernames > 0:
            print(f"⚠️  يوجد {empty_usernames} سجل بدون اسم مستخدم")
        
        # Show data examples to demonstrate the fixes
        print("\n🔍 أمثلة على البيانات قبل التصحيح:")
        sample_data = df.head(3)
        for index, row in sample_data.iterrows():
            print(f"   السطر {index+2}:")
            print(f"     - اسم المستخدم: {row['اسم المستخدم']}")
            print(f"     - الرقم القومي: {row['الرقم القومي']} → {fix_numeric_string(row['الرقم القومي'])}")
            if 'رقم الهاتف' in row:
                print(f"     - رقم الهاتف: {row['رقم الهاتف']} → {fix_numeric_string(row['رقم الهاتف'])}")
            if 'رقم الواتساب' in row:
                print(f"     - رقم الواتساب: {row['رقم الواتساب']} → {fix_numeric_string(row['رقم الواتساب'])}")
        
        # Check sample data
        print("\n📄 عينة من البيانات (الصفوف الأولى):")
        print(df.head(3).to_string(index=False))
        
        return True
        
    except Exception as e:
        print(f"❌ خطأ في قراءة الملف: {str(e)}")
        return False

def check_existing_users():
    """
    Check existing users in database for information
    """
    try:
        users = session.query(User).all()
        print(f"🔍 يوجد {len(users)} مستخدم في قاعدة البيانات")
        if users:
            print("أول 10 مستخدمين:")
            for user in users[:10]:
                print(f"   - {user.username}: {user.name}")
        return len(users)
    except Exception as e:
        print(f"⚠️  لا يمكن التحقق من المستخدمين: {e}")
        return 0

def main():
    print("=" * 70)
    print("🚀 برنامج استيراد بيانات الموظفين من ملف الإكسل إلى قاعدة البيانات")
    print("=" * 70)
    
    # Check database connection first
    print("🔍 جاري التحقق من اتصال قاعدة البيانات...")
    try:
        user_count = check_existing_users()
        if user_count == 0:
            print("⚠️  تحذير: لا يوجد مستخدمون في قاعدة البيانات!")
            print("   سيتم تخطي جميع السجلات أثناء الاستيراد")
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة البيانات: {e}")
        print("   يرجى التأكد من إعدادات قاعدة البيانات")
        return
    
    # Get Excel file path
    excel_file_path = input("📁 أدخل مسار ملف الإكسل: ").strip().strip('"')
    
    if not os.path.exists(excel_file_path):
        print("❌ الملف غير موجود!")
        return
    
    # Step 1: Validate file structure
    print("\n1. جاري التحقق من هيكل الملف...")
    if not validate_excel_structure(excel_file_path):
        print("❌ فشل التحقق من هيكل الملف!")
        return
    
    # Step 2: Confirm import
    print(f"\n2. تأكيد الاستيراد:")
    df = pd.read_excel(excel_file_path, dtype=str)
    print(f"   - الملف: {excel_file_path}")
    print(f"   - عدد السجلات: {len(df)}")
    
    confirm = input("هل تريد متابعة استيراد البيانات؟ (نعم/لا): ").strip().lower()
    if confirm not in ['نعم', 'yes', 'y', '']:
        print("❌ تم إلغاء الاستيراد")
        return
    
    # Step 3: Import data
    print("\n3. بدء استيراد البيانات...")
    success_count, error_count, missing_users_count = import_employee_data_from_excel(excel_file_path)
    
    # Step 4: Show final results
    print("\n" + "🎯 " + "="*50 + " 🎯")
    if success_count > 0:
        print(f"🎉 تم استيراد {success_count} سجل بنجاح!")
        if missing_users_count > 0:
            print(f"⏭️  تم تخطي {missing_users_count} مستخدم غير موجود")
        if error_count > 0:
            print(f"⚠️  حدثت {error_count} أخطاء أثناء الاستيراد")
    else:
        print("❌ لم يتم استيراد أي سجلات")
        if missing_users_count > 0:
            print(f"⏭️  تم تخطي {missing_users_count} مستخدم غير موجود")
    
    print("🎯 " + "="*50 + " 🎯")

if __name__ == "__main__":
    main()