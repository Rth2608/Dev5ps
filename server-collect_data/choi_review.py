import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.connect_db import engine
import pandas as pd
from sqlalchemy import text
from indicators.calculate import calculate_indicators

start_time = time.time()


# 기존 for문으로 전체 반복시 O(N²)의 시간이 필요하므로 사실상 실사용 불가한 수준임
def calculate_strategy_data(df, strategy: str, risk_reward_ratio: float):

    try:
        entry_condition = eval(strategy, {}, df)
    except Exception as e:
        print(f"[전략 선택 오류] strategy: {strategy}, error: {e}")
        return pd.DataFrame()

    entry_df = df[entry_condition]
    if entry_df.empty:
        return pd.DataFrame()

    results = []

    for _, entry_row in entry_df.iterrows():
        entry_time = entry_row["timestamp"]
        close_price = entry_row["close"]
        stop_loss = entry_row["low"]
        take_profit = close_price + risk_reward_ratio * (close_price - stop_loss)

        post_entry_df = df[df["timestamp"] > entry_time]

        exit_time = None
        # 포지션이 종료되지 않은 경우도 테이블에 open으로 표시할 예정 (exit_time 은 null로 저장)
        exit_type = "open"

        for _, row in post_entry_df.iterrows():
            if row["low"] <= stop_loss:
                exit_time = row["timestamp"]
                exit_type = "stop"
                break
            elif row["high"] >= take_profit:
                exit_time = row["timestamp"]
                exit_type = "target"
                break

        results.append(
            {
                "entry_time": entry_time,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "exit_time": exit_time,
                "exit_type": exit_type,
            }
        )

    return pd.DataFrame(results)


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
    check_table_query = f"""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name =  'trade_results'
    );
    """
    with engine.begin() as conn:
        conn.execute(text(create_table_query))
        result = conn.execute(text(check_table_query)).scalar()
        if result:
            conn.execute(text(f"DELETE FROM trade_results"))

    data.to_sql("trade_results", engine, if_exists="append", index=False)
    print(f"→ " "trade_results" " 테이블에 데이터 저장 완료 (기존 데이터는 초기화)")


def apply_strategy_and_save(
    symbol: str, interval: str, strategy: str, risk_reward_ratio: float
):

    table_name = f"{symbol}_{interval}".lower()
    query = f'SELECT * FROM "{table_name}" ORDER BY timestamp;'
    df = pd.read_sql(query, engine)
    df = calculate_indicators(df)

    result_df = calculate_strategy_data(df, strategy, risk_reward_ratio)
    save_result_to_table(result_df)


# 구현시 strategy는 프론트엔드에서 UI로 입력받은 내용을 바탕으로 query로 변경 후 넣을 예정
# "btc", "1h"는 테스트용으로 하드코딩 하였지만 구현시 프론트엔드에서 UI로 입력받는 symbols_intervals.py의 symbols와 intervals를 값으로 할 예정
# risk_reward_ratio도 테스트를 위해 2.0으로 하드코딩 해놓았지만 구현시 프론트엔드에서 UI로 입력받을 실수 값임
apply_strategy_and_save(
    symbol="btc",
    interval="1h",
    strategy="volume > 30",
    risk_reward_ratio=2.0,
)

# for문으로 할 때 O(N²) : 느림 ( choi_modified.py로 더 빠르게 구현함 )
end_time = time.time()
elapsed = end_time - start_time
print(f"총 소요 시간: {elapsed:.2f}초")
