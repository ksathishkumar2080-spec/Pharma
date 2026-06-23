# Internal Oncology Intelligence OS

An internal intelligence operating system for oncology commercial teams. The platform continuously ingests, enriches, scores, and operationalizes scientific, competitive, and HCP intelligence into actionable recommendations.

## Architecture

```
oncology-intel-os/
├── services/
│   ├── ingestion/          # Data ingestion connectors
│   ├── identity/           # Entity resolution layer
│   ├── graph/              # Neo4j knowledge graph
│   ├── enrichment/         # Enrichment pipelines
│   ├── scoring/            # Lead & opportunity scoring
│   ├── triggers/           # Buying signal detection
│   ├── messaging/          # Human messaging intelligence
│   ├── workflows/          # Automation orchestration
│   └── dashboard/          # Executive command center API
├── shared/                 # Shared models, utils, config
├── docker-compose.yml
└── pyproject.toml
```

## Quick Start

```bash
cp .env.example .env
docker-compose up -d
```

## Tech Stack

- **API**: Python + FastAPI
- **Relational DB**: PostgreSQL
- **Graph DB**: Neo4j
- **Search**: Elasticsearch
- **Cache**: Redis
- **Orchestration**: Temporal
- **Scraping**: Playwright + Scrapy
- **LLM**: Claude (Anthropic) via `anthropic` SDK
- **Vector DB**: pgvector (PostgreSQL extension)
