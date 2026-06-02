# SentinelVision: Smart AI CCTV Security System

SentinelVision is a smart security camera system that uses Artificial Intelligence (AI) to watch your camera streams, detect events, and keep your premises safe. 

Unlike standard security cameras, SentinelCV automatically recognizes people, tracks if important items go missing, monitors restricted areas, and sends you instant email alerts when critical events happen.

---

## 🚀 Key Features

* **Smart Person Detection**: Automatically recognizes people in the camera view using AI.
* **Restricted Area Monitoring**: Set a camera as a "restricted zone" and get instant alarms if someone enters.
* **Asset Protection (Object Tracking)**: Monitors important items (like laptops or bags) and alerts you if they disappear.
* **Non-Blocking Email Alerts**: Sends automated email notifications without slowing down the live camera streams.
* **Live Video Dashboard**: A clean, modern web interface to watch live feeds, view alert histories, and toggle restricted areas.
* **System Health Diagnostics**: A built-in health monitor page that verifies if your database, AI models, and camera streams are running correctly.
* **Power-Saving Mode**: The system uses smart motion detection to only run heavy AI models when movement is detected, saving over 90% of computer processing power.

---

## 🛠️ How It Works (Simple Flow)

```text
  [Camera Stream] (Webcam, RTSP, or Video File)
         │
         ▼
  [Smart Motion Check] (Is something moving?)
         │
         ├─── No ───► [Power-Saving Standby] (No AI running)
         │
         └─── Yes ──► [AI Inferences] (YOLO Object Detect & Face Recognition)
                            │
                            ▼
                      [Event Rules Engine]
                            │
                            ▼
                      [Alarms & Alerts Created]
                            │
         ┌──────────────────┴──────────────────┐
         ▼                                     ▼
  [Saved to Database]                [Background Email Alert]
```

---

## 📂 Folder Structure

* `app/` - The core application code (routing, database, and logic).
* `data/` - Where the local database, camera snapshots, and AI weights are saved.
* `logs/` - Logs tracking camera status, events, AI processing, and web requests.
* `tests/` - Automatic test scripts to ensure the system is working perfectly.
* `requirements.txt` - List of Python packages required to run this app.
* `app.py` - The main file you run to start the server.

---

## 💾 Installation & Setup

### Prerequisites
* **Python 3.10+** (Programming language)
* **CMake** (Utility program, required to compile the face-recognition library)
* A webcam or a camera stream URL

### 1. Clone the Project
Open Git Bash or your terminal and run:
```bash
git clone https://github.com/ahmedmustafa28/sentinel-vision.git
cd sentinel-vision
```

### 2. Configure Settings (`.env`)
Create a new file named `.env` in the root folder and add your settings:
```env
APP_NAME="SentinelCV AI Surveillance"
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false

# Database Path
DB_URL="sqlite:///./data/sqlite/cctv.db"
DB_ECHO=false

# Email Notification Settings (Optional)
ENABLE_EMAIL_ALERTS=true
SMTP_HOST="smtp.gmail.com"
SMTP_PORT=587
SMTP_USER="your-email@gmail.com"
SMTP_PASS="your-app-password"
ALERT_TO_EMAIL="recipient-email@gmail.com"
```

### 3. Install Dependencies
Run these commands in your terminal to set up a virtual environment and install dependencies:
```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install all packages
pip install -r requirements.txt
```

### 4. Add Known Faces (Optional)
Put reference photos of people you want the system to recognize in the `known_faces/` folder. Name the photo after the person (e.g. `jane.jpg`, `john.png`). The system will automatically learn their faces on startup.

---

## 🖥️ How to Run

1. **Start the Application**:
   ```bash
   python app.py
   ```
2. **Open the Web Portal**:
   Open your browser and navigate to:
   * **Dashboard & Live Video**: [http://localhost:8000](http://localhost:8000)
   * **System Health Status**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 🧪 Automatic Tests
To run the automated tests and verify that the database and notification streams are working perfectly:
```bash
pytest -v
```

---

## 📄 License
This project is licensed under the MIT License.

---
