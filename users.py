import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import pandas as pd
from PIL import Image, ImageTk
import threading

# Add the current directory to path to import models
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models import User, Department
from database import Base, db_session

class DepartmentTransferGUI:
    """Smart GUI interface for managing department transfers"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("نظام نقل الموظفين بين الأقسام - Smart Interface")
        self.root.geometry("1200x700")
        self.root.configure(bg='#f0f2f5')
        
        # Custom colors
        self.colors = {
            'primary': '#2c3e50',
            'secondary': '#3498db',
            'success': '#27ae60',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'light': '#ecf0f1',
            'dark': '#2c3e50',
            'info': '#17a2b8'
        }
        
        # Create session
        self.session = db_session
        
        # Initialize data
        self.departments = []
        self.users = []
        self.selected_users = []
        
        # Setup UI
        self.setup_ui()
        self.load_data()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Header
        header_frame = tk.Frame(self.root, bg=self.colors['primary'], height=80)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        title_label = tk.Label(
            header_frame,
            text="نظام إدارة ونقل الموظفين بين الأقسام",
            font=('Arial', 18, 'bold'),
            fg='white',
            bg=self.colors['primary']
        )
        title_label.pack(pady=20)
        
        # Main container
        main_container = tk.Frame(self.root, bg='#f0f2f5')
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Left panel - Departments
        left_panel = tk.Frame(main_container, bg='white', relief=tk.RAISED, bd=1)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Right panel - Users and Actions
        right_panel = tk.Frame(main_container, bg='white', relief=tk.RAISED, bd=1)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Department panel
        dept_header = tk.Frame(left_panel, bg=self.colors['secondary'], height=40)
        dept_header.pack(fill=tk.X)
        dept_header.pack_propagate(False)
        
        tk.Label(
            dept_header,
            text="الأقسام المتاحة",
            font=('Arial', 12, 'bold'),
            fg='white',
            bg=self.colors['secondary']
        ).pack(pady=8)
        
        # Search departments
        search_dept_frame = tk.Frame(left_panel, bg='white', padx=10, pady=10)
        search_dept_frame.pack(fill=tk.X)
        
        tk.Label(search_dept_frame, text="بحث:", bg='white').pack(side=tk.RIGHT, padx=(5, 0))
        self.dept_search_var = tk.StringVar()
        self.dept_search_var.trace('w', lambda *args: self.filter_departments())
        dept_search_entry = tk.Entry(search_dept_frame, textvariable=self.dept_search_var, width=30)
        dept_search_entry.pack(side=tk.RIGHT)
        
        # Departments treeview
        dept_tree_frame = tk.Frame(left_panel, bg='white')
        dept_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Scrollbar for departments
        dept_scrollbar = tk.Scrollbar(dept_tree_frame)
        dept_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.dept_tree = ttk.Treeview(
            dept_tree_frame,
            columns=('ID', 'Name', 'Employees'),
            show='headings',
            height=15,
            yscrollcommand=dept_scrollbar.set,
            selectmode='browse'
        )
        
        self.dept_tree.heading('ID', text='رقم', anchor=tk.CENTER)
        self.dept_tree.heading('Name', text='اسم القسم', anchor=tk.CENTER)
        self.dept_tree.heading('Employees', text='عدد الموظفين', anchor=tk.CENTER)
        
        self.dept_tree.column('ID', width=80, anchor=tk.CENTER)
        self.dept_tree.column('Name', width=200, anchor=tk.CENTER)
        self.dept_tree.column('Employees', width=100, anchor=tk.CENTER)
        
        self.dept_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dept_scrollbar.config(command=self.dept_tree.yview)
        
        # Bind selection
        self.dept_tree.bind('<<TreeviewSelect>>', self.on_dept_select)
        
        # Department actions
        dept_actions_frame = tk.Frame(left_panel, bg='white', padx=10, pady=10)
        dept_actions_frame.pack(fill=tk.X)
        
        tk.Button(
            dept_actions_frame,
            text="تحديث بيانات الأقسام",
            command=self.load_data,
            bg=self.colors['info'],
            fg='white',
            font=('Arial', 10, 'bold'),
            relief=tk.RAISED,
            padx=10,
            pady=5
        ).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(
            dept_actions_frame,
            text="تصدير بيانات الأقسام",
            command=self.export_departments,
            bg=self.colors['success'],
            fg='white',
            font=('Arial', 10, 'bold'),
            relief=tk.RAISED,
            padx=10,
            pady=5
        ).pack(side=tk.RIGHT, padx=5)
        
        # Users panel
        users_header = tk.Frame(right_panel, bg=self.colors['secondary'], height=40)
        users_header.pack(fill=tk.X)
        users_header.pack_propagate(False)
        
        tk.Label(
            users_header,
            text="الموظفون",
            font=('Arial', 12, 'bold'),
            fg='white',
            bg=self.colors['secondary']
        ).pack(pady=8)
        
        # Filter controls
        filter_frame = tk.Frame(right_panel, bg='white', padx=10, pady=10)
        filter_frame.pack(fill=tk.X)
        
        # Department filter
        tk.Label(filter_frame, text="القسم:", bg='white').pack(side=tk.RIGHT, padx=(10, 0))
        self.dept_filter_var = tk.StringVar(value="جميع الأقسام")
        self.dept_filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.dept_filter_var,
            state='readonly',
            width=25
        )
        self.dept_filter_combo.pack(side=tk.RIGHT, padx=5)
        self.dept_filter_combo.bind('<<ComboboxSelected>>', lambda e: self.filter_users())
        
        # Search users
        tk.Label(filter_frame, text="بحث:", bg='white').pack(side=tk.RIGHT, padx=(10, 0))
        self.user_search_var = tk.StringVar()
        self.user_search_var.trace('w', lambda *args: self.filter_users())
        user_search_entry = tk.Entry(filter_frame, textvariable=self.user_search_var, width=30)
        user_search_entry.pack(side=tk.RIGHT)
        
        # Users treeview with checkboxes
        users_tree_frame = tk.Frame(right_panel, bg='white')
        users_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        
        # Scrollbar for users
        user_scrollbar = tk.Scrollbar(users_tree_frame)
        user_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.users_tree = ttk.Treeview(
            users_tree_frame,
            columns=('Select', 'ID', 'Username', 'Name', 'Department'),
            show='headings',
            height=15,
            yscrollcommand=user_scrollbar.set
        )
        
        self.users_tree.heading('Select', text='تحديد', anchor=tk.CENTER)
        self.users_tree.heading('ID', text='رقم', anchor=tk.CENTER)
        self.users_tree.heading('Username', text='اسم المستخدم', anchor=tk.CENTER)
        self.users_tree.heading('Name', text='الاسم الكامل', anchor=tk.CENTER)
        self.users_tree.heading('Department', text='القسم الحالي', anchor=tk.CENTER)
        
        self.users_tree.column('Select', width=60, anchor=tk.CENTER)
        self.users_tree.column('ID', width=60, anchor=tk.CENTER)
        self.users_tree.column('Username', width=120, anchor=tk.CENTER)
        self.users_tree.column('Name', width=200, anchor=tk.CENTER)
        self.users_tree.column('Department', width=150, anchor=tk.CENTER)
        
        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        user_scrollbar.config(command=self.users_tree.yview)
        
        # Selection actions
        selection_frame = tk.Frame(right_panel, bg='white', padx=10, pady=10)
        selection_frame.pack(fill=tk.X)
        
        tk.Button(
            selection_frame,
            text="تحديد الكل",
            command=self.select_all_users,
            bg=self.colors['info'],
            fg='white',
            font=('Arial', 10),
            relief=tk.RAISED,
            padx=10,
            pady=5
        ).pack(side=tk.RIGHT, padx=5)
        
        tk.Button(
            selection_frame,
            text="إلغاء تحديد الكل",
            command=self.deselect_all_users,
            bg=self.colors['warning'],
            fg='white',
            font=('Arial', 10),
            relief=tk.RAISED,
            padx=10,
            pady=5
        ).pack(side=tk.RIGHT, padx=5)
        
        self.selected_count_label = tk.Label(
            selection_frame,
            text="0 مستخدم محدد",
            font=('Arial', 10, 'bold'),
            bg='white',
            fg=self.colors['primary']
        )
        self.selected_count_label.pack(side=tk.LEFT)
        
        # Transfer controls
        transfer_frame = tk.Frame(self.root, bg=self.colors['light'], relief=tk.RAISED, bd=1)
        transfer_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Target department selection
        target_frame = tk.Frame(transfer_frame, bg=self.colors['light'], padx=20, pady=15)
        target_frame.pack(fill=tk.X)
        
        tk.Label(
            target_frame,
            text="القسم الهدف:",
            font=('Arial', 12, 'bold'),
            bg=self.colors['light']
        ).pack(side=tk.RIGHT, padx=(10, 0))
        
        self.target_dept_var = tk.StringVar()
        self.target_dept_combo = ttk.Combobox(
            target_frame,
            textvariable=self.target_dept_var,
            state='readonly',
            width=30,
            font=('Arial', 11)
        )
        self.target_dept_combo.pack(side=tk.RIGHT, padx=5)
        
        # Transfer buttons
        button_frame = tk.Frame(transfer_frame, bg=self.colors['light'], padx=20, pady=10)
        button_frame.pack(fill=tk.X)
        
        # Bulk actions
        tk.Button(
            button_frame,
            text="📄 استيراد موظفين من ملف",
            command=self.import_from_file,
            bg=self.colors['info'],
            fg='white',
            font=('Arial', 11, 'bold'),
            relief=tk.RAISED,
            padx=15,
            pady=8,
            cursor='hand2'
        ).pack(side=tk.RIGHT, padx=10)
        
        tk.Button(
            button_frame,
            text="📤 تصدير الموظفين المحددين",
            command=self.export_selected_users,
            bg=self.colors['success'],
            fg='white',
            font=('Arial', 11, 'bold'),
            relief=tk.RAISED,
            padx=15,
            pady=8,
            cursor='hand2'
        ).pack(side=tk.RIGHT, padx=10)
        
        # Transfer action
        self.transfer_button = tk.Button(
            button_frame,
            text="🔄 نقل الموظفين المحددين",
            command=self.transfer_selected_users,
            bg=self.colors['primary'],
            fg='white',
            font=('Arial', 12, 'bold'),
            relief=tk.RAISED,
            padx=20,
            pady=10,
            cursor='hand2',
            state=tk.DISABLED
        )
        self.transfer_button.pack(side=tk.RIGHT, padx=10)
        
        # Status bar
        self.status_bar = tk.Label(
            self.root,
            text="جاهز - اختر الموظفين والقسم الهدف",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            bg=self.colors['dark'],
            fg='white',
            font=('Arial', 10)
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def load_data(self):
        """Load departments and users data"""
        try:
            self.status_bar.config(text="جاري تحميل البيانات...")
            self.root.update()
            
            # Load departments
            self.departments = self.session.query(Department).order_by(Department.name).all()
            
            # Update departments tree
            self.dept_tree.delete(*self.dept_tree.get_children())
            
            dept_items = []
            for dept in self.departments:
                employee_count = self.session.query(User).filter_by(
                    department_id=dept.id,
                    is_admin=False
                ).count()
                
                item_id = self.dept_tree.insert('', 'end', values=(
                    dept.id,
                    dept.name,
                    employee_count
                ))
                dept_items.append((dept.name, dept.id))
            
            # Update department filter combo
            self.dept_filter_combo['values'] = ['جميع الأقسام'] + [dept[0] for dept in dept_items]
            
            # Update target department combo
            self.target_dept_combo['values'] = [dept[0] for dept in dept_items]
            
            # Load users
            self.users = self.session.query(User).filter_by(is_admin=False).order_by(User.name).all()
            
            # Update users tree
            self.users_tree.delete(*self.users_tree.get_children())
            self.selected_users = []
            
            for user in self.users:
                dept_name = "غير معين"
                if user.department_id:
                    dept = next((d for d in self.departments if d.id == user.department_id), None)
                    dept_name = dept.name if dept else "غير معين"
                
                # Create checkbox
                checkbox_var = tk.BooleanVar(value=False)
                checkbox_var.trace('w', lambda *args, uid=user.id: self.on_user_check(uid, checkbox_var))
                
                item_id = self.users_tree.insert('', 'end', values=(
                    "☐",
                    user.id,
                    user.username,
                    user.name,
                    dept_name
                ), tags=(str(user.id),))
                
                # Store checkbox reference
                self.users_tree.set(item_id, column='Select', value="☐")
                
                # Bind checkbox click
                self.users_tree.tag_bind(str(user.id), '<Button-1>', 
                    lambda e, item=item_id, uid=user.id: self.toggle_user_check(item, uid))
            
            self.update_selected_count()
            self.status_bar.config(text=f"تم تحميل {len(self.departments)} قسم و {len(self.users)} موظف")
            
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ في تحميل البيانات: {str(e)}")
            self.status_bar.config(text="خطأ في تحميل البيانات")
    
    def filter_departments(self):
        """Filter departments based on search"""
        search_term = self.dept_search_var.get().lower()
        
        # Show all items first
        for item in self.dept_tree.get_children():
            self.dept_tree.item(item, tags=())
        
        if search_term:
            # Hide items that don't match
            for item in self.dept_tree.get_children():
                values = self.dept_tree.item(item, 'values')
                if values and values[1].lower().find(search_term) == -1:
                    self.dept_tree.detach(item)
    
    def filter_users(self):
        """Filter users based on criteria"""
        search_term = self.user_search_var.get().lower()
        dept_filter = self.dept_filter_var.get()
        
        # Show all items first
        for item in self.users_tree.get_children():
            self.users_tree.item(item, tags=())
        
        # Apply filters
        for item in self.users_tree.get_children():
            values = self.users_tree.item(item, 'values')
            show_item = True
            
            if search_term:
                # Search in username, name, and department
                search_text = f"{values[2]} {values[3]} {values[4]}".lower()
                if search_text.find(search_term) == -1:
                    show_item = False
            
            if dept_filter != "جميع الأقسام" and show_item:
                if values[4] != dept_filter:
                    show_item = False
            
            if not show_item:
                self.users_tree.detach(item)
    
    def on_dept_select(self, event):
        """Handle department selection"""
        selection = self.dept_tree.selection()
        if selection:
            dept_id = self.dept_tree.item(selection[0], 'values')[0]
            
            # Highlight users in this department
            for item in self.users_tree.get_children():
                values = self.users_tree.item(item, 'values')
                if values[4] == self.dept_tree.item(selection[0], 'values')[1]:
                    self.users_tree.item(item, tags=('selected_dept',))
                    self.users_tree.tag_configure('selected_dept', background='#e8f4f8')
                else:
                    self.users_tree.item(item, tags=())
    
    def toggle_user_check(self, item_id, user_id):
        """Toggle user checkbox"""
        current_val = self.users_tree.item(item_id, 'values')[0]
        new_val = "✓" if current_val == "☐" else "☐"
        self.users_tree.set(item_id, column='Select', value=new_val)
        
        if new_val == "✓":
            if user_id not in self.selected_users:
                self.selected_users.append(user_id)
        else:
            if user_id in self.selected_users:
                self.selected_users.remove(user_id)
        
        self.update_selected_count()
    
    def on_user_check(self, user_id, var):
        """Handle checkbox state change"""
        if var.get():
            if user_id not in self.selected_users:
                self.selected_users.append(user_id)
        else:
            if user_id in self.selected_users:
                self.selected_users.remove(user_id)
        
        self.update_selected_count()
    
    def select_all_users(self):
        """Select all visible users"""
        for item in self.users_tree.get_children():
            # Check if item is visible (not detached)
            if self.users_tree.item(item, 'tags'):
                values = self.users_tree.item(item, 'values')
                user_id = int(values[1])
                
                # Update checkbox display
                self.users_tree.set(item, column='Select', value="✓")
                
                # Add to selected list if not already
                if user_id not in self.selected_users:
                    self.selected_users.append(user_id)
        
        self.update_selected_count()
    
    def deselect_all_users(self):
        """Deselect all users"""
        for item in self.users_tree.get_children():
            # Update checkbox display
            self.users_tree.set(item, column='Select', value="☐")
        
        self.selected_users.clear()
        self.update_selected_count()
    
    def update_selected_count(self):
        """Update selected users count display"""
        count = len(self.selected_users)
        self.selected_count_label.config(text=f"{count} مستخدم محدد")
        
        # Enable/disable transfer button
        if count > 0 and self.target_dept_var.get():
            self.transfer_button.config(state=tk.NORMAL, bg=self.colors['success'])
        else:
            self.transfer_button.config(state=tk.DISABLED, bg='gray')
    
    def transfer_selected_users(self):
        """Transfer selected users to target department"""
        if not self.selected_users:
            messagebox.showwarning("تحذير", "الرجاء تحديد موظفين للنقل")
            return
        
        target_dept_name = self.target_dept_var.get()
        if not target_dept_name:
            messagebox.showwarning("تحذير", "الرجاء اختيار القسم الهدف")
            return
        
        # Find target department
        target_dept = next((d for d in self.departments if d.name == target_dept_name), None)
        if not target_dept:
            messagebox.showerror("خطأ", "القسم الهدف غير موجود")
            return
        
        # Confirm transfer
        confirm = messagebox.askyesno(
            "تأكيد النقل",
            f"هل أنت متأكد من نقل {len(self.selected_users)} موظف إلى قسم {target_dept_name}؟"
        )
        
        if not confirm:
            return
        
        # Perform transfer
        successful = []
        failed = []
        
        for user_id in self.selected_users:
            user = self.session.query(User).get(user_id)
            if user:
                old_dept_name = "غير معين"
                if user.department_id:
                    old_dept = next((d for d in self.departments if d.id == user.department_id), None)
                    old_dept_name = old_dept.name if old_dept else "غير معين"
                
                try:
                    user.department_id = target_dept.id
                    self.session.commit()
                    successful.append((user.name, old_dept_name))
                except Exception as e:
                    self.session.rollback()
                    failed.append((user.name, str(e)))
        
        # Show results
        result_message = f"✅ تم نقل {len(successful)} موظف بنجاح\n"
        
        if successful:
            result_message += "\nالموظفون الذين تم نقلهم:\n"
            for name, old_dept in successful[:10]:  # Show first 10
                result_message += f"• {name} (من {old_dept})\n"
            
            if len(successful) > 10:
                result_message += f"... و{len(successful) - 10} آخرين\n"
        
        if failed:
            result_message += f"\n❌ فشل نقل {len(failed)} موظف:\n"
            for name, error in failed:
                result_message += f"• {name}: {error}\n"
        
        # Show detailed results in new window
        self.show_transfer_results(successful, failed, target_dept_name)
        
        # Reload data
        self.load_data()
    
    def show_transfer_results(self, successful, failed, target_dept):
        """Show transfer results in a detailed window"""
        result_window = tk.Toplevel(self.root)
        result_window.title("نتيجة عملية النقل")
        result_window.geometry("600x500")
        result_window.configure(bg='white')
        
        # Header
        header_frame = tk.Frame(result_window, bg=self.colors['primary'], height=60)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        tk.Label(
            header_frame,
            text=f"نتيجة النقل إلى قسم: {target_dept}",
            font=('Arial', 14, 'bold'),
            fg='white',
            bg=self.colors['primary']
        ).pack(pady=15)
        
        # Stats
        stats_frame = tk.Frame(result_window, bg='white', padx=20, pady=10)
        stats_frame.pack(fill=tk.X)
        
        tk.Label(
            stats_frame,
            text=f"✅ {len(successful)} نجاح | ❌ {len(failed)} فشل",
            font=('Arial', 12, 'bold'),
            bg='white',
            fg=self.colors['dark']
        ).pack()
        
        # Results notebook
        notebook = ttk.Notebook(result_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Successful transfers tab
        success_frame = tk.Frame(notebook, bg='white')
        notebook.add(success_frame, text=f"✅ الناجحون ({len(successful)})")
        
        success_text = scrolledtext.ScrolledText(success_frame, wrap=tk.WORD, height=15)
        success_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        for name, old_dept in successful:
            success_text.insert(tk.END, f"• {name} (من قسم {old_dept})\n")
        
        success_text.config(state=tk.DISABLED)
        
        # Failed transfers tab
        if failed:
            fail_frame = tk.Frame(notebook, bg='white')
            notebook.add(fail_frame, text=f"❌ الفاشلون ({len(failed)})")
            
            fail_text = scrolledtext.ScrolledText(fail_frame, wrap=tk.WORD, height=15)
            fail_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            for name, error in failed:
                fail_text.insert(tk.END, f"• {name}: {error}\n")
            
            fail_text.config(state=tk.DISABLED)
        
        # Export button
        export_frame = tk.Frame(result_window, bg='white', pady=10)
        export_frame.pack(fill=tk.X)
        
        tk.Button(
            export_frame,
            text="📥 تصدير التقرير",
            command=lambda: self.export_transfer_report(successful, failed, target_dept),
            bg=self.colors['success'],
            fg='white',
            font=('Arial', 10, 'bold'),
            relief=tk.RAISED,
            padx=15,
            pady=5
        ).pack()
    
    def import_from_file(self):
        """Import users from file for transfer"""
        file_path = filedialog.askopenfilename(
            title="اختر ملف المستخدمين",
            filetypes=[
                ("Text files", "*.txt"),
                ("Excel files", "*.xlsx *.xls"),
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            if file_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_path)
            elif file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            else:
                # Read as text file
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip()]
                
                user_ids = []
                usernames = []
                
                for line in lines:
                    if line.isdigit():
                        user_ids.append(int(line))
                    else:
                        usernames.append(line)
                
                # Show import dialog
                import_dialog = tk.Toplevel(self.root)
                import_dialog.title("استيراد موظفين")
                import_dialog.geometry("400x300")
                import_dialog.configure(bg='white')
                
                tk.Label(
                    import_dialog,
                    text=f"تم العثور على {len(user_ids)} رقم و {len(usernames)} اسم",
                    font=('Arial', 11),
                    bg='white',
                    pady=10
                ).pack()
                
                # Preview
                preview_text = scrolledtext.ScrolledText(import_dialog, height=10)
                preview_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
                
                if user_ids:
                    preview_text.insert(tk.END, "الأرقام:\n")
                    for uid in user_ids[:20]:
                        user = self.session.query(User).get(uid)
                        preview_text.insert(tk.END, f"• {uid}: {user.name if user else 'غير موجود'}\n")
                
                if usernames:
                    preview_text.insert(tk.END, "\nأسماء المستخدمين:\n")
                    for uname in usernames[:20]:
                        user = self.session.query(User).filter_by(username=uname).first()
                        preview_text.insert(tk.END, f"• {uname}: {user.name if user else 'غير موجود'}\n")
                
                preview_text.config(state=tk.DISABLED)
                
                # Import button
                def process_import():
                    # Select users
                    for uid in user_ids:
                        user = self.session.query(User).get(uid)
                        if user and user.id not in self.selected_users:
                            self.selected_users.append(user.id)
                    
                    for uname in usernames:
                        user = self.session.query(User).filter_by(username=uname).first()
                        if user and user.id not in self.selected_users:
                            self.selected_users.append(user.id)
                    
                    # Update display
                    self.update_selected_users_display()
                    import_dialog.destroy()
                    messagebox.showinfo("نجاح", f"تم تحديد {len(self.selected_users)} موظف")
                
                tk.Button(
                    import_dialog,
                    text="استيراد",
                    command=process_import,
                    bg=self.colors['success'],
                    fg='white',
                    font=('Arial', 10, 'bold'),
                    relief=tk.RAISED,
                    padx=15,
                    pady=5
                ).pack(pady=10)
                
                return
            
            # Handle Excel/CSV import
            import_window = tk.Toplevel(self.root)
            import_window.title("استيراد من جدول")
            import_window.geometry("800x600")
            
            # Show preview
            preview_text = scrolledtext.ScrolledText(import_window, wrap=tk.WORD)
            preview_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            preview_text.insert(tk.END, f"تم تحميل {len(df)} سطر:\n\n")
            preview_text.insert(tk.END, df.head().to_string())
            preview_text.config(state=tk.DISABLED)
            
            # Column selection
            col_frame = tk.Frame(import_window)
            col_frame.pack(fill=tk.X, padx=10, pady=5)
            
            tk.Label(col_frame, text="اختر عمود أرقام الموظفين:").pack(side=tk.LEFT, padx=5)
            col_var = tk.StringVar()
            col_combo = ttk.Combobox(col_frame, textvariable=col_var, values=list(df.columns))
            col_combo.pack(side=tk.LEFT, padx=5)
            
            def process_excel_import():
                selected_col = col_var.get()
                if selected_col and selected_col in df.columns:
                    user_ids = []
                    for value in df[selected_col]:
                        try:
                            uid = int(float(value))
                            user_ids.append(uid)
                        except:
                            pass
                    
                    # Add to selection
                    for uid in user_ids:
                        user = self.session.query(User).get(uid)
                        if user and user.id not in self.selected_users:
                            self.selected_users.append(user.id)
                    
                    self.update_selected_users_display()
                    import_window.destroy()
                    messagebox.showinfo("نجاح", f"تم تحديد {len(user_ids)} موظف")
            
            tk.Button(
                import_window,
                text="استيراد",
                command=process_excel_import,
                bg=self.colors['success'],
                fg='white'
            ).pack(pady=10)
            
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ في قراءة الملف: {str(e)}")
    
    def update_selected_users_display(self):
        """Update checkboxes for selected users"""
        for item in self.users_tree.get_children():
            values = self.users_tree.item(item, 'values')
            if values:
                user_id = int(values[1])
                if user_id in self.selected_users:
                    self.users_tree.set(item, column='Select', value="✓")
        
        self.update_selected_count()
    
    def export_selected_users(self):
        """Export selected users to file"""
        if not self.selected_users:
            messagebox.showwarning("تحذير", "لا يوجد موظفين محددين للتصدير")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("CSV files", "*.csv"),
                ("Text files", "*.txt")
            ],
            initialfile=f"موظفين_{datetime.now().strftime('%Y%m%d_%H%M')}"
        )
        
        if not file_path:
            return
        
        try:
            # Get selected users data
            users_data = []
            for user_id in self.selected_users:
                user = self.session.query(User).get(user_id)
                if user:
                    dept_name = "غير معين"
                    if user.department_id:
                        dept = next((d for d in self.departments if d.id == user.department_id), None)
                        dept_name = dept.name if dept else "غير معين"
                    
                    users_data.append({
                        'رقم الموظف': user.id,
                        'اسم المستخدم': user.username,
                        'الاسم الكامل': user.name,
                        'القسم الحالي': dept_name,
                        'تاريخ الإضافة': datetime.now().strftime('%Y-%m-%d %H:%M')
                    })
            
            df = pd.DataFrame(users_data)
            
            if file_path.endswith('.xlsx'):
                df.to_excel(file_path, index=False, engine='openpyxl')
            elif file_path.endswith('.csv'):
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for user in users_data:
                        f.write(f"{user['رقم الموظف']}, {user['اسم المستخدم']}, {user['الاسم الكامل']}\n")
            
            messagebox.showinfo("نجاح", f"تم تصدير {len(users_data)} موظف إلى {file_path}")
            
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ في التصدير: {str(e)}")
    
    def export_departments(self):
        """Export departments data"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("CSV files", "*.csv")
            ],
            initialfile=f"أقسام_{datetime.now().strftime('%Y%m%d_%H%M')}"
        )
        
        if not file_path:
            return
        
        try:
            dept_data = []
            for dept in self.departments:
                employee_count = self.session.query(User).filter_by(
                    department_id=dept.id,
                    is_admin=False
                ).count()
                
                dept_data.append({
                    'رقم القسم': dept.id,
                    'اسم القسم': dept.name,
                    'عدد الموظفين': employee_count,
                    'تاريخ الإنشاء': dept.created_at.strftime('%Y-%m-%d') if dept.created_at else '',
                    'المدير': dept.primary_manager.name if dept.primary_manager else ''
                })
            
            df = pd.DataFrame(dept_data)
            
            if file_path.endswith('.xlsx'):
                df.to_excel(file_path, index=False, engine='openpyxl')
            elif file_path.endswith('.csv'):
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            
            messagebox.showinfo("نجاح", f"تم تصدير {len(dept_data)} قسم إلى {file_path}")
            
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ في التصدير: {str(e)}")
    
    def export_transfer_report(self, successful, failed, target_dept):
        """Export transfer report"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[
                ("Excel files", "*.xlsx"),
                ("CSV files", "*.csv"),
                ("Text files", "*.txt")
            ],
            initialfile=f"تقرير_نقل_{datetime.now().strftime('%Y%m%d_%H%M')}"
        )
        
        if not file_path:
            return
        
        try:
            report_data = []
            
            # Successful transfers
            for name, old_dept in successful:
                report_data.append({
                    'النوع': 'ناجح',
                    'اسم الموظف': name,
                    'القسم السابق': old_dept,
                    'القسم الجديد': target_dept,
                    'الحالة': 'تم النقل'
                })
            
            # Failed transfers
            for name, error in failed:
                report_data.append({
                    'النوع': 'فاشل',
                    'اسم الموظف': name,
                    'القسم السابق': 'غير معروف',
                    'القسم الجديد': target_dept,
                    'الحالة': f'فشل: {error}'
                })
            
            df = pd.DataFrame(report_data)
            
            if file_path.endswith('.xlsx'):
                with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                    # Summary sheet
                    summary_data = {
                        'إجمالي المحددين': [len(successful) + len(failed)],
                        'الناجحون': [len(successful)],
                        'الفاشلون': [len(failed)],
                        'تاريخ العملية': [datetime.now().strftime('%Y-%m-%d %H:%M')],
                        'القسم الهدف': [target_dept]
                    }
                    pd.DataFrame(summary_data).to_excel(writer, sheet_name='ملخص', index=False)
                    
                    # Details sheet
                    df.to_excel(writer, sheet_name='التفاصيل', index=False)
                    
                    # Formatting
                    workbook = writer.book
                    worksheet = writer.sheets['ملخص']
                    
                    # Apply formatting
                    for row in worksheet.iter_rows(min_row=1, max_row=1):
                        for cell in row:
                            cell.font = workbook.add_format({'bold': True, 'bg_color': '#2c3e50', 'color': 'white'})
                    
            elif file_path.endswith('.csv'):
                df.to_csv(file_path, index=False, encoding='utf-8-sig')
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"تقرير نقل الموظفين\n")
                    f.write(f"التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                    f.write(f"القسم الهدف: {target_dept}\n")
                    f.write(f"إجمالي المحددين: {len(successful) + len(failed)}\n")
                    f.write(f"الناجحون: {len(successful)}\n")
                    f.write(f"الفاشلون: {len(failed)}\n\n")
                    
                    f.write("الناجحون:\n")
                    for name, old_dept in successful:
                        f.write(f"• {name} (من {old_dept})\n")
                    
                    if failed:
                        f.write("\nالفاشلون:\n")
                        for name, error in failed:
                            f.write(f"• {name}: {error}\n")
            
            messagebox.showinfo("نجاح", f"تم تصدير التقرير إلى {file_path}")
            
        except Exception as e:
            messagebox.showerror("خطأ", f"حدث خطأ في تصدير التقرير: {str(e)}")

def main():
    """Main function"""
    root = tk.Tk()
    
    # Set window icon and style
    root.iconbitmap(default='')  # Add icon path if available
    
    # Configure ttk style
    style = ttk.Style()
    style.theme_use('clam')
    
    # Configure colors
    style.configure('Treeview', 
                   background='white',
                   foreground='black',
                   rowheight=25,
                   fieldbackground='white')
    style.map('Treeview', background=[('selected', '#3498db')])
    
    # Create and run app
    app = DepartmentTransferGUI(root)
    
    # Center window on screen
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    root.mainloop()

if __name__ == "__main__":
    main()