#!/usr/bin/env python3
"""
Local FastAPI backend for agent data collection
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import List, Dict, Any

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

# In-memory storage
DB: Dict[str, AgentPayload] = {}

templates = Jinja2Templates(directory="templates")

@app.post("/ingest")
def ingest_data(payload: AgentPayload):
    """Receive agent data"""
    hostname = payload.host_details.hostname
    print(f"Received data from: {hostname}")
    DB[hostname] = payload
    return {"status": "success", "hostname": hostname}

@app.get("/api/hosts", response_model=List[str])
def get_hosts():
    """List all hosts"""
    return list(DB.keys())

@app.get("/api/hosts/{hostname}", response_model=AgentPayload)
def get_host_data(hostname: str):
    """Get data for specific host"""
    if hostname in DB:
        return DB[hostname]
    return {"error": "Host not found"}

@app.get("/", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    """Main dashboard"""
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "hosts": list(DB.keys())}
    )

@app.get("/hosts/{hostname}", response_class=HTMLResponse)
async def view_host_details(request: Request, hostname: str):
    """Host details page"""
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
            "passed_checks": passed_checks
        }
    )
