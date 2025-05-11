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

    entry_df = entry_df.iloc[:1].copy()  # 진입시점

    entry_time = entry_df["timestamp"].iloc[0]  # 진입시점의 timestamp
    stop_loss = entry_df["low"].iloc[0]  # 손절가: 진입시점의 low
    take_profit = entry_df["close"].iloc[0] + risk_reward_ratio * (
        entry_df["close"].iloc[0] - stop_loss
    )  # 익절가: 진입시점의 close + risk_reward_ratio * (진입시점의 close - 진입시점의 low)

    post_entry_df = df[df["timestamp"] > entry_time]  # 진입 이후의 데이터

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

    result = pd.DataFrame(
        [
            {
                "entry_time": entry_time,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "exit_time": exit_time,
                "exit_type": exit_type,
            }
        ]
    )

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


def apply_strategy_and_save(
    symbol: str, interval: str, strategy: str, risk_reward_ratio: float
):

    table_name = f"{symbol}_{interval}".lower()
    query = f'SELECT * FROM "{table_name}" ORDER BY timestamp;'
    df = pd.read_sql(query, engine)
    df = calculate_indicators(df)

    result_df = calculate_strategy_data(df, strategy, risk_reward_ratio)
    save_result_to_table(result_df)
