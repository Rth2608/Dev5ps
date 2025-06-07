from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from get_data import get_ohlcv_data, get_filtered_data, get_data_from_table
from shared.symbols_intervals import SYMBOLS, INTERVALS
from filtered_func import (
    run_conditional_lateral_backtest,
    save_result_to_table,
    calculate_statics
)
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from datetime import datetime as dt

app = FastAPI()

# streamlit에서 api호출 가능하도록 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/filtered-ohlcv")
def read_filtered_ohlcv():
    try:
        data = get_filtered_data()
        safe_data = jsonable_encoder(data)
        return safe_data

    except Exception as e:
        print(repr(e))
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )


@app.get("/filtered-candle-data")
def get_candle_data(
    entry_time: str,
    exit_time: str,
    symbol: str,
    interval: str,
):
    entry_dt = None
    exit_dt = None
    try:
        # 2020-01-23 00:00:00+00
        entry_dt = dt.strptime(entry_time, "%Y-%m-%d %H:%M:%S%z")
        exit_dt = dt.strptime(exit_time, "%Y-%m-%d %H:%M:%S%z")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid time format",
        )

    if entry_dt > exit_dt:
        raise HTTPException(
            status_code=400,
            detail="Entry time is ahead of Exit time",
        )

    if symbol.upper() not in SYMBOLS or interval.lower() not in INTERVALS:
        raise HTTPException(
            status_code=400,
            detail="Invalid symbol or interval",
        )
    try:
        data = get_ohlcv_data(
            symbol=symbol,
            interval=interval,
            filter="timestamp",
            min_value=entry_time,
            max_value=exit_time,
        )
        safe_data = jsonable_encoder(data)
        return safe_data
    except Exception as e:
        print(repr(e))
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )


# 캔들 데이터 호출 api
@app.get("/ohlcv/{symbol}/{interval}")
def read_ohlcv(
    symbol: str,
    interval: str,
) -> list:

    symbol = symbol.upper()
    interval = interval.lower()
    if symbol not in SYMBOLS or interval not in INTERVALS:
        raise HTTPException(
            status_code=400,
            detail="Invalid symbol or interval",
        )
    try:
        data = get_ohlcv_data(symbol, interval)
        safe_data = jsonable_encoder(data)
        return safe_data
    except Exception as e:
        print(f"Error fetching data for {symbol}_{interval}: {repr(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )


class StrategyRequest(BaseModel):
    symbol: str
    interval: str
    strategy_sql: str
    risk_reward_ratio: float


@app.post("/save_strategy")
def save_strategy(req: StrategyRequest):
    try:
        result_df = run_conditional_lateral_backtest(
            symbol=req.symbol,
            interval=req.interval,
            strategy_sql=req.strategy_sql,
            risk_reward_ratio=req.risk_reward_ratio,
        )
        save_result_to_table(result_df)
        if result_df.empty:
            return {"message": "전략 실행, 결과 없음"}
        return {
            "message": "전략 실행 및 결과 저장 완료",
            "rows": len(result_df),
            "total_profit_rate": result_df["cum_profit_rate"].iloc[-1],
        }
    except Exception as e:
        print(repr(e))
        raise HTTPException(
            status_code=500,
            detail="Error while running strategy",
        )


@app.get("/filtered-profit-rate")
def get_filtered_profit_rate():
    try:
        data = get_data_from_table(
            table_name="filtered",
            return_type=["entry_time", "profit_rate", "cum_profit_rate"],
        )
        return jsonable_encoder(data)
    except Exception as e:
        print(repr(e))
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )


@app.get("/filtered-tp-sl-rate")
def get_filtered_tp_sl_rate():
    try:
        statics = calculate_statics()
        return statics
    except Exception as e:
        print(repr(e))
        raise HTTPException(
            status_code=500,
            detail="Internal Server Error",
        )
