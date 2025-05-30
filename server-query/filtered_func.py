import time
from shared.connect_db import engine
import pandas as pd
from sqlalchemy import text
import pandas as pd
import numpy as np


def run_conditional_lateral_backtest(
    symbol: str, interval: str, strategy_sql: str, risk_reward_ratio: float
) -> pd.DataFrame:
    table_name = f"{symbol}_{interval}".lower()

    # what_indicators 열에 해당하는 string 추출
    indicators = [
        "rsi",
        "rsi_signal",
        "ema_7",
        "ema_25",
        "ema_99",
        "macd",
        "macd_signal",
        "boll_ma",
        "boll_upper",
        "boll_lower",
        "volume_ma_20",
        ]
    is_indicators = [indicator for indicator in indicators if indicator in strategy_sql]
    if not is_indicators:
        what_indicators_str = "None"
    else:
        what_indicators_str = ' and '.join(sorted(is_indicators))


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
        END AS result,
        :symbol AS symbol, 
        :interval AS interval, 
        '{strategy_sql}' AS strategy,
        '{what_indicators_str}' AS what_indicators
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
        df = pd.read_sql(text(query), conn, params={"rr_ratio": risk_reward_ratio, "symbol": symbol, "interval": interval})

    # 수익률 계산
    non_zero = df["entry_price"] != 0
    df["profit_rate"] = np.where(
        (df["result"] == "TP") & non_zero,
        (df["take_profit"] - df["entry_price"]) / df["entry_price"],
        np.where(
            (df["result"] == "SL") & non_zero,
            (df["stop_loss"] - df["entry_price"]) / df["entry_price"],
            np.nan
        )
    )
    # 누적 수익률 계산
    df["cum_profit_rate"] = df["profit_rate"].fillna(0).cumsum()

    return df


def save_result_to_table(data: pd.DataFrame):
    if data.empty:
        print("저장할 결과가 없습니다.")
        return

    table_name = "filtered"
    # entry_price도 테이블에 추가함
    create_table_query = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
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

# 승률 계산 함수
# total_count : SL + TP의 총 개수, tp_count : TP의 개수, sl_count : SL의 개수, tp_rate : TP의 비율
def calculate_rate(df: pd.DataFrame) -> dict:
    total_count = df["result"].isin(["TP", "SL"]).sum()
    tp_count = (df["result"] == "TP").sum()
    tp_rate = tp_count / total_count if total_count > 0 else 0

    return {
        "total_count": total_count,
        "tp_count": tp_count,
        "sl_count": total_count - tp_count,
        "tp_rate": tp_rate,
    }
