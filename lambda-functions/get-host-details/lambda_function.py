"""
Lambda: Get host details
"""

import json
import boto3
import os
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
        hostname = event.get('pathParameters', {}).get('hostname')
        
        if not hostname:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Missing hostname parameter'})
            }
        
        response = table.get_item(Key={'hostname': hostname})
        item = response.get('Item')
        
        if not item:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Host not found', 'hostname': hostname})
            }
        
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
        
        print(f"Retrieved data for {hostname}")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps(host_data, cls=DecimalEncoder)
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
