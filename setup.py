import sqlite3

# Connect to SQLite database (it will be created if it doesn't exist)
conn = sqlite3.connect('trades.db')
cursor = conn.cursor()

# Create a table to store trade mappings
cursor.execute('''
CREATE TABLE IF NOT EXISTS trade_mappings (
    main_trade_id TEXT PRIMARY KEY,
    replica_trade_id TEXT,
    symbol TEXT
)
''')

conn.commit()
conn.close()
