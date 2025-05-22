import pandas as pd
import numpy as np
from sqlalchemy import text
from shared.connect_db import engine


def get_ohlcv_data(
    symbol: str,
    interval: str,
    # filter: str = None,
    # min_value: float = None,
    # max_value: float = None,
    return_type: str | list[str] = None,
) -> list:

    TABLE_NAME = f"{symbol.lower()}_{interval}"

    if return_type is None:
        # Default return type
        return_type = ["timestamp", "open", "high", "low", "close", "volume"]
    elif isinstance(return_type, str):
        # Wrap to list
        return_type = [return_type]

    # Wrap with double quotes
    select_clause = "SELECT " + ", ".join([f'"{col}"' for col in return_type])

    params = {}
    where_clause_list = []
    where_clause = ""
    """
    if filter is not None:
        if min_value is not None:
            where_clause_list.append(f'"{filter}" >= :min_value')
            params["min_value"] = min_value
        if max_value is not None:
            where_clause_list.append(f'"{filter}" <= :max_value')
            params["max_value"] = max_value
        where_clause = "WHERE " + " AND ".join(where_clause_list)
    """
    try:
        with engine.connect() as conn:
            query = text(
                f"{select_clause} FROM {TABLE_NAME} {where_clause} ORDER BY timestamp"
            )
            df = pd.read_sql(query, conn, params=params)

    except Exception as e:
        print(f"{TABLE_NAME} DB error: {e}")
        raise e

    if df.empty:
        return []

    # inf, -inf 제거 처리
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df = df.where(pd.notnull(df), None)

    return df.to_dict(orient="records")


def get_full_ohlcv_data(symbol: str, interval: str) -> list:
    return get_ohlcv_data(symbol, interval)
