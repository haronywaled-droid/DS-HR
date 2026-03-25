#!/usr/bin/env python3
# fingerprint_scheduler.py
# Runs fingerprint export every 5 minutes

import schedule
import time
import sys
import os

from datetime import datetime, timedelta

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def run_fingerprint_export():
    """Run the fingerprint export script"""
    try:
        print(f"\n{'='*60}")
        print(f"⏰ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting fingerprint export")
        print('='*60)
        
        # Import and run the fingerprint script
        import request
        request.main()
        
        print(f"\n✅ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Export completed successfully")
        print(f"🔄 Next run at: {(datetime.now() + timedelta(minutes=5)).strftime('%H:%M:%S')}")
        
    except Exception as e:
        print(f"\n❌ [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main scheduler function"""
    print("\n" + "="*60)
    print("🚀 Fingerprint Export Scheduler")
    print("📅 Will run every 5 minutes")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    print("Press Ctrl+C to stop")
    print("="*60)
    
    # Schedule to run every 5 minutes
    schedule.every(5).minutes.do(run_fingerprint_export)
    
    # Run immediately on start
    run_fingerprint_export()
    
    # Keep the scheduler running
    while True:
        try:
            schedule.run_pending()
            time.sleep(2)  # Check every second
        except KeyboardInterrupt:
            print(f"\n\n🛑 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Stopping scheduler...")
            print("Goodbye! 👋")
            break

if __name__ == "__main__":
    # Install schedule if not installed
    try:
        import schedule
    except ImportError:
        print("Installing schedule library...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "schedule"])
        import schedule
    
    main()