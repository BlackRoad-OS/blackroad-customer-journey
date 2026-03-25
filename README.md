<!-- BlackRoad SEO Enhanced -->

# ulackroad customer journey

> Part of **[BlackRoad OS](https://blackroad.io)** — Sovereign Computing for Everyone

[![BlackRoad OS](https://img.shields.io/badge/BlackRoad-OS-ff1d6c?style=for-the-badge)](https://blackroad.io)
[![BlackRoad OS](https://img.shields.io/badge/Org-BlackRoad-OS-2979ff?style=for-the-badge)](https://github.com/BlackRoad-OS)
[![License](https://img.shields.io/badge/License-Proprietary-f5a623?style=for-the-badge)](LICENSE)

**ulackroad customer journey** is part of the **BlackRoad OS** ecosystem — a sovereign, distributed operating system built on edge computing, local AI, and mesh networking by **BlackRoad OS, Inc.**

## About BlackRoad OS

BlackRoad OS is a sovereign computing platform that runs AI locally on your own hardware. No cloud dependencies. No API keys. No surveillance. Built by [BlackRoad OS, Inc.](https://github.com/BlackRoad-OS-Inc), a Delaware C-Corp founded in 2025.

### Key Features
- **Local AI** — Run LLMs on Raspberry Pi, Hailo-8, and commodity hardware
- **Mesh Networking** — WireGuard VPN, NATS pub/sub, peer-to-peer communication
- **Edge Computing** — 52 TOPS of AI acceleration across a Pi fleet
- **Self-Hosted Everything** — Git, DNS, storage, CI/CD, chat — all sovereign
- **Zero Cloud Dependencies** — Your data stays on your hardware

### The BlackRoad Ecosystem
| Organization | Focus |
|---|---|
| [BlackRoad OS](https://github.com/BlackRoad-OS) | Core platform and applications |
| [BlackRoad OS, Inc.](https://github.com/BlackRoad-OS-Inc) | Corporate and enterprise |
| [BlackRoad AI](https://github.com/BlackRoad-AI) | Artificial intelligence and ML |
| [BlackRoad Hardware](https://github.com/BlackRoad-Hardware) | Edge hardware and IoT |
| [BlackRoad Security](https://github.com/BlackRoad-Security) | Cybersecurity and auditing |
| [BlackRoad Quantum](https://github.com/BlackRoad-Quantum) | Quantum computing research |
| [BlackRoad Agents](https://github.com/BlackRoad-Agents) | Autonomous AI agents |
| [BlackRoad Network](https://github.com/BlackRoad-Network) | Mesh and distributed networking |
| [BlackRoad Education](https://github.com/BlackRoad-Education) | Learning and tutoring platforms |
| [BlackRoad Labs](https://github.com/BlackRoad-Labs) | Research and experiments |
| [BlackRoad Cloud](https://github.com/BlackRoad-Cloud) | Self-hosted cloud infrastructure |
| [BlackRoad Forge](https://github.com/BlackRoad-Forge) | Developer tools and utilities |

### Links
- **Website**: [blackroad.io](https://blackroad.io)
- **Documentation**: [docs.blackroad.io](https://docs.blackroad.io)
- **Chat**: [chat.blackroad.io](https://chat.blackroad.io)
- **Search**: [search.blackroad.io](https://search.blackroad.io)

---


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
