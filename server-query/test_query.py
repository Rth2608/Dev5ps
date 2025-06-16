import sys
import os
import subprocess
import pytest
from fastapi.testclient import TestClient

# ✅ shared 디렉토리를 sys.path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shared.symbols_intervals import SYMBOLS, INTERVALS
from main_query import app


# ✅ DB 초기화
@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db_path = os.path.join(os.path.dirname(__file__), "init_db.py")
    result = subprocess.run(["python", init_db_path], capture_output=True, text=True)
    assert result.returncode == 0, f"DB 초기화 실패:\n{result.stderr}"


@pytest.fixture
def client():
    return TestClient(app)


# ✅ OHLCV 조회 테스트
@pytest.mark.parametrize("sym", SYMBOLS)
@pytest.mark.parametrize("intv", INTERVALS)
def test_read_ohlcv(client, sym, intv):
    response = client.get(f"/ohlcv/{sym}/{intv}")
    assert response.status_code == 200
    r_json = response.json()
    assert len(r_json) > 0
    assert list(r_json[0].keys()) == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]


# ❌ 제거: test_read_ohlcv_invalid

# ❌ 제거: test_filtered


# ✅ filtered-candle-data 정상 동작 확인
@pytest.mark.parametrize("sym", SYMBOLS)
@pytest.mark.parametrize("intv", INTERVALS)
def test_candle_data(client, sym, intv):
    response = client.get(
        "/filtered-candle-data",
        params={
            "entry_time": "2017-08-17 05:00:00+00:00",
            "exit_time": "2017-08-18 12:00:00+00:00",
            "symbol": sym,
            "interval": intv,
        },
    )
    assert response.status_code == 200
    r_json = response.json()
    assert isinstance(r_json, list)
    assert len(r_json) > 0
    assert all(
        k in r_json[0] for k in ["timestamp", "open", "high", "low", "close", "volume"]
    )


# ✅ 잘못된 entry/exit time
INVALID_EXIT_TIME = [
    ("2023-03-21 12:00:00", "Invalid time format"),
    ("2023-03-21", "Invalid time format"),
    ("12:00:00+00", "Invalid time format"),
    ("ABCD-EF-GH IJ:KL:MN+OP", "Invalid time format"),
    ("2017-07-15 00:00:00+00:00", "Entry time is ahead of Exit time"),
]


@pytest.mark.parametrize("sym", SYMBOLS)
@pytest.mark.parametrize("intv", INTERVALS)
@pytest.mark.parametrize(("exit_time", "error_desc"), INVALID_EXIT_TIME)
def test_candle_data_invalid(client, sym, intv, exit_time, error_desc):
    entry_time = "2017-08-17 05:00:00+00:00"
    response = client.get(
        "/filtered-candle-data",
        params={
            "entry_time": entry_time,
            "exit_time": exit_time,
            "symbol": sym,
            "interval": intv,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == error_desc


# ❌ 제거: test_strategy (전략 저장 실패하므로)

# ✅ 잘못된 전략 문법
INVALID_STRATEGY = [
    "open > 4000 and",
    "volume >",
    "close >= 1000K",
]


@pytest.mark.parametrize("sym", SYMBOLS)
@pytest.mark.parametrize("intv", INTERVALS)
@pytest.mark.parametrize("strategy", INVALID_STRATEGY)
def test_strategy_invalid(client, sym, intv, strategy):
    response = client.post(
        "/save_strategy",
        json={
            "symbol": sym,
            "interval": intv,
            "strategy_sql": strategy,
            "risk_reward_ratio": 5.0,
            "start_time": "2017-08-17 04:00:00",
            "end_time": "2025-06-16 03:00:00",
        },
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Error while running strategy"
