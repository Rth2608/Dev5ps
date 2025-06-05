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
            0.0
        )
    )
    # 누적 수익률 계산
    df["cum_profit_rate"] = (1 + df["profit_rate"].fillna(0)).cumprod() - 1
    df[["profit_rate", "cum_profit_rate"]] = df[["profit_rate", "cum_profit_rate"]] * 100

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

# 통계량 계산
def calculate_statics() -> dict:
    table_name = "filtered"
    query = f'SELECT * FROM "{table_name}"'

    
    with engine.connect() as conn:
        df = pd.read_sql(text(query), conn)

        
    if df.empty:
        return {
        "total_count": 0,
        "tp_count": 0,
        "sl_count": 0,
        "tp_rate": 0.0,
        "expectancy": 0.0,
        "profit_mean": 0.0,
        "profit_std": 0.0,
        "profit_min": 0.0,
        "profit_max": 0.0,
        "loss_mean": 0.0,
        "loss_std": 0.0,
        "loss_min": 0.0,
        "loss_max": 0.0,
        "profit_rate_mean": 0.0,
        "profit_rate_std": 0.0,
        "profit_rate_min": 0.0,
        "profit_rate_max": 0.0,
        "expectancy": 0.0,
        "mdd": 0.0,
        "low_time": None,
        "high_time": None,
        "final_profit_rate": 0.0
        }

    total_count = df["result"].isin(["TP", "SL"]).sum()
    tp_count = (df["result"] == "TP").sum()
    sl_count = (df["result"] == "SL").sum()
    tp_rate = tp_count*100 / total_count if total_count > 0 else 0


    df_profit = df[df["result"] == "TP"]["profit_rate"]
    profit_mean = df_profit.mean() if not df_profit.empty else 0.0
    profit_std = df_profit.std() if len(df_profit) >= 2 else 0.0  
    profit_min = df_profit.min() if not df_profit.empty else 0.0
    profit_max = df_profit.max() if not df_profit.empty else 0.0 


    df_loss = df[df["result"] == "SL"]["profit_rate"]
    loss_mean = df_loss.mean() if not df_loss.empty else 0.0
    loss_std  = df_loss.std()  if len(df_loss) >= 2 else 0.0
    loss_min  = df_loss.min()  if not df_loss.empty else 0.0
    loss_max  = df_loss.max()  if not df_loss.empty else 0.0
    
    df_rate= df[df["result"].isin(["TP", "SL"])]
    profit_rate_mean = df_rate["profit_rate"].mean() if not df_rate.empty else 0.0
    profit_rate_std = df_rate["profit_rate"].std() if len(df_rate) >= 2 else 0.0
    profit_rate_min = df_rate["profit_rate"].min() if not df_rate.empty else 0.0
    profit_rate_max = df_rate["profit_rate"].max() if not df_rate.empty else 0.0
    
    expectancy = (tp_count * profit_mean + sl_count * loss_mean) / total_count if total_count > 0 else 0.0

    cum_max = df["cum_profit_rate"].cummax()
    drawdown = df["cum_profit_rate"] - cum_max
    low_idx = drawdown.idxmin()
    high_idx = df.loc[:low_idx, "cum_profit_rate"].idxmax()
    low_price = df.loc[low_idx, "cum_profit_rate"]*0.01+1
    high_price = df.loc[high_idx, "cum_profit_rate"]*0.01+1
    mdd = (low_price - high_price)*100 / high_price if high_price != 0 else -100.0
    low_time = df.loc[low_idx, "entry_time"]
    high_time = df.loc[high_idx, "entry_time"]
    low_time_str = low_time.date().isoformat() if isinstance(low_time, pd.Timestamp) else None
    high_time_str = high_time.date().isoformat() if isinstance(high_time, pd.Timestamp) else None

    final_profit_rate = df["cum_profit_rate"].iloc[-1]

    return {
    "total_count": int(total_count),
    "tp_count": int(tp_count),
    "sl_count": int(sl_count),
    "tp_rate": float(tp_rate),
    "profit_mean": float(profit_mean),
    "profit_std": float(profit_std),
    "profit_min": float(profit_min),
    "profit_max": float(profit_max),
    "loss_mean": float(loss_mean),
    "loss_std": float(loss_std),
    "loss_min": float(loss_min),
    "loss_max": float(loss_max),
    "profit_rate_mean": float(profit_rate_mean),
    "profit_rate_std": float(profit_rate_std),
    "profit_rate_min": float(profit_rate_min),
    "profit_rate_max": float(profit_rate_max),
    "expectancy": float(expectancy),
    "mdd": float(mdd),
    "low_time": low_time_str,    
    "high_time": high_time_str,
    "final_profit_rate": final_profit_rate
}
