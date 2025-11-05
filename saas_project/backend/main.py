#!/usr/bin/env python3
"""
Local FastAPI backend for agent data collection
Supports both local in-memory storage and AWS API Gateway proxy mode
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import os
import requests

# Configuration - check if AWS mode is enabled
AWS_API_ENDPOINT = os.environ.get('AWS_API_ENDPOINT', '')
USE_AWS_MODE = bool(AWS_API_ENDPOINT)

class HostDetails(BaseModel):
    hostname: str
    os_type: str
    os_version: str

class Package(BaseModel):
    name: str
    version: str

class CISResult(BaseModel):
    check: str
    status: str
    evidence: str

class AgentPayload(BaseModel):
    host_details: HostDetails
    installed_packages: List[Package]
    cis_results: List[CISResult]

app = FastAPI(
    title="Security Agent Backend",
    description="Receives data from Linux agents"
)

# In-memory storage (only used in local mode)
DB: Dict[str, AgentPayload] = {}

templates = Jinja2Templates(directory="templates")

# Helper functions for AWS mode
def fetch_aws_hosts():
    """Fetch hosts from AWS API Gateway"""
    try:
        response = requests.get(f"{AWS_API_ENDPOINT}/hosts", timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('hosts', [])
    except Exception as e:
        print(f"Error fetching from AWS: {e}")
        return []

def fetch_aws_host_details(hostname: str):
    """Fetch specific host details from AWS"""
    try:
        response = requests.get(f"{AWS_API_ENDPOINT}/hosts/{hostname}", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching host details from AWS: {e}")
        return None

@app.post("/ingest")
def ingest_data(payload: AgentPayload):
    """Receive agent data (only works in local mode)"""
    hostname = payload.host_details.hostname
    print(f"Received data from: {hostname}")
    DB[hostname] = payload
    return {"status": "success", "hostname": hostname}

@app.get("/api/hosts")
def get_hosts():
    """List all hosts - supports both local and AWS mode"""
    if USE_AWS_MODE:
        hosts_data = fetch_aws_hosts()
        return {"hosts": hosts_data, "count": len(hosts_data), "mode": "AWS"}
    else:
        return {"hosts": list(DB.keys()), "count": len(DB), "mode": "Local"}

@app.get("/api/hosts/{hostname}")
def get_host_data(hostname: str):
    """Get data for specific host - supports both local and AWS mode"""
    if USE_AWS_MODE:
        host_data = fetch_aws_host_details(hostname)
        if host_data:
            return host_data
        return {"error": "Host not found"}
    else:
        if hostname in DB:
            return DB[hostname]
        return {"error": "Host not found"}

@app.get("/", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    """Main dashboard - supports both local and AWS mode"""
    if USE_AWS_MODE:
        hosts_data = fetch_aws_hosts()
        mode = "AWS"
    else:
        hosts_data = [{"hostname": k} for k in DB.keys()]
        mode = "Local"
    
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "hosts": hosts_data,
            "mode": mode,
            "aws_mode": USE_AWS_MODE
        }
    )

@app.get("/hosts/{hostname}", response_class=HTMLResponse)
async def view_host_details(request: Request, hostname: str):
    """Host details page - supports both local and AWS mode"""
    if USE_AWS_MODE:
        host_data = fetch_aws_host_details(hostname)
        if not host_data:
            return HTMLResponse("<h2>Host not found</h2>", status_code=404)
        
        # Extract data from AWS response format
        cis_results = host_data.get('cis_results', [])
        total_checks = host_data.get('metrics', {}).get('total_checks', len(cis_results))
        passed_checks = host_data.get('metrics', {}).get('passed_checks', 0)
        
        return templates.TemplateResponse(
            "host_details.html", 
            {
                "request": request, 
                "host": host_data,
                "total_checks": total_checks,
                "passed_checks": passed_checks,
                "aws_mode": True
            }
        )
    else:
        if hostname not in DB:
            return HTMLResponse("<h2>Host not found</h2>", status_code=404)
        
        host_data = DB[hostname]
        total_checks = len(host_data.cis_results)
        passed_checks = sum(1 for r in host_data.cis_results if r.status == 'pass')
        
        return templates.TemplateResponse(
            "host_details.html", 
            {
                "request": request, 
                "host": host_data,
                "total_checks": total_checks,
                "passed_checks": passed_checks,
                "aws_mode": False
            }
        )
