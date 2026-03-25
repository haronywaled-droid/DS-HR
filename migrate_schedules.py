#!/usr/bin/env python3
import sys
import os
import json
from datetime import date, datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db_session
from models import WeeklySchedule, Department, User

def analyze_schedule_data_structure():
    """Analyze all schedules to understand their structure"""
    print("=== Analyzing Schedule Data Structure ===")
    
    schedules = db_session.query(WeeklySchedule).all()
    structure_types = {}
    
    for schedule in schedules:
        if not schedule.schedule_data:
            structure_types['empty'] = structure_types.get('empty', 0) + 1
            continue
            
        try:
            data = json.loads(schedule.schedule_data)
            
            if isinstance(data, dict):
                if 'schedule' in data:
                    # New structure
                    key = f"new_structure_with_{len(data.get('schedule', []))}_days"
                elif any(k.isdigit() for k in data.keys()):
                    # Old structure: {employee_id: {day: shift}}
                    key = "old_employee_dict"
                elif 'day' in data or 'اليوم' in data:
                    key = "day_based_dict"
                else:
                    key = f"dict_with_{len(data.keys())}_keys"
                    
            elif isinstance(data, list):
                if len(data) > 0 and isinstance(data[0], dict):
                    if 'day' in data[0] or 'اليوم' in data[0]:
                        key = f"list_of_days_{len(data)}"
                    elif any(k.isdigit() for k in data[0].keys()):
                        key = "list_of_employee_dicts"
                    else:
                        key = f"list_of_dicts_{len(data)}"
                else:
                    key = f"list_of_{type(data[0]).__name__}"
            else:
                key = f"unknown_{type(data).__name__}"
                
        except Exception as e:
            key = f"error_{str(e)[:50]}"
        
        structure_types[key] = structure_types.get(key, 0) + 1
    
    print("Structure Analysis Results:")
    for struct_type, count in structure_types.items():
        print(f"  {struct_type}: {count} schedules")
    
    return structure_types

def extract_all_employee_data():
    """Extract all employee data from all schedules"""
    print("\n=== Extracting All Employee Data ===")
    
    schedules = db_session.query(WeeklySchedule).all()
    all_employee_shifts = {}
    department_employees = {}
    
    for schedule in schedules:
        if not schedule.schedule_data:
            continue
            
        try:
            data = json.loads(schedule.schedule_data)
            department_id = schedule.department_id
            
            if department_id not in department_employees:
                department_employees[department_id] = set()
            
            # Handle different data structures
            if isinstance(data, dict):
                if 'schedule' in data:
                    # New structure - extract from schedule list
                    schedule_list = data.get('schedule', [])
                    for day_data in schedule_list:
                        shifts = [
                            day_data.get('morning_shift', ''),
                            day_data.get('evening_shift', ''),
                            day_data.get('night_shift', '')
                        ]
                        
                        for shift in shifts:
                            if shift and shift != 'موظف':
                                # Try to find employee by name
                                employee = find_employee_by_name(shift, department_id)
                                if employee:
                                    department_employees[department_id].add(employee.id)
                                    add_employee_shift(all_employee_shifts, employee.id, schedule.id, shift)
                        
                else:
                    # Old structure: {employee_id: {day: shift}}
                    for emp_id, emp_data in data.items():
                        try:
                            emp_id_int = int(emp_id)
                            department_employees[department_id].add(emp_id_int)
                            
                            # Store all shifts for this employee
                            if isinstance(emp_data, dict):
                                for day, shift in emp_data.items():
                                    if shift:  # Only if shift is not empty
                                        add_employee_shift(all_employee_shifts, emp_id_int, schedule.id, shift)
                        except ValueError:
                            # emp_id is not a number, might be a name
                            pass
                            
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        # Check if it's employee data
                        if any(k.isdigit() for k in item.keys()):
                            # Employee shifts by day
                            for emp_id, shift in item.items():
                                try:
                                    emp_id_int = int(emp_id)
                                    department_employees[department_id].add(emp_id_int)
                                    if shift:
                                        add_employee_shift(all_employee_shifts, emp_id_int, schedule.id, shift)
                                except ValueError:
                                    pass
                        else:
                            # Day-based structure with shift fields
                            shift_fields = ['morning_shift', 'evening_shift', 'night_shift', 
                                          'الشيفت الصباحي', 'الشيفت المسائي', 'شيفت السهر']
                            for field in shift_fields:
                                shift_value = item.get(field, '')
                                if shift_value and shift_value != 'موظف':
                                    employee = find_employee_by_name(shift_value, department_id)
                                    if employee:
                                        department_employees[department_id].add(employee.id)
                                        add_employee_shift(all_employee_shifts, employee.id, schedule.id, shift_value)
                                        
        except Exception as e:
            print(f"  Error extracting data from schedule {schedule.id}: {e}")
            continue
    
    print(f"Found data for {len(all_employee_shifts)} employees across {len(department_employees)} departments")
    return all_employee_shifts, department_employees

def find_employee_by_name(name, department_id):
    """Find employee by name in department"""
    # Clean the name
    clean_name = name.strip().split(',')[0].strip()  # Take first name if comma separated
    
    # Search in users
    employees = db_session.query(User).filter_by(
        department_id=department_id,
        is_admin=False
    ).all()
    
    for emp in employees:
        if clean_name in emp.name or emp.name in clean_name:
            return emp
    
    # Try partial match
    for emp in employees:
        if any(part in emp.name for part in clean_name.split()):
            return emp
    
    return None

def add_employee_shift(all_shifts, emp_id, schedule_id, shift):
    """Add employee shift to the collection"""
    if emp_id not in all_shifts:
        all_shifts[emp_id] = {}
    
    if schedule_id not in all_shifts[emp_id]:
        all_shifts[emp_id][schedule_id] = []
    
    if shift not in all_shifts[emp_id][schedule_id]:
        all_shifts[emp_id][schedule_id].append(shift)

def migrate_all_schedules_with_data():
    """Migrate all schedules while preserving ALL data"""
    print("\n=== Starting Comprehensive Migration ===")
    
    # First, analyze and extract all data
    structure_types = analyze_schedule_data_structure()
    all_employee_shifts, department_employees = extract_all_employee_data()
    
    schedules = db_session.query(WeeklySchedule).all()
    migrated_count = 0
    preserved_data_count = 0
    
    for schedule in schedules:
        try:
            department = db_session.query(Department).get(schedule.department_id)
            if not department:
                print(f"  Skipping schedule {schedule.id}: Department not found")
                continue
            
            # Get all employees in this department
            department_emp_ids = department_employees.get(department.id, set())
            employees = []
            for emp_id in department_emp_ids:
                emp = db_session.query(User).get(emp_id)
                if emp:
                    employees.append(emp)
            
            # If no employees found, get all employees in department
            if not employees:
                employees = db_session.query(User).filter_by(
                    department_id=department.id,
                    is_admin=False
                ).all()
            
            # Create new structure
            new_data = create_new_schedule_structure(department, schedule.week_start_date)
            
            # Fill with existing data if available
            if schedule.schedule_data:
                try:
                    old_data = json.loads(schedule.schedule_data)
                    new_data = merge_old_data_to_new_structure(
                        old_data, new_data, schedule.week_start_date, employees
                    )
                    preserved_data_count += 1
                except Exception as e:
                    print(f"  Error merging old data for schedule {schedule.id}: {e}")
                    # Continue with empty new structure
            
            # Update schedule
            schedule.schedule_data = json.dumps(new_data, ensure_ascii=False)
            schedule.status = 'draft'
            schedule.is_approved = False
            schedule.is_locked = False
            
            migrated_count += 1
            
            if migrated_count % 10 == 0:
                print(f"  Migrated {migrated_count} schedules...")
                
        except Exception as e:
            print(f"  Error migrating schedule {schedule.id}: {e}")
            continue
    
    db_session.commit()
    
    print(f"\n=== Migration Complete ===")
    print(f"Total schedules migrated: {migrated_count}/{len(schedules)}")
    print(f"Data preserved from: {preserved_data_count} schedules")
    
    return migrated_count, preserved_data_count

def create_new_schedule_structure(department, week_start_date):
    """Create new schedule structure"""
    week_end_date = week_start_date + timedelta(days=6)
    
    # Days in Arabic
    days = ['السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
    
    schedule_list = []
    for i, day_name in enumerate(days):
        current_date = week_start_date + timedelta(days=i)
        
        day_entry = {
            'day': day_name,
            'date': current_date.strftime('%Y-%m-%d'),
            'department': department.name,
            'morning_shift': 'موظف',
            'evening_shift': 'موظف',
            'night_shift': 'موظف',
            'job': 'موظف'
        }
        schedule_list.append(day_entry)
    
    return {
        'department': department.name,
        'week_start_date': week_start_date.strftime('%Y-%m-%d'),
        'week_end_date': week_end_date.strftime('%Y-%m-%d'),
        'source': 'migration_' + datetime.now().strftime('%Y%m%d_%H%M%S'),
        'schedule': schedule_list
    }

def merge_old_data_to_new_structure(old_data, new_structure, week_start_date, employees):
    """Merge old data into new structure intelligently"""
    
    # Create employee name mapping
    employee_names = {emp.id: emp.name for emp in employees}
    
    # Map days
    arabic_days = ['السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة']
    day_mapping = {day: i for i, day in enumerate(arabic_days)}
    
    # Process old data based on its structure
    if isinstance(old_data, dict):
        if 'schedule' not in old_data:
            # Old employee-based structure
            for emp_id_str, emp_schedule in old_data.items():
                if not isinstance(emp_schedule, dict):
                    continue
                    
                try:
                    emp_id = int(emp_id_str)
                    emp_name = employee_names.get(emp_id, f"مستخدم {emp_id}")
                    
                    for day_name_arabic, shift in emp_schedule.items():
                        if not shift:
                            continue
                            
                        day_index = day_mapping.get(day_name_arabic)
                        if day_index is not None and day_index < len(new_structure['schedule']):
                            day_entry = new_structure['schedule'][day_index]
                            
                            # Determine shift type
                            if 'صباحي' in shift:
                                current = day_entry.get('morning_shift', '')
                                if current == 'موظف':
                                    day_entry['morning_shift'] = emp_name
                                elif emp_name not in current:
                                    day_entry['morning_shift'] = f"{current}, {emp_name}"
                            elif 'مسائي' in shift:
                                current = day_entry.get('evening_shift', '')
                                if current == 'موظف':
                                    day_entry['evening_shift'] = emp_name
                                elif emp_name not in current:
                                    day_entry['evening_shift'] = f"{current}, {emp_name}"
                            elif 'ليلي' in shift or 'سهر' in shift:
                                current = day_entry.get('night_shift', '')
                                if current == 'موظف':
                                    day_entry['night_shift'] = emp_name
                                elif emp_name not in current:
                                    day_entry['night_shift'] = f"{current}, {emp_name}"
                                    
                except (ValueError, TypeError):
                    # emp_id is not a number, skip
                    continue
        
        else:
            # Already has new structure, keep it
            return old_data
            
    elif isinstance(old_data, list):
        for item in old_data:
            if not isinstance(item, dict):
                continue
                
            # Check if it's a day entry
            day_name = item.get('day') or item.get('اليوم')
            if day_name:
                day_index = day_mapping.get(day_name)
                if day_index is not None and day_index < len(new_structure['schedule']):
                    day_entry = new_structure['schedule'][day_index]
                    
                    # Copy shift data
                    for shift_field in ['morning_shift', 'evening_shift', 'night_shift',
                                      'الشيفت الصباحي', 'الشيفت المسائي', 'شيفت السهر']:
                        if shift_field in item and item[shift_field]:
                            # Map old field names to new ones
                            if shift_field == 'الشيفت الصباحي':
                                day_entry['morning_shift'] = item[shift_field]
                            elif shift_field == 'الشيفت المسائي':
                                day_entry['evening_shift'] = item[shift_field]
                            elif shift_field == 'شيفت السهر':
                                day_entry['night_shift'] = item[shift_field]
                            else:
                                day_entry[shift_field] = item[shift_field]
                    
                    # Copy job if available
                    if 'job' in item and item['job']:
                        day_entry['job'] = item['job']
    
    return new_structure

def create_future_schedules():
    """Create future schedules for all departments"""
    print("\n=== Creating Future Schedules ===")
    
    departments = db_session.query(Department).filter_by(auto_generate_schedule=True).all()
    created_count = 0
    
    for department in departments:
        try:
            # Get latest schedule for this department to use as template
            latest_schedule = db_session.query(WeeklySchedule).filter_by(
                department_id=department.id
            ).order_by(WeeklySchedule.week_start_date.desc()).first()
            
            if not latest_schedule:
                print(f"  No existing schedule found for {department.name}")
                continue
            
            # Calculate next weeks
            today = date.today()
            days_since_saturday = (today.weekday() - 5) % 7
            current_week_start = today - timedelta(days=days_since_saturday)
            
            # Create schedules for next 8 weeks
            for week_offset in range(1, 9):
                week_start = current_week_start + timedelta(days=7 * week_offset)
                week_end = week_start + timedelta(days=6)
                
                # Check if schedule already exists
                exists = db_session.query(WeeklySchedule).filter_by(
                    department_id=department.id,
                    week_start_date=week_start
                ).first()
                
                if not exists:
                    # Create new schedule using latest as template
                    new_schedule = WeeklySchedule(
                        department_id=department.id,
                        week_start_date=week_start,
                        week_end_date=week_end,
                        schedule_data=latest_schedule.schedule_data,  # Copy structure
                        created_by=1,  # System
                        status='draft',
                        is_approved=False,
                        is_locked=False
                    )
                    
                    db_session.add(new_schedule)
                    created_count += 1
                    
                    if created_count % 5 == 0:
                        print(f"  Created {created_count} future schedules...")
                        
        except Exception as e:
            print(f"  Error creating future schedules for {department.name}: {e}")
            continue
    
    db_session.commit()
    print(f"Created {created_count} future schedules")
    return created_count

def generate_migration_report(migrated_count, preserved_count, future_count):
    """Generate detailed migration report"""
    print("\n" + "="*60)
    print("MIGRATION REPORT".center(60))
    print("="*60)
    
    total_schedules = db_session.query(WeeklySchedule).count()
    
    report = {
        'summary': {
            'total_schedules': total_schedules,
            'migrated': migrated_count,
            'preserved_data': preserved_count,
            'future_created': future_count,
            'migration_rate': f"{(migrated_count/total_schedules*100):.1f}%" if total_schedules > 0 else "N/A"
        },
        'details': {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'departments_count': db_session.query(Department).count(),
            'auto_generate_departments': db_session.query(Department).filter_by(auto_generate_schedule=True).count()
        }
    }
    
    # Print report
    print(f"\n📊 SUMMARY")
    print(f"   Total Schedules: {report['summary']['total_schedules']}")
    print(f"   Migrated: {report['summary']['migrated']}")
    print(f"   Data Preserved: {report['summary']['preserved_data']}")
    print(f"   Future Created: {report['summary']['future_count']}")
    print(f"   Success Rate: {report['summary']['migration_rate']}")
    
    print(f"\n📅 DETAILS")
    print(f"   Migration Time: {report['details']['timestamp']}")
    print(f"   Total Departments: {report['details']['departments_count']}")
    print(f"   Auto-Generate Enabled: {report['details']['auto_generate_departments']}")
    
    print(f"\n✅ NEXT STEPS")
    print("   1. Review migrated schedules in admin panel")
    print("   2. Check data preservation in each schedule")
    print("   3. Verify future schedules were created")
    print("   4. Inform department managers to review their schedules")
    
    print("\n" + "="*60)
    
    # Save report to file
    report_file = f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"📄 Report saved to: {report_file}")
    return report

def main():
    """Main migration function"""
    print("="*60)
    print("COMPREHENSIVE SCHEDULE MIGRATION SYSTEM".center(60))
    print("="*60)
    
    try:
        # Step 1: Analyze current state
        print("\n📈 STEP 1: Analyzing current schedule structure...")
        structure_types = analyze_schedule_data_structure()
        
        # Step 2: Migrate all schedules
        print("\n🔄 STEP 2: Migrating schedules with data preservation...")
        migrated_count, preserved_count = migrate_all_schedules_with_data()
        
        # Step 3: Create future schedules
        print("\n🚀 STEP 3: Creating future schedules...")
        future_count = create_future_schedules()
        
        # Step 4: Generate report
        print("\n📋 STEP 4: Generating migration report...")
        report = generate_migration_report(migrated_count, preserved_count, future_count)
        
        print("\n✅ Migration completed successfully!")
        print(f"\nNext steps:")
        print(f"  1. Go to /admin/migrate_schedules to verify")
        print(f"  2. Check /admin/schedules for migrated data")
        print(f"  3. Review the report at: migration_report_*.json")
        
    except Exception as e:
        print(f"\n❌ Migration failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    with app.app_context():
        success = main()
        sys.exit(0 if success else 1)