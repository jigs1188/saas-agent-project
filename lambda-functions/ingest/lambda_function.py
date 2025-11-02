"""
Lambda Function: Ingest Security Data
--------------------------------------
This is the "front door" where security agents send their data.
When an agent runs on a Linux server, it POSTs JSON data here.
This function validates it, calculates some metrics, and stores it in DynamoDB.

This is probably the most important Lambda function because everything starts here!
"""

import json
import boto3
import os
from datetime import datetime
from decimal import Decimal

# Connect to our DynamoDB table where we store all the host data
# The environment variables (REGION, TABLE_NAME) are set automatically when we deploy
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('REGION', 'us-east-1'))
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'saas-hosts'))


def lambda_handler(event, context):
    """
    This is what runs when an agent sends data to our API
    
    The flow is: Agent → API Gateway → This Function → DynamoDB
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Parse the JSON body
        # API Gateway sends it as a string, so we convert it to a Python dict
        if isinstance(event.get('body'), str):
            body = json.loads(event['body'])
        else:
            body = event.get('body', {})
        
        # Basic validation - make sure we got the essential data
        # Without host_details, we don't even know which server this is from!
        if 'host_details' not in body:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing required field: host_details'
                })
            }
        
        # Extract the hostname - this is our primary key in the database
        hostname = body['host_details'].get('hostname')
        if not hostname:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing hostname in host_details'
                })
            }
        
        # Extract all the data from the payload
        host_details = body.get('host_details', {})
        installed_packages = body.get('installed_packages', [])
        cis_results = body.get('cis_results', [])
        agent_version = body.get('agent_version', '1.0.0')
        
        # Calculate some useful metrics
        # These make it easy to show summary stats without parsing all the detailed data
        total_checks = len(cis_results)
        passed_checks = sum(1 for r in cis_results if r.get('status') == 'pass')
        # Security score = percentage of checks that passed
        security_score = int((passed_checks / total_checks * 100)) if total_checks > 0 else 0
        total_packages = len(installed_packages)
        
        # Grab the IP address of the agent that sent this data
        # Useful for troubleshooting and security
        source_ip = event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')
        
        # Current timestamp (in seconds since epoch)
        current_timestamp = int(datetime.utcnow().timestamp())
        
        # Check if this host already exists in our database
        # If it's a new host, we'll record when we first saw it
        try:
            response = table.get_item(Key={'hostname': hostname})
            existing_item = response.get('Item')
            # Keep the original first_seen timestamp if the host exists
            first_seen = existing_item.get('metadata', {}).get('first_seen', current_timestamp) if existing_item else current_timestamp
        except Exception as e:
            print(f"Error checking existing item: {e}")
            first_seen = current_timestamp
        
        # Structure the data for DynamoDB
        # I organized it into sections: data (raw agent data), metrics (calculated stats), metadata (tracking info)
        item = {
            'hostname': hostname,  # Primary key
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
        
        # DynamoDB requires Decimal instead of float for numbers
        # This little trick converts all floats to Decimals
        item = json.loads(json.dumps(item), parse_float=Decimal)
        
        # Save it to the database!
        table.put_item(Item=item)
        
        print(f"✅ Successfully ingested data for host: {hostname} (score: {security_score}%)")
        
        # Send back a success response to the agent
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
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
        # The agent sent us malformed JSON
        print(f"❌ JSON decode error: {e}")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Invalid JSON in request body',
                'details': str(e)
            })
        }
    
    except Exception as e:
        # Something unexpected went wrong
        print(f"❌ Error processing request: {e}")
        import traceback
        traceback.print_exc()  # Print full stack trace to CloudWatch logs
        
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
