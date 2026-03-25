import os
import shutil
from pathlib import Path

def fix_flask_static():
    """إصلاح هيكل الملفات لـ Flask"""
    base_dir = Path(r"D:\Haron\08-01-2026\hr_system")
    
    # 1. إنشاء مجلد static إذا لم يكن موجوداً
    static_dir = base_dir / "static"
    static_dir.mkdir(exist_ok=True)
    
    # 2. نسخ الملفات من css, js إلى static
    folders_to_copy = ["css", "js"]
    
    for folder in folders_to_copy:
        src = base_dir / folder
        dst = static_dir / folder
        
        if src.exists():
            # حذف الوجهة إذا كانت موجودة
            if dst.exists():
                shutil.rmtree(dst)
            
            # نسخ المجلد
            shutil.copytree(src, dst)
            print(f"✓ تم نسخ {folder} إلى static/")
        else:
            print(f"✗ مجلد {folder} غير موجود")
    
    # 3. إصلاح المسارات في HTML
    html_file = base_dir / "templates" / "manager" / "edit_schedule.html"
    
    if html_file.exists():
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # استبدال المسارات
        content = content.replace('href="css/', 'href="/static/css/')
        content = content.replace('src="js/', 'src="/static/js/')
        content = content.replace('href="../../../css/', 'href="/static/css/')
        content = content.replace('src="../../../js/', 'src="/static/js/')
        
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ تم إصلاح المسارات في {html_file.name}")
    
    # 4. إصلاح ملف 404
    error_file = base_dir / "templates" / "404.html"
    if error_file.exists():
        with open(error_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        content = content.replace("url_for('dashboard'", "url_for('user_dashboard'")
        
        with open(error_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✓ تم إصلاح صفحة 404")
    
    print("\n✅ تم الإصلاح! أعد تشغيل Flask.")

if __name__ == "__main__":
    fix_flask_static()