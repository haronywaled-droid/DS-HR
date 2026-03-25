import sqlite3
import os

print("=" * 60)
print("DATABASE DEBUGGER")
print("=" * 60)

# Find all database files
db_files = []
for file in os.listdir('.'):
    if file.endswith('.db'):
        db_files.append(file)
        print(f"Found: {file}")

if not db_files:
    print("No .db files found!")
    exit()

print("\n" + "=" * 60)

# Check each database
for db_file in db_files:
    print(f"\nChecking: {db_file}")
    print("-" * 40)
    
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Check if weekly_schedules exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_schedules'")
        if cursor.fetchone():
            print("✓ weekly_schedules table exists")
            
            # Get columns
            cursor.execute("PRAGMA table_info(weekly_schedules)")
            columns = cursor.fetchall()
            
            print(f"Columns ({len(columns)} total):")
            for col in columns:
                col_id, name, type_, notnull, default_val, pk = col
                print(f"  {col_id:2}. {name:20} {type_:15} {'PK' if pk else ''}")
            
            # Check for our problem columns
            problem_cols = ['week_number', 'month', 'year']
            missing = []
            for col_name in problem_cols:
                if not any(col[1] == col_name for col in columns):
                    missing.append(col_name)
            
            if missing:
                print(f"\n❌ MISSING COLUMNS: {', '.join(missing)}")
                
                # Try to add them
                print("\nAttempting to add missing columns...")
                for col in missing:
                    try:
                        if col == 'week_number':
                            cursor.execute(f"ALTER TABLE weekly_schedules ADD COLUMN {col} INTEGER")
                        elif col in ['month', 'year']:
                            cursor.execute(f"ALTER TABLE weekly_schedules ADD COLUMN {col} INTEGER")
                        print(f"  ✓ Added {col}")
                    except Exception as e:
                        print(f"  ✗ Failed to add {col}: {e}")
                
                conn.commit()
            else:
                print(f"\n✓ All required columns present!")
                
        else:
            print("❌ weekly_schedules table NOT FOUND!")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking {db_file}: {e}")

print("\n" + "=" * 60)
print("DEBUG COMPLETE")
print("=" * 60)
input("\nPress Enter to exit...")