#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess

# Color codes for terminal printing
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Get the project root directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

def check_and_install_dependencies():
    print("Checking for required dependencies...")
    dependencies = ["ultralytics", "alembic"]
    missing = []
    for dep in dependencies:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)
            
    if not missing:
        print("Required dependencies are already installed.")
        return True
        
    print(f"Missing dependencies: {', '.join(missing)}. Installing...")
    try:
        # Install only the missing essential packages to avoid recompiling heavy requirements
        subprocess.run([sys.executable, "-m", "pip", "install"] + missing, check=True)
        print("Dependencies installed successfully.")
        return True
    except Exception as e:
        print(f"Failed to install dependencies automatically: {e}")
        return False

def create_directories():
    dirs = [
        "data/sqlite",
        "data/models/yolo",
        "data/raw/known_faces",
        "data/raw/unknown_faces",
        "data/snapshots",
        "data/reports",
        "logs"
    ]
    try:
        for d in dirs:
            os.makedirs(d, exist_ok=True)
        return True, "Directories created successfully"
    except Exception as e:
        return False, f"Failed to create directories: {e}"

def setup_env():
    env_file = ".env"
    env_example = ".env.example"
    
    if os.path.exists(env_file):
        return True, ".env file already exists"
        
    if not os.path.exists(env_example):
        return False, ".env.example does not exist in project root"
        
    try:
        shutil.copy(env_example, env_file)
        print(f"\n{YELLOW}[REMINDER]{RESET} Please open the '.env' file and configure your SMTP credentials "
              f"(SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_TO_EMAIL) to enable email alerts.\n")
        return True, ".env copied from .env.example"
    except Exception as e:
        return False, f"Failed to copy .env: {e}"

def setup_yolo_weights():
    dest_path = os.path.join("data", "models", "yolo", "yolov8n.pt")
    if os.path.exists(dest_path):
        return True, "YOLOv8n weights already exist in data/models/yolo/"
    
    try:
        print("Downloading YOLOv8n weights via Ultralytics API...")
        from ultralytics import YOLO
        # This downloads yolov8n.pt to current working directory (PROJECT_ROOT)
        model = YOLO("yolov8n.pt")
        
        # Move it to the destination
        if os.path.exists("yolov8n.pt"):
            shutil.move("yolov8n.pt", dest_path)
            return True, "Downloaded and moved YOLOv8n weights successfully"
        else:
            # Check default Ultralytics config cache location as fallback
            default_cached = os.path.expanduser("~/.config/Ultralytics/yolov8n.pt")
            if os.path.exists(default_cached):
                shutil.copy(default_cached, dest_path)
                return True, "Copied YOLOv8n weights from cache successfully"
            return False, "yolov8n.pt not found in workspace root after download"
    except Exception as e:
        return False, f"YOLOv8n weights download failed: {e}"

def run_migrations():
    try:
        print("Running database migrations...")
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return True, "Alembic migrations completed successfully"
        else:
            err_msg = result.stderr.strip() or result.stdout.strip()
            return False, f"Alembic failed: {err_msg}"
    except Exception as e:
        return False, f"Failed to execute alembic: {e}"

def main():
    # Change working directory to project root
    os.chdir(PROJECT_ROOT)
    
    print(f"{BOLD}{BLUE}=================================================={RESET}")
    print(f"{BOLD}{BLUE}          SentinelVision Bootstrap Setup          {RESET}")
    print(f"{BOLD}{BLUE}=================================================={RESET}\n")
    
    # 1. Check/Install dependencies
    check_and_install_dependencies()
    print()
    
    checklist = []
    
    # Step 1: Create required directories
    print("1. Creating required directories...")
    success, msg = create_directories()
    checklist.append(("Create Directories", success, msg))
    print(f"   Result: {'PASS' if success else 'FAIL'} - {msg}\n")
    
    # Step 2: Set up environment configuration (.env)
    print("2. Setting up environment configuration (.env)...")
    success, msg = setup_env()
    checklist.append(("Configure .env File", success, msg))
    print(f"   Result: {'PASS' if success else 'FAIL'} - {msg}\n")
    
    # Step 3: Set up YOLO weights
    print("3. Setting up YOLOv8n weights...")
    success, msg = setup_yolo_weights()
    checklist.append(("Download YOLOv8n Weights", success, msg))
    print(f"   Result: {'PASS' if success else 'FAIL'} - {msg}\n")
    
    # Step 4: Run Alembic migrations
    print("4. Applying database migrations...")
    success, msg = run_migrations()
    checklist.append(("Run Alembic Migrations", success, msg))
    print(f"   Result: {'PASS' if success else 'FAIL'} - {msg}\n")
    
    # Print colour-coded checklist summary
    print(f"{BOLD}{BLUE}=================================================={RESET}")
    print(f"{BOLD}{BLUE}              Setup Process Summary               {RESET}")
    print(f"{BOLD}{BLUE}=================================================={RESET}")
    
    env_reminder = False
    for title, success, msg in checklist:
        status_color = GREEN if success else RED
        status_text = "PASS" if success else "FAIL"
        print(f"{title:<35} [ {status_color}{status_text}{RESET} ]")
        if not success:
            print(f"   {RED}Error: {msg}{RESET}")
        if title == "Configure .env File" and "copied from .env.example" in msg:
            env_reminder = True
            
    print(f"{BOLD}{BLUE}=================================================={RESET}")
    
    if env_reminder:
        print(f"\n{BOLD}{YELLOW}[IMPORTANT]{RESET} SMTP configuration is required for email alerts.")
        print("Please edit the newly created '.env' file with your SMTP mail credentials.")
    
    # Exit with code 0 if all crucial steps pass (except migrations, since alembic might not be configured)
    # But if directories, env, or weights setup fail, exit with 1.
    crucial_steps = checklist[:-1]
    if all(step[1] for step in crucial_steps):
        print(f"\n{GREEN}Setup completed successfully!{RESET}\n")
        sys.exit(0)
    else:
        print(f"\n{RED}Setup encountered errors in crucial steps.{RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
