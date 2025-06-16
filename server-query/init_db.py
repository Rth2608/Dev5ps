import psycopg2
from datetime import datetime, timedelta

# 심볼과 인터벌
SYMBOLS = ["BTC", "ETH", "XRP", "SOL"]
INTERVALS = ["15m", "1h", "4h", "1d"]

conn = psycopg2.connect(
    host="localhost",
    port="5432",
    dbname="postgres",
    user="postgres",
    password="yourpassword",
)
cur = conn.cursor()


# 테이블 생성 함수
def create_table(table_name):
    cur.execute(f"DROP TABLE IF EXISTS {table_name}")
    cur.execute(
        f"""
        CREATE TABLE {table_name} (
            timestamp TIMESTAMPTZ PRIMARY KEY,
            open NUMERIC,
            high NUMERIC,
            low NUMERIC,
            close NUMERIC,
            volume NUMERIC
        )
    """
    )


# 샘플 데이터 생성
def generate_ohlcv(start_time, count, open_base):
    return [
        (
            (start_time + timedelta(minutes=15 * i)).isoformat(),
            open_base + i,
            open_base + i + 10,
            open_base + i - 5,
            open_base + i + 3,
            1000 + i * 10,
        )
        for i in range(count)
    ]


# 모든 테이블 생성 및 샘플 데이터 삽입
start_time = datetime(2017, 8, 17, 0, 0)

for sym in SYMBOLS:
    for intv in INTERVALS:
        table = f"{sym.lower()}_{intv}"
        create_table(table)
        data = generate_ohlcv(start_time, 40, 1000)
        for row in data:
            cur.execute(
                f"""
                INSERT INTO {table} (timestamp, open, high, low, close, volume)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                row,
            )

# filtered 테이블도 미리 생성
cur.execute("DROP TABLE IF EXISTS filtered")
cur.execute(
    """
    CREATE TABLE filtered (
        entry_time TIMESTAMPTZ,
        exit_time TIMESTAMPTZ,
        symbol TEXT,
        interval TEXT,
        PRIMARY KEY (entry_time, exit_time, symbol, interval)
    )
"""
)

conn.commit()
cur.close()
conn.close()
print("✅ All test tables created.")
