#!/usr/bin/env python3
"""
Test fixed lambda with direct invocation.
"""
import boto3
import json

lambda_client = boto3.client('lambda', region_name='us-west-2')

print("Testing gdelt-silver-backfill with direct invocation...")
print("Date: 2022-06-08")

response = lambda_client.invoke(
    FunctionName='gdelt-silver-backfill',
    InvocationType='RequestResponse',
    Payload=json.dumps({'date': '2022-06-08'})
)

result = json.loads(response['Payload'].read())
print(f"\nStatus Code: {result['statusCode']}")

body = json.loads(result['body'])
print(f"\nResult:")
print(json.dumps(body, indent=2))

if body.get('status') == 'success':
    print(f"\n✓ Lambda execution successful!")
    print(f"  Bronze records: {body['bronze_records']:,}")
    print(f"  Silver rows: {body['wide_rows']}")
    print(f"  Silver columns: {body['wide_columns']}")
else:
    print(f"\n✗ Lambda execution failed!")
