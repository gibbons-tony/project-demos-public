#!/usr/bin/env python3
"""
Clear test environment before testing fixed lambda.
Per GDELT_LAMBDA_REFERENCE_GUIDE.md procedure.
"""
import boto3
import awswrangler as wr

print("Clearing test environment...")

# 1. Delete S3 silver files
print("\n1. Deleting S3 silver files...")
try:
    deleted = wr.s3.delete_objects(path='s3://groundtruth-capstone/processed/gdelt/silver/gdelt_wide/')
    print(f"   ✓ Deleted S3 files")
except Exception as e:
    print(f"   Note: {e}")

# 2. Delete DynamoDB SILVER_* entries
print("\n2. Deleting DynamoDB SILVER_* entries...")
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
table = dynamodb.Table('groundtruth-capstone-file-tracking')

response = table.scan(
    FilterExpression='begins_with(file_name, :prefix)',
    ExpressionAttributeValues={':prefix': 'SILVER_'}
)

deleted_count = 0
for item in response.get('Items', []):
    table.delete_item(Key={'file_name': item['file_name']})
    deleted_count += 1
    print(f"   Deleted: {item['file_name']}")

print(f"   ✓ Deleted {deleted_count} DynamoDB entries")

# 3. Purge SQS queue
print("\n3. Purging SQS queue...")
sqs = boto3.client('sqs', region_name='us-west-2')
queue_url = 'https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-silver-backfill-queue'

try:
    sqs.purge_queue(QueueUrl=queue_url)
    print(f"   ✓ Queue purged")
except Exception as e:
    print(f"   Note: {e}")

print("\n✓ Test environment cleared - ready for testing")
