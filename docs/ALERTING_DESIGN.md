# Alerting System Design (vision + partial implementation)

## Implementation status (`main`)

**Already in the codebase:** `src/alerts/` — rule-driven **`AlertEngine`**, `config/alerts.json`, cooldowns and alert history storage, **log** notifier, and **HTTP webhook** notifier (`webhook_url` per rule or `ALERT_WEBHOOK_URL`). See [PROJECT_STATUS.md](PROJECT_STATUS.md) for the short roadmap.

**Still design / future work (this document):** SMTP and other cloud notifiers, Slack block payloads, technical-indicator conditions, CLI subcommands, dashboard management UI. Phases and checkboxes below describe the **full** vision, not only what is merged today.

## Overview

A flexible alerting system to notify users when stocks meet specific conditions, enabling timely buying decisions.

## Use Cases

### 1. Price-Based Alerts

```text
"Alert me when AAPL drops below $150"
"Alert me when TSLA reaches $200"
"Alert me when any S&P 500 stock drops >5% in a day"
```

### 2. Screening-Based Alerts

```text
"Alert me when high volume stocks gain >5%"
"Alert me when a stock meets my screening criteria for the first time"
"Alert me when RSI < 30 (oversold)"
```

### 3. Pattern-Based Alerts

```text
"Alert me when 50-day MA crosses above 200-day MA (golden cross)"
"Alert me when a stock breaks out of 52-week high"
"Alert me when volume is 3x average"
```

---

## Architecture

```text
src/
└── alerts/                          # Implemented (partial — see status above)
    ├── __init__.py
    ├── alert_engine.py              # Core alert evaluation
    ├── alert_rules.py               # Rule definitions
    ├── notifiers/                   # Notification channels
    │   ├── __init__.py
    │   ├── aws_sns_notifier.py      # AWS SNS (SMS/Email)
    │   ├── azure_notifier.py        # Azure Service Bus/Event Grid
    │   ├── gcp_pubsub_notifier.py   # Google Cloud Pub/Sub
    │   ├── email_notifier.py        # SMTP Email (cloud-agnostic)
    │   ├── webhook_notifier.py      # Slack/Discord/Custom
    │   └── base_notifier.py         # Abstract base
    └── alert_storage.py             # Alert history

config/
└── alerts.json                      # User-defined alert rules
```

---

## Configuration Example

### `config/alerts.json`

```json
{
  "alerts": [
    {
      "id": "alert_1",
      "name": "AAPL Price Drop",
      "enabled": true,
      "condition": {
        "type": "price_threshold",
        "symbol": "AAPL",
        "operator": "less_than",
        "value": 150.0
      },
      "notifications": ["aws_sns", "email"],
      "cooldown_minutes": 60
    },
    {
      "id": "alert_2",
      "name": "High Volume Gainers",
      "enabled": true,
      "condition": {
        "type": "screening_match",
        "filters": {
          "volume_threshold": 5000000,
          "min_daily_change_pct": 5.0
        }
      },
      "notifications": ["azure_service_bus", "webhook"],
      "cooldown_minutes": 1440
    },
    {
      "id": "alert_3",
      "name": "Oversold RSI",
      "enabled": false,
      "condition": {
        "type": "technical_indicator",
        "indicator": "RSI",
        "period": 14,
        "operator": "less_than",
        "value": 30
      },
      "notifications": ["gcp_pubsub", "email"],
      "cooldown_minutes": 360
    }
  ]
}
```

---

## Environment Variables

```bash
# AWS SNS
AWS_REGION=us-east-1
AWS_SNS_TOPIC_ARN=arn:aws:sns:us-east-1:123456789:stock-alerts
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret

# Azure Service Bus
AZURE_SERVICE_BUS_CONNECTION_STRING=Endpoint=sb://your-namespace.servicebus.windows.net/...
AZURE_SERVICE_BUS_QUEUE_NAME=stock-alerts
# Or Azure Event Grid
AZURE_EVENT_GRID_TOPIC_ENDPOINT=https://your-topic.region.eventgrid.azure.net/api/events
AZURE_EVENT_GRID_ACCESS_KEY=your-access-key

# Google Cloud Pub/Sub
GCP_PROJECT_ID=your-project-id
GCP_PUBSUB_TOPIC=stock-alerts
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Email (SMTP - Cloud Agnostic)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_EMAIL_TO=recipient@example.com

# Webhook (Cloud Agnostic)
WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

## Implementation Plan

### Phase 1: Core Alert Engine (2-3 days)

- [ ] Alert rule parser
- [ ] Condition evaluator
- [ ] Alert storage (history)
- [ ] Cooldown mechanism

### Phase 2: Basic Notifications (1-2 days)

- [ ] Email notifier (SMTP)
- [ ] Webhook notifier (generic HTTP POST)
- [ ] Notification formatting

### Phase 3: Cloud Provider Integration (2-3 days)

- [ ] AWS SNS notifier (SMS/Email)
- [ ] Azure Service Bus notifier
- [ ] Azure Event Grid notifier
- [ ] Google Cloud Pub/Sub notifier
- [ ] Cloud credentials handling
- [ ] Error handling and retries for all providers

### Phase 4: Advanced Features (3-4 days)

- [ ] Technical indicators (RSI, MACD)
- [ ] Pattern detection
- [ ] Multi-condition alerts (AND/OR logic)
- [ ] Alert templates

### Phase 5: UI/UX (2-3 days)

- [ ] CLI for managing alerts
- [ ] Alert testing/dry-run mode
- [ ] Alert history viewer
- [ ] Alert performance metrics

---

## Example Usage

### CLI Commands (Proposed)

```bash
# List alerts
python main.py alerts list

# Add alert
python main.py alerts add \
  --name "AAPL Price Drop" \
  --condition "price < 150" \
  --symbol AAPL \
  --notify aws_sns  # or azure_service_bus, gcp_pubsub, email, webhook

# Test alert
python main.py alerts test alert_1

# Enable/disable
python main.py alerts enable alert_1
python main.py alerts disable alert_1

# View history
python main.py alerts history --days 7
```

### Programmatic Usage

**AWS SNS:**

```python
from src.alerts import AlertEngine, PriceThresholdAlert, AWSSNSNotifier

alert = PriceThresholdAlert(symbol="AAPL", threshold=150.0, operator="less_than")
notifier = AWSSNSNotifier(topic_arn=os.getenv("AWS_SNS_TOPIC_ARN"))
alert.add_notifier(notifier)

engine = AlertEngine()
engine.add_alert(alert)
engine.evaluate(stock_data)
```

**Azure Service Bus:**

```python
from src.alerts import AlertEngine, PriceThresholdAlert, AzureServiceBusNotifier

alert = PriceThresholdAlert(symbol="AAPL", threshold=150.0, operator="less_than")
notifier = AzureServiceBusNotifier(
    connection_string=os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING"),
    queue_name=os.getenv("AZURE_SERVICE_BUS_QUEUE_NAME")
)
alert.add_notifier(notifier)
```

**Google Cloud Pub/Sub:**

```python
from src.alerts import AlertEngine, PriceThresholdAlert, GCPPubSubNotifier

alert = PriceThresholdAlert(symbol="AAPL", threshold=150.0, operator="less_than")
notifier = GCPPubSubNotifier(
    project_id=os.getenv("GCP_PROJECT_ID"),
    topic_name=os.getenv("GCP_PUBSUB_TOPIC")
)
alert.add_notifier(notifier)
```

---

## Notification Examples

### SMS via AWS SNS

```text
🚨 Stock Alert: AAPL Price Drop

Apple Inc (AAPL) is now $148.50
Condition: Price < $150.00
Change: -2.5% today

Time: 2026-01-04 14:30:00 UTC
```

### Azure Service Bus Message

```json
{
  "alertId": "alert_1",
  "alertName": "AAPL Price Drop",
  "symbol": "AAPL",
  "currentPrice": 148.50,
  "condition": "price < 150.00",
  "changePercent": -2.5,
  "timestamp": "2026-01-04T14:30:00Z"
}
```

### Google Cloud Pub/Sub Message

```json
{
  "alert_id": "alert_1",
  "alert_name": "AAPL Price Drop",
  "symbol": "AAPL",
  "current_price": 148.50,
  "condition": "price < 150.00",
  "change_percent": -2.5,
  "timestamp": "2026-01-04T14:30:00Z",
  "attributes": {
    "alert_type": "price_threshold",
    "severity": "high"
  }
}
```

### Email (Cloud Agnostic)

```text
Subject: 🚨 Stock Alert: High Volume Gainers

You have 3 stocks matching your "High Volume Gainers" alert:

1. NVDA (NVIDIA) - $450.25 (+5.8%, vol: 52M)
2. AMD (AMD) - $125.80 (+6.2%, vol: 48M)
3. INTC (Intel) - $42.10 (+5.1%, vol: 65M)

View details: [link to dashboard]
Manage alerts: [link to settings]
```

### Slack Webhook

```json
{
  "text": "🚨 Stock Alert Triggered",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*AAPL Price Drop Alert*\nApple Inc (AAPL) is now $148.50\nCondition: Price < $150.00"
      }
    }
  ]
}
```

---

## Technical Considerations

### Rate Limiting

- Cooldown periods prevent alert spam
- Per-alert cooldown configuration
- Global rate limits for notifications

### Data Requirements

- Real-time or near-real-time data needed
- May require WebSocket or streaming API
- Consider API call costs for frequent checks

### Reliability

- Alert evaluation should be idempotent
- Retry failed notifications
- Store alert history for audit

### Security

- Secure credential storage
- Encrypted notification channels
- Alert access control (if multi-user)

---

## Testing Strategy

```python
# Unit tests
def test_price_threshold_alert_triggers():
    alert = PriceThresholdAlert("AAPL", 150, "less_than")
    stock = {"symbol": "AAPL", "close": 148.0}
    assert alert.evaluate(stock) == True

# Integration tests
def test_sns_notification_sent():
    notifier = SNSNotifier(topic_arn="test-topic")
    result = notifier.send("Test message")
    assert result.status_code == 200

# End-to-end tests
def test_full_alert_workflow():
    # Create alert → evaluate → notify → verify history
    pass
```

---

## Future Enhancements

- **AI-powered alerts**: "Alert me when this stock is a good buy"
- **Portfolio alerts**: Track entire portfolio performance
- **Social alerts**: Alert when a stock is trending on Twitter/Reddit
- **Backtest alerts**: Test alert rules against historical data
- **Mobile app**: Push notifications to mobile devices

---

## Cost Considerations

### AWS SNS Pricing (as of 2026)

- SMS: $0.00645 per message (US)
- Email: $2 per 100,000 emails
- Very affordable for personal use

### Azure Service Bus Pricing (as of 2026)

- Basic Tier: $0.05 per million operations
- Standard Tier: $10/month + $0.80 per million operations
- Premium Tier: Variable based on usage
- Very cost-effective for moderate usage

### Google Cloud Pub/Sub Pricing (as of 2026)

- First 10 GB/month: Free
- Message ingestion: $40 per TB
- Message delivery: $40 per TB
- Excellent free tier for personal use

### Cloud-Agnostic Free Options

- SMTP email (Gmail, Outlook, SendGrid free tier)
- Webhook to free services (Discord, Telegram, Slack incoming webhooks)
- Local notifications (desktop/mobile)

### Recommendation

For personal use, all three cloud providers are affordable:

- **AWS SNS**: Best for SMS notifications
- **Azure Service Bus**: Best for complex workflows
- **GCP Pub/Sub**: Best free tier, great for high volume
- **SMTP Email**: Best for completely free notifications

---

## Priority: HIGH

This feature directly enables the core use case: **making timely buy/sell decisions**.

**Estimated Effort**: 2-3 weeks for full implementation
**Impact**: Very High - enables proactive trading
**Dependencies**: None (can be built independently)

---

## Contributing

Want to implement this feature? See [CONTRIBUTING.md](../CONTRIBUTING.md) and start with Phase 1!

**Contact**: Open an issue with tag `feature: alerting` to discuss implementation details.
