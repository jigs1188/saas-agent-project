# SaaS Security Monitoring System

A serverless security monitoring solution for Linux systems featuring a lightweight agent that collects security data and communicates with AWS cloud infrastructure. The system displays results through a web dashboard for real-time security monitoring.

## Overview

This system provides comprehensive security monitoring for Linux environments:

- **Linux Agent** - Python-based agent that runs on Linux servers (supports Ubuntu, RHEL, Debian, CentOS, Alpine)
- **AWS Backend** - Serverless cloud infrastructure using API Gateway, Lambda, and DynamoDB
- **Web Dashboard** - Real-time visualization of security status and host metrics

## Architecture

```
Linux Server → API Gateway → Lambda Functions → DynamoDB
    ↓              ↓              ↓                ↓
Security Agent   REST API     Data Processing   JSON Storage
```

The system uses AWS serverless architecture for scalability and cost efficiency.

## Key Features

### Security Agent
- **Package Inventory** - Collects installed packages via dpkg, rpm, or apk
- **CIS Benchmarks** - Implements 10 security configuration checks
- **Multi-Distro Support** - Works across Ubuntu, Debian, RHEL, CentOS, Alpine
- **Secure Communication** - HTTPS-based data transmission to AWS
- **Deployable Package** - Installs as .deb package

### Cloud Backend
- **API Gateway** - REST endpoints for data ingestion and retrieval
- **Lambda Functions** - 4 serverless functions for data processing
- **DynamoDB** - NoSQL database for persistent storage
- **API Security** - API key authentication
- **Monitoring** - CloudWatch logging

### Web Dashboard
- **Host Inventory** - View all monitored Linux systems
- **Security Metrics** - Track security scores and compliance trends
- **CIS Results** - Detailed pass/fail status for each check
- **Package Tracking** - Complete software inventory per host
- **Responsive UI** - Modern web interface

## CIS Security Checks

The agent implements 10 security configuration checks based on CIS benchmarks:

1. **SSH Security** - Root login disabled over SSH
2. **Firewall Status** - UFW or firewalld enabled and configured
3. **Audit System** - Auditd service running
4. **Security Modules** - AppArmor or SELinux enabled
5. **File Permissions** - No world-writable files present
6. **Filesystem Security** - Unused filesystems disabled
7. **Time Sync** - Chrony or NTP configured
8. **Password Policy** - Password complexity and expiration enforced
9. **Login Security** - GDM auto-login disabled
10. **Sudo Security** - No passwordless sudo access
## Deployment

### Prerequisites
- AWS account with appropriate permissions
- AWS CLI configured with credentials
- Python 3.7 or higher
- Bash shell environment

### AWS Infrastructure Setup

```bash
# Configure AWS credentials
aws configure
# Deploy complete infrastructure (5-10 minutes)
./deploy-aws-serverless.sh
```

The deployment script performs the following operations:
- Creates DynamoDB table with appropriate schema
- Packages and deploys 4 Lambda functions
- Configures API Gateway with REST endpoints
- Generates API key for authentication
- Outputs configuration for agent deployment

### Agent Installation

After AWS deployment completes, configure and run the agent:

```bash
# Configure environment variables from deployment output
export API_GATEWAY_ENDPOINT="https://[your-api-id].execute-api.us-east-1.amazonaws.com/prod"
export API_KEY="[your-generated-api-key]"

# Execute agent (requires root privileges for security checks)
cd saas_project/agent
sudo -E python3 agent.py
```

**Note:** The `-E` flag preserves environment variables when running with sudo.

### Viewing Results

**Option 1: Direct API Queries**

**Option 1: Direct API Queries**

```bash
# Retrieve all monitored hosts
curl "https://[your-api-id].execute-api.us-east-1.amazonaws.com/prod/hosts"

# View aggregated security results
curl "https://[your-api-id].execute-api.us-east-1.amazonaws.com/prod/cis-results"

# Get specific host details
curl "https://[your-api-id].execute-api.us-east-1.amazonaws.com/prod/hosts/[hostname]"

# Check DynamoDB data
aws dynamodb scan --table-name saas-hosts --region us-east-1
```

**Option 2: Web Dashboard (Recommended)**

Run the local backend in AWS mode to view data in a beautiful web interface:

```bash
cd saas_project/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export AWS_API_ENDPOINT="https://[your-api-id].execute-api.us-east-1.amazonaws.com/prod"
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Open browser: http://localhost:8000
```

The dashboard will fetch and display all data from AWS in real-time.

**AWS Console Access:**
- **DynamoDB**: `https://console.aws.amazon.com/dynamodbv2`
- **Lambda**: `https://console.aws.amazon.com/lambda`
- **API Gateway**: `https://console.aws.amazon.com/apigateway`

## Project Structure

```
saas-agent-project/
├── saas_project/
│   ├── agent/                    # Linux security agent
│   │   ├── agent.py             # Main agent implementation
│   │   ├── requirements.txt
│   │   └── packaging/           # Debian package structure
│   └── backend/                  # FastAPI backend (local testing)
│       ├── main.py
│       └── templates/           # Dashboard UI templates
├── lambda-functions/             # AWS Lambda implementations
│   ├── ingest/                  # Data ingestion endpoint
│   ├── get-hosts/               # Host listing endpoint
│   ├── get-host-details/        # Detailed host data endpoint
│   └── get-cis-results/         # Aggregated security results
├── deploy-aws-serverless.sh     # Automated deployment script
└── deployment-config.txt        # Generated AWS configuration
```

## API Endpoints

### POST /ingest
Receives security data from agents
- **Authentication**: Requires API key
- **Payload**: JSON with host details, packages, and CIS results
- **Response**: Status confirmation with hostname

### GET /hosts
Returns list of all monitored hosts
- **Response**: Array of hosts with summary metrics

### GET /hosts/{hostname}
Retrieves detailed data for specific host
- **Parameters**: hostname (path parameter)
- **Response**: Complete host details including packages and CIS results

### GET /cis-results
Aggregated security check results across all hosts
- **Response**: Overall statistics, per-check breakdown, and critical failures

## Cost Analysis

**AWS Free Tier** (first 12 months):
- Lambda: 1M requests/month included
- API Gateway: 1M calls/month included
- DynamoDB: 25GB storage always free

**Estimated Monthly Cost** (post-free tier, 100 hosts, 10 updates/day):
- Lambda invocations: ~$3.20
- API Gateway calls: ~$3.00
- DynamoDB storage: ~$0.50
- **Total**: ~$6.70/month

This represents an 87% cost reduction compared to traditional EC2-based approaches.

## Local Development

For local testing without AWS deployment:

### Option 1: Local Mode (Agent sends data to local backend)

```bash
# Terminal 1: Start local backend in local mode
cd saas_project/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Run agent locally
cd saas_project/agent
export BACKEND_URL="http://127.0.0.1:8000/ingest"
unset API_GATEWAY_ENDPOINT  # Disable AWS mode
sudo -E python3 agent.py

# Access dashboard at http://127.0.0.1:8000
# Dashboard displays data from local in-memory storage
```

### Option 2: AWS Dashboard Mode (View AWS data in local dashboard)

```bash
# Terminal 1: Start local backend in AWS mode
cd saas_project/backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export AWS_API_ENDPOINT="https://[your-api-id].execute-api.us-east-1.amazonaws.com/prod"
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Run agent to AWS (optional)
cd saas_project/agent
export API_GATEWAY_ENDPOINT="https://[your-api-id].execute-api.us-east-1.amazonaws.com/prod"
export API_KEY="[your-api-key]"
sudo -E python3 agent.py

# Access dashboard at http://127.0.0.1:8000
# Dashboard displays data fetched from AWS DynamoDB via API Gateway
```

**Key Difference:**
- **Local Mode**: Agent → Local Backend (in-memory storage) → Dashboard
- **AWS Mode**: Agent → AWS API Gateway → DynamoDB, Dashboard → AWS API Gateway → Display data

The backend automatically detects the mode based on the `AWS_API_ENDPOINT` environment variable.

## Testing Procedures

```bash
# Direct Lambda invocation
aws lambda invoke \
  --function-name saas-security-get-hosts-function \
  --region us-east-1 \
  response.json

# API endpoint testing
curl -X GET "https://[api-id].execute-api.us-east-1.amazonaws.com/prod/hosts"

# DynamoDB data inspection
aws dynamodb scan --table-name saas-hosts --region us-east-1
```

## System Requirements

**Agent Requirements:**
- Python 3.7 or higher
- `requests` library
- Root/sudo privileges (for security checks)
- Supported distributions: Ubuntu, Debian, RHEL, CentOS, Alpine

**Backend Dashboard Requirements:**
- Python 3.7 or higher
- FastAPI framework
- Uvicorn ASGI server
- Jinja2 templating engine
- `requests` library (for AWS mode)

**AWS Deployment:**
- AWS account with appropriate IAM permissions
- AWS CLI configured
- Bash shell environment

**Local Development:**
- FastAPI framework
- Uvicorn ASGI server
- Jinja2 templating engine

## Technical Implementation

**Agent Architecture:**
- Multi-distribution package manager detection
- CIS benchmark implementation
- HTTPS communication with retry logic
- JSON payload formatting
- Supports both local backend and AWS API Gateway

**Cloud Architecture:**
- RESTful API design
- Serverless compute with Lambda
- NoSQL data storage with DynamoDB
- API key-based authentication
- CloudWatch monitoring and logging

**Dashboard Architecture:**
- FastAPI backend with dual-mode support (local/AWS)
- Dynamic data fetching from AWS API Gateway
- Real-time visualization with modern UI
- Responsive design with TailwindCSS
- Auto-detection of data source mode

## License

MIT License - Open source software

## Contact & Support

For technical questions or issues, refer to the deployment logs and AWS CloudWatch for debugging information.

---

Built as a demonstration of serverless security monitoring architecture using AWS managed services.

