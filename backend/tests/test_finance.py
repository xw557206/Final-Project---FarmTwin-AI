import pytest
from fastapi.testclient import TestClient

from backend.finance import break_even_price, break_even_quantity, contribution_margin, depreciation, gross_profit, irr, npv, operating_profit, payback_period, production_cost, unit_cost
from backend import db
from backend.main import app


def test_known_finance_calculations():
    assert production_cost(100, 50, 25, 25) == 200
    assert unit_cost(200, 100) == 2
    assert contribution_margin(500, 300)["contribution_margin"] == 200
    assert float(contribution_margin(500, 300)["contribution_margin_pct"]) == pytest.approx(0.4)
    assert gross_profit(500, 200)["gross_profit"] == 300
    assert float(gross_profit(500, 200)["gross_margin_pct"]) == pytest.approx(0.6)
    assert operating_profit(500, 200, 100)["operating_profit"] == 200
    assert break_even_quantity(1000, 10, 5) == 200
    assert break_even_price(1000, 200, 5) == 10
    assert depreciation(10000, 1000, 9) == pytest.approx(1000)


def test_finance_edge_cases_and_capital_metrics():
    with pytest.raises(ValueError): unit_cost(100, 0)
    with pytest.raises(ValueError): break_even_quantity(100, 4, 4)
    assert float(npv(1000, [300, 400, 500], 0.1)) == pytest.approx(-21.04, abs=0.01)
    assert float(irr([-1000, 600, 600])) == pytest.approx(0.1307, abs=0.001)
    assert float(payback_period([-1000, 600, 600])) == pytest.approx(1.67, abs=0.01)
    assert irr([-100, 200, -100]) is None


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "finance.db")
    import backend.main as main
    monkeypatch.setattr(main, "seed_database", db.seed_database)


def test_finance_api_is_database_backed_and_investment_is_hypothetical():
    with TestClient(app) as client:
        summary = client.get("/api/finance/summary").json()
        assert summary["data_status"] == "SYNTHETIC"
        assert summary["revenue"] > 0
        assert summary["cash_inflows"] != summary["operating_profit"]
        investment = client.post("/api/finance/investments/evaluate", json={"project_name":"Test greenhouse","initial_investment":10000,"lifespan_years":3,"annual_incremental_revenue":6000,"annual_operating_costs":1500,"annual_maintenance":300,"working_capital":500,"working_capital_recovery":500,"residual_value":1000,"discount_rate":0.1,"tax_rate":0}).json()
        assert investment["status"] == "HYPOTHETICAL"
        assert investment["npv"] is not None
        assert client.get("/api/finance/transactions").status_code == 200
