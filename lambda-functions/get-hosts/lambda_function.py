"""
Lambda Function: Get All Hosts
-------------------------------
This function handles the GET /hosts endpoint.
When someone calls our API, this code runs in AWS Lambda and returns 
a list of all the servers that have sent us security data.

Lambda is different from a regular server - it only runs when triggered,
and AWS automatically scales it up or down based on demand.
"""

import json
import boto3
import os
from boto3.dynamodb.conditions import Attr
from decimal import Decimal

# Connect to DynamoDB (AWS's NoSQL database)
# The environment variables are set by AWS when the Lambda function is deployed
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('REGION', 'us-east-1'))
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'saas-hosts'))

class DecimalEncoder(json.JSONEncoder):
    """
    DynamoDB stores numbers as Decimal type, but JSON doesn't understand that.
    This helper class converts Decimal to regular int or float before sending the response.
    Took me a while to figure this out - kept getting serialization errors!
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            # If it's a whole number, convert to int, otherwise convert to float
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    This is the main entry point - Lambda calls this function when someone hits our API.
    
    'event' contains information about the HTTP request (headers, parameters, etc.)
    'context' contains Lambda runtime information (but we don't use it here)
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Scan the entire table to get all hosts
        # NOTE: In production with lots of data, scan() can be slow and expensive
        # A better approach would be to use a secondary index with Query
        response = table.scan()
        items = response.get('Items', [])
        
        # DynamoDB pagination - if there's more data, keep fetching
        # DynamoDB returns max 1MB at a time, so we might need multiple requests
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))
        
        # Transform the data into a cleaner format
        # We don't need to send everything, just the important summary info
        hosts = []
        for item in items:
            host_data = {
                'hostname': item.get('hostname'),
                'os_type': item.get('data', {}).get('host_details', {}).get('os_type'),
                'os_version': item.get('data', {}).get('host_details', {}).get('os_version'),
                'security_score': item.get('metrics', {}).get('security_score', 0),
                'passed_checks': item.get('metrics', {}).get('passed_checks', 0),
                'total_checks': item.get('metrics', {}).get('total_checks', 0),
                'total_packages': item.get('metrics', {}).get('total_packages', 0),
                'last_seen': item.get('metadata', {}).get('last_seen'),
                'last_ip': item.get('metadata', {}).get('last_ip'),
                'agent_version': item.get('metadata', {}).get('agent_version')
            }
            hosts.append(host_data)
        
        # Sort alphabetically by hostname - makes it easier to find hosts in the UI
        hosts.sort(key=lambda x: x.get('hostname', ''))
        
        print(f"✅ Retrieved {len(hosts)} hosts")
        
        # Return the data as a JSON HTTP response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'  # Allow requests from any origin (for CORS)
            },
            'body': json.dumps({
                'hosts': hosts,
                'count': len(hosts)
            }, cls=DecimalEncoder)  # Use our custom encoder to handle Decimals
        }
        
    except Exception as e:
        # If anything goes wrong, log the error and return an error response
        print(f"❌ Error retrieving hosts: {e}")
        import traceback
        traceback.print_exc()  # This prints the full error stack trace to CloudWatch logs
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'details': str(e)
            })
        }
