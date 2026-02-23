# blackroad-customer-journey

> Map, analyze, and visualize multi-channel customer journeys with funnel analytics.

## Features

- **Funnel Stage Management** — define ordered conversion stages with entry/exit events
- **Session Tracking** — capture customer sessions across channels and devices
- **Touchpoint Recording** — log every interaction with automatic stage detection
- **Funnel Analysis** — entry counts, conversion rates, drop-off rates, avg time per stage
- **Conversion Path Mining** — top paths ranked by frequency and conversion rate
- **Dropoff Analytics** — reasons, time-of-day patterns, and channel breakdowns
- **Channel Attribution** — sessions, conversions, and value per marketing channel
- **Customer LTV Segments** — equal-width bucketing of lifetime value
- **Journey Heatmap** — 24×7 touchpoint density matrix

## Quick Start

```bash
pip install -r requirements.txt
python src/customer_journey.py funnel add "Awareness" 1 --entry-event page_view
python src/customer_journey.py session cust-001 organic --device desktop
python src/customer_journey.py analyze --days 30
python src/customer_journey.py paths --limit 5
python src/customer_journey.py channels --days 7
python src/customer_journey.py heatmap --hours 168
```

## CLI Commands

| Command       | Description                          |
|---------------|--------------------------------------|
| `funnel add`  | Add a funnel stage                   |
| `funnel show` | ASCII funnel with conversion stats   |
| `session`     | Start a customer session             |
| `touchpoint`  | Record a touchpoint event            |
| `analyze`     | Full funnel analysis                 |
| `paths`       | Top conversion paths                 |
| `dropoffs`    | Dropoff analysis for a stage         |
| `channels`    | Channel attribution report           |
| `heatmap`     | Journey heatmap (24×7 grid)          |

## Running Tests

```bash
pytest tests/ -v --cov=src
```

## License

Proprietary — BlackRoad OS, Inc. All rights reserved.
