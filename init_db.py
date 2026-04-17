"""
Database Initialization Script
Run this to create all tables with proper schema
Usage:
  python init_db.py
  python init_db.py --yes
"""

import argparse
import sys

from app import create_app, db
from app.models.user import User
from app.models.workgroup import Workgroup
from app.models.workgroupAssignment import WorkgroupAssignment
from app.models.bug import Bug
from app.models.bug_tests import BugTest
from app.models.bug_stations import BugStation

def _confirmed(skip_prompt=False):
    if skip_prompt:
        return True

    try:
        confirm = input("Are you absolutely sure? (type 'yes' to proceed): ")
    except EOFError:
        print(
            "No confirmation was provided. Run this from an interactive terminal "
            "or pass --yes if you really want to wipe and recreate the database."
        )
        return False

    return confirm.lower() == 'yes'

def init_database(skip_prompt=False):
    app = create_app(start_scheduler=False)
    
    with app.app_context():
        print("!" * 60)
        print("  WARNING: This will WIPE all data in THE DATABASE.")
        print("!" * 60)
        if not _confirmed(skip_prompt):
            print("Initialization cancelled.")
            return 1

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

    return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Wipe and recreate the database schema.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt. This will wipe all existing data.",
    )
    args = parser.parse_args()
    sys.exit(init_database(skip_prompt=args.yes))
