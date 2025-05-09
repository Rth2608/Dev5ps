import pandas as pd
import numpy as np
from sqlalchemy import text
from shared.connect_db import engine

# symbol_interval 테이블에서 OHLCV 데이터를 조회하고 반환
def get_ohlcv_data(symbol: str, interval: str) -> list[dict | None]:

    TABLE_NAME = f"{symbol.lower()}_{interval}"
    # Query to select OHLCV
    query = text(
        'SELECT "timestamp", "open", "high", "low", "close", "volume" '\
        f"FROM {TABLE_NAME} ORDER BY timestamp"
        )

    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
    except Exception as e:
        print(f"{TABLE_NAME} DB error: {e}")
        raise e

    if df.empty:
        return []

    # inf, -inf 제거 처리
    df.replace([np.inf, -np.inf], np.nan, inplace = True)
    df = df.where(pd.notnull(df), None)

    return df.to_dict(orient = "records")
