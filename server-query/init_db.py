import psycopg2
from datetime import datetime, timedelta

# PostgreSQL 접속 설정
conn = psycopg2.connect(
    host="localhost", port="5432", dbname="test", user="test", password="test"
)
cur = conn.cursor()

# 심볼별 테이블 목록
tables = ["btc_1h", "btc_4h", "eth_1h", "eth_4h"]

# 기존 테이블 삭제 및 재생성
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


# 샘플 OHLCV 데이터 생성 함수
def generate_ohlcv(start_time_str, count, open_base):
    base_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
    return [
        (
            (base_time + timedelta(hours=4 * i)).isoformat(),
            open_base + i * 10,
            open_base + i * 10 + 100,
            open_base + i * 10 - 50,
            open_base + i * 10 + 20,
            5000 + i * 10,
        )
        for i in range(count)
    ]


# 각 테이블별 데이터 생성c
ohlcv_data = {
    "btc_1h": generate_ohlcv("2017-08-17T05:00:00Z", 40, 1000),
    "btc_4h": generate_ohlcv("2017-08-17T05:00:00Z", 40, 1200),
    "eth_1h": generate_ohlcv("2017-08-17T05:00:00Z", 40, 300),
    "eth_4h": generate_ohlcv("2017-08-17T05:00:00Z", 40, 500),
}

for table, rows in ohlcv_data.items():
    cur.executemany(
        f"""
        INSERT INTO {table} (timestamp, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s)
    """,
        rows,
    )

# 전략 실행 결과 테이블 생성
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

# 커밋 및 연결 종료
conn.commit()
cur.close()
conn.close()
