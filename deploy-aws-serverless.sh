#!/bin/bash
################################################################################
# AWS Serverless Deployment - Complete Automation Script
# Deploys: DynamoDB + Lambda + API Gateway
# Architecture: API Gateway → Lambda → DynamoDB (as per assignment PDF)
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
PROJECT_NAME="saas-security"
TABLE_NAME="saas-hosts"
LAMBDA_RUNTIME="python3.11"
API_STAGE="prod"

# Function to print colored messages
print_info() {
    echo -e "${BLUE}ℹ ${NC}$1"
}

print_success() {
    echo -e "${GREEN}✅ ${NC}$1"
}

print_warning() {
    echo -e "${YELLOW}⚠️  ${NC}$1"
}

print_error() {
    echo -e "${RED}❌ ${NC}$1"
}

print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install it first."
        exit 1
    fi
    print_success "AWS CLI found: $(aws --version)"
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials not configured. Run 'aws configure'"
        exit 1
    fi
    
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    print_success "AWS Account ID: $ACCOUNT_ID"
    
    # Check region
    print_info "Using region: $AWS_REGION"
    
    # Check if jq is installed (optional but helpful)
    if ! command -v jq &> /dev/null; then
        print_warning "jq not found. Install it for better JSON parsing (optional)"
    else
        print_success "jq found"
    fi
}

# Create DynamoDB table
create_dynamodb_table() {
    print_header "Creating DynamoDB Table"
    
    # Check if table already exists
    if aws dynamodb describe-table --table-name $TABLE_NAME --region $AWS_REGION &> /dev/null; then
        print_warning "Table '$TABLE_NAME' already exists"
        read -p "Do you want to delete and recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Deleting existing table..."
            aws dynamodb delete-table --table-name $TABLE_NAME --region $AWS_REGION
            aws dynamodb wait table-not-exists --table-name $TABLE_NAME --region $AWS_REGION
            print_success "Table deleted"
        else
            print_info "Keeping existing table"
            return 0
        fi
    fi
    
    print_info "Creating table: $TABLE_NAME"
    
    aws dynamodb create-table \
        --table-name $TABLE_NAME \
        --attribute-definitions \
            AttributeName=hostname,AttributeType=S \
        --key-schema \
            AttributeName=hostname,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --tags Key=Project,Value=$PROJECT_NAME Key=Environment,Value=Production \
        --region $AWS_REGION
    
    print_info "Waiting for table to become active..."
    aws dynamodb wait table-exists --table-name $TABLE_NAME --region $AWS_REGION
    
    print_success "DynamoDB table created successfully"
}

# Create IAM role for Lambda
create_lambda_role() {
    print_header "Creating IAM Role for Lambda"
    
    ROLE_NAME="${PROJECT_NAME}-lambda-execution-role"
    
    # Check if role exists
    if aws iam get-role --role-name $ROLE_NAME &> /dev/null; then
        print_warning "Role '$ROLE_NAME' already exists"
        LAMBDA_ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
        print_info "Using existing role: $LAMBDA_ROLE_ARN"
        return 0
    fi
    
    # Create trust policy
    cat > /tmp/lambda-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
    
    # Create role
    print_info "Creating IAM role: $ROLE_NAME"
    aws iam create-role \
        --role-name $ROLE_NAME \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json \
        --description "Execution role for SaaS Security Lambda functions"
    
    # Attach basic execution policy
    aws iam attach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    # Create DynamoDB access policy
    cat > /tmp/lambda-dynamodb-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:BatchGetItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}",
        "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}/index/*"
      ]
    }
  ]
}
EOF
    
    aws iam put-role-policy \
        --role-name $ROLE_NAME \
        --policy-name DynamoDBAccess \
        --policy-document file:///tmp/lambda-dynamodb-policy.json
    
    LAMBDA_ROLE_ARN=$(aws iam get-role --role-name $ROLE_NAME --query 'Role.Arn' --output text)
    
    print_success "IAM role created: $LAMBDA_ROLE_ARN"
    print_warning "Waiting 10 seconds for IAM role to propagate..."
    sleep 10
}

# Deploy Lambda functions
deploy_lambda_functions() {
    print_header "Deploying Lambda Functions"
    
    LAMBDA_DIR="lambda-functions"
    
    if [ ! -d "$LAMBDA_DIR" ]; then
        print_error "Lambda functions directory not found: $LAMBDA_DIR"
        print_info "Please run this script from the project root directory"
        exit 1
    fi
    
    # Array of functions to deploy
    declare -A FUNCTIONS
    FUNCTIONS=(
        ["ingest"]="Ingests security data from agents"
        ["get-hosts"]="Returns list of all hosts"
        ["get-host-details"]="Returns detailed host information"
        ["get-cis-results"]="Returns aggregated CIS results"
    )
    
    for func_name in "${!FUNCTIONS[@]}"; do
        func_description="${FUNCTIONS[$func_name]}"
        lambda_name="${PROJECT_NAME}-${func_name}-function"
        func_dir="$LAMBDA_DIR/$func_name"
        
        print_info "Deploying: $lambda_name"
        
        # Create deployment package
        cd "$func_dir"
        zip -q -r "/tmp/${func_name}-function.zip" .
        cd - > /dev/null
        
        # Check if function exists
        if aws lambda get-function --function-name $lambda_name --region $AWS_REGION &> /dev/null; then
            print_warning "Function exists, updating code..."
            aws lambda update-function-code \
                --function-name $lambda_name \
                --zip-file "fileb:///tmp/${func_name}-function.zip" \
                --region $AWS_REGION > /dev/null
        else
            print_info "Creating new function..."
            aws lambda create-function \
                --function-name $lambda_name \
                --runtime $LAMBDA_RUNTIME \
                --role $LAMBDA_ROLE_ARN \
                --handler lambda_function.lambda_handler \
                --zip-file "fileb:///tmp/${func_name}-function.zip" \
                --timeout 30 \
                --memory-size 256 \
                --environment "Variables={TABLE_NAME=$TABLE_NAME,REGION=$AWS_REGION}" \
                --description "$func_description" \
                --region $AWS_REGION > /dev/null
        fi
        
        print_success "Deployed: $lambda_name"
    done
    
    # Cleanup
    rm -f /tmp/*-function.zip
}

# Create API Gateway
create_api_gateway() {
    print_header "Creating API Gateway"
    
    API_NAME="${PROJECT_NAME}-api"
    
    # Check if API exists
    existing_api=$(aws apigateway get-rest-apis --region $AWS_REGION --query "items[?name=='$API_NAME'].id" --output text)
    
    if [ -n "$existing_api" ]; then
        print_warning "API '$API_NAME' already exists (ID: $existing_api)"
        API_ID="$existing_api"
    else
        print_info "Creating REST API: $API_NAME"
        API_ID=$(aws apigateway create-rest-api \
            --name "$API_NAME" \
            --description "REST API for SaaS Security Monitoring" \
            --endpoint-configuration types=REGIONAL \
            --region $AWS_REGION \
            --query 'id' \
            --output text)
        print_success "API created: $API_ID"
    fi
    
    # Get root resource
    ROOT_ID=$(aws apigateway get-resources \
        --rest-api-id $API_ID \
        --region $AWS_REGION \
        --query 'items[0].id' \
        --output text)
    
    print_info "Root resource ID: $ROOT_ID"
    
    # Create resources and methods
    create_api_endpoint "/ingest" "POST" "${PROJECT_NAME}-ingest-function" "true"
    create_api_endpoint "/hosts" "GET" "${PROJECT_NAME}-get-hosts-function" "false"
    create_api_endpoint "/cis-results" "GET" "${PROJECT_NAME}-get-cis-results-function" "false"
    
    # Create /hosts/{hostname} endpoint
    create_nested_api_endpoint
}

# Helper function to create API endpoint
create_api_endpoint() {
    local path=$1
    local method=$2
    local lambda_name=$3
    local requires_api_key=$4
    
    print_info "Creating endpoint: $method $path"
    
    # Create resource
    local resource_name=$(echo $path | sed 's/\///')
    local resource_id=$(aws apigateway get-resources \
        --rest-api-id $API_ID \
        --region $AWS_REGION \
        --query "items[?path=='$path'].id" \
        --output text)
    
    if [ -z "$resource_id" ]; then
        resource_id=$(aws apigateway create-resource \
            --rest-api-id $API_ID \
            --parent-id $ROOT_ID \
            --path-part $resource_name \
            --region $AWS_REGION \
            --query 'id' \
            --output text)
    fi
    
    # Create method
    aws apigateway put-method \
        --rest-api-id $API_ID \
        --resource-id $resource_id \
        --http-method $method \
        --authorization-type NONE \
        --api-key-required $requires_api_key \
        --region $AWS_REGION &> /dev/null || true
    
    # Integrate with Lambda
    local lambda_uri="arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${lambda_name}/invocations"
    
    aws apigateway put-integration \
        --rest-api-id $API_ID \
        --resource-id $resource_id \
        --http-method $method \
        --type AWS_PROXY \
        --integration-http-method POST \
        --uri $lambda_uri \
        --region $AWS_REGION &> /dev/null || true
    
    # Grant permission
    aws lambda add-permission \
        --function-name $lambda_name \
        --statement-id "apigateway-${method}-${resource_name}-$(date +%s)" \
        --action lambda:InvokeFunction \
        --principal apigateway.amazonaws.com \
        --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*/*" \
        --region $AWS_REGION &> /dev/null || true
}

# Helper function for nested endpoint
create_nested_api_endpoint() {
    print_info "Creating endpoint: GET /hosts/{hostname}"
    
    # Get /hosts resource ID
    local hosts_id=$(aws apigateway get-resources \
        --rest-api-id $API_ID \
        --region $AWS_REGION \
        --query "items[?path=='/hosts'].id" \
        --output text)
    
    # Create {hostname} resource
    local hostname_id=$(aws apigateway get-resources \
        --rest-api-id $API_ID \
        --region $AWS_REGION \
        --query "items[?path=='/hosts/{hostname}'].id" \
        --output text)
    
    if [ -z "$hostname_id" ]; then
        hostname_id=$(aws apigateway create-resource \
            --rest-api-id $API_ID \
            --parent-id $hosts_id \
            --path-part '{hostname}' \
            --region $AWS_REGION \
            --query 'id' \
            --output text)
    fi
    
    # Create GET method
    aws apigateway put-method \
        --rest-api-id $API_ID \
        --resource-id $hostname_id \
        --http-method GET \
        --authorization-type NONE \
        --request-parameters method.request.path.hostname=true \
        --region $AWS_REGION &> /dev/null || true
    
    # Integrate with Lambda
    local lambda_uri="arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${PROJECT_NAME}-get-host-details-function/invocations"
    
    aws apigateway put-integration \
        --rest-api-id $API_ID \
        --resource-id $hostname_id \
        --http-method GET \
        --type AWS_PROXY \
        --integration-http-method POST \
        --uri $lambda_uri \
        --region $AWS_REGION &> /dev/null || true
    
    # Grant permission
    aws lambda add-permission \
        --function-name "${PROJECT_NAME}-get-host-details-function" \
        --statement-id "apigateway-GET-hostname-$(date +%s)" \
        --action lambda:InvokeFunction \
        --principal apigateway.amazonaws.com \
        --source-arn "arn:aws:execute-api:${AWS_REGION}:${ACCOUNT_ID}:${API_ID}/*/*" \
        --region $AWS_REGION &> /dev/null || true
}

# Deploy API
deploy_api() {
    print_header "Deploying API"
    
    print_info "Creating deployment to stage: $API_STAGE"
    
    aws apigateway create-deployment \
        --rest-api-id $API_ID \
        --stage-name $API_STAGE \
        --stage-description "Production stage" \
        --description "Deployment $(date '+%Y-%m-%d %H:%M:%S')" \
        --region $AWS_REGION > /dev/null
    
    API_ENDPOINT="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/${API_STAGE}"
    
    print_success "API deployed successfully"
}

# Create API key
create_api_key() {
    print_header "Creating API Key"
    
    KEY_NAME="${PROJECT_NAME}-agent-key"
    
    # Check if key exists
    existing_key=$(aws apigateway get-api-keys --region $AWS_REGION --query "items[?name=='$KEY_NAME'].id" --output text)
    
    if [ -n "$existing_key" ]; then
        print_warning "API key '$KEY_NAME' already exists"
        API_KEY=$(aws apigateway get-api-key \
            --api-key $existing_key \
            --include-value \
            --region $AWS_REGION \
            --query 'value' \
            --output text)
    else
        API_KEY_ID=$(aws apigateway create-api-key \
            --name "$KEY_NAME" \
            --description "API key for Linux security agents" \
            --enabled \
            --region $AWS_REGION \
            --query 'id' \
            --output text)
        
        API_KEY=$(aws apigateway get-api-key \
            --api-key $API_KEY_ID \
            --include-value \
            --region $AWS_REGION \
            --query 'value' \
            --output text)
        
        # Create usage plan
        USAGE_PLAN_ID=$(aws apigateway create-usage-plan \
            --name "${PROJECT_NAME}-usage-plan" \
            --description "Usage plan for security agents" \
            --throttle burstLimit=100,rateLimit=50 \
            --quota limit=10000,period=DAY \
            --api-stages apiId=$API_ID,stage=$API_STAGE \
            --region $AWS_REGION \
            --query 'id' \
            --output text)
        
        # Associate key with usage plan
        aws apigateway create-usage-plan-key \
            --usage-plan-id $USAGE_PLAN_ID \
            --key-id $API_KEY_ID \
            --key-type API_KEY \
            --region $AWS_REGION > /dev/null
    fi
    
    print_success "API Key created"
}

# Print summary
print_summary() {
    print_header "Deployment Complete! 🎉"
    
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          AWS SERVERLESS DEPLOYMENT SUMMARY                 ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}DynamoDB Table:${NC}        $TABLE_NAME"
    echo -e "${BLUE}API Gateway ID:${NC}        $API_ID"
    echo -e "${BLUE}API Endpoint:${NC}          $API_ENDPOINT"
    echo -e "${BLUE}API Key:${NC}               $API_KEY"
    echo ""
    echo -e "${YELLOW}Available Endpoints:${NC}"
    echo -e "  ${GREEN}POST${NC} $API_ENDPOINT/ingest           (requires API key)"
    echo -e "  ${GREEN}GET${NC}  $API_ENDPOINT/hosts"
    echo -e "  ${GREEN}GET${NC}  $API_ENDPOINT/hosts/{hostname}"
    echo -e "  ${GREEN}GET${NC}  $API_ENDPOINT/cis-results"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo -e "  1. Update agent configuration:"
    echo -e "     ${BLUE}export API_GATEWAY_ENDPOINT=\"$API_ENDPOINT\"${NC}"
    echo -e "     ${BLUE}export API_KEY=\"$API_KEY\"${NC}"
    echo ""
    echo -e "  2. Test the deployment:"
    echo -e "     ${BLUE}curl -X POST \"$API_ENDPOINT/ingest\" \\${NC}"
    echo -e "     ${BLUE}  -H \"x-api-key: $API_KEY\" \\${NC}"
    echo -e "     ${BLUE}  -H \"Content-Type: application/json\" \\${NC}"
    echo -e "     ${BLUE}  -d '{\"host_details\":{...}}'${NC}"
    echo ""
    echo -e "  3. Run the agent:"
    echo -e "     ${BLUE}cd saas_project/agent${NC}"
    echo -e "     ${BLUE}sudo -E python3 agent.py${NC}"
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  Save this information! You'll need it for configuration  ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    
    # Save to file
    cat > deployment-config.txt <<EOF
# AWS Deployment Configuration
# Generated: $(date)

AWS_REGION=$AWS_REGION
DYNAMODB_TABLE=$TABLE_NAME
API_GATEWAY_ID=$API_ID
API_ENDPOINT=$API_ENDPOINT
API_KEY=$API_KEY

# Environment variables for agent
export API_GATEWAY_ENDPOINT="$API_ENDPOINT"
export API_KEY="$API_KEY"

# Test commands
# List hosts:
curl "$API_ENDPOINT/hosts"

# Get specific host:
curl "$API_ENDPOINT/hosts/HOSTNAME"

# Get CIS results:
curl "$API_ENDPOINT/cis-results"

# Ingest data (with API key):
curl -X POST "$API_ENDPOINT/ingest" \\
  -H "x-api-key: $API_KEY" \\
  -H "Content-Type: application/json" \\
  -d @test-payload.json
EOF
    
    print_success "Configuration saved to: deployment-config.txt"
}

# Main execution
main() {
    print_header "AWS Serverless Deployment"
    print_info "Project: $PROJECT_NAME"
    print_info "Region: $AWS_REGION"
    echo ""
    
    check_prerequisites
    create_dynamodb_table
    create_lambda_role
    deploy_lambda_functions
    create_api_gateway
    deploy_api
    create_api_key
    print_summary
}

# Run main function
main "$@"
