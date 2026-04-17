import os
from app import create_app
from app.extensions import db
from app.models.user import User
import sqlite3

# 1. Reset Database
db_path = 'rro_local.db'
if os.path.exists(db_path):
    try:
        os.remove(db_path)
        print("Removed old database.")
    except Exception as e:
        print(f"Failed to remove database: {e}")

app = create_app(start_scheduler=False)
with app.app_context():
    db.create_all()
    print("Database schema created.")

# 2. Ingest Mock Data
print("Ingesting mock data...")
os.system("python ingest_mock_bugs.py")

# 3. Update User Passwords to Sanjana@2005
with app.app_context():
    users = User.query.all()
    for user in users:
        user.password = 'Sanjana@2005'
    db.session.commit()
    print("Updated all user passwords to Sanjana@2005.")

print("Setup complete.")
