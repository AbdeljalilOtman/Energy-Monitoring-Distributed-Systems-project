# Energy Monitoring Distributed Systems Project

Distributed monitoring platform for ML workloads with:
- A central Flask dashboard/backend
- Edge node telemetry daemons
- Real-time KPI visualization and storage

## Repository Layout

- `backend/`: central server (Flask API, dashboard, database connector)
- `edge-node/`: edge daemon and metric collectors
- `docs/`: deployment/testing guides and requirement PDFs
- `docs/specs/`: normalized copies of provided project specifications

## What Was Integrated

This repository now contains:
- Central backend from your `daemon_project`
- Colleague daemon stack integrated to backend format
- Transformer from nested edge payload to backend flat KPI records
- Multi-node testing and deployment documentation

## Quick Start

### 1) Run backend (central node)

```powershell
cd backend
pip install -r requirements.txt
python app.py
```

Backend listens on port `5000`.

### 2) Run edge daemon (edge node)

```powershell
cd edge-node
python daemon.py
```

Before live transmission, set `dry_run` to `false` and update `backend_url` to the central node IP.

## Key Endpoints

- `POST /api/kpi/submit`: ingest KPI records
- `GET /api/dashboard/summary`: node-level summary
- `GET /api/metrics/<node_id>`: latest metrics by node
- `GET /api/metrics/aggregated/<node_id>`: KPI aggregation

## Documentation

- `docs/TESTING_GUIDE_MULTINODE.md`: 2-computer WiFi/hotspot validation
- `docs/DEPLOYMENT_GUIDE.md`: full deployment and architecture
- `docs/QUICK_REFERENCE.md`: concise command checklist
- `edge-node/README_INTEGRATION.md`: edge integration details

## Notes

- If your network blocks external CDNs, dashboard JS libraries may fail to load.
- If hotspot isolates clients, edge-to-backend HTTP can time out.
- Use the troubleshooting sections in `docs/TESTING_GUIDE_MULTINODE.md` for both cases.
