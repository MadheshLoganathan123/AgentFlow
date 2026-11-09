# AgentFlow — Local Development Guide

## Prerequisites
- **Python**: 3.11+
- **Node.js**: 20+ (with npm)
- **Docker & Docker Compose**: Installed and running
- **Git**

## Quick Start

### 1. Clone & Setup Environment
```bash
git clone <repo-url> agentflow
cd agentflow
cp .env.example .env
```

### 2. Start PostgreSQL with pgvector (via Docker)
```bash
docker compose up postgres -d
```

### 3. Install Python Dependencies
```bash
python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements-dev.txt
pip install -e packages/contracts
pip install -e packages/db
pip install -e services/orchestrator
pip install -e services/api
```

### 4. Run Automated Tests
```bash
pytest
```

### 5. Start Backend API
```bash
python -m uvicorn services.api.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be accessible at: `http://localhost:8000/docs`

### 6. Start Frontend Dashboard
```bash
cd apps/web
npm install
npm run dev
```
Dashboard will be accessible at: `http://localhost:3000`

### 7. Run Everything via Docker Compose
```bash
docker compose up --build
```

