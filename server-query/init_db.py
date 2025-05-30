import psycopg2

# GitHub Actions 환경에 맞는 DB 접속 설정
conn = psycopg2.connect(
    host="localhost", port="5432", dbname="test", user="test", password="test"
)

cur = conn.cursor()

# 테이블 이름 목록
tables = ["btc_1h", "btc_4h", "eth_1h", "eth_4h"]

# 🔄 개별 심볼+interval 테이블 생성 및 초기화
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

# 🧪 샘플 데이터 삽입
ohlcv_data = {
    "btc_1h": [("2017-08-17 05:00:00+00", 1000, 1100, 900, 1050, 5000)],
    "btc_4h": [("2017-08-17 05:00:00+00", 1000, 1500, 900, 1200, 5000)],
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

# ⚙️ 전략 저장용 테이블 생성
cur.execute("DROP TABLE IF EXISTS strategy")
cur.execute(
    """
    CREATE TABLE strategy (
        id SERIAL PRIMARY KEY,
        symbol TEXT NOT NULL,
        interval TEXT NOT NULL,
        strategy_sql TEXT NOT NULL,
        risk_reward_ratio FLOAT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
"""
)

# ⚙️ 전략 실행 결과 저장용 filtered 테이블 생성 (🛠️ 필수 컬럼 포함)
cur.execute("DROP TABLE IF EXISTS filtered")
cur.execute(
    """
    CREATE TABLE filtered (
        entry_time TIMESTAMPTZ,
        entry_price NUMERIC,
        stop_loss NUMERIC,
        take_profit NUMERIC,
        exit_time TIMESTAMPTZ,
        symbol TEXT,
        interval TEXT
    )
"""
)

conn.commit()
cur.close()
conn.close()
