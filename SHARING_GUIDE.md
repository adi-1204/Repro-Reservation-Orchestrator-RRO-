# Project Setup & Sharing Guide

This guide explains how to set up and run the **Repro-Reservation-Orchestrator (RRO)** on a new machine.

## 1. Prerequisites
- **Python 3.8+**
- **MySQL Server** (Ensure it is running)
- Any modern web browser

## 2. Initial Setup
1. **Clone the repository** and enter the folder.
2. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```
3. **Configure Environment**: 
   Create a `.env` file in the root directory. You can use the following template (update with your MySQL password):
   ```env
   KEY=your_secret_key
   DB_USER=root
   DB_PASSWORD=YOUR_PASSWORD
   DB_HOST=localhost
   DB_NAME=repro_db

   BUGZ_HOST=http://127.0.0.1:5000
   BUGZ_USER=mock_user
   BUGZ_PASSWORD=mock_pass
   ```

## 3. Database Initialization
Before running the app for the first time, you must prepare the database:
```powershell
# 1. Create the database
python create_db.py

# 2. Initialize tables
python init_db.py

# 3. Seed users and initial bugs
python ingest_mock_bugs.py

# 4. Generate AI Analysis (Populates the dashboard's AI fields)
python generate_ml_analysis.py --force
```

## 4. Running the Servers
To see the full functionality (including AI analysis and Bugzilla fetching), you need to run **two** terminals:

### Terminal 1: Mock API Server
This mimics the internal data sources.
```powershell
python mock_api_server.py
```

### Terminal 2: Main Application
This is the user interface.
```powershell
python run.py
```
After starting this, open your browser to: **`http://127.0.0.1:5000`** (or the port shown in the terminal).

---
*Note: If you have access to the real HPE network, you can update `BUGZ_HOST` in the `.env` to point to the production Bugzilla instance.*
