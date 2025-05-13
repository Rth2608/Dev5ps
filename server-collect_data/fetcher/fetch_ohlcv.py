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


'''
############################################################

def calculate_strategy_data(df, strategy: str, risk_reward_ratio: float):

##  이용자가 선택한 전략에 맞는 행들만 새로 구성. 
    try:
        entry_condition = eval(strategy, {}, df)
    except Exception as e:
        print(f"[전략 선택 오류] strategy: {strategy}, error: {e}")
        return pd.DataFrame()

    entry_df = df[entry_condition]
    if entry_df.empty:
        return pd.DataFrame()

    entry_df = entry_df.iloc[:1].copy() # 진입시점

    entry_time = entry_df["timestamp"].iloc[0] # 진입시점의 timestamp
    stop_loss = entry_df["low"].iloc[0]   # 손절가: 진입시점의 low
    take_profit = entry_df["close"].iloc[0] + risk_reward_ratio * (entry_df["close"].iloc[0] - stop_loss) # 익절가: 진입시점의 close + risk_reward_ratio * (진입시점의 close - 진입시점의 low)
    
    post_entry_df = df[df["timestamp"] > entry_time] # 진입 이후의 데이터

    exit_time = None
    exit_type = None

    # 손절가와 익절가에 도달한 timestamp 구하기기
    for _, row in post_entry_df.iterrows():
        if row["low"] <= stop_loss:
            exit_time = row["timestamp"]
            exit_type = "stop"
            break
        elif row["high"] >= take_profit:
            exit_time = row["timestamp"]
            exit_type = "target"
            break

    if exit_time is None:
        print("손절/익절 도달하지 않음")
        return pd.DataFrame()

    result = pd.DataFrame([{
        "entry_time": entry_time,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "exit_time": exit_time,
        "exit_type": exit_type
    }])

    return result

### 전략에 따른 손익 데이터 저장
def save_result_to_table(data: pd.DataFrame):
    if data.empty:
        print("저장할 걀과가 없습니다.")
        return

    create_table_query = """
    CREATE TABLE IF NOT EXISTS trade_results (
        entry_time TIMESTAMPTZ PRIMARY KEY,
        stop_loss DOUBLE PRECISION,
        take_profit DOUBLE PRECISION,
        exit_time TIMESTAMPTZ,
        exit_type TEXT
    );
    """
    with engine.begin() as conn:
        conn.execute(text(create_table_query))
    
    data.to_sql("trade_results", engine, if_exists="append", index=False)
    print("→ 트레이드 결과과 저장 완료")

def apply_strategy_and_save(symbol: str, interval: str, strategy: str, risk_reward_ratio: float):

    table_name = f"{symbol}_{interval}".lower()
    query = f'SELECT * FROM "{table_name}" ORDER BY timestamp;'
    df = pd.read_sql(query, engine)
    df = calculate_indicators(df)

    result_df = calculate_strategy_data(df, strategy, risk_reward_ratio)
    save_result_to_table(result_df)
   '''