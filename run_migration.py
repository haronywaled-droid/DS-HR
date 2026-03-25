#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db_session
from datetime import datetime

def run_migration_test():
    """تشغيل اختبار الهجرة"""
    print("="*60)
    print("اختبار نظام الهجرة".center(60))
    print("="*60)
    
    with app.app_context():
        try:
            # تحليل هياكل البيانات
            from app import analyze_schedule_structures
            result = analyze_schedule_structures()
            
            if result['success']:
                print("\n📊 تحليل هياكل الجداول:")
                for struct_type, count in result['structure_types'].items():
                    print(f"  {struct_type}: {count}")
                print(f"  إجمالي الجداول: {result['total_schedules']}")
            else:
                print(f"\n❌ فشل في التحليل: {result['message']}")
                return
            
            # تنفيذ الهجرة
            from app import migrate_all_schedules_to_new_structure
            migrated_count, preserved_count = migrate_all_schedules_to_new_structure()
            
            print(f"\n✅ نتيجة الهجرة:")
            print(f"  الجداول المنجزة: {migrated_count}")
            print(f"  الجداول التي حُفظت بياناتها: {preserved_count}")
            
            # إنشاء جداول مستقبلية
            from app import generate_future_schedules_after_migration
            future_count = generate_future_schedules_after_migration()
            print(f"  الجداول المستقبلية المنشأة: {future_count}")
            
            print(f"\n🎉 تم اكتمال الهجرة بنجاح!")
            
        except Exception as e:
            print(f"\n❌ خطأ في الهجرة: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    run_migration_test()