"""Tests for alert delivery status recording."""

from src.alerts.alert_storage import AlertStorage
from src.alerts.delivery_status import latest_deliveries_by_channel, record_notifier_delivery


class EmailNotifier:
    pass


class WebhookNotifier:
    pass


class LogNotifier:
    pass


def test_record_delivery_and_latest_by_channel(tmp_path):
    storage = AlertStorage(data_dir=tmp_path)

    record_notifier_delivery(
        storage, alert_id="a1", notifier=EmailNotifier(), success=True, test=True
    )
    record_notifier_delivery(
        storage, alert_id="a1", notifier=WebhookNotifier(), success=False, test=True
    )
    record_notifier_delivery(
        storage, alert_id="a1", notifier=EmailNotifier(), success=True, test=False
    )

    latest = latest_deliveries_by_channel(storage)
    assert len(latest) == 2
    by_channel = {item["channel"]: item for item in latest}
    assert by_channel["email"]["success"] is True
    assert by_channel["email"]["test"] is False
    assert by_channel["webhook"]["success"] is False


def test_record_notifier_delivery_skips_log_notifier(tmp_path):
    storage = AlertStorage(data_dir=tmp_path)
    record_notifier_delivery(storage, alert_id="a1", notifier=LogNotifier(), success=True)
    assert latest_deliveries_by_channel(storage) == []
