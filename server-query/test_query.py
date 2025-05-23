import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest
from fastapi.testclient import TestClient
from shared.symbols_intervals import SYMBOLS, INTERVALS
from main_query import app


@pytest.fixture
def client(autouse=True):
    return TestClient(app)


@pytest.mark.parametrize("sym", SYMBOLS)
@pytest.mark.parametrize("intv", INTERVALS)
def test_read_ohlcv(client, sym, intv):
    # by API
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


def test_read_ohlcv_invalid(client):
    # Test XRP - not in SYMBOLS
    response = client.get(f"/ohlcv/XRP/1h")
    assert response.status_code == 400
    # Test 2h - not in INTERVAL
    response = client.get(f"/ohlcv/BTC/2h")
    assert response.status_code == 400


def test_filtered(client):
    response = client.get("/filtered-ohlcv")
    assert response.status_code == 200
    r_json = response.json()
    assert list(r_json[0].keys()) == ["entry_time", "exit_time", "symbol", "interval"]


@pytest.mark.parametrize("sym", SYMBOLS)
@pytest.mark.parametrize("intv", INTERVALS)
def test_candle_data(client, sym, intv):
    response = client.get(
        "/filtered-candle-data",
        params={
            "entry_time": "2020-01-23 00:00:00+00:00",
            "exit_time": "2023-03-21 12:34:56+00:00",
            "symbol": sym,
            "interval": intv,
        },
    )
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


INVALID_EXIT_TIME = [
    ("2023-03-21 12:34:56", "Invalid time format"),  # No TZ
    ("2023-03-21", "Invalid time format"),  # No Time
    ("12:34:56+00", "Invalid time format"),  # No Date
    ("ABCD-EF-GH IJ:KL:MN+OP", "Invalid time format"),  # random literals
    (
        "2020-01-01 00:00:00+00:00",
        "Entry time is ahead of Exit time",
    ),  # Ahead of entry time
]


@pytest.mark.parametrize("sym", SYMBOLS)
@pytest.mark.parametrize("intv", INTERVALS)
@pytest.mark.parametrize(("exit_time", "error_desc"), INVALID_EXIT_TIME)
def test_candle_data_invalid(client, sym, intv, exit_time, error_desc):
    entry_time = "2020-01-23 00:00:00+00:00"
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
    r_json = response.json()
    assert r_json["detail"] == error_desc


VALID_STRATEGY = [
    "open > 4000 and close > 4500",
    "volume > 100000",
    "close >= high",
]


@pytest.mark.parametrize("sym", SYMBOLS)
@pytest.mark.parametrize("intv", INTERVALS)
@pytest.mark.parametrize("strategy", VALID_STRATEGY)
def test_strategy(client, sym, intv, strategy):

    response = client.post(
        "/save_strategy",
        json={
            "symbol": sym,
            "interval": intv,
            "strategy_sql": strategy,
            "risk_reward_ratio": 5.0,  # random float
        },
    )
    assert response.status_code == 200
    r_json = response.json()
    assert r_json["message"] == "전략 실행 및 결과 저장 완료"
    assert r_json["rows"] > 0


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
            "risk_reward_ratio": 5.0,  # random float
        },
    )
    assert response.status_code == 500
    r_json = response.json()
    assert r_json["detail"] == "Error while running strategy"
