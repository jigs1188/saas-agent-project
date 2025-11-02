"""
Lambda: Get all hosts
"""

import json
import boto3
import os
from boto3.dynamodb.conditions import Attr
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('REGION', 'us-east-1'))
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'saas-hosts'))

class DecimalEncoder(json.JSONEncoder):
    """Convert Decimal to int/float for JSON"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Scan table
        response = table.scan()
        items = response.get('Items', [])
        
        # Handle pagination
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))
        
        # Build response
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
        
        hosts.sort(key=lambda x: x.get('hostname', ''))
        
        print(f"Retrieved {len(hosts)} hosts")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'hosts': hosts, 'count': len(hosts)}, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Internal server error', 'details': str(e)})
        }
