from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from get_data import get_full_ohlcv_data
from shared.symbols_intervals import SYMBOLS, INTERVALS
from filtered_func import (
    run_conditional_lateral_backtest,
    save_result_to_table,
)
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from sqlalchemy import text
from shared.connect_db import engine
import pandas as pd

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
    query = text(
        """
        SELECT entry_time, exit_time, symbol, interval
        FROM filtered
        ORDER BY entry_time
    """
    )
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)

        # timestamp → ISO 8601 문자열로 변환
        df["entry_time"] = df["entry_time"].astype(str)
        df["exit_time"] = df["exit_time"].astype(str)

        return JSONResponse(content=df.to_dict(orient="records"))

    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/filtered-candle-data")
def get_candle_data(
    entry_time: str = Query(...),
    exit_time: str = Query(...),
    symbol: str = Query(...),
    interval: str = Query(...),
):
    table_name = f"{symbol.lower()}_{interval}"
    query = text(
        f"""
        SELECT timestamp, open, high, low, close, volume
        FROM "{table_name}"
        WHERE timestamp BETWEEN :entry AND :exit
        ORDER BY timestamp
    """
    )

    with engine.connect() as conn:
        df = pd.read_sql(query, conn, params={"entry": entry_time, "exit": exit_time})

    # timestamp → 문자열
    df["timestamp"] = df["timestamp"].astype(str)

    return JSONResponse(content=df.to_dict(orient="records"))


# 캔들 데이터 호출 api
@app.get("/ohlcv/{symbol}/{interval}")
def read_ohlcv(
        symbol: str,
        interval: str,
        ):
    
    symbol = symbol.upper()
    interval = interval.lower()
    if symbol not in SYMBOLS or interval not in INTERVALS:
        raise HTTPException(
            status_code = 400,
            detail = "Invalid symbol or interval"
            )
    try:
        data = get_full_ohlcv_data(symbol, interval)
        safe_data = jsonable_encoder(data)
        return safe_data
    except Exception as e:
        print(f"Error fetching data for {symbol}_{interval}: {e}")
        raise HTTPException(
            status_code = 500,
            detail = "Internal Server Error"
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
        return {"message": "전략 실행 및 결과 저장 완료", "rows": len(result_df)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
