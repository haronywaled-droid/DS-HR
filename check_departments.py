# check_departments.py
from database import db_session
from models import Department

departments = db_session.query(Department).all()
for dept in departments:
    print(f"القسم: {dept.name}")
    print(f"  - لديه هيكل: {'نعم' if dept.schedule_structure else 'لا'}")
    print(f"  - التوليد التلقائي: {'نعم' if dept.auto_generate_schedule else 'لا'}")
    
    if dept.schedule_structure:
        try:
            import json
            structure = json.loads(dept.schedule_structure)
            print(f"  - نوع الهيكل: {type(structure)}")
        except:
            print(f"  - هيكل غير صالح")