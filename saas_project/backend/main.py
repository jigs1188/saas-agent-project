#!/usr/bin/env python3
"""
SaaS Security Agent Backend
----------------------------
This is a FastAPI server that receives security data from Linux agents and displays
it in a web dashboard. I built this for local development and testing before deploying
to AWS. In production, Lambda functions replace this server.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from typing import List, Dict, Any

# --- Data Models ---
# These define the structure of JSON data we expect from the agent
# Pydantic validates the data automatically, which is pretty handy

class HostDetails(BaseModel):
    hostname: str
    os_type: str
    os_version: str

class Package(BaseModel):
    name: str
    version: str

class CISResult(BaseModel):
    check: str
    status: str  # 'pass' or 'fail'
    evidence: str  # What we found on the system

class AgentPayload(BaseModel):
    host_details: HostDetails
    installed_packages: List[Package]
    cis_results: List[CISResult]

# --- Application Setup ---
app = FastAPI(
    title="SaaS Security Agent Backend",
    description="Receives and displays data from Linux security agents."
)

# In-memory "database" - just a Python dictionary
# In a real application, we'd use PostgreSQL or MongoDB, but for testing this works fine
# The key is the hostname, value is all the data from that host
DB: Dict[str, AgentPayload] = {}

# Setup for rendering HTML pages
# Jinja2 is a templating engine - it lets us insert Python data into HTML
templates = Jinja2Templates(directory="templates")

# --- API Endpoints ---

@app.post("/ingest")
def ingest_data(payload: AgentPayload):
    """
    This is where the agent sends its data
    FastAPI automatically validates the JSON against our AgentPayload model
    """
    hostname = payload.host_details.hostname
    print(f" Received data from host: {hostname}")  # This prints to the terminal
    
    # Store it in our dictionary
    DB[hostname] = payload
    
    return {"status": "success", "hostname": hostname}

@app.get("/api/hosts", response_model=List[str])
def get_hosts():
    """Returns a list of all hostnames that have sent us data"""
    # list(DB.keys()) gives us all the hostnames
    return list(DB.keys())

@app.get("/api/hosts/{hostname}", response_model=AgentPayload)
def get_host_data(hostname: str):
    """Returns all the data for a specific host"""
    if hostname in DB:
        return DB[hostname]
    # If the host doesn't exist, return an error
    return {"error": "Host not found"}

# --- Frontend HTML Endpoints ---
# These serve actual HTML pages for the web dashboard

@app.get("/", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    """
    This is the main page - shows a list of all monitored hosts
    We pass the list of hostnames to the HTML template
    """
    return templates.TemplateResponse(
        "index.html", 
        {"request": request, "hosts": list(DB.keys())}
    )

@app.get("/hosts/{hostname}", response_class=HTMLResponse)
async def view_host_details(request: Request, hostname: str):
    """
    This page shows detailed information for one specific host
    Including all packages and security check results
    """
    if hostname not in DB:
        # If we don't have data for this host, show an error
        return HTMLResponse("<h2>Host not found</h2>", status_code=404)
    
    host_data = DB[hostname]
    
    # Calculate some summary statistics
    total_checks = len(host_data.cis_results)
    passed_checks = sum(1 for r in host_data.cis_results if r.status == 'pass')
    # sum() with a generator expression - counts how many checks have status='pass'
    
    return templates.TemplateResponse(
        "host_details.html", 
        {
            "request": request, 
            "host": host_data,
            "total_checks": total_checks,
            "passed_checks": passed_checks
        }
    )
