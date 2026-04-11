import sqlite3
import os

def view_database():
    db_path = 'rro_local.db'
    if not os.path.exists(db_path):
        print(f"Database file {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    def print_table(title, query):
        print(f"\n=== {title} ===")
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            if not rows:
                print("   (Empty)")
                return
            
            # Get column names
            colnames = [description[0] for description in cursor.description]
            print("   " + " | ".join(colnames))
            print("   " + "-" * (sum(len(c) for c in colnames) + 3 * len(colnames)))
            
            for row in rows:
                print("   " + " | ".join(str(val) for val in row))
        except Exception as e:
            print(f"   Error: {e}")

    # Summary of all tables
    print("\n=== Database Table Summary ===")
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [r[0] for r in cursor.fetchall()]
        print(f"   {'Table Name':<30} | {'Row Count':<10}")
        print("   " + "-" * 45)
        for table in tables:
            cursor.execute(f'SELECT count(*) FROM "{table}"')
            count = cursor.fetchone()[0]
            print(f"   {table:<30} | {count:<10}")
    except Exception as e:
        print(f"   Error: {e}")

    # Detailed view of specific tables
    print_table("Users", 'SELECT ID, First_Name, Role, Email FROM Users LIMIT 5')
    print_table("Bugs", 'SELECT id, bug_code, status, engineer_id FROM Bugs LIMIT 5')
    print_table("Reservations By Name", 'SELECT * FROM Reservations_By_Name LIMIT 5')
    print_table("Reservations By Config", 'SELECT * FROM Reservations_By_Config LIMIT 5')

    conn.close()

if __name__ == '__main__':
    view_database()
