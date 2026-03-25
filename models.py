from sqlalchemy import Column, Integer, String, Boolean, Date, Text, DateTime, Float, ForeignKey, JSON, UniqueConstraint, Table
from database import Base
from flask_login import UserMixin 
from datetime import datetime, date 
import json 
from sqlalchemy.orm import relationship, Session
from datetime import timedelta
import hashlib
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from sqlalchemy.orm import relationship, backref 


# Add these classes to your models.py file

class Message(Base):
    """Internal messaging system similar to email"""
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    subject = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    priority = Column(String(20), default='normal')  # normal, high, urgent
    has_attachments = Column(Boolean, default=False)
    is_draft = Column(Boolean, default=False)
    is_starred = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    thread_id = Column(Integer, ForeignKey('messages.id'), nullable=True)  # For replies
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    recipients = relationship("MessageRecipient", back_populates="message", cascade="all, delete-orphan")
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")
    replies = relationship("Message", backref=backref("parent", remote_side=[id]))
    
    def to_dict(self):
        """Convert message to dictionary"""
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'sender_name': self.sender.name if self.sender else '',
            'subject': self.subject,
            'body': self.body,
            'priority': self.priority,
            'has_attachments': self.has_attachments,
            'is_draft': self.is_draft,
            'is_starred': self.is_starred,
            'is_archived': self.is_archived,
            'thread_id': self.thread_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'recipients': [r.to_dict() for r in self.recipients],
            'attachments': [a.to_dict() for a in self.attachments]
        }
    
    def get_recipients_by_type(self, recipient_type='to'):
        """Get recipients of specific type (to, cc, bcc)"""
        return [r for r in self.recipients if r.recipient_type == recipient_type]
    
    def get_all_recipients(self, exclude_bcc=False):
        """Get all recipients, optionally excluding BCC"""
        if exclude_bcc:
            return [r for r in self.recipients if r.recipient_type != 'bcc']
        return self.recipients


class MessageRecipient(Base):
    """Message recipients (supports TO, CC, BCC)"""
    __tablename__ = 'message_recipients'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    recipient_type = Column(String(10), default='to')  # to, cc, bcc
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)
    is_archived = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    
    # Relationships
    message = relationship("Message", back_populates="recipients")
    user = relationship("User", foreign_keys=[user_id], back_populates="received_messages")
    
    def to_dict(self):
        """Convert recipient to dictionary"""
        return {
            'id': self.id,
            'message_id': self.message_id,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else '',
            'recipient_type': self.recipient_type,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'is_archived': self.is_archived,
            'is_deleted': self.is_deleted
        }
    
    def mark_as_read(self):
        """Mark message as read"""
        self.is_read = True
        self.read_at = datetime.now()
    
    def mark_as_unread(self):
        """Mark message as unread"""
        self.is_read = False
        self.read_at = None
    
    def archive(self):
        """Archive message"""
        self.is_archived = True
    
    def unarchive(self):
        """Unarchive message"""
        self.is_archived = False
    
    def delete(self):
        """Soft delete message"""
        self.is_deleted = True


class MessageAttachment(Base):
    """Message attachments"""
    __tablename__ = 'message_attachments'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)  # in bytes
    mime_type = Column(String(100), nullable=True)
    uploaded_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    message = relationship("Message", back_populates="attachments")
    
    def to_dict(self):
        """Convert attachment to dictionary"""
        return {
            'id': self.id,
            'message_id': self.message_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'file_size_formatted': self.get_formatted_size(),
            'mime_type': self.mime_type,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }
    
    def get_formatted_size(self):
        """Get formatted file size (KB, MB)"""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        else:
            return f"{self.file_size / (1024 * 1024):.1f} MB"


class MessageFolder(Base):
    """Custom folders for organizing messages"""
    __tablename__ = 'message_folders'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(20), default='#3b82f6')  # Default blue
    icon = Column(String(50), default='fa-folder')  # Font Awesome icon
    is_system = Column(Boolean, default=False)  # System folders like Inbox, Sent, etc.
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id], back_populates="message_folders")
    messages = relationship("MessageFolderAssignment", back_populates="folder", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Convert folder to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'color': self.color,
            'icon': self.icon,
            'is_system': self.is_system,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'message_count': len(self.messages) if self.messages else 0
        }


class MessageFolderAssignment(Base):
    """Assign messages to folders"""
    __tablename__ = 'message_folder_assignments'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), nullable=False)
    folder_id = Column(Integer, ForeignKey('message_folders.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    assigned_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    message = relationship("Message", backref="folder_assignments")
    folder = relationship("MessageFolder", back_populates="messages")
    user = relationship("User", foreign_keys=[user_id])
    
    def to_dict(self):
        """Convert folder assignment to dictionary"""
        return {
            'id': self.id,
            'message_id': self.message_id,
            'folder_id': self.folder_id,
            'folder_name': self.folder.name if self.folder else '',
            'user_id': self.user_id,
            'assigned_at': self.assigned_at.isoformat() if self.assigned_at else None
        }


# Add system folders creation function
def create_system_folders(user_id, db_session):
    """Create system folders for a new user"""
    system_folders = [
        {'name': 'صندوق الوارد', 'icon': 'fa-inbox', 'color': '#3b82f6'},
        {'name': 'المرسلة', 'icon': 'fa-paper-plane', 'color': '#10b981'},
        {'name': 'المسودات', 'icon': 'fa-edit', 'color': '#f59e0b'},
        {'name': 'المهملات', 'icon': 'fa-trash', 'color': '#ef4444'},
        {'name': 'المميزة', 'icon': 'fa-star', 'color': '#fbbf24'},
        {'name': 'الأرشيف', 'icon': 'fa-archive', 'color': '#6b7280'}
    ]
    
    for folder_data in system_folders:
        folder = MessageFolder(
            user_id=user_id,
            name=folder_data['name'],
            icon=folder_data['icon'],
            color=folder_data['color'],
            is_system=True
        )
        db_session.add(folder)
    
    db_session.commit()


# Add to User class to include messages relationship (add this inside the existing User class)
# Find your User class and add these relationships:

"""
# Add these lines inside your User class:

    # Message relationships
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("MessageRecipient", back_populates="user")
    message_folders = relationship("MessageFolder", back_populates="user")
"""

# Here's the complete User class with the added relationships:

class User(Base, UserMixin):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=True)
    password_hash = Column(String(120), nullable=False)
    is_admin = Column(Boolean, default=False)
    is_manager = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    department_id = Column(Integer, ForeignKey('departments.id'))
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime)
    
    
    # Add these message relationships
    sent_messages = relationship("Message", foreign_keys="Message.sender_id", back_populates="sender")
    received_messages = relationship("MessageRecipient", back_populates="user")
    message_folders = relationship("MessageFolder", back_populates="user", cascade="all, delete-orphan")

    def get_id(self):
        return str(self.id)
    
    def get_unread_messages_count(self):
        """Get count of unread messages"""
        from sqlalchemy import func
        return len([r for r in self.received_messages if not r.is_read and not r.is_deleted])
    
    def get_inbox_messages(self):
        """Get all inbox messages (not archived, not deleted)"""
        return [r for r in self.received_messages 
                if not r.is_archived and not r.is_deleted]
    
    def get_archived_messages(self):
        """Get archived messages"""
        return [r for r in self.received_messages if r.is_archived and not r.is_deleted]


class ScheduleRepopulationLog(Base):
    __tablename__ = 'schedule_repopulation_logs'
    
    id = Column(Integer, primary_key=True)
    target_schedule_id = Column(Integer, ForeignKey('weekly_schedules.id'), nullable=False)
    source_schedule_id = Column(Integer, ForeignKey('weekly_schedules.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    details = Column(Text)
    performed_at = Column(DateTime, default=datetime.now)
    
    # العلاقات
    target_schedule = relationship("WeeklySchedule", foreign_keys=[target_schedule_id])
    source_schedule = relationship("WeeklySchedule", foreign_keys=[source_schedule_id])
    user = relationship("User")


class DepartmentManager(Base):
    __tablename__ = 'department_managers'
    
    id = Column(Integer, primary_key=True)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    # Manager permissions
    can_manage_schedules = Column(Boolean, default=False)
    can_manage_leaves = Column(Boolean, default=False)
    can_manage_permissions = Column(Boolean, default=False)
    can_manage_advances = Column(Boolean, default=False)
    can_manage_rewards = Column(Boolean, default=False)
    can_view_reports = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(Integer, ForeignKey('users.id'))
    
    # Explicit relationships with foreign_keys parameter
    department = relationship("Department", backref="managers")
    user = relationship("User", foreign_keys=[user_id], backref="managed_departments")
    creator = relationship("User", foreign_keys=[created_by])


class EmployeeData(Base):
    __tablename__ = 'employee_data'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    
    # كل الحقول يجب أن تكون nullable=True
    arabic_name = Column(String(200), nullable=True)
    english_name = Column(String(200), nullable=True)
    national_id = Column(String(20), nullable=True)
    id_issue_date = Column(Date, nullable=True)
    birth_date = Column(Date, nullable=True)
    age = Column(Integer, nullable=True)
    whatsapp = Column(String(20), nullable=True)
    phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    military_status = Column(String(50), nullable=True)
    marital_status = Column(String(50), nullable=True)
    qualification = Column(String(100), nullable=True)
    graduation_year = Column(Integer, nullable=True)
    grade = Column(String(50), nullable=True)
    has_work = Column(Boolean, default=False)
    workplace = Column(String(200), nullable=True)
    job_title = Column(String(100), nullable=True)
    insurance_number = Column(String(50), nullable=True)
    tax_number = Column(String(50), nullable=True)
    
    # جهات الاتصال
    emergency1_name = Column(String(100), nullable=True)
    emergency1_phone = Column(String(20), nullable=True)
    emergency1_address = Column(String(200), nullable=True)
    emergency1_relation = Column(String(50), nullable=True)
    emergency2_name = Column(String(100), nullable=True)
    emergency2_phone = Column(String(20), nullable=True)
    emergency2_address = Column(String(200), nullable=True)
    emergency2_relation = Column(String(50), nullable=True)
    
    # الملفات
    national_id_image = Column(String(255), nullable=True)
    military_status_image = Column(String(255), nullable=True)
    qualification_image = Column(String(255), nullable=True)
    salary_details = Column(String(255), nullable=True)
    employment_status = Column(String(255), nullable=True)
    
    profession_license = Column(String(100), nullable=True)
    union_card = Column(String(100), nullable=True)
    
    # التتبع
    completion_percentage = Column(Integer, default=0)
    last_updated = Column(DateTime, nullable=True)
    updated_by = Column(String(100), nullable=True)
    needs_update = Column(Boolean, default=False)

    def calculate_completion(self):
        """احسب نسبة اكتمال البيانات"""
        total_fields = 25
        completed_fields = 0
        
        fields_to_check = [
            self.arabic_name, self.english_name, self.national_id,
            self.id_issue_date, self.birth_date, self.phone, 
            self.whatsapp, self.address, self.military_status,
            self.marital_status, self.qualification, self.graduation_year,
            self.grade, self.workplace, self.job_title,
            self.insurance_number, self.tax_number, self.profession_license,
            self.union_card, self.emergency1_name, self.emergency1_phone,
            self.emergency1_relation, self.emergency1_address,
            self.emergency2_name, self.emergency2_phone,
            self.emergency2_relation, self.emergency2_address
        ]
        
        completed_fields = sum(1 for field in fields_to_check if field)
        
        completion_percentage = int((completed_fields / total_fields) * 100) if total_fields > 0 else 0
        self.completion_percentage = completion_percentage
        return completion_percentage

    def get_missing_fields(self):
        """ارجع قائمة بالحقول المطلوبة غير المكتملة"""
        missing_fields = []
        
        field_names = {
            'arabic_name': 'الاسم بالعربية',
            'english_name': 'الاسم بالإنجليزية',
            'national_id': 'الرقم القومي',
            'birth_date': 'تاريخ الميلاد',
            'phone': 'رقم الهاتف',
            'address': 'العنوان',
            'marital_status': 'الحالة الاجتماعية',
            'qualification': 'المؤهل الدراسي',
            'emergency1_name': 'اسم جهة الاتصال الأولى',
            'emergency1_phone': 'هاتف جهة الاتصال الأولى',
            'emergency1_relation': 'صلة القرابة للاتصال الأول',
            'emergency1_address': 'عنوان جهة الاتصال الأولى'
        }
        
        for field, arabic_name in field_names.items():
            if not getattr(self, field, None):
                missing_fields.append(arabic_name)
        
        return missing_fields


class LeaveRequest(Base):
    __tablename__ = 'leave_requests'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    department_id = Column(Integer, ForeignKey('departments.id'))
    leave_type = Column(String(100))
    
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    leave_date = Column(Date)
    shift_name = Column(String(50))
    shift_time = Column(String(50))
    shift_job = Column(String(100))
    
    total_days = Column(Integer, default=1)
    
    reason = Column(Text)
    status = Column(String(20), default='pending')
    
    parent_request_id = Column(Integer, nullable=True)
    shift_order = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.now)
    approved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    user = relationship("User", foreign_keys=[user_id])
    department = relationship("Department")
    approver = relationship("User", foreign_keys=[approved_by])
    
    def get_shift_info(self):
        return {
            'shift_name': self.shift_name,
            'shift_time': self.shift_time,
            'shift_job': self.shift_job,
            'leave_date': self.leave_date.strftime('%Y-%m-%d') if self.leave_date else None
        }


class PermissionRequest(Base):
    __tablename__ = 'permission_requests'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    permission_type = Column(String(100), nullable=False)
    date = Column(Date, nullable=False)
    time = Column(Integer)
    reason = Column(Text)
    extra_data = Column(Text)
    status = Column(String(20), default='pending')
    approved_by = Column(Integer, ForeignKey('users.id'))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    
    user = relationship('User', foreign_keys=[user_id])
    department = relationship('Department')
    approver = relationship('User', foreign_keys=[approved_by])
    
    @property
    def extra_data_dict(self):
        if not self.extra_data:
            return {}
        
        try:
            if isinstance(self.extra_data, str):
                return json.loads(self.extra_data)
            elif isinstance(self.extra_data, dict):
                return self.extra_data
            else:
                return {}
        except json.JSONDecodeError:
            return {}
        except Exception:
            return {}
    
    @property
    def shift_name(self):
        extra_data = self.extra_data_dict
        return extra_data.get('shift') or ''
    
    @property
    def shift_job(self):
        extra_data = self.extra_data_dict
        return extra_data.get('job') or ''
    
    @property
    def exchange_employee_name(self):
        extra_data = self.extra_data_dict
        return extra_data.get('employee_name') or ''
    
    @property
    def time_period(self):
        extra_data = self.extra_data_dict
        return extra_data.get('time_period') or ''
    
    @property
    def attendance_type(self):
        extra_data = self.extra_data_dict
        return extra_data.get('attendance_type') or ''
    
    @property
    def overtime_hours(self):
        extra_data = self.extra_data_dict
        hours = extra_data.get('hours') or extra_data.get('overtime_hours') or 0
        return hours


class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    notification_type = Column(String(50))
    related_id = Column(Integer)
    action_url = Column(String(200))
    
    user = relationship("User", foreign_keys=[user_id])


class SalarySlip(Base):
    __tablename__ = 'salary_slips'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    month = Column(String(7), nullable=False)
    arabic_month = Column(String(20), nullable=True)
    file_name = Column(String(200), nullable=True)
    file_path = Column(String(200), nullable=False)
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.now)
    is_viewed = Column(Boolean, default=False)
    is_auto_detected = Column(Boolean, default=False)
    
    user = relationship("User", foreign_keys=[user_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])


class AdvanceRequest(Base):
    __tablename__ = 'advance_requests'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    amount = Column(Float, nullable=False)
    reason = Column(Text)
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, default=datetime.now)
    approved_by = Column(Integer, ForeignKey('users.id'))
    approved_at = Column(DateTime)
    installment_months = Column(Integer, default=1)
    rejection_reason = Column(Text)


class EmployeeBalance(Base):
    __tablename__ = 'employee_balances'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    leave_balance = Column(Integer, default=12)
    permission_balance = Column(Integer, default=2)
    advance_balance = Column(Float, default=0)
    last_updated = Column(DateTime, default=datetime.now)
    updated_by = Column(Integer, ForeignKey('users.id'))


class Department(Base):
    __tablename__ = 'departments'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    primary_manager_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    created_by = Column(Integer, ForeignKey('users.id'))
    
    schedule_structure = Column(Text)
    schedule_columns = Column(Text)
    advance_policy_max_amount = Column(Float, default=0)
    advance_policy_max_installments = Column(Integer, default=1)
    
    auto_generate_schedule = Column(Boolean, default=True)
    schedule_template = Column(Text)
    schedule_structure_version = Column(Integer, default=1)
    structure_last_modified = Column(DateTime)
    
    primary_manager = relationship("User", foreign_keys=[primary_manager_id])
    creator = relationship("User", foreign_keys=[created_by])
    employees = relationship("User", backref="department", foreign_keys="User.department_id")
    
    def update_structure(self, new_structure):
        self.schedule_structure = new_structure
        self.schedule_structure_version = (self.schedule_structure_version or 0) + 1
        self.structure_last_modified = datetime.now()
    
    def get_schedule_structure_json(self):
        try:
            if self.schedule_structure:
                return json.loads(self.schedule_structure)
            return []
        except:
            return []


class RewardPenalty(Base):
    __tablename__ = 'rewards_penalties'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    type = Column(String(20), nullable=False)
    amount = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)
    effective_date = Column(Date, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.now)


# ============================================================================
# نماذج الجداول الأسبوعية المطلوبة
# ============================================================================
class ScheduleStructureRow(Base):
    __tablename__ = 'schedule_structure_rows'
    
    id = Column(Integer, primary_key=True)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    # تم إزالة day_name لأنه نفس الهيكل لكل الأيام
    job_title = Column(String(100), nullable=False)
    job_code = Column(String(20), nullable=True) 
    morning_shift = Column(String(100), nullable=False, default="")
    evening_shift = Column(String(100), nullable=False, default="")
    night_shift = Column(String(100), nullable=False, default="")
    
    row_order = Column(Integer, default=0)
    
    manager_can_edit_shifts = Column(Boolean, default=True)
    manager_can_add_rows = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, onupdate=datetime.now)
    created_by = Column(Integer, ForeignKey('users.id'))
    
    department = relationship("Department", backref="structure_rows")
    creator = relationship("User", foreign_keys=[created_by])
    
    def to_dict(self):
        """تحويل الكائن إلى قاموس"""
        return {
            'id': self.id,
            'department_id': self.department_id,
            'job_title': self.job_title,
            'morning_shift': self.morning_shift,
            'evening_shift': self.evening_shift,
            'night_shift': self.night_shift,
            'row_order': self.row_order,
            'manager_can_edit_shifts': self.manager_can_edit_shifts,
            'manager_can_add_rows': self.manager_can_add_rows,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def get_assigned_employees_count(self):
        """إرجاع عدد الموظفين المعينين في هذا الصف"""
        count = 0
        if self.morning_shift and self.morning_shift.strip():
            count += 1
        if self.evening_shift and self.evening_shift.strip():
            count += 1
        if self.night_shift and self.night_shift.strip():
            count += 1
        return count


class WeeklySchedule(Base):
    __tablename__ = 'weekly_schedules'
    __table_args__ = (
        UniqueConstraint('department_id', 'week_start_date', name='unique_department_week'),
    )
    
    id = Column(Integer, primary_key=True)
    department_id = Column(Integer, ForeignKey('departments.id'), nullable=False)
    
    week_start_date = Column(Date, nullable=False)
    week_end_date = Column(Date, nullable=False)
    week_number = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    
    is_approved = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    is_template = Column(Boolean, default=False)
    
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    approved_by = Column(Integer, ForeignKey('users.id'))
    approved_at = Column(DateTime)
    updated_at = Column(DateTime, onupdate=datetime.now)
    updated_by = Column(Integer, ForeignKey('users.id'))
    
    department = relationship("Department")
    creator = relationship("User", foreign_keys=[created_by], backref="created_schedules")
    approver = relationship("User", foreign_keys=[approved_by])
    updater = relationship("User", foreign_keys=[updated_by])
    
    schedule_details = relationship("ScheduleDetail", backref="weekly_schedule", cascade="all, delete-orphan")
    

    
    def add_custom_row(self, db_session, day_date, job_title, day_name=None, current_user_id=None):
        """إضافة صف مخصص للجدول"""
        if not day_name:
            # تحديد اسم اليوم بالعربية
            day_index = (day_date.weekday() + 1) % 7  # تحويل إلى الأسبوع العربي (0 = السبت)
            arabic_days = ['السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
            day_name = arabic_days[day_index]
        
        # العثور على أعلى ترتيب للصفوف في هذا اليوم
        max_order = db_session.query(func.max(ScheduleDetail.row_order)).filter_by(
            weekly_schedule_id=self.id,
            day_date=day_date
        ).scalar() or 0
        
        # إنشاء الصف الجديد
        new_detail = ScheduleDetail(
            weekly_schedule_id=self.id,
            day_date=day_date,
            day_name=day_name,
            job_title=job_title,
            morning_shift=None,
            evening_shift=None,
            night_shift=None,
            row_order=max_order + 1,
            is_custom=True,
            created_by=current_user_id,
            created_at=datetime.now()
        )
        
        db_session.add(new_detail)
        return new_detail

    def get_days_of_week(self):
        days = []
        current_date = self.week_start_date
        while current_date <= self.week_end_date:
            days.append(current_date)
            current_date += timedelta(days=1)
        return days
    

    # في ملف models.py في class WeeklySchedule
    def sync_with_department_structure(self, db_session, force=False):
        """مزامنة الجدول مع هيكل القسم الحالي"""
        try:
            department = db_session.query(Department).get(self.department_id)
            if not department:
                return False
            
            # الحصول على هيكل القسم
            structure_rows = db_session.query(ScheduleStructureRow).filter_by(
                department_id=self.department_id
            ).order_by('row_order').all()
            
            if not structure_rows:
                return False
            
            # حذف التفاصيل القديمة
            db_session.query(ScheduleDetail).filter_by(
                weekly_schedule_id=self.id
            ).delete()
            
            # إضافة التفاصيل الجديدة من هيكل القسم
            for day_offset in range(7):
                current_date = self.week_start_date + timedelta(days=day_offset)
                day_name = self.get_arabic_day_name(current_date)
                
                row_order = 1
                for structure_row in structure_rows:
                    detail = ScheduleDetail(
                        weekly_schedule_id=self.id,
                        day_date=current_date,
                        day_name=day_name,
                        job_title=structure_row.job_title,
                        morning_shift=structure_row.morning_shift,
                        evening_shift=structure_row.evening_shift,
                        night_shift=structure_row.night_shift,
                        row_order=row_order,
                        is_custom=False
                    )
                    db_session.add(detail)
                    row_order += 1
            
            return True
            
        except Exception as e:
            print(f"Error syncing schedule {self.id}: {str(e)}")
            return False


    @staticmethod
    def get_arabic_day_name(date_obj):
        days = {
            'Monday': 'الإثنين',
            'Tuesday': 'الثلاثاء',
            'Wednesday': 'الأربعاء',
            'Thursday': 'الخميس',
            'Friday': 'الجمعة',
            'Saturday': 'السبت',
            'Sunday': 'الأحد'
        }
        english_day = date_obj.strftime('%A')
        return days.get(english_day, english_day)
    
    def copy_row(self, db_session, source_row_id, new_job_title=None):
        try:
            session = Session.object_session(self) or db_session
            
            source_details = session.query(ScheduleDetail).filter_by(
                weekly_schedule_id=self.id,
                id=source_row_id
            ).first()
            
            if not source_details:
                return None
            
            days = self.get_days_of_week()
            new_row_id = None
            
            for day_date in days:
                new_detail = ScheduleDetail(
                    weekly_schedule_id=self.id,
                    day_date=day_date,
                    day_name=self.get_arabic_day_name(day_date),
                    job_title=new_job_title if new_job_title else f"{source_details.job_title} (نسخة)",
                    morning_shift=source_details.morning_shift,
                    evening_shift=source_details.evening_shift,
                    night_shift=source_details.night_shift,
                    row_order=999,
                    is_custom=True
                )
                session.add(new_detail)
                if not new_row_id:
                    new_row_id = new_detail.id
            
            self.reorder_rows(db_session)
            
            return new_row_id
            
        except Exception as e:
            print(f"Error copying row: {str(e)}")
            return None
    
    def reorder_rows(self, db_session):
        try:
            session = Session.object_session(self) or db_session
            
            details = session.query(ScheduleDetail).filter_by(
                weekly_schedule_id=self.id,
                day_date=self.week_start_date
            ).order_by('row_order', 'id').all()
            
            for order, detail in enumerate(details):
                session.query(ScheduleDetail).filter_by(
                    weekly_schedule_id=self.id,
                    job_title=detail.job_title
                ).update({'row_order': order})
            
            return True
        except Exception as e:
            print(f"Error reordering rows: {str(e)}")
            return False

class ScheduleDetail(Base):
    __tablename__ = 'schedule_details'
    
    id = Column(Integer, primary_key=True)
    weekly_schedule_id = Column(Integer, ForeignKey('weekly_schedules.id'), nullable=False)
    
    day_date = Column(Date, nullable=False)
    day_name = Column(String(20), nullable=False)
    is_custom = Column(Boolean, default=False)

    job_title = Column(String(100), nullable=False)
    morning_shift = Column(String(100), nullable=True)
    evening_shift = Column(String(100), nullable=True)
    night_shift = Column(String(100), nullable=True)
    
    row_order = Column(Integer, default=0)
    is_custom = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    
    modified_by = Column(Integer, ForeignKey('users.id'))
    modified_at = Column(DateTime)
    
    modifier = relationship("User", foreign_keys=[modified_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'day_date': self.day_date.strftime('%Y-%m-%d') if self.day_date else None,
            'day_name': self.day_name,
            'job_title': self.job_title,
            'morning_shift': self.morning_shift,
            'evening_shift': self.evening_shift,
            'night_shift': self.night_shift,
            'row_order': self.row_order,
            'is_custom': self.is_custom,
            'notes': self.notes
        }


class ScheduleApprovalHistory(Base):
    __tablename__ = 'schedule_approval_history'
    
    id = Column(Integer, primary_key=True)
    schedule_id = Column(Integer, ForeignKey('weekly_schedules.id'), nullable=False)
    action = Column(String(50), nullable=False)
    comments = Column(Text, nullable=True)
    performed_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    performed_at = Column(DateTime, default=datetime.now)
    
    schedule = relationship("WeeklySchedule", backref="approval_history")
    performer = relationship("User", foreign_keys=[performed_by])


# تعريف جدول الوسيط لمشاهدة الجداول
user_schedule_view = Table('user_schedule_view', Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('schedule_id', Integer, ForeignKey('weekly_schedules.id'), primary_key=True),
    Column('viewed_at', DateTime, default=datetime.now)
)

# إضافة العلاقة للمستخدم بعد تعريف جميع النماذج
User.schedules_viewed = relationship(
    "WeeklySchedule",
    secondary=user_schedule_view,
    backref="viewed_by_users"
)

# إصلاح العلاقات في Department class لتجنب المشاكل الدائرية
Department.sync_all_schedules = lambda self: {
    'success': False,
    'message': 'هذه الدالة تتطلب جلسة قاعدة بيانات، يرجى استخدامها من داخل التطبيق'
}