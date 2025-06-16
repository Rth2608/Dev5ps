import pandas as pd
import numpy as np
from sqlalchemy import text
from shared.connect_db import engine


def wrap_strs_with_quote(x: str | list[str]) -> str:
    if isinstance(x, str):
        return f'"{x}"'
    return ", ".join([f'"{col}"' for col in x])


def get_data_from_table(
    table_name: str,
    return_type: str | list[str],
    order_by: str | None = None,
    filter: str | None = None,  # Optional, single key
    min_value=None,
    max_value=None,
) -> list:

    COLS = wrap_strs_with_quote(return_type)
    params = {}
    where_clause = ""
    # empty df
    df = pd.DataFrame()

    if order_by is None:
        # set default sort by first col of return type
        order_by = return_type if isinstance(return_type, str) else return_type[0]

    if filter is not None:
        # filter (WHERE) is set
        where_clause = f"WHERE {filter} "
        if min_value is not None:
            params["min"] = min_value
        if max_value is not None:
            params["max"] = max_value

        match len(params):
            case 2:
                # use BETWEEN
                where_clause += "BETWEEN :min AND :max"
            case 1:
                if min_value is not None:
                    where_clause += ">= :min"
                else:  # max_value
                    where_clause += "<= :max"
            case _:
                raise ValueError("WHERE field missing value(s)")

    query = text(
        f'SELECT {COLS} FROM "{table_name}" {where_clause} ORDER BY "{order_by}"'
    )
    try:
        with engine.connect() as conn:
            df = pd.read_sql(
                query,
                conn,
                params=params,
            )
    except Exception as e:
        print(e)

    if df.empty:
        return []

    # inf, -inf 제거 처리
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df = df.where(pd.notnull(df), None)

    # omit row with NULL value
    df = df.dropna(how="any", axis=0)

    # convert timestamptz to str (ISO 8601)
    for col in df.columns:
        if isinstance(df[col].dtype, pd.DatetimeTZDtype):
            # detects pandas datetime
            df[col] = df[col].astype(str)

    return df.to_dict(orient="records")


def get_ohlcv_data(
    symbol: str,
    interval: str,
    filter=None,
    min_value=None,
    max_value=None,
) -> list:

    table_name = f"{symbol}_{interval}".lower()
    return_type = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    return get_data_from_table(
        table_name=table_name,
        return_type=return_type,
        filter=filter,
        min_value=min_value,
        max_value=max_value,
    )


def get_filtered_data() -> list:
    table_name = "filtered"
    return_type = [
        "entry_time",
        "exit_time",
        "symbol",
        "interval",
        "entry_price",
        "stop_loss",
        "take_profit",
    ]
    return get_data_from_table(
        table_name=table_name,
        return_type=return_type,
    )
