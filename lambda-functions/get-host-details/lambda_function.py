"""
Lambda Function: Get Host Details
----------------------------------
This handles GET /hosts/{hostname} endpoint
When you click on a specific host in the dashboard, this function 
returns all the detailed information about that server.
"""

import json
import boto3
import os
from decimal import Decimal

# Connect to our DynamoDB table
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('REGION', 'us-east-1'))
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'saas-hosts'))

class DecimalEncoder(json.JSONEncoder):
    """
    Same Decimal conversion issue as the other Lambda functions
    DynamoDB uses Decimal, JSON uses int/float
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    Gets detailed information for one specific host
    
    API Gateway passes the hostname from the URL as a path parameter
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Extract hostname from the URL path
        # For example, if the URL is /hosts/server01, hostname will be "server01"
        hostname = event.get('pathParameters', {}).get('hostname')
        
        if not hostname:
            # Someone called the endpoint without providing a hostname
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing hostname parameter'
                })
            }
        
        # Look up the host in DynamoDB using the hostname as the key
        response = table.get_item(Key={'hostname': hostname})
        item = response.get('Item')
        
        if not item:
            # This hostname doesn't exist in our database
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Host not found',
                    'hostname': hostname
                })
            }
        
        # Prepare the response data - organize it nicely
        # The data structure in DynamoDB is a bit nested, so we're restructuring it here
        host_data = {
            'hostname': item.get('hostname'),
            'host_details': item.get('data', {}).get('host_details', {}),
            'installed_packages': item.get('data', {}).get('installed_packages', []),
            'cis_results': item.get('data', {}).get('cis_results', []),
            'metrics': {
                'security_score': item.get('metrics', {}).get('security_score', 0),
                'passed_checks': item.get('metrics', {}).get('passed_checks', 0),
                'total_checks': item.get('metrics', {}).get('total_checks', 0),
                'total_packages': item.get('metrics', {}).get('total_packages', 0)
            },
            'metadata': {
                'agent_version': item.get('metadata', {}).get('agent_version'),
                'last_ip': item.get('metadata', {}).get('last_ip'),
                'first_seen': item.get('metadata', {}).get('first_seen'),
                'last_seen': item.get('metadata', {}).get('last_seen'),
                'updated_at': item.get('metadata', {}).get('updated_at')
            }
        }
        
        print(f"✅ Retrieved data for host: {hostname}")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(host_data, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"❌ Error retrieving host details: {e}")
        import traceback
        traceback.print_exc()
        
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
