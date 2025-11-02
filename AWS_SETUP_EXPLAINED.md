# How I Set Up AWS - Step by Step

## Overview
This document explains exactly how I set up AWS for this project. I'm documenting this for myself so I can confidently explain it in the interview.

---

## What is AWS and Why Use It?

**AWS (Amazon Web Services)** is Amazon's cloud platform. Instead of buying physical servers, you rent computing power. Benefits:
- No upfront hardware costs
- Pay only for what you use
- Scales automatically
- 99.99% uptime guarantee

---

## The Services I Used

### 1. API Gateway
**What it is**: Creates REST APIs that other applications can call
**What I used it for**: Provides endpoints for my agent to send data
**Cost**: First 1 million calls/month free

**Think of it like**: The receptionist at a company - receives requests and routes them to the right department.

### 2. Lambda  
**What it is**: Run code without managing servers
**What I used it for**: Process agent data and query DynamoDB
**Cost**: First 1 million requests/month free

**Think of it like**: Hiring someone only when you need them, not keeping them on staff 24/7.

### 3. DynamoDB
**What it is**: NoSQL database (stores JSON documents)
**What I used it for**: Store host information and security data
**Cost**: 25 GB always free

**Think of it like**: A filing cabinet where each folder (host) contains JSON documents.

### 4. IAM (Identity and Access Management)
**What it is**: Controls who/what can access AWS resources
**What I used it for**: Give Lambda permission to write to DynamoDB
**Cost**: Always free

**Think of it like**: Security badges that control who can enter which rooms.

---

## Step-by-Step: How I Set Everything Up

### Phase 1: AWS Account Setup

#### 1. Created AWS Account
1. Went to https://aws.amazon.com/free/
2. Clicked "Create a Free Account"
3. Entered email: [your email]
4. Set password
5. Chose "Personal" account type
6. Entered credit card (required but won't charge on free tier)
7. Verified phone number
8. Selected "Basic Support (Free)"

**Time taken**: ~10 minutes

#### 2. Got Access Credentials
1. Logged into AWS Console
2. Clicked my username → "Security credentials"
3. Scrolled to "Access keys"
4. Clicked "Create access key"
5. Selected "Command Line Interface (CLI)"
6. Clicked "Next" → "Create access key"
7. Downloaded and saved:
   - Access Key ID (like a username)
   - Secret Access Key (like a password)

**Important**: Saved these in `.env` file (never commit to git!)

---

### Phase 2: Local Setup

#### 3. Installed AWS CLI
The AWS Command Line Interface lets me control AWS from my terminal.

```bash
# Downloaded installer
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"

# Extracted
unzip awscliv2.zip

# Installed
sudo ./aws/install

# Verified
aws --version
# Output: aws-cli/2.31.27
```

**Time taken**: 5 minutes

#### 4. Configured AWS CLI
```bash
aws configure
```

Entered:
- AWS Access Key ID: [my access key from step 2]
- AWS Secret Access Key: [my secret key from step 2]
- Default region name: `us-east-1` (Virginia datacenter)
- Default output format: `json`

This created files in `~/.aws/`:
- `credentials` - stores keys
- `config` - stores preferences

**Time taken**: 2 minutes

#### 5. Tested Connection
```bash
aws sts get-caller-identity
```

Output showed my account ID - confirmed it worked!

---

### Phase 3: Creating AWS Resources

#### 6. Created DynamoDB Table

**What I needed**: A table to store host data
**Key decision**: Use hostname as partition key (unique identifier)

Command I ran:
```bash
aws dynamodb create-table \
  --table-name saas-hosts \
  --attribute-definitions AttributeName=hostname,AttributeType=S \
  --key-schema AttributeName=hostname,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

**What this means**:
- `table-name`: Called it "saas-hosts"
- `AttributeType=S`: Hostname is a String
- `KeyType=HASH`: Hostname is the partition key
- `PAY_PER_REQUEST`: Only pay for reads/writes I actually do
- `region us-east-1`: Virginia datacenter

**Time taken**: 2 minutes
**Cost**: $0 (free tier covers 25GB)

---

#### 7. Created IAM Role for Lambda

**Why needed**: Lambda functions need permission to access DynamoDB

**Step 1**: Create trust policy (who can use this role)
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
```

**Step 2**: Create the role
```bash
aws iam create-role \
  --role-name saas-security-lambda-execution-role \
  --assume-role-policy-document file://trust-policy.json
```

**Step 3**: Attach basic Lambda permissions
```bash
aws iam attach-role-policy \
  --role-name saas-security-lambda-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

This gives Lambda permission to write logs to CloudWatch.

**Step 4**: Create DynamoDB access policy
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:Query",
      "dynamodb:Scan"
    ],
    "Resource": "arn:aws:dynamodb:us-east-1:ACCOUNT_ID:table/saas-hosts"
  }]
}
```

**Step 5**: Attach DynamoDB policy
```bash
aws iam put-role-policy \
  --role-name saas-security-lambda-execution-role \
  --policy-name DynamoDBAccess \
  --policy-document file://dynamodb-policy.json
```

**Time taken**: 10 minutes
**Cost**: Free

---

#### 8. Created Lambda Functions

I created 4 Lambda functions. Here's how I did the first one:

**Step 1**: Write the Python code
Created `lambda-functions/ingest/lambda_function.py`

**Step 2**: Package it
```bash
cd lambda-functions/ingest
zip function.zip lambda_function.py
```

**Step 3**: Deploy to AWS
```bash
aws lambda create-function \
  --function-name saas-security-ingest-function \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/saas-security-lambda-execution-role \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://function.zip \
  --environment Variables={TABLE_NAME=saas-hosts,REGION=us-east-1}
```

**What this means**:
- `runtime python3.11`: Use Python 3.11
- `role`: Use the IAM role I created
- `handler`: Call `lambda_handler` function
- `environment`: Set environment variables

**Repeated for all 4 functions**:
1. ingest - receives data
2. get-hosts - lists hosts
3. get-host-details - shows one host
4. get-cis-results - aggregates security checks

**Time taken**: 20 minutes (5 min each)
**Cost**: Free (1M requests/month)

---

#### 9. Created API Gateway

**What I needed**: REST API endpoints for the agent to call

**Step 1**: Create the API
```bash
aws apigateway create-rest-api \
  --name saas-security-api \
  --endpoint-configuration types=REGIONAL
```

Got back API ID: `6n4x0gsk8j`

**Step 2**: Create resources (URL paths)
- `/ingest` - for POST requests
- `/hosts` - for GET requests
- `/hosts/{hostname}` - for GET requests
- `/cis-results` - for GET requests

**Step 3**: Add methods to each resource
For example, `/hosts` needs GET method:
```bash
aws apigateway put-method \
  --rest-api-id 6n4x0gsk8j \
  --resource-id RESOURCE_ID \
  --http-method GET \
  --authorization-type NONE
```

**Step 4**: Connect to Lambda functions
```bash
aws apigateway put-integration \
  --rest-api-id 6n4x0gsk8j \
  --resource-id RESOURCE_ID \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:ACCOUNT_ID:function:saas-security-get-hosts-function/invocations
```

**Step 5**: Grant permission
Lambda needs permission to be called by API Gateway:
```bash
aws lambda add-permission \
  --function-name saas-security-get-hosts-function \
  --statement-id apigateway-access \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:ACCOUNT_ID:6n4x0gsk8j/*/*"
```

**Step 6**: Deploy the API
```bash
aws apigateway create-deployment \
  --rest-api-id 6n4x0gsk8j \
  --stage-name prod
```

**Final API URL**: `https://6n4x0gsk8j.execute-api.us-east-1.amazonaws.com/prod`

**Time taken**: 30 minutes
**Cost**: Free (1M calls/month)

---

#### 10. Created API Key

**Why needed**: Secure the `/ingest` endpoint

```bash
aws apigateway create-api-key \
  --name saas-security-agent-key \
  --enabled

aws apigateway create-usage-plan \
  --name saas-security-usage-plan \
  --throttle burstLimit=100,rateLimit=50 \
  --api-stages apiId=6n4x0gsk8j,stage=prod
```

Got API Key: `GNw8sV37D9aQvBtb8QV8r51JW4hS5Fc4P77LRqd8`

**Time taken**: 5 minutes
**Cost**: Free

---

## What Each Component Does (Simple Explanation)

```
Agent (on server) → API Gateway → Lambda → DynamoDB
     ↓                  ↓           ↓          ↓
 Collects data      Receives    Processes   Stores
                    request     request     data
```

### Flow When Agent Runs:
1. Agent collects packages and security checks
2. Sends JSON to API Gateway `/ingest` endpoint
3. API Gateway forwards to `ingest` Lambda function
4. Lambda validates data and writes to DynamoDB
5. Returns success response to agent

### Flow When Viewing Data:
1. Browser requests `/hosts` endpoint
2. API Gateway calls `get-hosts` Lambda
3. Lambda reads from DynamoDB
4. Returns list of all hosts
5. Browser displays data

---

## Common AWS Concepts Explained

### Regions
AWS has datacenters worldwide. I chose `us-east-1` (Virginia) because:
- It's the largest and most reliable
- Newest features launch here first
- Lowest prices

### ARN (Amazon Resource Name)
Unique identifier for AWS resources. Format:
```
arn:aws:SERVICE:REGION:ACCOUNT:RESOURCE
arn:aws:lambda:us-east-1:850549932916:function:saas-security-ingest-function
```

### CloudWatch
Automatic logging service. All Lambda output goes here. View logs:
```bash
aws logs tail /aws/lambda/saas-security-ingest-function --follow
```

---

## Automation Script

I created `deploy-aws-serverless.sh` to automate all this. It:
1. Checks AWS CLI is configured
2. Creates DynamoDB table
3. Creates IAM role
4. Deploys all Lambda functions
5. Creates API Gateway
6. Sets up permissions
7. Outputs configuration

Run it: `./deploy-aws-serverless.sh`

---

## Cost Breakdown (Again)

### Free Tier (12 months):
- Lambda: 1M requests/month - FREE
- API Gateway: 1M calls/month - FREE
- DynamoDB: 25GB storage - FREE (always!)

### After Free Tier:
- Lambda: $0.20/month (for 10K req/day)
- API Gateway: $3.50/month
- DynamoDB: $2.50/month (for 100 hosts)
- **Total: ~$6.70/month**

### Traditional Alternative:
- EC2 t3.small: $15/month
- RDS db.t3.micro: $15/month
- ALB: $20/month
- **Total: ~$50/month**

**My savings: 87%!**

---

## Troubleshooting I Did

### Problem 1: "Credentials not found"
**Solution**: Ran `aws configure` and entered keys

### Problem 2: "Table already exists"
**Solution**: Used `--no-cli-pager` to avoid interactive prompts

### Problem 3: "403 Forbidden" on API
**Solution**: Added `x-api-key` header to requests

### Problem 4: Lambda timeout
**Solution**: Increased timeout from 3s to 30s

---

## Security Best Practices I Followed

1. **API Key Authentication**: Only agents with key can send data
2. **IAM Least Privilege**: Lambda only has permissions it needs
3. **HTTPS Only**: All API calls encrypted
4. **No Hardcoded Credentials**: Used environment variables
5. **CloudWatch Logging**: All actions logged for audit

---

## What I Would Add for Production

1. **VPC**: Put Lambda in private network
2. **WAF**: Web Application Firewall on API Gateway
3. **Secrets Manager**: Store API key securely
4. **CloudWatch Alarms**: Alert on errors
5. **X-Ray**: Distributed tracing
6. **DynamoDB Backups**: Point-in-time recovery
7. **Multiple Regions**: Disaster recovery

---

## Interview Talking Points

### "Why AWS?"
"AWS is the market leader with the most mature services. The free tier let me test everything at no cost, and serverless means I don't have to manage servers - perfect for a monitoring solution."

### "How long did setup take?"
"About 2-3 hours for the first manual setup. Then I automated it into a script that runs in 5-10 minutes. The automation was important because I wanted to be able to recreate the infrastructure if needed."

### "What was hardest?"
"Understanding IAM permissions. It took me a while to figure out that Lambda needed explicit permission to be called by API Gateway, and separate permission to access DynamoDB. Reading AWS documentation and error messages helped me understand the security model."

### "What would you do differently?"
"I'd use Infrastructure as Code from the start - either AWS CDK or Terraform. My bash script works but IaC tools provide better state management and rollback capabilities."

---

## Key Files Reference

- `/workspaces/saas-agent-project/deployment-config.txt` - Your actual AWS config
- `/workspaces/saas-agent-project/deploy-aws-serverless.sh` - Deployment automation
- `/workspaces/saas-agent-project/lambda-functions/` - Lambda function code

---

## Quick Test Commands

```bash
# Set your config
export AWS_PAGER=""
API_ENDPOINT="https://6n4x0gsk8j.execute-api.us-east-1.amazonaws.com/prod"

# Test APIs
curl "$API_ENDPOINT/hosts"
curl "$API_ENDPOINT/cis-results"

# View DynamoDB
aws dynamodb scan --table-name saas-hosts --region us-east-1

# Check Lambda logs
aws logs tail /aws/lambda/saas-security-ingest-function --follow
```

---

Remember: You don't need to memorize every AWS command. What's important is understanding:
- What each service does
- Why you chose it
- How they connect together
- Trade-offs you considered

Good luck! 🚀
