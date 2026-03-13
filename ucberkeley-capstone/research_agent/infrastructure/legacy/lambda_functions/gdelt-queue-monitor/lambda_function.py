"""
AWS Lambda Function for Monitoring SQS Queue Progress
Used by Step Functions to detect when bronze processing is complete

Returns queue depth and processing status for decision making
"""

import json
import boto3
import logging
from typing import Dict

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
sqs = boto3.client('sqs', region_name='us-west-2')


def lambda_handler(event, context):
    """
    Main Lambda handler - checks SQS queue status

    Event structure:
    {
        "queue_url": "https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-csv-backfill-queue"
    }

    Returns:
    {
        "messages_in_queue": int,
        "messages_in_flight": int,
        "total_messages": int,
        "is_empty": bool,
        "processing_complete": bool
    }
    """
    queue_url = event.get('queue_url')

    if not queue_url:
        logger.error("No queue_url provided in event")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'queue_url is required'})
        }

    try:
        logger.info(f"Checking queue status for: {queue_url}")

        # Get queue attributes
        response = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=[
                'ApproximateNumberOfMessages',
                'ApproximateNumberOfMessagesNotVisible',
                'ApproximateNumberOfMessagesDelayed'
            ]
        )

        attributes = response['Attributes']

        # Extract metrics
        messages_in_queue = int(attributes.get('ApproximateNumberOfMessages', 0))
        messages_in_flight = int(attributes.get('ApproximateNumberOfMessagesNotVisible', 0))
        messages_delayed = int(attributes.get('ApproximateNumberOfMessagesDelayed', 0))

        total_messages = messages_in_queue + messages_in_flight + messages_delayed

        # Determine status
        is_empty = total_messages == 0
        processing_complete = is_empty  # Processing complete when queue is fully drained

        result = {
            'messages_in_queue': messages_in_queue,
            'messages_in_flight': messages_in_flight,
            'messages_delayed': messages_delayed,
            'total_messages': total_messages,
            'is_empty': is_empty,
            'processing_complete': processing_complete,
            'queue_url': queue_url
        }

        logger.info(f"Queue status: {result}")

        return {
            'statusCode': 200,
            'body': json.dumps(result),
            **result  # Include result at top level for Step Functions
        }

    except Exception as e:
        logger.error(f"Error checking queue status: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


# For local testing
if __name__ == "__main__":
    test_event = {
        "queue_url": "https://sqs.us-west-2.amazonaws.com/534150427458/groundtruth-gdelt-csv-backfill-queue"
    }

    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
