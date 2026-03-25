#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User and Department Management System - UPDATED
A graphical interface to manage users, departments, and department managers
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import sqlite3
from datetime import datetime
import sys
import os

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class DatabaseManager:
    """Database manager for user and department operations - UPDATED for hr_system"""
    
    def __init__(self, db_path='hr_system.db'):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()
    
    def connect(self):
        """Connect to the database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            print("Connected to database successfully")
            
            # Test connection by checking available tables
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = self.cursor.fetchall()
            print(f"Available tables: {[table[0] for table in tables]}")
            
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            print("Database connection closed")
    
    def get_all_users(self):
        """Get all users from database - UPDATED for your schema"""
        try:
            query = """
            SELECT 
                u.id, u.username, u.name, u.email, u.is_admin, 
                u.is_manager, u.is_active, u.department_id,
                d.name as department_name
            FROM users u
            LEFT JOIN departments d ON u.department_id = d.id
            ORDER BY u.name
            """
            self.cursor.execute(query)
            users = self.cursor.fetchall()
            
            # Convert to list of dictionaries
            columns = ['id', 'username', 'name', 'email', 'is_admin', 
                      'is_manager', 'is_active', 'department_id', 'department_name']
            return [dict(zip(columns, user)) for user in users]
        except sqlite3.Error as e:
            print(f"Error fetching users: {e}")
            # Try with different table names
            try:
                # Check what tables exist
                self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%user%';")
                user_tables = self.cursor.fetchall()
                print(f"User tables found: {user_tables}")
                
                # If no users found, return empty list
                return []
            except:
                return []
    
    def get_all_departments(self):
        """Get all departments from database - UPDATED for your schema"""
        try:
            query = """
            SELECT 
                d.id, d.name, d.primary_manager_id,
                u.name as manager_name,
                COUNT(emp.id) as employee_count
            FROM departments d
            LEFT JOIN users u ON d.primary_manager_id = u.id
            LEFT JOIN users emp ON emp.department_id = d.id AND emp.is_admin = 0
            GROUP BY d.id
            ORDER BY d.name
            """
            self.cursor.execute(query)
            departments = self.cursor.fetchall()
            
            columns = ['id', 'name', 'primary_manager_id', 'manager_name', 'employee_count']
            return [dict(zip(columns, dept)) for dept in departments]
        except sqlite3.Error as e:
            print(f"Error fetching departments: {e}")
            # Try with different table names
            try:
                # Check what tables exist
                self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%department%';")
                dept_tables = self.cursor.fetchall()
                print(f"Department tables found: {dept_tables}")
                
                # If no departments found, return empty list
                return []
            except:
                return []
    
    def get_available_managers(self):
        """Get all users who can be managers (non-admin, active users)"""
        try:
            query = """
            SELECT id, username, name 
            FROM users 
            WHERE is_admin = 0 AND is_active = 1
            ORDER BY name
            """
            self.cursor.execute(query)
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"Error fetching available managers: {e}")
            return []
    
    def get_department_users(self, department_id):
        """Get all users in a specific department"""
        try:
            query = """
            SELECT id, username, name, is_manager, is_active
            FROM users
            WHERE department_id = ? AND is_admin = 0
            ORDER BY name
            """
            self.cursor.execute(query, (department_id,))
            users = self.cursor.fetchall()
            
            columns = ['id', 'username', 'name', 'is_manager', 'is_active']
            return [dict(zip(columns, user)) for user in users]
        except sqlite3.Error as e:
            print(f"Error fetching department users: {e}")
            return []
    
    def create_user(self, username, name, email, password, is_admin=False, is_manager=False, department_id=None):
        """Create a new user - UPDATED for your schema"""
        try:
            # Check if username already exists
            self.cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if self.cursor.fetchone():
                return False, "Username already exists"
            
            # Create user
            query = """
            INSERT INTO users 
            (username, name, email, password_hash, is_admin, is_manager, department_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # In a real application, you should hash the password
            # For now, we'll use a simple hash
            import hashlib
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            
            self.cursor.execute(query, (username, name, email, password_hash, 
                                       int(is_admin), int(is_manager), department_id, datetime.now()))
            
            user_id = self.cursor.lastrowid
            
            # Create employee balance for non-admin users
            if not is_admin:
                try:
                    balance_query = """
                    INSERT INTO employee_balances (user_id, leave_balance, permission_balance)
                    VALUES (?, 12, 2)
                    """
                    self.cursor.execute(balance_query, (user_id,))
                except sqlite3.Error as e:
                    print(f"Note: Could not create employee balance: {e}")
                    # Continue without employee balance
            
            self.conn.commit()
            return True, f"User '{username}' created successfully"
            
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, f"Error creating user: {e}"
    
    def update_user(self, user_id, username, name, email, is_admin, is_manager, department_id, is_active):
        """Update user information"""
        try:
            # Check if username already exists for another user
            self.cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", (username, user_id))
            if self.cursor.fetchone():
                return False, "Username already exists for another user"
            
            query = """
            UPDATE users 
            SET username = ?, name = ?, email = ?, 
                is_admin = ?, is_manager = ?, department_id = ?, is_active = ?
            WHERE id = ?
            """
            
            self.cursor.execute(query, (username, name, email, 
                                       int(is_admin), int(is_manager), department_id, int(is_active), user_id))
            
            # If user is no longer a manager, check if they're primary manager of any department
            if not is_manager:
                try:
                    self.cursor.execute("SELECT id FROM departments WHERE primary_manager_id = ?", (user_id,))
                    departments = self.cursor.fetchall()
                    for dept in departments:
                        self.cursor.execute("UPDATE departments SET primary_manager_id = NULL WHERE id = ?", (dept[0],))
                except sqlite3.Error:
                    pass  # Ignore if departments table doesn't exist
            
            self.conn.commit()
            return True, f"User '{username}' updated successfully"
            
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, f"Error updating user: {e}"
    
    def delete_user(self, user_id):
        """Delete a user"""
        try:
            # Get user info before deletion
            self.cursor.execute("SELECT username FROM users WHERE id = ?", (user_id,))
            user = self.cursor.fetchone()
            if not user:
                return False, "User not found"
            
            # Check if user is primary manager of any department
            try:
                self.cursor.execute("SELECT name FROM departments WHERE primary_manager_id = ?", (user_id,))
                managed_depts = self.cursor.fetchall()
                
                if managed_depts:
                    dept_names = ", ".join([dept[0] for dept in managed_depts])
                    return False, f"Cannot delete user who is primary manager of: {dept_names}"
            except sqlite3.Error:
                pass  # Ignore if departments table doesn't exist
            
            # Delete related records first
            try:
                # Delete employee balance
                self.cursor.execute("DELETE FROM employee_balances WHERE user_id = ?", (user_id,))
                
                # Delete employee data
                self.cursor.execute("DELETE FROM employee_data WHERE user_id = ?", (user_id,))
            except sqlite3.Error:
                pass  # Ignore if tables don't exist
            
            # Delete user
            self.cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            
            self.conn.commit()
            return True, f"User '{user[0]}' deleted successfully"
            
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, f"Error deleting user: {e}"
    
    def create_department(self, name, primary_manager_id=None):
        """Create a new department"""
        try:
            # Check if department table exists
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='departments'")
            if not self.cursor.fetchone():
                return False, "Departments table does not exist in the database"
            
            # Check if department name already exists
            self.cursor.execute("SELECT id FROM departments WHERE name = ?", (name,))
            if self.cursor.fetchone():
                return False, "Department name already exists"
            
            query = """
            INSERT INTO departments (name, primary_manager_id, created_at)
            VALUES (?, ?, ?)
            """
            
            self.cursor.execute(query, (name, primary_manager_id, datetime.now()))
            dept_id = self.cursor.lastrowid
            
            # Update the manager if primary_manager_id is provided
            if primary_manager_id:
                self.cursor.execute(
                    "UPDATE users SET is_manager = 1, department_id = ? WHERE id = ?",
                    (dept_id, primary_manager_id)
                )
            
            self.conn.commit()
            return True, f"Department '{name}' created successfully"
            
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, f"Error creating department: {e}"
        except Exception as e:
            return False, f"Error: {e}"
    
    def update_department(self, department_id, name, primary_manager_id):
        """Update department information"""
        try:
            # Check if department name already exists for another department
            self.cursor.execute("SELECT id FROM departments WHERE name = ? AND id != ?", (name, department_id))
            if self.cursor.fetchone():
                return False, "Department name already exists for another department"
            
            # Get current primary manager
            self.cursor.execute("SELECT primary_manager_id FROM departments WHERE id = ?", (department_id,))
            current_manager = self.cursor.fetchone()
            current_manager_id = current_manager[0] if current_manager else None
            
            # Update department
            query = "UPDATE departments SET name = ?, primary_manager_id = ? WHERE id = ?"
            self.cursor.execute(query, (name, primary_manager_id, department_id))
            
            # Handle manager changes
            if current_manager_id != primary_manager_id:
                # Remove manager role from old manager if not managing any other department
                if current_manager_id:
                    self.cursor.execute(
                        "SELECT COUNT(*) FROM departments WHERE primary_manager_id = ? AND id != ?",
                        (current_manager_id, department_id)
                    )
                    other_depts = self.cursor.fetchone()[0]
                    
                    if other_depts == 0:
                        self.cursor.execute(
                            "UPDATE users SET is_manager = 0 WHERE id = ?",
                            (current_manager_id,)
                        )
                
                # Add manager role to new manager
                if primary_manager_id:
                    self.cursor.execute(
                        "UPDATE users SET is_manager = 1, department_id = ? WHERE id = ?",
                        (department_id, primary_manager_id)
                    )
            
            self.conn.commit()
            return True, f"Department '{name}' updated successfully"
            
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, f"Error updating department: {e}"
    
    def delete_department(self, department_id):
        """Delete a department"""
        try:
            # Get department info before deletion
            self.cursor.execute("SELECT name FROM departments WHERE id = ?", (department_id,))
            dept = self.cursor.fetchone()
            if not dept:
                return False, "Department not found"
            
            # Check if department has users
            self.cursor.execute("SELECT COUNT(*) FROM users WHERE department_id = ?", (department_id,))
            user_count = self.cursor.fetchone()[0]
            
            if user_count > 0:
                return False, f"Cannot delete department with {user_count} users. Reassign users first."
            
            # Delete department
            self.cursor.execute("DELETE FROM departments WHERE id = ?", (department_id,))
            
            self.conn.commit()
            return True, f"Department '{dept[0]}' deleted successfully"
            
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, f"Error deleting department: {e}"
    
    def assign_users_to_department(self, user_ids, department_id):
        """Assign multiple users to a department"""
        try:
            # Get department name for message
            dept_name = "Unknown"
            if department_id:
                self.cursor.execute("SELECT name FROM departments WHERE id = ?", (department_id,))
                dept = self.cursor.fetchone()
                if dept:
                    dept_name = dept[0]
            
            # Update each user
            success_count = 0
            for user_id in user_ids:
                self.cursor.execute(
                    "UPDATE users SET department_id = ? WHERE id = ?",
                    (department_id, user_id)
                )
                success_count += 1
            
            self.conn.commit()
            return True, f"Assigned {success_count} users to department '{dept_name}'"
            
        except sqlite3.Error as e:
            self.conn.rollback()
            return False, f"Error assigning users: {e}"
    
    def get_user_activity(self, user_id):
        """Get user activity statistics"""
        try:
            activity = {
                'leave_requests': 0,
                'permission_requests': 0,
                'salary_slips': 0
            }
            
            # Check for leave_requests table
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='leave_requests'")
            if self.cursor.fetchone():
                self.cursor.execute(
                    "SELECT COUNT(*) FROM leave_requests WHERE user_id = ?",
                    (user_id,)
                )
                activity['leave_requests'] = self.cursor.fetchone()[0]
            
            # Check for permission_requests table
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='permission_requests'")
            if self.cursor.fetchone():
                self.cursor.execute(
                    "SELECT COUNT(*) FROM permission_requests WHERE user_id = ?",
                    (user_id,)
                )
                activity['permission_requests'] = self.cursor.fetchone()[0]
            
            # Check for salary_slips table
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='salary_slips'")
            if self.cursor.fetchone():
                self.cursor.execute(
                    "SELECT COUNT(*) FROM salary_slips WHERE user_id = ?",
                    (user_id,)
                )
                activity['salary_slips'] = self.cursor.fetchone()[0]
            
            return activity
            
        except sqlite3.Error as e:
            print(f"Error getting user activity: {e}")
            return {'leave_requests': 0, 'permission_requests': 0, 'salary_slips': 0}
    
    def check_database_structure(self):
        """Check and report on database structure"""
        try:
            print("\n" + "="*60)
            print("DATABASE STRUCTURE CHECK")
            print("="*60)
            
            # Get all tables
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
            tables = self.cursor.fetchall()
            
            print(f"\nTotal tables found: {len(tables)}")
            for table in tables:
                print(f"  - {table[0]}")
                
                # Get column information
                try:
                    self.cursor.execute(f"PRAGMA table_info({table[0]});")
                    columns = self.cursor.fetchall()
                    print(f"    Columns: {len(columns)}")
                    for col in columns[:3]:  # Show first 3 columns
                        print(f"      {col[1]} ({col[2]})")
                    if len(columns) > 3:
                        print(f"      ... and {len(columns)-3} more")
                except:
                    print(f"    Could not read column info")
            
            print("\n" + "="*60)
            
            # Check for required tables
            required_tables = ['users', 'departments']
            missing_tables = []
            
            for req_table in required_tables:
                found = False
                for table in tables:
                    if table[0].lower() == req_table.lower():
                        found = True
                        break
                if not found:
                    missing_tables.append(req_table)
            
            if missing_tables:
                print(f"\n⚠️  Missing required tables: {missing_tables}")
                print("   The application may not work properly.")
            else:
                print("\n✅ All required tables found!")
            
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"Error checking database structure: {e}")


class UserManagementApp:
    """Main application for user and department management"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("User and Department Management System - HR System")
        self.root.geometry("1200x700")
        
        # Initialize database manager
        self.db = DatabaseManager()
        
        # Check database structure
        self.db.check_database_structure()
        
        # Configure styles
        self.setup_styles()
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create tabs
        self.create_users_tab()
        self.create_departments_tab()
        self.create_assignments_tab()
        self.create_statistics_tab()
        
        # Status bar
        self.status_bar = tk.Label(root, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Load initial data
        self.refresh_all_tabs()
        
        # Check if database is properly set up
        self.check_database_setup()
    
    def setup_styles(self):
        """Configure tkinter styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure colors
        style.configure('Title.TLabel', font=('Arial', 14, 'bold'))
        style.configure('Header.TLabel', font=('Arial', 11, 'bold'))
        style.configure('Success.TLabel', foreground='green')
        style.configure('Error.TLabel', foreground='red')
        
        # Configure button styles
        style.configure('Primary.TButton', font=('Arial', 10, 'bold'))
        style.configure('Success.TButton', background='green', foreground='white')
        style.configure('Danger.TButton', background='red', foreground='white')
    
    def check_database_setup(self):
        """Check if database is properly set up"""
        try:
            users = self.db.get_all_users()
            departments = self.db.get_all_departments()
            
            if not users and not departments:
                response = messagebox.askyesno(
                    "Database Setup",
                    "No users or departments found in the database.\n\n"
                    "Would you like to create a default admin user?"
                )
                
                if response:
                    self.create_default_admin()
            
        except Exception as e:
            print(f"Error checking database setup: {e}")
    
    def create_default_admin(self):
        """Create a default admin user"""
        try:
            success, message = self.db.create_user(
                username='admin',
                name='System Administrator',
                email='admin@example.com',
                password='admin123',
                is_admin=True,
                is_manager=True
            )
            
            if success:
                messagebox.showinfo("Success", 
                                  "Default admin user created successfully!\n\n"
                                  "Username: admin\n"
                                  "Password: admin123\n\n"
                                  "Please change the password after first login.")
                self.refresh_all_tabs()
            else:
                messagebox.showerror("Error", f"Failed to create admin user: {message}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create admin user: {str(e)}")
            
    def create_users_tab(self):
        """Create users management tab"""
        self.users_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.users_tab, text='Users Management')
        
        # Top frame for user list
        top_frame = ttk.Frame(self.users_tab)
        top_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # User list frame
        list_frame = ttk.LabelFrame(top_frame, text="Users List", padding=10)
        list_frame.pack(side=tk.LEFT, fill='both', expand=True, padx=(0, 5))
        
        # Treeview for users
        columns = ('ID', 'Username', 'Name', 'Email', 'Admin', 'Manager', 'Active', 'Department')
        self.users_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)
        
        # Define headings
        for col in columns:
            self.users_tree.heading(col, text=col)
            self.users_tree.column(col, width=100)
        
        # Adjust column widths
        self.users_tree.column('ID', width=50)
        self.users_tree.column('Username', width=100)
        self.users_tree.column('Name', width=150)
        self.users_tree.column('Email', width=150)
        self.users_tree.column('Admin', width=60)
        self.users_tree.column('Manager', width=70)
        self.users_tree.column('Active', width=60)
        self.users_tree.column('Department', width=150)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=scrollbar.set)
        
        self.users_tree.pack(side=tk.LEFT, fill='both', expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection event
        self.users_tree.bind('<<TreeviewSelect>>', self.on_user_select)
        
        # Action buttons frame
        action_frame = ttk.Frame(top_frame)
        action_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # Action buttons
        ttk.Label(action_frame, text="User Actions", font=('Arial', 11, 'bold')).pack(pady=(0, 10))
        
        self.create_user_btn = ttk.Button(action_frame, text="Create New User", 
                                         command=self.open_create_user_dialog)
        self.create_user_btn.pack(pady=5, fill=tk.X)
        
        self.edit_user_btn = ttk.Button(action_frame, text="Edit Selected User", 
                                       command=self.open_edit_user_dialog, state='disabled')
        self.edit_user_btn.pack(pady=5, fill=tk.X)
        
        self.delete_user_btn = ttk.Button(action_frame, text="Delete Selected User", 
                                         command=self.delete_user, state='disabled')
        self.delete_user_btn.pack(pady=5, fill=tk.X)
        
        self.view_details_btn = ttk.Button(action_frame, text="View User Details", 
                                          command=self.view_user_details, state='disabled')
        self.view_details_btn.pack(pady=5, fill=tk.X)
        
        ttk.Separator(action_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        ttk.Label(action_frame, text="Quick Actions", font=('Arial', 11, 'bold')).pack(pady=(0, 10))
        
        self.activate_user_btn = ttk.Button(action_frame, text="Activate/Deactivate User", 
                                           command=self.toggle_user_status, state='disabled')
        self.activate_user_btn.pack(pady=5, fill=tk.X)
        
        self.make_manager_btn = ttk.Button(action_frame, text="Toggle Manager Role", 
                                          command=self.toggle_manager_role, state='disabled')
        self.make_manager_btn.pack(pady=5, fill=tk.X)
        
        # Refresh button
        ttk.Separator(action_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        refresh_btn = ttk.Button(action_frame, text="Refresh List", command=self.refresh_users_tab)
        refresh_btn.pack(pady=5, fill=tk.X)
    
    def create_departments_tab(self):
        """Create departments management tab"""
        self.departments_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.departments_tab, text='Departments Management')
        
        # Top frame for department list
        top_frame = ttk.Frame(self.departments_tab)
        top_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Department list frame
        list_frame = ttk.LabelFrame(top_frame, text="Departments List", padding=10)
        list_frame.pack(side=tk.LEFT, fill='both', expand=True, padx=(0, 5))
        
        # Treeview for departments
        columns = ('ID', 'Name', 'Manager', 'Employees')
        self.departments_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.departments_tree.heading(col, text=col)
            self.departments_tree.column(col, width=150)
        
        self.departments_tree.column('ID', width=50)
        self.departments_tree.column('Employees', width=80)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.departments_tree.yview)
        self.departments_tree.configure(yscrollcommand=scrollbar.set)
        
        self.departments_tree.pack(side=tk.LEFT, fill='both', expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind selection event
        self.departments_tree.bind('<<TreeviewSelect>>', self.on_department_select)
        
        # Action buttons frame
        action_frame = ttk.Frame(top_frame)
        action_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # Action buttons
        ttk.Label(action_frame, text="Department Actions", font=('Arial', 11, 'bold')).pack(pady=(0, 10))
        
        self.create_dept_btn = ttk.Button(action_frame, text="Create New Department", 
                                         command=self.open_create_department_dialog)
        self.create_dept_btn.pack(pady=5, fill=tk.X)
        
        self.edit_dept_btn = ttk.Button(action_frame, text="Edit Selected Department", 
                                       command=self.open_edit_department_dialog, state='disabled')
        self.edit_dept_btn.pack(pady=5, fill=tk.X)
        
        self.delete_dept_btn = ttk.Button(action_frame, text="Delete Selected Department", 
                                         command=self.delete_department, state='disabled')
        self.delete_dept_btn.pack(pady=5, fill=tk.X)
        
        self.view_dept_users_btn = ttk.Button(action_frame, text="View Department Users", 
                                             command=self.view_department_users, state='disabled')
        self.view_dept_users_btn.pack(pady=5, fill=tk.X)
        
        # Refresh button
        ttk.Separator(action_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        refresh_btn = ttk.Button(action_frame, text="Refresh List", command=self.refresh_departments_tab)
        refresh_btn.pack(pady=5, fill=tk.X)
    
    def create_assignments_tab(self):
        """Create user assignment tab"""
        self.assignments_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.assignments_tab, text='User Assignments')
        
        # Main frame
        main_frame = ttk.Frame(self.assignments_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Left side - Users without department
        left_frame = ttk.LabelFrame(main_frame, text="Users Without Department", padding=10)
        left_frame.pack(side=tk.LEFT, fill='both', expand=True, padx=(0, 5))
        
        self.unassigned_listbox = tk.Listbox(left_frame, selectmode=tk.MULTIPLE, height=15)
        self.unassigned_listbox.pack(fill='both', expand=True)
        
        # Middle - Assignment controls
        middle_frame = ttk.Frame(main_frame)
        middle_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Label(middle_frame, text="Assign To:", font=('Arial', 11, 'bold')).pack(pady=(20, 5))
        
        self.dept_combo = ttk.Combobox(middle_frame, state='readonly', width=25)
        self.dept_combo.pack(pady=5)
        
        self.assign_btn = ttk.Button(middle_frame, text="Assign Selected", 
                                    command=self.assign_users_to_department)
        self.assign_btn.pack(pady=20)
        
        ttk.Separator(middle_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        self.unassign_btn = ttk.Button(middle_frame, text="Unassign Selected", 
                                      command=self.unassign_users)
        self.unassign_btn.pack(pady=5)
        
        # Right side - Department users
        right_frame = ttk.LabelFrame(main_frame, text="Department Users", padding=10)
        right_frame.pack(side=tk.RIGHT, fill='both', expand=True, padx=(5, 0))
        
        # Department selector
        dept_selector_frame = ttk.Frame(right_frame)
        dept_selector_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(dept_selector_frame, text="Select Department:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.dept_users_combo = ttk.Combobox(dept_selector_frame, state='readonly', width=20)
        self.dept_users_combo.pack(side=tk.LEFT)
        self.dept_users_combo.bind('<<ComboboxSelected>>', self.on_department_combo_select)
        
        # Users in selected department
        self.dept_users_listbox = tk.Listbox(right_frame, selectmode=tk.MULTIPLE, height=15)
        self.dept_users_listbox.pack(fill='both', expand=True)
        
        # Refresh button
        refresh_frame = ttk.Frame(main_frame)
        refresh_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))
        
        refresh_btn = ttk.Button(refresh_frame, text="Refresh Assignments", 
                                command=self.refresh_assignments_tab)
        refresh_btn.pack()
    
    def create_statistics_tab(self):
        """Create statistics tab"""
        self.stats_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_tab, text='Statistics')
        
        # Main frame
        main_frame = ttk.Frame(self.stats_tab)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Statistics display
        self.stats_text = scrolledtext.ScrolledText(main_frame, width=80, height=30)
        self.stats_text.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Buttons frame
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=(5, 0))
        
        refresh_btn = ttk.Button(buttons_frame, text="Refresh Statistics", 
                                command=self.refresh_statistics_tab)
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        export_btn = ttk.Button(buttons_frame, text="Export to File", 
                               command=self.export_statistics)
        export_btn.pack(side=tk.LEFT, padx=5)
    
    def refresh_all_tabs(self):
        """Refresh all tabs"""
        self.refresh_users_tab()
        self.refresh_departments_tab()
        self.refresh_assignments_tab()
        self.refresh_statistics_tab()
        self.update_status("All data refreshed")
    
    def refresh_users_tab(self):
        """Refresh users list"""
        try:
            # Clear existing items
            for item in self.users_tree.get_children():
                self.users_tree.delete(item)
            
            # Get users from database
            users = self.db.get_all_users()
            
            # Add users to treeview
            for user in users:
                # Format boolean values
                is_admin = "✓" if user['is_admin'] else ""
                is_manager = "✓" if user['is_manager'] else ""
                is_active = "✓" if user['is_active'] else ""
                department = user['department_name'] or "No Department"
                
                self.users_tree.insert('', 'end', values=(
                    user['id'],
                    user['username'],
                    user['name'],
                    user['email'] or "",
                    is_admin,
                    is_manager,
                    is_active,
                    department
                ))
            
            self.update_status(f"Loaded {len(users)} users")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh users: {str(e)}")
    
    def refresh_departments_tab(self):
        """Refresh departments list"""
        try:
            # Clear existing items
            for item in self.departments_tree.get_children():
                self.departments_tree.delete(item)
            
            # Get departments from database
            departments = self.db.get_all_departments()
            
            # Add departments to treeview
            for dept in departments:
                manager = dept['manager_name'] or "No Manager"
                self.departments_tree.insert('', 'end', values=(
                    dept['id'],
                    dept['name'],
                    manager,
                    dept['employee_count']
                ))
            
            # Update comboboxes in assignments tab
            self.update_department_comboboxes()
            
            self.update_status(f"Loaded {len(departments)} departments")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh departments: {str(e)}")
    
    def refresh_assignments_tab(self):
        """Refresh assignments tab"""
        try:
            # Clear existing items
            self.unassigned_listbox.delete(0, tk.END)
            self.dept_users_listbox.delete(0, tk.END)
            
            # Get users without department
            users = self.db.get_all_users()
            unassigned_users = [u for u in users if not u['department_id'] and not u['is_admin']]
            
            # Add to unassigned listbox
            for user in unassigned_users:
                self.unassigned_listbox.insert(tk.END, f"{user['name']} ({user['username']})")
            
            # Store user IDs for reference
            self.unassigned_user_ids = [user['id'] for user in unassigned_users]
            
            # Update department combobox
            self.update_department_comboboxes()
            
            # Select first department if available
            if self.dept_combo['values']:
                self.dept_combo.current(0)
                self.on_department_combo_select()
            
            self.update_status(f"Found {len(unassigned_users)} unassigned users")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh assignments: {str(e)}")
    
    def refresh_statistics_tab(self):
        """Refresh statistics tab"""
        try:
            # Clear existing text
            self.stats_text.delete(1.0, tk.END)
            
            # Get statistics
            users = self.db.get_all_users()
            departments = self.db.get_all_departments()
            
            # Calculate statistics
            total_users = len(users)
            active_users = len([u for u in users if u['is_active']])
            admin_users = len([u for u in users if u['is_admin']])
            manager_users = len([u for u in users if u['is_manager']])
            
            # Users per department
            dept_stats = {}
            for dept in departments:
                dept_stats[dept['name']] = dept['employee_count']
            
            # Generate statistics text
            stats_text = "=" * 60 + "\n"
            stats_text += "USER AND DEPARTMENT STATISTICS\n"
            stats_text += "=" * 60 + "\n\n"
            
            stats_text += "📊 USER STATISTICS:\n"
            stats_text += "-" * 40 + "\n"
            stats_text += f"Total Users: {total_users}\n"
            stats_text += f"Active Users: {active_users}\n"
            stats_text += f"Inactive Users: {total_users - active_users}\n"
            stats_text += f"Admin Users: {admin_users}\n"
            stats_text += f"Manager Users: {manager_users}\n\n"
            
            stats_text += "🏢 DEPARTMENT STATISTICS:\n"
            stats_text += "-" * 40 + "\n"
            stats_text += f"Total Departments: {len(departments)}\n\n"
            
            if departments:
                stats_text += "Users per Department:\n"
                for dept_name, count in dept_stats.items():
                    stats_text += f"  • {dept_name}: {count} users\n"
            else:
                stats_text += "No departments found\n"
            
            stats_text += "\n" + "=" * 60 + "\n"
            stats_text += f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            stats_text += "=" * 60
            
            # Insert into text widget
            self.stats_text.insert(1.0, stats_text)
            
            self.update_status("Statistics refreshed")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to refresh statistics: {str(e)}")
    
    def update_department_comboboxes(self):
        """Update department comboboxes in assignments tab"""
        try:
            departments = self.db.get_all_departments()
            dept_names = [dept['name'] for dept in departments]
            
            # Update combobox values
            self.dept_combo['values'] = dept_names
            self.dept_users_combo['values'] = dept_names
            
            # Store department IDs for reference
            self.department_ids = {dept['name']: dept['id'] for dept in departments}
            
        except Exception as e:
            print(f"Error updating department comboboxes: {e}")
    
    def on_user_select(self, event):
        """Handle user selection"""
        selection = self.users_tree.selection()
        if selection:
            # Enable edit and delete buttons
            self.edit_user_btn.config(state='normal')
            self.delete_user_btn.config(state='normal')
            self.view_details_btn.config(state='normal')
            self.activate_user_btn.config(state='normal')
            self.make_manager_btn.config(state='normal')
            
            # Get selected user data
            item = self.users_tree.item(selection[0])
            user_values = item['values']
            
            # Store selected user ID
            self.selected_user_id = user_values[0]
            
            # Update button text based on user status
            is_active = user_values[6] == "✓"
            is_manager = user_values[5] == "✓"
            
            self.activate_user_btn.config(
                text="Deactivate User" if is_active else "Activate User"
            )
            self.make_manager_btn.config(
                text="Remove Manager Role" if is_manager else "Make Manager"
            )
        else:
            # Disable buttons if no selection
            self.edit_user_btn.config(state='disabled')
            self.delete_user_btn.config(state='disabled')
            self.view_details_btn.config(state='disabled')
            self.activate_user_btn.config(state='disabled')
            self.make_manager_btn.config(state='disabled')
            self.selected_user_id = None
    
    def on_department_select(self, event):
        """Handle department selection"""
        selection = self.departments_tree.selection()
        if selection:
            # Enable buttons
            self.edit_dept_btn.config(state='normal')
            self.delete_dept_btn.config(state='normal')
            self.view_dept_users_btn.config(state='normal')
            
            # Get selected department data
            item = self.departments_tree.item(selection[0])
            dept_values = item['values']
            
            # Store selected department ID
            self.selected_department_id = dept_values[0]
        else:
            # Disable buttons if no selection
            self.edit_dept_btn.config(state='disabled')
            self.delete_dept_btn.config(state='disabled')
            self.view_dept_users_btn.config(state='disabled')
            self.selected_department_id = None
    
    def on_department_combo_select(self, event=None):
        """Handle department selection in assignments tab"""
        selected_dept = self.dept_users_combo.get()
        if selected_dept and selected_dept in self.department_ids:
            dept_id = self.department_ids[selected_dept]
            self.load_department_users(dept_id)
    
    def load_department_users(self, department_id):
        """Load users for selected department"""
        try:
            # Clear existing items
            self.dept_users_listbox.delete(0, tk.END)
            
            # Get department users
            users = self.db.get_department_users(department_id)
            
            # Add to listbox
            for user in users:
                status = "✓" if user['is_active'] else "✗"
                manager = " (Manager)" if user['is_manager'] else ""
                self.dept_users_listbox.insert(
                    tk.END, 
                    f"{status} {user['name']} ({user['username']}){manager}"
                )
            
            # Store user IDs for reference
            self.department_user_ids = [user['id'] for user in users]
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load department users: {str(e)}")
    
    def open_create_user_dialog(self):
        """Open dialog to create new user"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create New User")
        dialog.geometry("500x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Form fields
        fields_frame = ttk.Frame(dialog, padding=20)
        fields_frame.pack(fill='both', expand=True)
        
        # Username
        ttk.Label(fields_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, pady=5)
        username_var = tk.StringVar()
        username_entry = ttk.Entry(fields_frame, textvariable=username_var, width=30)
        username_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # Name
        ttk.Label(fields_frame, text="Full Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(fields_frame, textvariable=name_var, width=30)
        name_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Email
        ttk.Label(fields_frame, text="Email:").grid(row=2, column=0, sticky=tk.W, pady=5)
        email_var = tk.StringVar()
        email_entry = ttk.Entry(fields_frame, textvariable=email_var, width=30)
        email_entry.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Password
        ttk.Label(fields_frame, text="Password:").grid(row=3, column=0, sticky=tk.W, pady=5)
        password_var = tk.StringVar()
        password_entry = ttk.Entry(fields_frame, textvariable=password_var, width=30, show="*")
        password_entry.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # Confirm Password
        ttk.Label(fields_frame, text="Confirm Password:").grid(row=4, column=0, sticky=tk.W, pady=5)
        confirm_var = tk.StringVar()
        confirm_entry = ttk.Entry(fields_frame, textvariable=confirm_var, width=30, show="*")
        confirm_entry.grid(row=4, column=1, sticky=tk.W, pady=5)
        
        # Admin checkbox
        admin_var = tk.BooleanVar()
        admin_check = ttk.Checkbutton(fields_frame, text="Is Administrator", variable=admin_var)
        admin_check.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Manager checkbox
        manager_var = tk.BooleanVar()
        manager_check = ttk.Checkbutton(fields_frame, text="Is Manager", variable=manager_var)
        manager_check.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Department selection
        ttk.Label(fields_frame, text="Department:").grid(row=7, column=0, sticky=tk.W, pady=5)
        dept_var = tk.StringVar()
        dept_combo = ttk.Combobox(fields_frame, textvariable=dept_var, width=27, state='readonly')
        
        # Get departments for combo
        departments = self.db.get_all_departments()
        dept_names = [dept['name'] for dept in departments]
        dept_combo['values'] = ["No Department"] + dept_names
        dept_combo.current(0)
        dept_combo.grid(row=7, column=1, sticky=tk.W, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(dialog, padding=20)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        def create_user():
            """Create user with validation"""
            # Validate inputs
            username = username_var.get().strip()
            name = name_var.get().strip()
            email = email_var.get().strip()
            password = password_var.get()
            confirm = confirm_var.get()
            
            if not username or not name:
                messagebox.showerror("Error", "Username and Name are required")
                return
            
            if password != confirm:
                messagebox.showerror("Error", "Passwords do not match")
                return
            
            if password and len(password) < 6:
                messagebox.showerror("Error", "Password must be at least 6 characters")
                return
            
            # Get department ID
            department_name = dept_var.get()
            department_id = None
            if department_name != "No Department":
                for dept in departments:
                    if dept['name'] == department_name:
                        department_id = dept['id']
                        break
            
            # Create user
            success, message = self.db.create_user(
                username, name, email, password, 
                admin_var.get(), manager_var.get(), department_id
            )
            
            if success:
                messagebox.showinfo("Success", message)
                dialog.destroy()
                self.refresh_all_tabs()
            else:
                messagebox.showerror("Error", message)
        
        ttk.Button(button_frame, text="Create User", command=create_user).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Set focus to username field
        username_entry.focus()
    
    def open_edit_user_dialog(self):
        """Open dialog to edit user"""
        if not self.selected_user_id:
            return
        
        try:
            # Get user data
            users = self.db.get_all_users()
            user_data = None
            for user in users:
                if user['id'] == self.selected_user_id:
                    user_data = user
                    break
            
            if not user_data:
                messagebox.showerror("Error", "User not found")
                return
            
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Edit User: {user_data['username']}")
            dialog.geometry("500x450")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Form fields
            fields_frame = ttk.Frame(dialog, padding=20)
            fields_frame.pack(fill='both', expand=True)
            
            # Username
            ttk.Label(fields_frame, text="Username:").grid(row=0, column=0, sticky=tk.W, pady=5)
            username_var = tk.StringVar(value=user_data['username'])
            username_entry = ttk.Entry(fields_frame, textvariable=username_var, width=30)
            username_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
            
            # Name
            ttk.Label(fields_frame, text="Full Name:").grid(row=1, column=0, sticky=tk.W, pady=5)
            name_var = tk.StringVar(value=user_data['name'])
            name_entry = ttk.Entry(fields_frame, textvariable=name_var, width=30)
            name_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
            
            # Email
            ttk.Label(fields_frame, text="Email:").grid(row=2, column=0, sticky=tk.W, pady=5)
            email_var = tk.StringVar(value=user_data['email'] or "")
            email_entry = ttk.Entry(fields_frame, textvariable=email_var, width=30)
            email_entry.grid(row=2, column=1, sticky=tk.W, pady=5)
            
            # Admin checkbox
            admin_var = tk.BooleanVar(value=user_data['is_admin'])
            admin_check = ttk.Checkbutton(fields_frame, text="Is Administrator", variable=admin_var)
            admin_check.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)
            
            # Manager checkbox
            manager_var = tk.BooleanVar(value=user_data['is_manager'])
            manager_check = ttk.Checkbutton(fields_frame, text="Is Manager", variable=manager_var)
            manager_check.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=5)
            
            # Active checkbox
            active_var = tk.BooleanVar(value=user_data['is_active'])
            active_check = ttk.Checkbutton(fields_frame, text="Is Active", variable=active_var)
            active_check.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=5)
            
            # Department selection
            ttk.Label(fields_frame, text="Department:").grid(row=6, column=0, sticky=tk.W, pady=5)
            dept_var = tk.StringVar()
            dept_combo = ttk.Combobox(fields_frame, textvariable=dept_var, width=27, state='readonly')
            
            # Get departments for combo
            departments = self.db.get_all_departments()
            dept_names = [dept['name'] for dept in departments]
            dept_combo['values'] = ["No Department"] + dept_names
            
            # Set current department
            current_dept = user_data['department_name'] or "No Department"
            dept_combo.set(current_dept)
            dept_combo.grid(row=6, column=1, sticky=tk.W, pady=5)
            
            # Buttons
            button_frame = ttk.Frame(dialog, padding=20)
            button_frame.pack(fill=tk.X, side=tk.BOTTOM)
            
            def update_user():
                """Update user information"""
                # Validate inputs
                username = username_var.get().strip()
                name = name_var.get().strip()
                email = email_var.get().strip()
                
                if not username or not name:
                    messagebox.showerror("Error", "Username and Name are required")
                    return
                
                # Get department ID
                department_name = dept_var.get()
                department_id = None
                if department_name != "No Department":
                    for dept in departments:
                        if dept['name'] == department_name:
                            department_id = dept['id']
                            break
                
                # Update user
                success, message = self.db.update_user(
                    user_data['id'], username, name, email,
                    admin_var.get(), manager_var.get(), department_id, active_var.get()
                )
                
                if success:
                    messagebox.showinfo("Success", message)
                    dialog.destroy()
                    self.refresh_all_tabs()
                else:
                    messagebox.showerror("Error", message)
            
            ttk.Button(button_frame, text="Update User", command=update_user).pack(side=tk.RIGHT, padx=5)
            ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open edit dialog: {str(e)}")
    
    def delete_user(self):
        """Delete selected user"""
        if not self.selected_user_id:
            return
        
        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Delete",
            "Are you sure you want to delete this user?\n\n"
            "This action cannot be undone."
        )
        
        if not confirm:
            return
        
        try:
            success, message = self.db.delete_user(self.selected_user_id)
            
            if success:
                messagebox.showinfo("Success", message)
                self.refresh_all_tabs()
            else:
                messagebox.showerror("Error", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete user: {str(e)}")
    
    def view_user_details(self):
        """View detailed information about selected user"""
        if not self.selected_user_id:
            return
        
        try:
            # Get user data
            users = self.db.get_all_users()
            user_data = None
            for user in users:
                if user['id'] == self.selected_user_id:
                    user_data = user
                    break
            
            if not user_data:
                messagebox.showerror("Error", "User not found")
                return
            
            # Get user activity
            activity = self.db.get_user_activity(self.selected_user_id)
            
            dialog = tk.Toplevel(self.root)
            dialog.title(f"User Details: {user_data['username']}")
            dialog.geometry("600x400")
            dialog.transient(self.root)
            
            # Create notebook for details
            notebook = ttk.Notebook(dialog)
            notebook.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Basic Info Tab
            basic_frame = ttk.Frame(notebook)
            notebook.add(basic_frame, text='Basic Information')
            
            info_text = f"""USER INFORMATION:
            {'=' * 50}
            ID: {user_data['id']}
            Username: {user_data['username']}
            Name: {user_data['name']}
            Email: {user_data['email'] or 'N/A'}
            
            ROLES:
            {'-' * 30}
            Administrator: {'Yes' if user_data['is_admin'] else 'No'}
            Manager: {'Yes' if user_data['is_manager'] else 'No'}
            Active: {'Yes' if user_data['is_active'] else 'No'}
            
            DEPARTMENT:
            {'-' * 30}
            Department: {user_data['department_name'] or 'No Department'}
            
            ACTIVITY STATISTICS:
            {'-' * 30}
            Leave Requests: {activity['leave_requests']}
            Permission Requests: {activity['permission_requests']}
            Salary Slips: {activity['salary_slips']}
            """
            
            info_label = tk.Text(basic_frame, wrap=tk.WORD, height=20, width=70)
            info_label.insert(1.0, info_text)
            info_label.config(state=tk.DISABLED)
            info_label.pack(padx=10, pady=10)
            
            # Close button
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill=tk.X, padx=10, pady=10)
            
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to view user details: {str(e)}")
    
    def toggle_user_status(self):
        """Toggle user active/inactive status"""
        if not self.selected_user_id:
            return
        
        try:
            # Get current user status
            users = self.db.get_all_users()
            user_data = None
            for user in users:
                if user['id'] == self.selected_user_id:
                    user_data = user
                    break
            
            if not user_data:
                return
            
            # Confirm action
            action = "deactivate" if user_data['is_active'] else "activate"
            confirm = messagebox.askyesno(
                "Confirm Action",
                f"Are you sure you want to {action} user '{user_data['username']}'?"
            )
            
            if not confirm:
                return
            
            # Update user status
            success, message = self.db.update_user(
                user_data['id'], user_data['username'], user_data['name'], 
                user_data['email'] or "", user_data['is_admin'], 
                user_data['is_manager'], user_data['department_id'], 
                not user_data['is_active']
            )
            
            if success:
                messagebox.showinfo("Success", message)
                self.refresh_all_tabs()
            else:
                messagebox.showerror("Error", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle user status: {str(e)}")
    
    def toggle_manager_role(self):
        """Toggle manager role for user"""
        if not self.selected_user_id:
            return
        
        try:
            # Get current user status
            users = self.db.get_all_users()
            user_data = None
            for user in users:
                if user['id'] == self.selected_user_id:
                    user_data = user
                    break
            
            if not user_data:
                return
            
            # Check if user is manager of any department
            if user_data['is_manager']:
                departments = self.db.get_all_departments()
                managed_depts = []
                for dept in departments:
                    if dept['primary_manager_id'] == user_data['id']:
                        managed_depts.append(dept['name'])
                
                if managed_depts:
                    dept_list = "\n".join(managed_depts)
                    messagebox.showwarning(
                        "Cannot Remove Manager Role",
                        f"This user is the primary manager of the following departments:\n\n"
                        f"{dept_list}\n\n"
                        f"Please assign new managers to these departments first."
                    )
                    return
            
            # Confirm action
            action = "remove manager role from" if user_data['is_manager'] else "make manager of"
            confirm = messagebox.askyesno(
                "Confirm Action",
                f"Are you sure you want to {action} user '{user_data['username']}'?"
            )
            
            if not confirm:
                return
            
            # Update user role
            success, message = self.db.update_user(
                user_data['id'], user_data['username'], user_data['name'], 
                user_data['email'] or "", user_data['is_admin'], 
                not user_data['is_manager'], user_data['department_id'], 
                user_data['is_active']
            )
            
            if success:
                messagebox.showinfo("Success", message)
                self.refresh_all_tabs()
            else:
                messagebox.showerror("Error", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle manager role: {str(e)}")
    
    def open_create_department_dialog(self):
        """Open dialog to create new department"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Create New Department")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Form fields
        fields_frame = ttk.Frame(dialog, padding=20)
        fields_frame.pack(fill='both', expand=True)
        
        # Department Name
        ttk.Label(fields_frame, text="Department Name:").grid(row=0, column=0, sticky=tk.W, pady=10)
        name_var = tk.StringVar()
        name_entry = ttk.Entry(fields_frame, textvariable=name_var, width=30)
        name_entry.grid(row=0, column=1, sticky=tk.W, pady=10)
        
        # Manager selection
        ttk.Label(fields_frame, text="Primary Manager:").grid(row=1, column=0, sticky=tk.W, pady=10)
        manager_var = tk.StringVar()
        manager_combo = ttk.Combobox(fields_frame, textvariable=manager_var, width=27, state='readonly')
        
        # Get available managers
        managers = self.db.get_available_managers()
        manager_names = ["No Manager"] + [f"{m[1]} ({m[2]})" for m in managers]
        manager_combo['values'] = manager_names
        manager_combo.current(0)
        manager_combo.grid(row=1, column=1, sticky=tk.W, pady=10)
        
        # Store manager IDs for reference
        self.manager_ids = {"No Manager": None}
        for m in managers:
            self.manager_ids[f"{m[1]} ({m[2]})"] = m[0]
        
        # Buttons
        button_frame = ttk.Frame(dialog, padding=20)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        def create_department():
            """Create department with validation"""
            name = name_var.get().strip()
            if not name:
                messagebox.showerror("Error", "Department name is required")
                return
            
            # Get manager ID
            manager_name = manager_var.get()
            manager_id = self.manager_ids.get(manager_name)
            
            # Create department
            success, message = self.db.create_department(name, manager_id)
            
            if success:
                messagebox.showinfo("Success", message)
                dialog.destroy()
                self.refresh_all_tabs()
            else:
                messagebox.showerror("Error", message)
        
        ttk.Button(button_frame, text="Create Department", 
                  command=create_department).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Cancel", 
                  command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Set focus to name field
        name_entry.focus()
    
    def open_edit_department_dialog(self):
        """Open dialog to edit department"""
        if not self.selected_department_id:
            return
        
        try:
            # Get department data
            departments = self.db.get_all_departments()
            dept_data = None
            for dept in departments:
                if dept['id'] == self.selected_department_id:
                    dept_data = dept
                    break
            
            if not dept_data:
                messagebox.showerror("Error", "Department not found")
                return
            
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Edit Department: {dept_data['name']}")
            dialog.geometry("500x300")
            dialog.transient(self.root)
            dialog.grab_set()
            
            # Form fields
            fields_frame = ttk.Frame(dialog, padding=20)
            fields_frame.pack(fill='both', expand=True)
            
            # Department Name
            ttk.Label(fields_frame, text="Department Name:").grid(row=0, column=0, sticky=tk.W, pady=10)
            name_var = tk.StringVar(value=dept_data['name'])
            name_entry = ttk.Entry(fields_frame, textvariable=name_var, width=30)
            name_entry.grid(row=0, column=1, sticky=tk.W, pady=10)
            
            # Manager selection
            ttk.Label(fields_frame, text="Primary Manager:").grid(row=1, column=0, sticky=tk.W, pady=10)
            manager_var = tk.StringVar()
            manager_combo = ttk.Combobox(fields_frame, textvariable=manager_var, width=27, state='readonly')
            
            # Get available managers
            managers = self.db.get_available_managers()
            manager_names = ["No Manager"] + [f"{m[1]} ({m[2]})" for m in managers]
            manager_combo['values'] = manager_names
            
            # Set current manager
            current_manager = dept_data['manager_name'] or "No Manager"
            manager_combo.set(current_manager)
            manager_combo.grid(row=1, column=1, sticky=tk.W, pady=10)
            
            # Store manager IDs for reference
            self.manager_ids = {"No Manager": None}
            for m in managers:
                self.manager_ids[f"{m[1]} ({m[2]})"] = m[0]
            
            # Employee count
            ttk.Label(fields_frame, text="Number of Employees:").grid(row=2, column=0, sticky=tk.W, pady=10)
            ttk.Label(fields_frame, text=str(dept_data['employee_count'])).grid(row=2, column=1, sticky=tk.W, pady=10)
            
            # Buttons
            button_frame = ttk.Frame(dialog, padding=20)
            button_frame.pack(fill=tk.X, side=tk.BOTTOM)
            
            def update_department():
                """Update department information"""
                name = name_var.get().strip()
                if not name:
                    messagebox.showerror("Error", "Department name is required")
                    return
                
                # Get manager ID
                manager_name = manager_var.get()
                manager_id = self.manager_ids.get(manager_name)
                
                # Update department
                success, message = self.db.update_department(
                    dept_data['id'], name, manager_id
                )
                
                if success:
                    messagebox.showinfo("Success", message)
                    dialog.destroy()
                    self.refresh_all_tabs()
                else:
                    messagebox.showerror("Error", message)
            
            ttk.Button(button_frame, text="Update Department", 
                      command=update_department).pack(side=tk.RIGHT, padx=5)
            ttk.Button(button_frame, text="Cancel", 
                      command=dialog.destroy).pack(side=tk.RIGHT, padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open edit dialog: {str(e)}")
    
    def delete_department(self):
        """Delete selected department"""
        if not self.selected_department_id:
            return
        
        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Delete",
            "Are you sure you want to delete this department?\n\n"
            "This action cannot be undone."
        )
        
        if not confirm:
            return
        
        try:
            success, message = self.db.delete_department(self.selected_department_id)
            
            if success:
                messagebox.showinfo("Success", message)
                self.refresh_all_tabs()
            else:
                messagebox.showerror("Error", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete department: {str(e)}")
    
    def view_department_users(self):
        """View users in selected department"""
        if not self.selected_department_id:
            return
        
        try:
            # Get department data
            departments = self.db.get_all_departments()
            dept_data = None
            for dept in departments:
                if dept['id'] == self.selected_department_id:
                    dept_data = dept
                    break
            
            if not dept_data:
                messagebox.showerror("Error", "Department not found")
                return
            
            # Get department users
            users = self.db.get_department_users(self.selected_department_id)
            
            dialog = tk.Toplevel(self.root)
            dialog.title(f"Users in Department: {dept_data['name']}")
            dialog.geometry("600x400")
            dialog.transient(self.root)
            
            # Create text widget
            text_widget = scrolledtext.ScrolledText(dialog, width=70, height=20)
            text_widget.pack(fill='both', expand=True, padx=10, pady=10)
            
            # Format user information
            user_text = f"DEPARTMENT: {dept_data['name']}\n"
            user_text += f"MANAGER: {dept_data['manager_name'] or 'No Manager'}\n"
            user_text += f"TOTAL EMPLOYEES: {dept_data['employee_count']}\n"
            user_text += "=" * 60 + "\n\n"
            
            if users:
                user_text += "EMPLOYEES LIST:\n"
                user_text += "-" * 40 + "\n"
                
                for i, user in enumerate(users, 1):
                    status = "Active" if user['is_active'] else "Inactive"
                    manager = " (Manager)" if user['is_manager'] else ""
                    user_text += f"{i}. {user['name']} ({user['username']}){manager}\n"
                    user_text += f"   Status: {status}\n\n"
            else:
                user_text += "No employees in this department.\n"
            
            # Insert text
            text_widget.insert(1.0, user_text)
            text_widget.config(state=tk.DISABLED)
            
            # Close button
            button_frame = ttk.Frame(dialog)
            button_frame.pack(fill=tk.X, padx=10, pady=10)
            
            ttk.Button(button_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to view department users: {str(e)}")
    
    def assign_users_to_department(self):
        """Assign selected users to selected department"""
        # Get selected users
        selected_indices = self.unassigned_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select users to assign")
            return
        
        # Get selected department
        dept_name = self.dept_combo.get()
        if not dept_name or dept_name not in self.department_ids:
            messagebox.showwarning("No Department", "Please select a department")
            return
        
        # Confirm assignment
        user_count = len(selected_indices)
        confirm = messagebox.askyesno(
            "Confirm Assignment",
            f"Assign {user_count} user(s) to department '{dept_name}'?"
        )
        
        if not confirm:
            return
        
        try:
            # Get user IDs
            user_ids = [self.unassigned_user_ids[i] for i in selected_indices]
            
            # Assign users
            success, message = self.db.assign_users_to_department(
                user_ids, self.department_ids[dept_name]
            )
            
            if success:
                messagebox.showinfo("Success", message)
                self.refresh_assignments_tab()
                self.refresh_users_tab()
            else:
                messagebox.showerror("Error", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to assign users: {str(e)}")
    
    def unassign_users(self):
        """Unassign selected users from department"""
        # Get selected users
        selected_indices = self.dept_users_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("No Selection", "Please select users to unassign")
            return
        
        # Get selected department
        dept_name = self.dept_users_combo.get()
        if not dept_name or dept_name not in self.department_ids:
            messagebox.showwarning("No Department", "Please select a department")
            return
        
        # Confirm unassignment
        user_count = len(selected_indices)
        confirm = messagebox.askyesno(
            "Confirm Unassignment",
            f"Unassign {user_count} user(s) from department '{dept_name}'?\n\n"
            "Users will be moved to 'No Department'."
        )
        
        if not confirm:
            return
        
        try:
            # Get user IDs
            user_ids = [self.department_user_ids[i] for i in selected_indices]
            
            # Unassign users (set department_id to NULL)
            success, message = self.db.assign_users_to_department(user_ids, None)
            
            if success:
                messagebox.showinfo("Success", message)
                self.refresh_assignments_tab()
                self.refresh_users_tab()
            else:
                messagebox.showerror("Error", message)
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to unassign users: {str(e)}")
    
    def export_statistics(self):
        """Export statistics to a file"""
        try:
            # Get statistics text
            stats_text = self.stats_text.get(1.0, tk.END)
            
            # Create file dialog
            from tkinter import filedialog
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                initialfile=f"user_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(stats_text)
                
                self.update_status(f"Statistics exported to: {file_path}")
                messagebox.showinfo("Export Successful", 
                                  f"Statistics exported to:\n{file_path}")
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export statistics: {str(e)}")
    
    def update_status(self, message):
        """Update status bar message"""
        self.status_bar.config(text=f"Status: {message}")
    
    def on_closing(self):
        """Handle application closing"""
        self.db.close()
        self.root.destroy()


def main():
    """Main function to run the application"""
    # Create root window
    root = tk.Tk()
    
    # Create application
    app = UserManagementApp(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Run application
    root.mainloop()


if __name__ == "__main__":
    main()