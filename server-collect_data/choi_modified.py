import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from shared.connect_db import engine
import pandas as pd
from sqlalchemy import text
from indicators.calculate import calculate_indicators
from sqlalchemy import text
import pandas as pd

start_time = time.time()


def run_conditional_lateral_backtest(
    symbol: str, interval: str, strategy_sql: str, risk_reward_ratio: float
) -> pd.DataFrame:
    table_name = f"{symbol}_{interval}".lower()

    query = f"""
    SELECT
        e.timestamp AS entry_time,
        e.close AS entry_price,
        e.low AS stop_loss,
        e.close + (e.close - e.low) * :rr_ratio AS take_profit,
        x.timestamp AS exit_time,
        CASE
            WHEN x.timestamp IS NULL THEN 'OPEN'
            WHEN x.low <= e.low THEN 'SL'
            WHEN x.high >= (e.close + (e.close - e.low) * :rr_ratio) THEN 'TP'
            ELSE 'UNKNOWN'
        END AS result
    FROM (
        SELECT timestamp, close, low
        FROM "{table_name}"
        WHERE {strategy_sql}
    ) e
    LEFT JOIN LATERAL (
        SELECT timestamp, low, high
        FROM "{table_name}" x
        WHERE x.timestamp > e.timestamp
          AND (
              x.low <= e.low
              OR x.high >= (e.close + (e.close - e.low) * :rr_ratio)
          )
        ORDER BY timestamp
        LIMIT 1
    ) x ON TRUE;
    """

    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn, params={"rr_ratio": risk_reward_ratio})

    return df


def save_result_to_table(data: pd.DataFrame):
    if data.empty:
        print("저장할 결과가 없습니다.")
        return

    table_name = "trade_results_modified"
    # entry_price도 테이블에 추가함
    create_table_query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        entry_time TIMESTAMPTZ PRIMARY KEY,
        entry_price DOUBLE PRECISION,
        stop_loss DOUBLE PRECISION,
        take_profit DOUBLE PRECISION,
        exit_time TIMESTAMPTZ,
        result TEXT
    );
    """

    check_table_query = f"""
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = '{table_name}'
    );
    """

    with engine.begin() as conn:
        conn.execute(text(create_table_query))
        result = conn.execute(text(check_table_query)).scalar()
        if result:
            conn.execute(text(f"DELETE FROM {table_name}"))

    data.to_sql(table_name, engine, if_exists="append", index=False)
    print(f"→ '{table_name}' 테이블에 데이터 저장 완료 (기존 데이터는 초기화)")


# 구현시 strategy는 프론트엔드에서 UI로 입력받은 내용을 바탕으로 query로 변경 후 넣을 예정
strategy = "rsi > 30"

# "btc", "1h"는 테스트용으로 하드코딩 하였지만 구현시 프론트엔드에서 UI로 입력받는 symbols_intervals.py의 symbols와 intervals를 값으로 할 예정
# risk_reward_ratio도 테스트를 위해 2.0으로 하드코딩 해놓았지만 구현시 프론트엔드에서 UI로 입력받을 실수 값임
df_result = run_conditional_lateral_backtest(
    "btc", "1h", strategy_sql=strategy, risk_reward_ratio=2.0
)
save_result_to_table(df_result)

# O(N log N)으로 기존 for문으로 할 때의 O(N²)보다 빠름
end_time = time.time()
elapsed = end_time - start_time
print(f"총 소요 시간: {elapsed:.2f}초")
