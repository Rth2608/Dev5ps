import psycopg2
from datetime import datetime, timedelta

# 심볼과 인터벌
SYMBOLS = ["BTC", "ETH", "XRP", "SOL"]
INTERVALS = ["15m", "1h", "4h", "1d"]

# DB 연결
conn = psycopg2.connect(
    host="localhost",
    port="5432",
    dbname="test",
    user="test",
    password="test",
)
cur = conn.cursor()


# 개별 테이블 생성 함수
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


# 샘플 데이터 생성 함수
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


# OHLCV 테이블들 생성 및 데이터 삽입
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


# filtered 테이블 생성 (테스트에서 사용하는 모든 컬럼 포함)
cur.execute("DROP TABLE IF EXISTS filtered")
cur.execute(
    """
    CREATE TABLE filtered (
        entry_time TIMESTAMPTZ,
        entry_price NUMERIC,
        stop_loss NUMERIC,
        take_profit NUMERIC,
        exit_time TIMESTAMPTZ,
        exit_price NUMERIC,
        profit_rate NUMERIC,
        cum_profit_rate NUMERIC,
        result TEXT,
        symbol TEXT,
        interval TEXT,
        what_indicators TEXT,
        PRIMARY KEY (entry_time, exit_time, symbol, interval)
    )
"""
)


# 커밋 및 종료
conn.commit()
cur.close()
conn.close()
print("✅ All test tables created.")
