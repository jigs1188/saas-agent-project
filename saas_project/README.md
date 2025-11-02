# SaaS Security Monitoring - Agent & Backend

This directory contains the core implementation components:
- **agent/** - Linux security data collection agent
- **backend/** - FastAPI web server for local development

## Components

### Agent (`agent/`)

Python-based security agent for Linux systems that collects:
- Installed packages (dpkg/rpm/apk support)
- System security configurations
- CIS benchmark check results

**Files:**
- `agent.py` - Main agent implementation
- `requirements.txt` - Python dependencies
- `packaging/debian/` - Debian package structure

### Backend (`backend/`)

FastAPI server providing:
- REST API for data ingestion
- Web dashboard for visualization
- In-memory data storage

**Files:**
- `main.py` - Server implementation
- `requirements.txt` - Dependencies
- `templates/` - HTML interface

## Quick Start

### Terminal 1: Start Backend Server

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Server runs at `http://127.0.0.1:8000`

### Terminal 2: Run Agent

```bash
cd agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# For local backend
export BACKEND_URL="http://127.0.0.1:8000/ingest"
sudo -E python3 agent.py

# For AWS backend
export API_GATEWAY_ENDPOINT="https://your-api.execute-api.region.amazonaws.com/prod"
export API_KEY="your-api-key-here"
sudo -E python3 agent.py
```

Root access required for security checks.

### View Dashboard

Navigate to `http://127.0.0.1:8000` to see:
- Host list
- Security status
- Package inventory
- CIS check results

## Building Debian Package

```bash
cd agent
dpkg-deb --build packaging/debian
```

Creates `debian.deb` for deployment:

```bash
sudo dpkg -i packaging/debian/debian.deb
```

Installs to `/usr/local/bin/saas-agent`

## API Endpoints

**POST /ingest**
- Receives agent data
- Body: JSON with host_details, installed_packages, cis_results

**GET /api/hosts**
- Returns list of monitored hosts

**GET /api/hosts/{hostname}**
- Returns detailed host data

## Data Structure

```json
{
  "host_details": {
    "hostname": "server01",
    "os_type": "Ubuntu",
    "os_version": "22.04"
  },
  "installed_packages": [
    {"name": "nginx", "version": "1.18.0"}
  ],
  "cis_results": [
    {
      "check": "SSH root login disabled",
      "status": "pass",
      "evidence": "PermitRootLogin no"
    }
  ]
}
```

## CIS Security Checks

1. SSH root login disabled
2. Firewall enabled
3. Audit daemon running
4. AppArmor/SELinux enabled
5. No world-writable files
6. Unused filesystems disabled
7. Time synchronization configured
8. Password policies enforced
9. GDM auto-login disabled
10. No passwordless sudo

## Requirements

**Agent:**
- Python 3.7+
- requests library
- Root/sudo access
- Supported: Ubuntu, Debian, RHEL, CentOS, Alpine

**Backend:**
- Python 3.7+
- FastAPI, Uvicorn, Jinja2

## Production Deployment

For production use, deploy to AWS serverless infrastructure (see main README). The local FastAPI backend is for development and testing only.
