"""
Lambda Function: Get CIS Results
---------------------------------
This aggregates security check results across ALL hosts.
Instead of looking at one server, this gives us a bird's-eye view of 
security across the entire infrastructure. Very useful for finding patterns
and identifying which security checks are failing most often.
"""

import json
import boto3
import os
from decimal import Decimal
from collections import defaultdict

# Connect to DynamoDB
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('REGION', 'us-east-1'))
table = dynamodb.Table(os.environ.get('TABLE_NAME', 'saas-hosts'))

class DecimalEncoder(json.JSONEncoder):
    """Helper for converting DynamoDB Decimals to JSON-friendly numbers"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)

def lambda_handler(event, context):
    """
    Aggregates CIS security check results from all hosts
    
    This function:
    1. Scans all hosts in the database
    2. Collects all their security check results
    3. Calculates statistics (pass/fail rates, which checks fail most, etc.)
    4. Returns a summary report
    """
    print(f"Received event: {json.dumps(event)}")
    
    try:
        # Get all hosts from DynamoDB
        response = table.scan()
        items = response.get('Items', [])
        
        # Handle pagination (same as get-hosts function)
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))
        
        # Initialize counters for statistics
        total_hosts = len(items)
        total_checks = 0
        total_passed = 0
        total_failed = 0
        
        # defaultdict is handy - it creates a new dict entry automatically if it doesn't exist
        # This saves us from checking "if key exists" every time
        check_stats = defaultdict(lambda: {
            'pass_count': 0,
            'fail_count': 0,
            'pass_rate': 0,
            'failed_hosts': []
        })
        
        # Loop through each host and count pass/fail for each security check
        for item in items:
            hostname = item.get('hostname')
            cis_results = item.get('data', {}).get('cis_results', [])
            
            for result in cis_results:
                check_name = result.get('check', 'Unknown')
                status = result.get('status', 'unknown')
                
                total_checks += 1
                
                if status == 'pass':
                    total_passed += 1
                    check_stats[check_name]['pass_count'] += 1
                elif status == 'fail':
                    total_failed += 1
                    check_stats[check_name]['fail_count'] += 1
                    # Keep track of which hosts failed this check
                    check_stats[check_name]['failed_hosts'].append({
                        'hostname': hostname,
                        'evidence': result.get('evidence', 'No evidence')
                    })
        
        # Calculate pass rate percentage for each check
        # Pass rate helps us quickly identify problematic checks
        for check_name, stats in check_stats.items():
            total = stats['pass_count'] + stats['fail_count']
            if total > 0:
                stats['pass_rate'] = round((stats['pass_count'] / total) * 100, 2)
        
        # Convert to a list and sort by pass rate (worst checks first)
        # This makes it easy to see which security controls need the most attention
        checks_summary = []
        for check_name, stats in check_stats.items():
            checks_summary.append({
                'check_name': check_name,
                'pass_count': stats['pass_count'],
                'fail_count': stats['fail_count'],
                'pass_rate': stats['pass_rate'],
                'failed_hosts': stats['failed_hosts']
            })
        
        checks_summary.sort(key=lambda x: x['pass_rate'])  # Sort ascending (worst first)
        
        # Calculate overall pass rate across all checks
        overall_pass_rate = round((total_passed / total_checks * 100), 2) if total_checks > 0 else 0
        
        # Identify critical failures - checks that are failing more than 50% of the time
        # These should be the top priority for fixing
        critical_checks = [
            check for check in checks_summary 
            if check['pass_rate'] < 50
        ]
        
        # Build the response with all the aggregated data
        response_data = {
            'summary': {
                'total_hosts': total_hosts,
                'total_checks': total_checks,
                'total_passed': total_passed,
                'total_failed': total_failed,
                'overall_pass_rate': overall_pass_rate
            },
            'checks': checks_summary,
            'critical_checks': critical_checks,
            'top_failing_checks': checks_summary[:5]  # Show the 5 worst-performing checks
        }
        
        print(f"✅ Aggregated CIS results: {total_checks} checks across {total_hosts} hosts")
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_data, cls=DecimalEncoder)
        }
        
    except Exception as e:
        print(f"❌ Error retrieving CIS results: {e}")
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
