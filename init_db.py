"""
Database Initialization Script
Run this to create all tables with proper schema
Usage: python init_db.py
"""

from app import create_app, db
from app.models.user import User
from app.models.workgroup import Workgroup
from app.models.workgroupAssignment import WorkgroupAssignment
from app.models.bug import Bug
from app.models.bug_tests import BugTest
from app.models.bug_stations import BugStation

def init_database():
    app = create_app()
    
    with app.app_context():
        print("Dropping all existing tables...")
        db.drop_all()
        
        print("Creating all tables from models...")
        db.create_all()
        
        print("\nDatabase initialized successfully!")
        print("\nTables created:")
        
        # Verify tables
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        for table in tables:
            print(f"   - {table}")
            columns = inspector.get_columns(table)
            for col in columns:
                print(f"      * {col['name']}: {col['type']}")
        
        print("\nForeign Keys:")
        for table in tables:
            fks = inspector.get_foreign_keys(table)
            if fks:
                print(f"   {table}:")
                for fk in fks:
                    print(f"      - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")

if __name__ == '__main__':
    init_database()
