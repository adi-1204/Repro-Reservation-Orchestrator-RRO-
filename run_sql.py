import sys
import os
from sqlalchemy import text
from app import create_app, db

def run_sql(input_val):
    app = create_app()
    with app.app_context():
        engine = db.engine
        
        # Check if input is a file path
        if os.path.exists(input_val):
            with open(input_val, 'r') as f:
                query = f.read()
            print(f"--- Executing File: {input_val} ---")
        else:
            query = input_val
            print(f"--- Executing Query: {input_val} ---")

        try:
            with engine.connect() as conn:
                # Split queries by semicolon if running a file (basic support)
                # MySQL connector handles multiple statements differently, 
                # but for simple inserts/selects this works.
                if ';' in query:
                    statements = [s.strip() for s in query.split(';') if s.strip()]
                    for s in statements:
                        result = conn.execute(text(s))
                        # Handle results if any
                        if s.lower().startswith('select'):
                            print_result(result)
                        else:
                            print(f"Affected rows: {result.rowcount}")
                else:
                    result = conn.execute(text(query))
                    if query.lower().startswith('select'):
                        print_result(result)
                    else:
                        print(f"Affected rows: {result.rowcount}")
                
                conn.commit()
                print("Done.")
        except Exception as e:
            print(f"Error: {e}")

def print_result(result):
    rows = result.fetchall()
    if not rows:
        print("   (Empty Result)")
        return
    
    colnames = result.keys()
    print(" | ".join(colnames))
    print("-" * 50)
    for row in rows:
        print(" | ".join(str(val) for val in row))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_sql.py \"SQL QUERY\" or python run_sql.py file.sql")
    else:
        run_sql(sys.argv[1])
