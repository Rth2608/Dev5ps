import pandas as pd
import time
from sqlalchemy import text
from fetcher.binance_client import fetch_from_binance, get_latest_timestamp, get_binance_start_time
from shared.connect_db import engine
from datetime import datetime, timezone, timedelta
from indicators.calculate import calculate_indicators

KST = timezone(timedelta(hours=9))

def to_kst(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(KST)

def table_exists(symbol: str, interval: str) -> bool:
    table_name = f"{symbol}_{interval}".lower()
    query = text("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = :table_name
        );
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"table_name": table_name})
        return result.scalar()

def create_dynamic_table(symbol: str, interval: str):
    table_name = f"{symbol}_{interval}".lower()
    query = f"""
        CREATE TABLE IF NOT EXISTS "{table_name}" (
            timestamp TIMESTAMPTZ PRIMARY KEY,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            rsi REAL,
            rsi_signal REAL,
            ema_7 REAL,
            ema_25 REAL,
            ema_99 REAL,
            macd REAL,
            macd_signal REAL,
            boll_ma REAL,
            boll_upper REAL,
            boll_lower REAL,
            volume_ma_20 REAL
        );
    """
    with engine.begin() as conn:
        conn.execute(text(query))
        print(f"`{table_name}`이 생성되었습니다.")
    time.sleep(1.0)

def save_to_db(symbol: str, interval: str):
    table_name = f"{symbol}_{interval}".lower()

    if not table_exists(symbol, interval):
        create_dynamic_table(symbol, interval)
        assert table_exists(symbol, interval), f"테이블 생성 실패: {table_name}"
        start_time = get_binance_start_time(symbol, interval)
        old_df = pd.DataFrame()
    else:
        start_time = get_latest_timestamp(symbol, interval)
        query = f'SELECT * FROM "{table_name}" ORDER BY timestamp DESC LIMIT 100;'
        old_df = pd.read_sql(query, engine).sort_values("timestamp")

    new_df = fetch_from_binance(symbol, interval, limit=1000, start_time=start_time)
    combined_df = pd.concat([old_df, new_df]).drop_duplicates(subset="timestamp").reset_index(drop=True)
    final_df = calculate_indicators(combined_df)
    to_save_df = final_df[final_df["timestamp"] >= (start_time or pd.Timestamp.min)]

    insert_sql = text(f"""
        INSERT INTO "{table_name}" (
            timestamp, open, high, low, close, volume,
            rsi, rsi_signal,
            ema_7, ema_25, ema_99,
            macd, macd_signal,
            boll_ma, boll_upper, boll_lower,
            volume_ma_20
        )
        VALUES (
            :timestamp, :open, :high, :low, :close, :volume,
            :rsi, :rsi_signal,
            :ema_7, :ema_25, :ema_99,
            :macd, :macd_signal,
            :boll_ma, :boll_upper, :boll_lower,
            :volume_ma_20
        )
        ON CONFLICT (timestamp) DO UPDATE SET
            rsi = EXCLUDED.rsi,
            rsi_signal = EXCLUDED.rsi_signal,
            ema_7 = EXCLUDED.ema_7,
            ema_25 = EXCLUDED.ema_25,
            ema_99 = EXCLUDED.ema_99,
            macd = EXCLUDED.macd,
            macd_signal = EXCLUDED.macd_signal,
            boll_ma = EXCLUDED.boll_ma,
            boll_upper = EXCLUDED.boll_upper,
            boll_lower = EXCLUDED.boll_lower,
            volume_ma_20 = EXCLUDED.volume_ma_20;
    """)

    MAX_RETRIES = 3
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with engine.begin() as conn:
                for _, row in to_save_df.iterrows():
                    conn.execute(insert_sql, row.to_dict())
            break
        except Exception as e:
            print(f"[경고] INSERT 실패 (시도 {attempt}/{MAX_RETRIES}): {e}")
            if "does not exist" in str(e):
                print("테이블 재생성 및 재시도...")
                create_dynamic_table(symbol, interval)
            else:
                raise