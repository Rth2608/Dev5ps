from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from get_data import get_full_ohlcv_data
from shared.symbols_intervals import SYMBOLS, INTERVALS

app = FastAPI()

# streamlit에서 api호출 가능하도록 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
