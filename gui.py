import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import customtkinter as ctk
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import or_
import json
from datetime import datetime, date
import sys
import os
import traceback
from pathlib import Path

# إعداد مظهر customtkinter
ctk.set_appearance_mode("light")  # وضع الفاتح
ctk.set_default_color_theme("blue")  # السمة الزرقاء

# إضافة المسار لملف النماذج
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# محاولة استيراد النماذج
try:
    from models import *
    print("✓ تم استيراد النماذج بنجاح")
except ImportError as e:
    print(f"✗ خطأ في استيراد النماذج: {e}")
    messagebox.showerror("خطأ", f"خطأ في استيراد النماذج: {e}\n\nتأكد من وجود ملف models.py")
    sys.exit(1)

# إعداد اتصال قاعدة البيانات
try:
    DATABASE_URL = 'sqlite:///hr_system.db'
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    print("✓ تم الاتصال بقاعدة البيانات بنجاح")
except Exception as e:
    print(f"✗ خطأ في الاتصال بقاعدة البيانات: {e}")
    messagebox.showerror("خطأ", f"خطأ في الاتصال بقاعدة البيانات: {e}")
    sys.exit(1)

class CRUDApp:
    def __init__(self):
        print("جاري تهيئة التطبيق...")
        
        # قائمة النماذج المتاحة
        self.models = {
            'المستخدمين': User,
            'الإدارات': Department,
            'الجداول الأسبوعية': WeeklySchedule,
            'طلبات الإجازة': LeaveRequest,
            'طلبات الأذونات': PermissionRequest,
            'الموظفين': EmployeeData,
            'الإشعارات': Notification,
            'المسير': SalarySlip,
            'طلبات السلف': AdvanceRequest,
            'أرصدة الموظفين': EmployeeBalance,
            'المكافآت والعقوبات': RewardPenalty,
            'مديري الإدارات': DepartmentManager,
            'قوالب الجداول': DepartmentScheduleTemplate,
            'سجل الجداول': ScheduleHistory
        }
        
        print(f"✓ تم تحميل {len(self.models)} نموذج")
        
        self.current_model = None
        self.current_data = []
        self.selected_record_id = None
        
        # إنشاء النافذة الرئيسية
        self.root = ctk.CTk()
        self.root.title("نظام إدارة الموارد البشرية")
        self.root.geometry("1200x700")
        
        # إعداد واجهة المستخدم
        self.setup_ui()
        
    def setup_ui(self):
        """إعداد واجهة المستخدم"""
        # إطار العنوان
        title_frame = ctk.CTkFrame(self.root)
        title_frame.pack(fill="x", padx=10, pady=5)
        
        title_label = ctk.CTkLabel(
            title_frame,
            text="نظام إدارة الموارد البشرية",
            font=("Arial", 18, "bold")
        )
        title_label.pack(pady=10)
        
        # إطار المحتوى الرئيسي
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # قسم النماذج على اليسار
        left_frame = ctk.CTkFrame(main_frame, width=250)
        left_frame.pack(side="left", fill="y", padx=(0, 5), pady=5)
        
        # عنوان قسم النماذج
        models_label = ctk.CTkLabel(
            left_frame,
            text="النماذج المتاحة",
            font=("Arial", 12, "bold")
        )
        models_label.pack(pady=(10, 5))
        
        # قائمة النماذج
        self.models_listbox = tk.Listbox(
            left_frame,
            font=("Arial", 10),
            bg="#f0f0f0",
            relief="flat",
            height=15
        )
        self.models_listbox.pack(fill="both", expand=True, padx=10, pady=5)
        
        # تعبئة قائمة النماذج
        for model_name in self.models.keys():
            self.models_listbox.insert(tk.END, model_name)
        
        # معلومات النموذج المحدد
        self.model_info_label = ctk.CTkLabel(
            left_frame,
            text="",
            font=("Arial", 10)
        )
        self.model_info_label.pack(pady=5)
        
        # ربط حدث اختيار النموذج
        self.models_listbox.bind('<<ListboxSelect>>', self.on_model_select)
        
        # قسم التحكم في المنتصف
        center_frame = ctk.CTkFrame(main_frame)
        center_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # أزرار التحكم
        control_frame = ctk.CTkFrame(center_frame)
        control_frame.pack(fill="x", pady=(0, 10))
        
        # إنشاء أزرار التحكم
        buttons = [
            ("🔄 عرض", self.on_view_click, "#4CAF50"),
            ("➕ إضافة", self.on_add_click, "#2196F3"),
            ("✏️ تعديل", self.on_edit_click, "#FF9800"),
            ("🗑️ حذف", self.on_delete_click, "#F44336")
        ]
        
        for text, command, color in buttons:
            btn = ctk.CTkButton(
                control_frame,
                text=text,
                command=command,
                width=100,
                height=35,
                fg_color=color,
                hover_color=self.darken_color(color),
                font=("Arial", 11)
            )
            btn.pack(side="left", padx=5)
        
        # إطار البحث
        search_frame = ctk.CTkFrame(center_frame)
        search_frame.pack(fill="x", pady=(0, 10))
        
        # عنوان قسم البحث
        search_label = ctk.CTkLabel(
            search_frame,
            text="البحث",
            font=("Arial", 12, "bold")
        )
        search_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        # حقل البحث
        search_input_frame = ctk.CTkFrame(search_frame)
        search_input_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            search_input_frame,
            text="كلمة البحث:",
            font=("Arial", 10)
        ).pack(side="left", padx=(0, 5))
        
        self.search_entry = ctk.CTkEntry(
            search_input_frame,
            width=250,
            font=("Arial", 10)
        )
        self.search_entry.pack(side="left", padx=(0, 5))
        
        search_btn = ctk.CTkButton(
            search_input_frame,
            text="🔍 بحث",
            command=self.on_search_click,
            width=80,
            height=30,
            font=("Arial", 10)
        )
        search_btn.pack(side="left")
        
        # خيارات عدد السجلات
        limit_frame = ctk.CTkFrame(search_frame)
        limit_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(
            limit_frame,
            text="عدد السجلات:",
            font=("Arial", 10)
        ).pack(side="left", padx=(0, 5))
        
        self.limit_combo = ctk.CTkComboBox(
            limit_frame,
            values=["10", "50", "100", "200", "الكل"],
            width=100,
            font=("Arial", 10)
        )
        self.limit_combo.set("50")
        self.limit_combo.pack(side="left")
        
        # منطقة عرض البيانات
        data_frame = ctk.CTkFrame(center_frame)
        data_frame.pack(fill="both", expand=True)
        
        # عنوان قسم البيانات
        data_label = ctk.CTkLabel(
            data_frame,
            text="بيانات النموذج",
            font=("Arial", 12, "bold")
        )
        data_label.pack(anchor="w", padx=10, pady=(10, 5))
        
        # مربع نص لعرض البيانات
        self.data_text = scrolledtext.ScrolledText(
            data_frame,
            font=("Courier New", 9),
            bg="#f9f9f9",
            fg="#333",
            wrap=tk.WORD,
            state="normal"
        )
        self.data_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # شريط الحالة
        self.status_bar = ctk.CTkLabel(
            self.root,
            text="جاهز - اختر نموذج لبدء العمل",
            anchor="w",
            font=("Arial", 9)
        )
        self.status_bar.pack(side="bottom", fill="x", padx=10, pady=5)
        
    def darken_color(self, hex_color):
        """تغميق اللون"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        darkened = tuple(max(0, c - 30) for c in rgb)
        return f'#{darkened[0]:02x}{darkened[1]:02x}{darkened[2]:02x}'
    
    def on_model_select(self, event):
        """حدث اختيار نموذج من القائمة"""
        selection = self.models_listbox.curselection()
        if selection:
            model_name = self.models_listbox.get(selection[0])
            self.current_model = self.models[model_name]
            
            self.model_info_label.configure(text=f"النموذج: {model_name}")
            self.status_bar.configure(text=f"تم اختيار: {model_name}")
            print(f"✓ تم اختيار نموذج: {model_name}")
    
    def view_data(self, model, limit=50):
        """عرض بيانات النموذج المحدد"""
        try:
            print(f"جاري عرض بيانات {model.__name__} (الحد: {limit})")
            
            # الحصول على البيانات
            if limit > 0:
                records = session.query(model).limit(limit).all()
            else:
                records = session.query(model).all()
            
            self.current_data = records
            
            if not records:
                return "لا توجد بيانات"
            
            # إنشاء جدول بسيط
            display_text = f"===== {model.__name__} =====\n"
            display_text += f"عدد السجلات: {len(records)}\n"
            display_text += "=" * 50 + "\n\n"
            
            # عرض البيانات بشكل مبسط
            for i, record in enumerate(records, 1):
                display_text += f"السجل #{i}:\n"
                display_text += "-" * 30 + "\n"
                
                # عرض بعض الحقول الرئيسية فقط
                for column in model.__table__.columns:
                    if column.name in ['id', 'name', 'username', 'title', 'description']:
                        value = getattr(record, column.name, '')
                        
                        if value is None:
                            value = ''
                        elif isinstance(value, (date, datetime)):
                            if isinstance(value, date):
                                value = value.strftime('%Y-%m-%d')
                            else:
                                value = value.strftime('%Y-%m-%d %H:%M')
                        elif isinstance(value, bool):
                            value = 'نعم' if value else 'لا'
                        
                        display_text += f"{column.name}: {value}\n"
                
                display_text += "\n"
            
            print(f"✓ تم تحضير {len(records)} سجل للعرض")
            return display_text
            
        except Exception as e:
            error_msg = f"خطأ في عرض البيانات: {str(e)}"
            print(f"✗ {error_msg}")
            return error_msg
    
    def on_view_click(self):
        """حدث النقر على زر العرض"""
        if not self.current_model:
            messagebox.showwarning("تحذير", "الرجاء اختيار نموذج أولاً من القائمة")
            return
        
        try:
            limit_str = self.limit_combo.get()
            limit = 0 if limit_str == "الكل" else int(limit_str)
            
            data = self.view_data(self.current_model, limit)
            self.data_text.delete(1.0, tk.END)
            self.data_text.insert(1.0, data)
            self.status_bar.configure(text=f'تم عرض {self.current_model.__name__}')
        except Exception as e:
            messagebox.showerror("خطأ", f"خطأ في العرض: {str(e)}")
    
    def create_add_edit_window(self, model, record=None):
        """إنشاء نافذة إضافة/تعديل"""
        window = ctk.CTkToplevel(self.root)
        title = f"تعديل {model.__name__}" if record else f"إضافة {model.__name__} جديد"
        window.title(title)
        window.geometry("500x600")
        window.transient(self.root)
        window.grab_set()
        
        try:
            fields = model.__table__.columns
            entries = {}
            
            # إنشاء إطار قابل للتمرير
            canvas = ctk.CTkCanvas(window)
            scrollbar = ctk.CTkScrollbar(window, command=canvas.yview)
            scrollable_frame = ctk.CTkFrame(canvas)
            
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            # تعبئة الحقول
            for field in fields:
                field_name = field.name
                field_type = str(field.type)
                current_value = record.get(field_name, '') if record else ''
                
                # تخطي الحقول التلقائية
                if field_name in ['id', 'created_at', 'updated_at'] and not record:
                    continue
                
                frame = ctk.CTkFrame(scrollable_frame)
                frame.pack(fill="x", padx=10, pady=5)
                
                label = ctk.CTkLabel(
                    frame,
                    text=f"{field_name}:",
                    width=150,
                    anchor="e",
                    font=("Arial", 10)
                )
                label.pack(side="left", padx=(0, 5))
                
                # تحديد نوع عنصر الإدخال
                if 'Boolean' in field_type:
                    var = tk.BooleanVar(value=bool(current_value))
                    checkbox = ctk.CTkCheckBox(
                        frame,
                        text="",
                        variable=var,
                        onvalue=True,
                        offvalue=False
                    )
                    checkbox.pack(side="left")
                    entries[field_name] = var
                
                elif 'Date' in field_type:
                    entry_frame = ctk.CTkFrame(frame)
                    entry_frame.pack(side="left", fill="x", expand=True)
                    
                    if isinstance(current_value, date):
                        date_str = current_value.strftime('%Y-%m-%d')
                    elif isinstance(current_value, str) and current_value:
                        date_str = current_value
                    else:
                        date_str = ''
                    
                    entry = ctk.CTkEntry(
                        entry_frame,
                        width=120,
                        font=("Arial", 10)
                    )
                    entry.insert(0, date_str)
                    entry.pack(side="left")
                    
                    # زر التقويم
                    calendar_btn = ctk.CTkButton(
                        entry_frame,
                        text="📅",
                        width=30,
                        command=lambda e=entry: self.show_calendar(e)
                    )
                    calendar_btn.pack(side="left", padx=(5, 0))
                    
                    entries[field_name] = entry
                
                elif 'Text' in field_type:
                    # ننتقل للسطر التالي للحقول الطويلة
                    label2 = ctk.CTkLabel(
                        scrollable_frame,
                        text=f"{field_name}:",
                        font=("Arial", 10)
                    )
                    label2.pack(anchor="w", padx=10, pady=(10, 0))
                    
                    text_widget = scrolledtext.ScrolledText(
                        scrollable_frame,
                        height=3,
                        width=50,
                        font=("Arial", 10)
                    )
                    text_widget.insert(1.0, str(current_value))
                    text_widget.pack(fill="x", padx=10, pady=(0, 10))
                    
                    entries[field_name] = text_widget
                
                else:
                    entry = ctk.CTkEntry(
                        frame,
                        width=200,
                        font=("Arial", 10)
                    )
                    entry.insert(0, str(current_value))
                    entry.pack(side="left", fill="x", expand=True)
                    entries[field_name] = entry
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # أزرار الحفظ والإلغاء
            button_frame = ctk.CTkFrame(window)
            button_frame.pack(fill="x", padx=10, pady=10)
            
            save_btn = ctk.CTkButton(
                button_frame,
                text="💾 حفظ",
                command=lambda: self.save_record(window, model, entries, record),
                width=100,
                height=35,
                fg_color="green"
            )
            save_btn.pack(side="left", padx=10)
            
            cancel_btn = ctk.CTkButton(
                button_frame,
                text="❌ إلغاء",
                command=window.destroy,
                width=100,
                height=35,
                fg_color="red"
            )
            cancel_btn.pack(side="left", padx=10)
            
            print(f"✓ تم إنشاء نافذة {title}")
            return window
            
        except Exception as e:
            print(f"✗ خطأ في إنشاء نافذة الإضافة/التعديل: {e}")
            messagebox.showerror("خطأ", f"خطأ في إنشاء النافذة: {e}")
            window.destroy()
            return None
    
    def show_calendar(self, entry):
        """عرض نافذة التقويم"""
        # يمكن إضافة تقويم حقيقي هنا (مثل tkcalendar)
        messagebox.showinfo("معلومة", "يمكن إضافة تقويم حقيقي هنا")
    
    def save_record(self, window, model, entries, record=None):
        """حفظ السجل"""
        try:
            values = {}
            
            for field_name, widget in entries.items():
                if isinstance(widget, tk.BooleanVar):
                    values[f'-{field_name}-'] = widget.get()
                elif isinstance(widget, (ctk.CTkEntry, tk.Entry)):
                    values[f'-{field_name}-'] = widget.get()
                elif isinstance(widget, scrolledtext.ScrolledText):
                    values[f'-{field_name}-'] = widget.get(1.0, tk.END).strip()
            
            if record:  # تحديث
                record_id = record.get('id')
                if record_id:
                    success, message = self.update_record(model, record_id, values)
            else:  # إضافة
                success, message = self.add_record(model, values)
            
            if success:
                messagebox.showinfo("نجاح", message)
                window.destroy()
                self.on_view_click()  # تحديث العرض
            else:
                messagebox.showerror("خطأ", message)
                
        except Exception as e:
            messagebox.showerror("خطأ", f"خطأ في الحفظ: {str(e)}")
    
    def add_record(self, model, values):
        """إضافة سجل جديد"""
        try:
            print(f"جاري إضافة سجل جديد لـ {model.__name__}")
            new_record = model()
            
            for field in model.__table__.columns:
                field_name = field.name
                field_type = str(field.type)
                
                # تخطي الحقول التلقائية
                if field_name in ['id', 'created_at', 'updated_at']:
                    continue
                    
                if f'-{field_name}-' in values:
                    value = values[f'-{field_name}-']
                    
                    # معالجة القيم الفارغة
                    if value is None or (isinstance(value, str) and not value.strip()):
                        continue
                    
                    # تحويل القيمة
                    try:
                        if 'Integer' in field_type:
                            value = int(float(value)) if value else None
                        elif 'Float' in field_type:
                            value = float(value) if value else None
                        elif 'Boolean' in field_type:
                            value = bool(value)
                        elif 'Date' in field_type:
                            if value and isinstance(value, str):
                                value = datetime.strptime(value.strip(), '%Y-%m-%d').date()
                            else:
                                value = None
                        elif 'DateTime' in field_type:
                            if value and isinstance(value, str):
                                value = datetime.strptime(value.strip(), '%Y-%m-%d %H:%M:%S')
                            else:
                                value = None
                        elif 'Text' in field_type or 'String' in field_type:
                            value = str(value).strip()
                    except Exception as e:
                        print(f"تحذير: خطأ في تحويل {field_name}: {e}")
                        value = None
                    
                    if value is not None:
                        setattr(new_record, field_name, value)
            
            session.add(new_record)
            session.commit()
            
            msg = f"تمت إضافة سجل جديد بنجاح (ID: {new_record.id})"
            print(f"✓ {msg}")
            return True, msg
            
        except Exception as e:
            session.rollback()
            error_msg = f"خطأ في الإضافة: {str(e)}"
            print(f"✗ {error_msg}")
            return False, error_msg
    
    def update_record(self, model, record_id, values):
        """تحديث سجل موجود"""
        try:
            print(f"جاري تحديث السجل {record_id} لـ {model.__name__}")
            record = session.query(model).get(record_id)
            
            if not record:
                return False, f"لم يتم العثور على السجل {record_id}"
            
            for field in model.__table__.columns:
                field_name = field.name
                field_type = str(field.type)
                
                # تخطي الحقول التلقائية
                if field_name in ['id', 'created_at', 'updated_at']:
                    continue
                    
                if f'-{field_name}-' in values:
                    value = values[f'-{field_name}-']
                    
                    # معالجة القيم الفارغة
                    if value is None or (isinstance(value, str) and not value.strip()):
                        continue
                    
                    # تحويل القيمة
                    try:
                        if 'Integer' in field_type:
                            value = int(float(value)) if value else None
                        elif 'Float' in field_type:
                            value = float(value) if value else None
                        elif 'Boolean' in field_type:
                            value = bool(value)
                        elif 'Date' in field_type:
                            if value and isinstance(value, str):
                                value = datetime.strptime(value.strip(), '%Y-%m-%d').date()
                            else:
                                value = None
                        elif 'DateTime' in field_type:
                            if value and isinstance(value, str):
                                value = datetime.strptime(value.strip(), '%Y-%m-%d %H:%M:%S')
                            else:
                                value = None
                        elif 'Text' in field_type or 'String' in field_type:
                            value = str(value).strip()
                    except Exception as e:
                        print(f"تحذير: خطأ في تحويل {field_name}: {e}")
                        continue
                    
                    if value is not None:
                        setattr(record, field_name, value)
            
            session.commit()
            msg = f"تم تحديث السجل {record_id} بنجاح"
            print(f"✓ {msg}")
            return True, msg
            
        except Exception as e:
            session.rollback()
            error_msg = f"خطأ في التحديث: {str(e)}"
            print(f"✗ {error_msg}")
            return False, error_msg
    
    def on_add_click(self):
        """حدث النقر على زر الإضافة"""
        if not self.current_model:
            messagebox.showwarning("تحذير", "الرجاء اختيار نموذج أولاً")
            return
        
        self.create_add_edit_window(self.current_model)
    
    def on_edit_click(self):
        """حدث النقر على زر التعديل"""
        if not self.current_model:
            messagebox.showwarning("تحذير", "الرجاء اختيار نموذج أولاً")
            return
        
        # الحصول على معرف السجل المحدد
        record_id = self.get_selected_record_id()
        if not record_id:
            messagebox.showwarning("تحذير", "الرجاء تحديد سجل أولاً")
            return
        
        try:
            # الحصول على السجل الحالي
            record = session.query(self.current_model).get(record_id)
            if not record:
                messagebox.showerror("خطأ", f"لم يتم العثور على السجل {record_id}")
                return
            
            # تحويل السجل إلى قاموس
            record_dict = {'id': record_id}
            for field in self.current_model.__table__.columns:
                value = getattr(record, field.name, '')
                if value is None:
                    record_dict[field.name] = ''
                elif isinstance(value, date):
                    record_dict[field.name] = value.strftime('%Y-%m-%d')
                elif isinstance(value, datetime):
                    record_dict[field.name] = value.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(value, bool):
                    record_dict[field.name] = str(value)
                else:
                    record_dict[field.name] = str(value)
            
            # فتح نافذة التعديل
            self.create_add_edit_window(self.current_model, record_dict)
            
        except Exception as e:
            messagebox.showerror("خطأ", f"خطأ في التعديل: {str(e)}")
    
    def on_delete_click(self):
        """حدث النقر على زر الحذف"""
        if not self.current_model:
            messagebox.showwarning("تحذير", "الرجاء اختيار نموذج أولاً")
            return
        
        # الحصول على معرف السجل المحدد
        record_id = self.get_selected_record_id()
        if not record_id:
            messagebox.showwarning("تحذير", "الرجاء تحديد سجل أولاً")
            return
        
        # تأكيد الحذف
        confirm = messagebox.askyesno(
            "تأكيد الحذف",
            f"هل أنت متأكد من حذف السجل رقم {record_id}؟"
        )
        
        if confirm:
            success, message = self.delete_record(self.current_model, record_id)
            
            if success:
                messagebox.showinfo("نجاح", message)
                self.on_view_click()  # تحديث العرض
            else:
                messagebox.showerror("خطأ", message)
    
    def delete_record(self, model, record_id):
        """حذف سجل"""
        try:
            print(f"جاري حذف السجل {record_id} من {model.__name__}")
            record = session.query(model).get(record_id)
            
            if record:
                session.delete(record)
                session.commit()
                msg = f"تم حذف السجل {record_id} بنجاح"
                print(f"✓ {msg}")
                return True, msg
            else:
                msg = f"لم يتم العثور على السجل {record_id}"
                print(f"✗ {msg}")
                return False, msg
                
        except Exception as e:
            session.rollback()
            error_msg = f"خطأ في الحذف: {str(e)}"
            print(f"✗ {error_msg}")
            return False, error_msg
    
    def get_selected_record_id(self):
        """الحصول على معرف السجل المحدد من النص المعروض"""
        try:
            # في هذا الإصدار المبسط، سنطلب من المستخدم إدخال ID
            record_id = tk.simpledialog.askinteger(
                "تحديد السجل",
                "أدخل معرف السجل (ID):"
            )
            return record_id
            
        except Exception as e:
            print(f"خطأ في تحديد السجل: {e}")
            return None
    
    def on_search_click(self):
        """حدث النقر على زر البحث"""
        if not self.current_model:
            messagebox.showwarning("تحذير", "الرجاء اختيار نموذج أولاً")
            return
        
        search_term = self.search_entry.get().strip()
        if not search_term:
            messagebox.showwarning("تحذير", "الرجاء إدخال كلمة للبحث")
            return
        
        try:
            limit_str = self.limit_combo.get()
            limit = 0 if limit_str == "الكل" else int(limit_str)
            
            data = self.search_data(self.current_model, search_term, limit)
            self.data_text.delete(1.0, tk.END)
            self.data_text.insert(1.0, data)
            self.status_bar.configure(text=f'تم البحث عن: {search_term}')
        except Exception as e:
            messagebox.showerror("خطأ", f"خطأ في البحث: {str(e)}")
    
    def search_data(self, model, search_term, limit=50):
        """بحث في البيانات"""
        try:
            print(f"جاري البحث عن '{search_term}' في {model.__name__}")
            
            query = session.query(model)
            
            # البحث في الحقول النصية
            conditions = []
            
            for column in model.__table__.columns:
                column_type = str(column.type)
                if any(t in column_type for t in ['VARCHAR', 'String', 'Text', 'CHAR']):
                    conditions.append(column.ilike(f'%{search_term}%'))
            
            if conditions:
                query = query.filter(or_(*conditions))
            
            # تحديد الحد
            if limit > 0:
                records = query.limit(limit).all()
            else:
                records = query.all()
            
            self.current_data = records
            
            if not records:
                return f"❌ لا توجد نتائج للبحث عن: '{search_term}'"
            
            # تنسيق النتائج
            display_text = f"نتائج البحث عن: '{search_term}' ({len(records)} نتيجة)\n"
            display_text += "=" * 50 + "\n\n"
            
            for i, record in enumerate(records, 1):
                display_text += f"نتيجة #{i}:\n"
                display_text += "-" * 30 + "\n"
                
                # عرض الحقول الرئيسية
                for column in model.__table__.columns:
                    if column.name in ['id', 'name', 'username', 'title', 'description', 'email']:
                        value = getattr(record, column.name, '')
                        
                        if value is None:
                            value = ''
                        elif isinstance(value, (date, datetime)):
                            if isinstance(value, date):
                                value = value.strftime('%Y-%m-%d')
                            else:
                                value = value.strftime('%Y-%m-%d %H:%M')
                        
                        display_text += f"{column.name}: {value}\n"
                
                display_text += "\n"
            
            print(f"✓ وجد {len(records)} نتيجة")
            return display_text
            
        except Exception as e:
            error_msg = f"خطأ في البحث: {str(e)}"
            print(f"✗ {error_msg}")
            return error_msg
    
    def run(self):
        """تشغيل التطبيق"""
        print("\n" + "="*50)
        print("بدء تشغيل نظام إدارة الموارد البشرية")
        print("="*50 + "\n")
        
        try:
            self.root.mainloop()
        except Exception as e:
            print(f"✗ خطأ فادح: {str(e)}")
            traceback.print_exc()
            messagebox.showerror("خطأ فادح", f"خطأ فادح في التطبيق:\n{str(e)}")
        finally:
            session.close()
            print("\n✓ تم إغلاق التطبيق بنجاح")

if __name__ == "__main__":
    try:
        print("بدء تشغيل التطبيق...")
        app = CRUDApp()
        app.run()
    except Exception as e:
        print(f"✗ خطأ فادح: {str(e)}")
        traceback.print_exc()
        messagebox.showerror("خطأ فادح", f"خطأ فادح في التطبيق:\n{str(e)}")