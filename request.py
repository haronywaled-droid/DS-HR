import pandas as pd
from zk import ZK, const
import socket
import time
from datetime import datetime
import sys
import warnings
import os
import glob
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

class ZKFingerprintExporter:
    def __init__(self, devices):
        self.devices = devices
        self.all_logs = []
        self.all_users = []
        self.connection_timeout = 30
        self.port = 4370
        self.start_date = datetime.now() - timedelta(days=31)
        self.fingerprint_logs = []  # لتخزين سجلات البصمات
    
    def test_connection(self, ip):
        """اختبار اتصال أساسي بالجهاز"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((ip, self.port))
            sock.close()
            return result == 0
        except:
            return False
    
    def connect_to_device(self, ip):
        """الاتصال بجهاز ZKTeco"""
        conn = None
        zk = ZK(ip, port=self.port, timeout=self.connection_timeout)
        
        try:
            print(f"🔄 محاولة الاتصال بـ {ip}:{self.port}...")
            conn = zk.connect()
            conn.disable_device()
            print(f"✅ تم الاتصال بنجاح بـ {ip}")
            return conn, zk
        except Exception as e:
            print(f"❌ فشل الاتصال بـ {ip}: {e}")
            return None, None
    
    def get_device_info(self, conn, ip):
        """الحصول على معلومات الجهاز"""
        device_info = {
            'ip_address': ip,
            'device_name': 'Unknown',
            'serial_number': 'Unknown',
            'platform': 'Unknown',
            'firmware_version': 'Unknown',
            'device_time': 'Unknown',
            'user_count': 0,
            'log_count': 0,
            'connection_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            device_info['device_name'] = conn.get_device_name() or 'Unknown'
            device_info['serial_number'] = conn.get_serialnumber() or 'Unknown'
            device_info['platform'] = conn.get_platform() or 'Unknown'
            device_info['firmware_version'] = conn.get_firmware_version() or 'Unknown'
            device_info['device_time'] = str(conn.get_time()) or 'Unknown'
            
        except Exception as e:
            print(f"   ⚠️ خطأ في جلب معلومات الجهاز: {e}")
        
        return device_info
    
    def get_users_data(self, conn, ip):
        """جلب بيانات المستخدمين"""
        users_data = []
        try:
            users = conn.get_users()
            print(f"   👥 جلب {len(users)} مستخدم...")
            
            for user in users:
                user_data = {
                    'device_ip': ip,
                    'user_id': user.uid,
                    'badge_number': user.user_id or '',
                    'name': user.name or '',
                    'privilege': self.get_privilege_name(user.privilege),
                    'password': user.password or '',
                    'group_id': user.group_id or '',
                    'card': user.card or '',
                    'is_active': not user.deleted,
                }
                users_data.append(user_data)
            
        except Exception as e:
            print(f"   ❌ خطأ في جلب المستخدمين: {e}")
        
        return users_data
    
    def get_attendance_logs(self, conn, ip):
        """جلب سجلات الحضور وتصفية للسنة الحالية فقط"""
        attendance_logs = []
        try:
            logs = conn.get_attendance()
            print(f"   📊 جلب {len(logs)} سجل حضور...")
            
            current_year_logs = 0
            other_year_logs = 0
            
            for log in logs:
                if log.timestamp.year == self.current_year:
                    log_data = {
                        'device_ip': ip,
                        'user_id': log.user_id,
                        'timestamp': log.timestamp,
                        'date': log.timestamp.date(),
                        'time': log.timestamp.time(),
                        'year': log.timestamp.year,
                        'month': log.timestamp.month,
                        'day': log.timestamp.day,
                        'status': log.status,
                        'punch': log.punch,
                        'uid': log.uid
                    }
                    attendance_logs.append(log_data)
                    current_year_logs += 1
                else:
                    other_year_logs += 1
            
            print(f"   ✅ تم تصفية السجلات: {current_year_logs} للسنة الحالية ({self.current_year})")
            print(f"   ⏳ تم تخطي: {other_year_logs} سجل لسنوات سابقة")
            
        except Exception as e:
            print(f"   ❌ خطأ في جلب سجلات الحضور: {e}")
        
        return attendance_logs
    
    def get_fingerprint_logs(self, conn, ip):
        """جلب سجلات البصمات"""
        fingerprint_data = []
        try:
            users = conn.get_users()
            print(f"   👆 جلب سجلات البصمات...")
            
            for user in users:
                try:
                    templates = conn.get_templates(user)
                    
                    for template in templates:
                        template_data = {
                            'device_ip': ip,
                            'user_id': user.uid,
                            'badge_number': user.user_id or '',
                            'name': user.name or '',
                            'finger_id': template.fid,
                            'size': template.size,
                            'valid': template.valid,
                            'template_date': datetime.now().date()  # تاريخ الحفظ
                        }
                        fingerprint_data.append(template_data)
                        
                except Exception as e:
                    #print(f"      ⚠️ خطأ في جلب بصمات المستخدم {user.uid}: {e}")
                    continue
            
            print(f"   ✅ تم جلب {len(fingerprint_data)} سجل بصمة")
            
        except Exception as e:
            print(f"   ❌ خطأ في جلب سجلات البصمات: {e}")
        
        return fingerprint_data
    
    def get_privilege_name(self, privilege_code):
        """تحويل كود الصلاحية إلى اسم"""
        privilege_map = {
            const.USER_DEFAULT: 'مستخدم عادي',
            const.USER_ADMIN: 'مدير',
            2: 'مستخدم خاص',
        }
        return privilege_map.get(privilege_code, f'غير معروف ({privilege_code})')
    
    def export_fingerprint_logs(self):
        """تصدير سجلات البصمات بعد التحميل"""
        try:
            if not self.fingerprint_logs:
                print("⚠️ لا توجد سجلات بصمات للتصدير")
                return None
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'سجلات البصمات_{self.current_year}_{timestamp}.xlsx'
            
            df_fingerprints = pd.DataFrame(self.fingerprint_logs)
            
            # ترتيب الأعمدة
            column_order = [
                'device_ip', 'user_id', 'badge_number', 'name', 
                'finger_id', 'size', 'valid', 'template_date'
            ]
            
            df_fingerprints = df_fingerprints[column_order]
            
            # تصدير إلى Excel
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df_fingerprints.to_excel(writer, sheet_name='سجلات البصمات', index=False)
                
                worksheet = writer.sheets['سجلات البصمات']
                
                # ضبط عرض الأعمدة
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    
                    adjusted_width = min(max_length + 2, 30)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            print(f"\n✅ تم تصدير سجلات البصمات إلى: {filename}")
            print(f"📊 عدد السجلات: {len(self.fingerprint_logs)}")
            print(f"📋 عدد الأجهزة: {df_fingerprints['device_ip'].nunique()}")
            
            return filename
            
        except Exception as e:
            print(f"❌ خطأ في تصدير سجلات البصمات: {e}")
            return None
    
    def export_logs_to_excel(self, logs_data, filename=None):
        """تصدير سجلات الحضور فقط إلى ملف Excel"""
        try:
            if not logs_data:
                print("⚠️ لا توجد سجلات حضور للتصدير")
                return None
            
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'attendance_{self.current_year}_{timestamp}.xlsx'
            
            df_logs = pd.DataFrame(logs_data)
            
            column_order = [
                'device_ip', 'user_id', 'timestamp', 'date', 'time',
                'year', 'month', 'day', 'status', 'punch', 'uid'
            ]
            
            available_columns = [col for col in column_order if col in df_logs.columns]
            df_logs = df_logs[available_columns]
            df_logs = df_logs.sort_values('timestamp', ascending=True)
            
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df_logs.to_excel(writer, sheet_name=f'Attendance_{self.current_year}', index=False)
                
                worksheet = writer.sheets[f'Attendance_{self.current_year}']
                
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            print(f"\n✅ تم التصدير بنجاح إلى: {filename}")
            print("=" * 60)
            print("📊 ملخص التصدير:")
            print(f"   عدد السجلات: {len(logs_data)}")
            print(f"   السنة: {self.current_year}")
            print(f"   عدد الأجهزة المصدرة: {df_logs['device_ip'].nunique()}")
            print(f"   الفترة الزمنية: من {df_logs['date'].min()} إلى {df_logs['date'].max()}")
            print("=" * 60)
            
            return filename
            
        except Exception as e:
            print(f"❌ خطأ في التصدير: {e}")
            return None
    
    def create_user_folders_and_files(self, daly_att_file='daly-att.xlsx'):
        """إنشاء مجلد att ومجلدات لكل كود مستخدم وحفظ ملف Excel لكل مستخدم"""
        try:
            if not os.path.exists(daly_att_file):
                print(f"❌ ملف {daly_att_file} غير موجود")
                return False
            
            print(f"\n📂 جارٍ قراءة الملف: {daly_att_file}")
            df = pd.read_excel(daly_att_file)
            
            if 'كود المستخدم' not in df.columns:
                print("❌ الملف لا يحتوي على عمود 'كود المستخدم'")
                return False
            
            # إنشاء المجلد الرئيسي att
            main_folder = 'att'
            if not os.path.exists(main_folder):
                os.makedirs(main_folder)
                print(f"✅ تم إنشاء المجلد الرئيسي: {main_folder}")
            
            # الحصول على قيم كود المستخدم الفريدة
            unique_user_codes = df['كود المستخدم'].dropna().unique()
            print(f"🔍 العثور على {len(unique_user_codes)} كود مستخدم فريد")
            
            # إنشاء مجلد وملف Excel لكل كود مستخدم
            for user_code in unique_user_codes:
                try:
                    # تحويل كود المستخدم إلى سلسلة وإزالة المسافات
                    user_code_str = str(user_code).strip()
                    
                    # إنشاء مجلد باسم كود المستخدم
                    user_folder = os.path.join(main_folder, user_code_str)
                    if not os.path.exists(user_folder):
                        os.makedirs(user_folder)
                    
                    # تصفية البيانات لهذا المستخدم فقط
                    user_data = df[df['كود المستخدم'] == user_code]
                    
                    # إزالة البيانات المكررة - يمكن تحديد الأعمدة التي يجب التحقق منها
                    # إذا كنت تريد التحقق من جميع الأعمدة:
                    # user_data = user_data.drop_duplicates()
                    
                    # أو يمكنك تحديد أعمدة محددة للتحقق من التكرار (مثال: التاريخ ووقت الحضور)
                    columns_to_check = ['التاريخ']  # أضف الأعمدة المناسبة هنا
                    if all(col in user_data.columns for col in columns_to_check):
                        user_data = user_data.drop_duplicates(subset=columns_to_check, keep='first')
                    else:
                        user_data = user_data.drop_duplicates()
                    
                    # ترتيب البيانات حسب التاريخ
                    if 'التاريخ' in user_data.columns:
                        user_data = user_data.sort_values('التاريخ', ascending=True)
                    
                    # حفظ البيانات في ملف Excel داخل المجلد
                    excel_filename = os.path.join(user_folder, f'{user_code_str}.xlsx')
                    
                    with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
                        user_data.to_excel(writer, sheet_name=f'الحضور_{user_code_str}', index=False)
                        
                        worksheet = writer.sheets[f'الحضور_{user_code_str}']
                        
                        # ضبط عرض الأعمدة
                        for column in worksheet.columns:
                            max_length = 0
                            column_letter = column[0].column_letter
                            
                            for cell in column:
                                try:
                                    if len(str(cell.value)) > max_length:
                                        max_length = len(str(cell.value))
                                except:
                                    pass
                            
                            adjusted_width = min(max_length + 2, 30)
                            worksheet.column_dimensions[column_letter].width = adjusted_width
                    
                    #print(f"   ✅ تم إنشاء ملف لـ {user_code_str}: {len(user_data)} سجل (بعد إزالة المكررات)")
                    
                except Exception as e:
                    print(f"   ❌ خطأ في معالجة المستخدم {user_code}: {e}")
                    continue
                
            print(f"\n🎉 تم الانتهاء من إنشاء المجلدات والملفات")
            print(f"📁 المجلد الرئيسي: {main_folder}")
            print(f"👤 عدد المجلدات المخلوقة: {len(unique_user_codes)}")
            print(f"📊 إجمالي السجلات المعالجة: {len(df)}")
            
            # إنشاء ملف ملخص
            self.create_summary_file(df, main_folder)
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في إنشاء المجلدات والملفات: {e}")
            return False
    
    def create_summary_file(self, df, main_folder):
        """إنشاء ملف ملخص يحتوي على إحصائيات"""
        try:
            summary_data = []
            
            # تحليل البيانات
            if 'كود المستخدم' in df.columns and 'اسم المستخدم' in df.columns:
                user_stats = df.groupby(['كود المستخدم', 'اسم المستخدم']).size().reset_index(name='عدد السجلات')
                
                for _, row in user_stats.iterrows():
                    summary_data.append({
                        'كود المستخدم': row['كود المستخدم'],
                        'اسم المستخدم': row['اسم المستخدم'],
                        'عدد السجلات': row['عدد السجلات'],
                        'المجلد': str(row['كود المستخدم']),
                        'ملف Excel': f"{row['كود المستخدم']}.xlsx"
                    })
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                summary_file = os.path.join(main_folder, 'ملخص_المستخدمين.xlsx')
                summary_df.to_excel(summary_file, index=False)
                print(f"📋 تم إنشاء ملف الملخص: {summary_file}")
                
                # إضافة إحصائيات عامة
                total_stats = {
                    'إجمالي المستخدمين': len(summary_data),
                    'إجمالي السجلات': len(df),
                    'تاريخ الإنشاء': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'المجلد الرئيسي': main_folder
                }
                
                stats_df = pd.DataFrame([total_stats])
                stats_file = os.path.join(main_folder, 'إحصائيات_عامة.xlsx')
                stats_df.to_excel(stats_file, index=False)
                print(f"📈 تم إنشاء ملف الإحصائيات: {stats_file}")
        
        except Exception as e:
            print(f"⚠️ خطأ في إنشاء ملف الملخص: {e}")
    
    def process_device(self, ip, get_fingerprints=False):
        """معالجة جهاز واحد"""
        print(f"\n{'='*60}")
        print(f"🔍 معالجة الجهاز: {ip}")
        
        if not self.test_connection(ip):
            print(f"❌ الجهاز غير متاح: {ip}")
            return None, None
        
        conn, zk = self.connect_to_device(ip)
        if not conn:
            return None, None
        
        logs_data = []
        fingerprints_data = []
        
        try:
            device_info = self.get_device_info(conn, ip)
            
            logs_data = self.get_attendance_logs(conn, ip)
            
            if get_fingerprints:
                fingerprints_data = self.get_fingerprint_logs(conn, ip)
            
            print(f"   📈 إحصاءات الجهاز {ip}:")
            print(f"      - عدد السجلات: {len(logs_data)}")
            if get_fingerprints:
                print(f"      - عدد سجلات البصمات: {len(fingerprints_data)}")
            
        except Exception as e:
            print(f"❌ خطأ أثناء معالجة الجهاز {ip}: {e}")
        finally:
            try:
                conn.enable_device()
                conn.disconnect()
                print(f"📴 تم فصل الاتصال بـ {ip}")
            except:
                pass
        
        return logs_data, fingerprints_data
    
    def add_user_info_to_sheets(self):
        """إضافة معلومات المستخدم لجميع ملفات attendance"""
        try:
            # البحث عن ملف emp-code.xlsx
            emp_code_file = 'emp-code.xlsx'
            if not os.path.exists(emp_code_file):
                print(f"❌ ملف {emp_code_file} غير موجود")
                return False
            
            # تحميل بيانات الموظفين
            emp_df = pd.read_excel(emp_code_file)
            print(f"✅ تم تحميل بيانات الموظفين من {emp_code_file}")
            print(f"📋 عدد الموظفين: {len(emp_df)}")
            
            # البحث عن جميع ملفات attendance
            attendance_files = glob.glob('attendance*.xlsx')
            print(f"\n🔍 العثور على {len(attendance_files)} ملف حضور")
            
            for file in attendance_files:
                #print(f"\n📂 معالجة الملف: {file}")
                
                try:
                    # تحميل ملف الحضور
                    attendance_df = pd.read_excel(file)
                    
                    if 'user_id' not in attendance_df.columns:
                        print(f"   ⚠️ ملف {file} لا يحتوي على عمود user_id")
                        continue
                    
                    # دمج البيانات مع emp-code باستخدام user_id
                    merged_df = pd.merge(
                        attendance_df,
                        emp_df[['user_id', 'اسم المستخدم', 'كود المستخدم']],
                        on='user_id',
                        how='left'
                    )
                    
                    # إعادة ترتيب الأعمدة
                    columns_order = ['device_ip', 'user_id', 'اسم المستخدم', 'كود المستخدم']
                    remaining_columns = [col for col in merged_df.columns if col not in columns_order]
                    final_columns = columns_order + remaining_columns
                    
                    merged_df = merged_df[final_columns]
                    
                    # حفظ الملف المعدل
                    merged_df.to_excel(file, index=False)
                    print(f"   ✅ تم تحديث الملف: {file}")
                    print(f"   📊 عدد السجلات: {len(merged_df)}")
                    
                except Exception as e:
                    #print(f"   ❌ خطأ في معالجة الملف {file}: {e}")

                    try:
                        os.remove(file)
                        #print(f"   ✅ تم حذف الملف {file}")
                    except Exception as delete_error:
                        print(f"   ⚠️ فشل في حذف الملف {file}: {delete_error}")                    
            
            return True
            
        except Exception as e:
            print(f"❌ خطأ في إضافة معلومات المستخدم: {e}")
            return False
    
    def merge_all_attendance_files(self):
        """دمج جميع ملفات الحضور وتصميمها بالشكل المطلوب"""
        try:
            # البحث عن جميع ملفات attendance
            attendance_files = glob.glob('attendance*.xlsx')
            
            if not attendance_files:
                print("❌ لم يتم العثور على ملفات attendance للدمج")
                return None
            
            print(f"\n🔀 دمج {len(attendance_files)} ملف حضور...")
            
            all_data = []
            
            for file in attendance_files:
                print(f"   📂 قراءة الملف: {file}")
                try:
                    df = pd.read_excel(file)
                    
                    # تحقق من وجود الأعمدة المطلوبة
                    required_columns = ['device_ip', 'user_id', 'timestamp']
                    
                    if all(col in df.columns for col in required_columns):
                        # إعادة تسمية الأعمدة
                        df_renamed = df.copy()
                        df_renamed = df_renamed.rename(columns={
                            'device_ip': 'رقم المكينة',
                            'user_id': 'كود المستخدم الالي',
                            'timestamp': 'التاريخ'
                        })
                        
                        # التأكد من وجود جميع الأعمدة المطلوبة
                        final_columns = ['رقم المكينة', 'اسم المستخدم', 'كود المستخدم', 'كود المستخدم الالي', 'التاريخ']
                        
                        for col in final_columns:
                            if col not in df_renamed.columns:
                                df_renamed[col] = ''
                        
                        # إعادة ترتيب الأعمدة
                        df_renamed = df_renamed[final_columns]
                        
                        all_data.append(df_renamed)
                        print(f"      ✅ تمت إضافة {len(df_renamed)} سجل")
                    else:
                        print(f"      ⚠️ الملف {file} لا يحتوي على الأعمدة المطلوبة")
                        
                except Exception as e:
                    print(f"      ❌ خطأ في قراءة الملف {file}: {e}")
            
            if not all_data:
                print("❌ لا توجد بيانات للدمج")
                return None
            
            # دمج جميع البيانات
            merged_df = pd.concat(all_data, ignore_index=True)
            
            # ترتيب البيانات حسب التاريخ
            if 'التاريخ' in merged_df.columns:
                merged_df['التاريخ'] = pd.to_datetime(merged_df['التاريخ'], errors='coerce')
                merged_df = merged_df.sort_values('التاريخ', ascending=True)
            
            # حفظ الملف النهائي
            output_file = 'daly-att.xlsx'
            merged_df.to_excel(output_file, index=False)
            
            print(f"\n✅ تم دمج جميع الملفات بنجاح")
            print(f"📁 الملف النهائي: {output_file}")
            print(f"📊 إجمالي السجلات: {len(merged_df)}")
            print(f"📅 النطاق الزمني: من {merged_df['التاريخ'].min()} إلى {merged_df['التاريخ'].max()}")
            
            return output_file
            
        except Exception as e:
            print(f"❌ خطأ في دمج الملفات: {e}")
            return None
    
    def run_complete_workflow(self):
        """تشغيل سير العمل الكامل بالترتيب"""
        print("🚀 سير العمل الكامل لتصدير سجلات البصمة")
        print("=" * 60)
        
        # المرحلة 1: جلب سجلات البصمات أولاً
        print("\n📋 المرحلة 1: جلب سجلات البصمات")
        print("-" * 40)
        
        self.fingerprint_logs = []
        for ip in self.devices:
            logs_data, fingerprints_data = self.process_device(ip, get_fingerprints=True)
            if fingerprints_data:
                self.fingerprint_logs.extend(fingerprints_data)
            time.sleep(1)
        
        if self.fingerprint_logs:
            self.export_fingerprint_logs()
        
        # المرحلة 2: جلب سجلات الحضور
        print("\n📋 المرحلة 2: جلب سجلات الحضور")
        print("-" * 40)
        
        all_logs_data = []
        for ip in self.devices:
            logs_data, _ = self.process_device(ip, get_fingerprints=False)
            if logs_data:
                all_logs_data.extend(logs_data)
            time.sleep(1)
        
        if all_logs_data:
            self.export_logs_to_excel(all_logs_data)
        
        # المرحلة 3: إضافة معلومات المستخدم
        print("\n📋 المرحلة 3: إضافة معلومات المستخدم للملفات")
        print("-" * 40)
        
        self.add_user_info_to_sheets()
        
        # المرحلة 4: دمج جميع الملفات
        print("\n📋 المرحلة 4: دمج جميع ملفات الحضور")
        print("-" * 40)
        
        merged_file = self.merge_all_attendance_files()
        
        # المرحلة 5: إنشاء مجلدات وملفات للمستخدمين
        print("\n📋 المرحلة 5: إنشاء مجلدات وملفات للمستخدمين")
        print("-" * 40)
        
        if merged_file and os.path.exists(merged_file):
            self.create_user_folders_and_files(merged_file)
        else:
            # محاولة استخدام ملف daly-att.xlsx إذا كان موجوداً
            if os.path.exists('daly-att.xlsx'):
                self.create_user_folders_and_files('daly-att.xlsx')
            else:
                print("⚠️ لم يتم العثور على ملف daly-att.xlsx")
        
        print("\n🎉 تم الانتهاء من جميع العمليات بنجاح!")
        print("=" * 60)

def main():
    """الدالة الرئيسية"""
    devices_ip = [
        "172.16.80.19",
        "172.16.80.50",
        "172.16.80.17",
        "172.16.80.27",
        "172.16.80.43",
        "172.16.80.44",
        "172.16.80.35",
        "172.16.80.39"
    ]
    
    print("=" * 60)
    print("📋 أجهزة البصمة المطلوبة:")
    for i, ip in enumerate(devices_ip, 1):
        print(f"  {i}. {ip}")
    print("=" * 60)
    
    current_year = datetime.now().year
    print(f"📅 السنة المستهدفة: {current_year}")
    
    exporter = ZKFingerprintExporter(devices_ip)
    
    # تشغيل سير العمل الكامل
    exporter.run_complete_workflow()

if __name__ == "__main__":
    print("📦 المكتبات المطلوبة:")
    print("pip install pyzk pandas openpyxl")
    print("\n🔧 جاري التحضير...")
    
    try:
        from zk import ZK, const
        import pandas as pd
        import os
        import glob
    except ImportError as e:
        print(f"\n❌ مكتبات مفقودة: {e}")
        print("\nيرجى تثبيت المكتبات أولاً:")
        print("pip install pyzk pandas openpyxl")
        sys.exit(1)
    
    main()