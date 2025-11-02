"""
Lambda: Ingest agent data
"""

import json
import boto3
import os
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('REGION', 'us-east-1'))
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'saas-hosts'))


def lambda_handler(event, context):
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Parse body
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Validate
        if 'host_details' not in body:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Missing required field: host_details'})
            }
        
        hostname = body['host_details'].get('hostname')
        if not hostname:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'error': 'Missing hostname in host_details'})
            }
        
        # Extract data
        host_details = body.get('host_details', {})
        installed_packages = body.get('installed_packages', [])
        cis_results = body.get('cis_results', [])
        agent_version = body.get('agent_version', '1.0.0')
        
        # Calculate metrics
        total_checks = len(cis_results)
        passed_checks = sum(1 for r in cis_results if r.get('status') == 'pass')
        security_score = int((passed_checks / total_checks * 100)) if total_checks > 0 else 0
        total_packages = len(installed_packages)
        
        source_ip = event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
        current_timestamp = int(datetime.utcnow().timestamp())
        
        # Check for existing host
        try:
            response = table.get_item(Key={'hostname': hostname})
            existing_item = response.get('Item')
            first_seen = existing_item.get('metadata', {}).get('first_seen', current_timestamp) if existing_item else current_timestamp
        except Exception as e:
            print(f"Error checking existing item: {e}")
            first_seen = current_timestamp
        
        # Build item
        item = {
            'hostname': hostname,
            'data': {
                'host_details': host_details,
                'installed_packages': installed_packages,
                'cis_results': cis_results
            },
            'metrics': {
                'security_score': security_score,
                'passed_checks': passed_checks,
                'total_checks': total_checks,
                'total_packages': total_packages
            },
            'metadata': {
                'agent_version': agent_version,
                'last_ip': source_ip,
                'first_seen': first_seen,
                'last_seen': current_timestamp,
                'updated_at': datetime.utcnow().isoformat()
            }
        }
        
        item = json.loads(json.dumps(item), parse_float=Decimal)
        table.put_item(Item=item)
        
        print(f"Ingested data for {hostname} (score: {security_score}%)")
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'status': 'success',
                'hostname': hostname,
                'security_score': security_score,
                'passed_checks': passed_checks,
                'total_checks': total_checks,
                'timestamp': datetime.utcnow().isoformat()
            })
        }
        
    except json.JSONDecodeError as e:
        print(f"JSON error: {e}")
        return {
            'statusCode': 400,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'error': 'Invalid JSON', 'details': str(e)})
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
