import psycopg2
import os

# 환경변수 기반 설정 (GitHub Actions에서도 적용됨)
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "test")
DB_USER = os.getenv("POSTGRES_USER", "test")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "test")

conn = psycopg2.connect(
    host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS
)

cur = conn.cursor()

tables = ["btc_1h", "btc_4h", "eth_1h", "eth_4h"]

for table in tables:
    cur.execute(f"DROP TABLE IF EXISTS {table}")
    cur.execute(
        f"""
        CREATE TABLE {table} (
            timestamp TIMESTAMPTZ PRIMARY KEY,
            open NUMERIC,
            high NUMERIC,
            low NUMERIC,
            close NUMERIC,
            volume NUMERIC
        )
    """
    )

ohlcv_data = {
    "btc_1h": [("2017-08-17 05:00:00+00", 1000, 1100, 900, 1050, 5000)],
    "btc_4h": [("2017-08-17 05:00:00+00", 1001, 1500, 900, 1200, 5000)],
    "eth_1h": [("2017-08-17 05:00:00+00", 300, 400, 250, 350, 2000)],
    "eth_4h": [("2017-08-17 05:00:00+00", 300, 500, 250, 400, 3000)],
}

for table, rows in ohlcv_data.items():
    cur.executemany(
        f"""
        INSERT INTO {table} (timestamp, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s)
    """,
        rows,
    )

cur.execute("DROP TABLE IF EXISTS filtered")
cur.execute(
    """
    CREATE TABLE filtered (
        entry_time TIMESTAMPTZ PRIMARY KEY,
        entry_price DOUBLE PRECISION,
        stop_loss DOUBLE PRECISION,
        take_profit DOUBLE PRECISION,
        exit_time TIMESTAMPTZ,
        result TEXT,
        symbol TEXT, 
        interval TEXT,
        strategy TEXT,
        what_indicators TEXT,
        profit_rate DOUBLE PRECISION,
        cum_profit_rate DOUBLE PRECISION
    )
"""
)

conn.commit()
cur.close()
conn.close()
