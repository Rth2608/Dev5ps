from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from get_data import get_ohlcv_data, get_filtered_data, get_data_from_table
from shared.symbols_intervals import SYMBOLS, INTERVALS
from filtered_func import (
    run_conditional_lateral_backtest,
    save_result_to_table,
    calculate_statics,
)
from pydantic import BaseModel
from fastapi.responses import JSONResponse
from datetime import datetime as dt
from shared.connect_db import engine
from sqlalchemy import text, select, distinct
from typing import Optional
import math

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# OHLCV 필터링 결과 조회
@app.get("/filtered-ohlcv")
def read_filtered_ohlcv():
    try:
        data = get_filtered_data()
        return jsonable_encoder(data)
    except Exception as e:
        print(repr(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")


# 캔들 구간 내 OHLCV 조회
@app.get("/filtered-candle-data")
def get_candle_data(entry_time: str, exit_time: str, symbol: str, interval: str):
    try:
        entry_dt = dt.strptime(entry_time, "%Y-%m-%d %H:%M:%S%z")
        exit_dt = dt.strptime(exit_time, "%Y-%m-%d %H:%M:%S%z")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid time format")

    if entry_dt > exit_dt:
        raise HTTPException(status_code=400, detail="Entry time is ahead of Exit time")

    if symbol.upper() not in SYMBOLS or interval.lower() not in INTERVALS:
        raise HTTPException(status_code=400, detail="Invalid symbol or interval")

    try:
        data = get_ohlcv_data(
            symbol=symbol,
            interval=interval,
            filter="timestamp",
            min_value=entry_time,
            max_value=exit_time,
        )
        return jsonable_encoder(data)
    except Exception as e:
        print(repr(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")


# 전체 OHLCV 조회
@app.get("/ohlcv/{symbol}/{interval}")
def read_ohlcv(symbol: str, interval: str) -> list:
    symbol = symbol.upper()
    interval = interval.lower()
    if symbol not in SYMBOLS or interval not in INTERVALS:
        raise HTTPException(status_code=400, detail="Invalid symbol or interval")
    try:
        data = get_ohlcv_data(symbol, interval)
        return jsonable_encoder(data)
    except Exception as e:
        print(f"Error fetching data for {symbol}_{interval}: {repr(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


# 💡 백테스트 전략 저장용 요청 모델
class StrategyRequest(BaseModel):
    symbol: str
    interval: str
    strategy_sql: str
    risk_reward_ratio: float
    start_time: Optional[str] = None
    end_time: Optional[str] = None


# 전략 저장 및 실행
@app.post("/save_strategy")
def save_strategy(req: StrategyRequest):
    try:
        result_df = run_conditional_lateral_backtest(
            symbol=req.symbol,
            interval=req.interval,
            strategy_sql=req.strategy_sql,
            risk_reward_ratio=req.risk_reward_ratio,
            start_time=req.start_time,
            end_time=req.end_time,
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
        raise HTTPException(status_code=500, detail="Error while running strategy")


# 수익률 그래프용 데이터
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
        raise HTTPException(status_code=500, detail="Internal Server Error")


# 통계 데이터 조회
@app.get("/filtered-tp-sl-rate")
def get_filtered_tp_sl_rate():
    try:
        statics = calculate_statics()
        return statics
    except Exception as e:
        print(repr(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")


# ⚡ 테이블에서 MIN/MAX timestamp 반환
@app.get("/time-range")
def get_time_range(symbol: str, interval: str):
    table_name = f"{symbol}_{interval}".lower()
    query = f"""
        SELECT MIN(timestamp) AS start_time, MAX(timestamp) AS end_time
        FROM "{table_name}"
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query)).mappings().fetchone()
        return {
            "start_time": (
                result["start_time"].isoformat() if result["start_time"] else None
            ),
            "end_time": result["end_time"].isoformat() if result["end_time"] else None,
        }
    except Exception as e:
        print(repr(e))
        raise HTTPException(status_code=500, detail="DB 조회 실패")


@app.get("/filtered-time-range")
def get_filtered_entry_time_range():
    query = """
        SELECT MIN(entry_time) AS start_time, MAX(entry_time) AS end_time
        FROM filtered
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query)).mappings().fetchone()
        return {
            "start_time": (
                result["start_time"].isoformat() if result["start_time"] else None
            ),
            "end_time": (
                result["end_time"].isoformat() if result["end_time"] else None
            ),
        }
    except Exception as e:
        print(repr(e))
        raise HTTPException(status_code=500, detail="DB 조회 실패")


@app.get("/what-indicators")
def get_distinct_indicators():
    query = "SELECT DISTINCT what_indicators FROM filtered"
    try:
        with engine.connect() as conn:
            rows = conn.execute(text(query)).fetchall()

        # 모든 지표 문자열에서 분해 → 중복 제거
        indicator_set = set()
        for row in rows:
            indicators = row[0]  # 문자열: "ema_7 and rsi and macd"
            if indicators:
                parts = [i.strip() for i in indicators.split("and")]
                indicator_set.update(parts)

        return {"indicators": sorted(indicator_set)}
    except Exception as e:
        print(repr(e))
        raise HTTPException(status_code=500, detail="보조지표 목록 조회 실패")


@app.get("/indicator-data")
def get_indicator_data(
    symbol: str, interval: str, indicator: str, entry_time: str, exit_time: str
):
    table_name = f"{symbol}_{interval}".lower()

    # ✅ 확장 매핑
    indicator_map = {
        "boll": ["boll_upper", "boll_lower", "boll_ma"],
        "rsi": ["rsi", "rsi_signal"],
        "macd": ["macd", "macd_signal"],
    }
    columns = indicator_map.get(indicator, [indicator])  # 기본 단일 컬럼

    # ✅ SQL 쿼리 동적 생성
    cols_str = ", ".join(f'"{col}"' for col in ["timestamp"] + columns)
    query = text(
        f"""
        SELECT {cols_str}
        FROM "{table_name}"
        WHERE timestamp BETWEEN :start AND :end
        ORDER BY timestamp
    """
    )

    try:
        with engine.connect() as conn:
            rows = (
                conn.execute(query, {"start": entry_time, "end": exit_time})
                .mappings()
                .all()
            )

        results = []
        seen = set()
        for row in rows:
            timestamp = row["timestamp"]
            for col in columns:
                val = row[col]
                if isinstance(val, float) and (math.isinf(val) or math.isnan(val)):
                    continue
                key = (timestamp, col)
                if key in seen:
                    continue
                seen.add(key)
                results.append(
                    {
                        "timestamp": timestamp.isoformat(),
                        "value": val,
                        "plot_area": (
                            "main"
                            if col.startswith("ema") or col.startswith("boll")
                            else "sub"
                        ),
                        "name": col,
                    }
                )

        return jsonable_encoder(results)

    except Exception as e:
        print(repr(e))
        raise HTTPException(status_code=500, detail=f"지표({indicator}) 조회 실패")


@app.get("/filtered-indicators")
def get_indicators_in_range(entry_time: str, exit_time: str):
    query = text(
        """
        SELECT DISTINCT what_indicators FROM filtered
        WHERE entry_time BETWEEN :start AND :end
    """
    )
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                query, {"start": entry_time, "end": exit_time}
            ).fetchall()

        indicator_set = set()
        for row in rows:
            val = row[0]
            if val:
                parts = [i.strip() for i in val.split("and")]
                indicator_set.update(parts)

        return {"what_indicators": " and ".join(sorted(indicator_set))}
    except Exception as e:
        print(repr(e))
        raise HTTPException(status_code=500, detail="보조지표 범위 조회 실패")
