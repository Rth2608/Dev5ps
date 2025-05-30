import psycopg2

# GitHub Actions 환경에 맞는 DB 접속 설정
conn = psycopg2.connect(
    host="localhost", port="5432", dbname="test", user="test", password="test"
)

cur = conn.cursor()

# ⚙️ ohlcv 테이블 초기화
cur.execute("DROP TABLE IF EXISTS ohlcv")
cur.execute(
    """
CREATE TABLE ohlcv (
    timestamp TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC
)
"""
)

# ⚙️ 전략 저장용 테이블 초기화
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

# ✅ ohlcv 테이블에 샘플 데이터 삽입
cur.executemany(
    """
INSERT INTO ohlcv (timestamp, symbol, interval, open, high, low, close, volume)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
""",
    [
        ("2017-08-17 05:00:00+00", "BTC", "4h", 1000, 1500, 900, 1200, 5000),
        ("2017-08-18 12:00:00+00", "BTC", "4h", 1200, 1600, 1100, 1300, 6000),
        ("2017-08-17 05:00:00+00", "ETH", "4h", 300, 500, 250, 400, 3000),
    ],
)

conn.commit()
cur.close()
conn.close()
