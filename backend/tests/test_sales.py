import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from backend import db
from backend.main import app
from backend.sales import match_score, offer_total


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_PATH", tmp_path / "sales.db")
    import backend.main as main
    monkeypatch.setattr(main, "seed_database", db.seed_database)


def test_matching_is_explainable_and_suppression_safe():
    with TestClient(app) as client:
        buyers = client.get("/api/sales/buyers").json()
        assert len(buyers) == 7
        result = client.get(f"/api/sales/match/product-tomato?quantity=200&delivery_date={(date.today()+timedelta(days=1)).isoformat()}").json()
        assert result["matches"]
        assert all(x["buyer"]["buyer_id"] != "buyer-suppressed" for x in result["matches"])
        assert result["classification"] == "POTENTIAL_COMMERCIAL_OPPORTUNITY"


def test_offer_draft_and_order_reserve_fulfill():
    with TestClient(app) as client:
        delivery=(date.today()+timedelta(days=1)).isoformat()
        offer=client.post("/api/sales/offers",json={"buyer_id":"buyer-grocer-greenway","proposed_delivery_date":delivery,"lines":[{"product_id":"product-tomato","lot_id":"lot-tomato-2026-01","quantity":200,"unit":"lb"}]}).json()
        assert offer["total_value"] == 650.0
        draft=client.post(f"/api/sales/offers/{offer['offer_id']}/email-draft").json()
        assert draft["sent"] is False
        exported=client.post(f"/api/sales/email-drafts/{draft['draft_id']}/export").json()
        assert exported["sent"] is False
        order=client.post(f"/api/sales/offers/{offer['offer_id']}/confirm",json={"buyer_confirmation_reference":"PO-DEMO-1","created_by":"Owner"})
        assert order.status_code == 200
        order_id=order.json()["order_id"]
        state=client.get("/api/inventory/lots/lot-tomato-2026-01").json()
        assert state["available"] == 450
        assert client.post(f"/api/sales/orders/{order_id}/fulfill",json={"buyer_confirmation_reference":"PO-DEMO-1","created_by":"Owner"}).status_code == 200
        assert client.post(f"/api/sales/orders/{order_id}/fulfill",json={"buyer_confirmation_reference":"PO-DEMO-1","created_by":"Owner"}).status_code == 409


def test_offer_cannot_overcommit_or_below_floor():
    with TestClient(app) as client:
        payload={"buyer_id":"buyer-grocer-greenway","proposed_delivery_date":(date.today()+timedelta(days=1)).isoformat(),"lines":[{"product_id":"product-tomato","lot_id":"lot-tomato-2026-01","quantity":700,"unit":"lb"}]}
        assert client.post("/api/sales/offers",json=payload).status_code == 422
        payload["lines"][0]["quantity"] = 10
        payload["lines"][0]["unit_price"] = 1
        assert client.post("/api/sales/offers",json=payload).status_code == 422


def test_sales_pure_calculations():
    assert offer_total([{"quantity":2,"unit_price":3.25}]) == 6.5
    assert match_score(preference_match=False,category_match=True,quantity=1,minimum_order=0,available=10,price=1,min_price=None,max_price=None,delivery_date=date.today(),sell_by_date=None)["eligible"] is False
