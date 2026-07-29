import sqlite3
import pandas as pd

conn = sqlite3.connect('tools/central_quiz.db')
tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table';", conn)

for table_name in tables['name']:
    print(f"--- Table: {table_name} ---")
    df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    print(df.to_string())
    print("\n")

conn.close()