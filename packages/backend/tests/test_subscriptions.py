import pytest
from datetime import date, timedelta
from decimal import Decimal

from app.extensions import db
from app.models import Expense, Subscription


def _create_expense(client, auth_header, amount, notes, days_ago=0):
    spent_at = (date.today() - timedelta(days=days_ago)).isoformat()
    r = client.post(
        "/expenses",
        json={
            "amount": str(amount),
            "currency": "INR",
            "notes": notes,
            "spent_at": spent_at,
            "expense_type": "debit",
            "payee": notes,
        },
        headers=auth_header,
    )
    assert r.status_code in (200, 201), f"create expense failed: {r.get_json()}"


class TestSubscriptionDetect:
    def test_detect_finds_recurring(self, client, auth_header):
        """Two expenses with same notes, similar amount, ~30 days apart -> detected."""
        _create_expense(client, auth_header, "499.00", "NETFLIX SUBSCRIPTION", days_ago=65)
        _create_expense(client, auth_header, "499.00", "NETFLIX SUBSCRIPTION", days_ago=35)
        _create_expense(client, auth_header, "500.00", "NETFLIX SUBSCRIPTION", days_ago=5)

        r = client.post("/subscriptions/detect", headers=auth_header)
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, list)
        netflix = [d for d in data if "netflix" in d["name"].lower()]
        assert len(netflix) == 1
        assert netflix[0]["frequency_days"] == 30
        assert netflix[0]["occurrences"] == 3

    def test_detect_ignores_one_off(self, client, auth_header):
        """Single expense should not be detected."""
        _create_expense(client, auth_header, "499.00", "ONE TIME PURCHASE", days_ago=10)
        r = client.post("/subscriptions/detect", headers=auth_header)
        data = r.get_json()
        assert len(data) == 0

    def test_detect_ignores_amount_variance(self, client, auth_header):
        """Large amount variance should not be detected."""
        _create_expense(client, auth_header, "100.00", "RANDOM MERCHANT", days_ago=30)
        _create_expense(client, auth_header, "500.00", "RANDOM MERCHANT", days_ago=2)
        r = client.post("/subscriptions/detect", headers=auth_header)
        data = r.get_json()
        assert len(data) == 0


class TestSubscriptionCRUD:
    def test_list_empty(self, client, auth_header):
        r = client.get("/subscriptions", headers=auth_header)
        assert r.status_code == 200
        assert r.get_json() == []

    def test_list_after_create(self, app_fixture, client, auth_header):
        sub = Subscription(
            user_id=1,
            name="Spotify",
            merchant_hint="spotify",
            typical_amount=Decimal("59.00"),
            frequency_days=30,
            currency="INR",
        )
        with app_fixture.app_context():
            db.session.add(sub)
            db.session.commit()

        r = client.get("/subscriptions", headers=auth_header)
        data = r.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Spotify"

    def test_update_subscription(self, app_fixture, client, auth_header):
        sub = Subscription(
            user_id=1, name="Old", merchant_hint="test", typical_amount=Decimal("10"), frequency_days=7
        )
        with app_fixture.app_context():
            db.session.add(sub)
            db.session.commit()
            sub_id = sub.id

        r = client.put(f"/subscriptions/{sub_id}", json={"name": "New Name", "is_confirmed": True}, headers=auth_header)
        assert r.status_code == 200
        with app_fixture.app_context():
            updated = db.session.get(Subscription, sub_id)
            assert updated.name == "New Name"
            assert updated.is_confirmed is True

    def test_delete_subscription(self, app_fixture, client, auth_header):
        sub = Subscription(
            user_id=1, name="ToDelete", merchant_hint="test", typical_amount=Decimal("10"), frequency_days=7
        )
        with app_fixture.app_context():
            db.session.add(sub)
            db.session.commit()
            sub_id = sub.id

        r = client.delete(f"/subscriptions/{sub_id}", headers=auth_header)
        assert r.status_code == 200
        with app_fixture.app_context():
            assert db.session.get(Subscription, sub_id) is None


class TestUpcoming:
    def test_upcoming_prediction(self, app_fixture, client, auth_header):
        today = date.today()
        sub = Subscription(
            user_id=1,
            name="Netflix",
            merchant_hint="netflix",
            typical_amount=Decimal("499.00"),
            frequency_days=30,
            currency="INR",
            is_active=True,
            last_seen=today - timedelta(days=28),
        )
        with app_fixture.app_context():
            db.session.add(sub)
            db.session.commit()

        r = client.get("/subscriptions/upcoming", headers=auth_header)
        assert r.status_code == 200
        data = r.get_json()
        assert len(data) == 1
        assert data[0]["name"] == "Netflix"
        assert data[0]["days_until"] == 2
