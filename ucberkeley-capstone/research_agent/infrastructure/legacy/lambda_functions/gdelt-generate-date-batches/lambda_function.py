"""
Helper Lambda to generate date batches for Step Functions Map state.

Splits a large date range into smaller batches for parallel processing.
"""

import json
from datetime import datetime, timedelta


def lambda_handler(event, context):
    """
    Generate date batches from a date range.

    Input:
    {
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "batch_size_days": 7  # Optional, default 7
    }

    Output:
    {
        "batches": [
            {"start_date": "2024-01-01", "end_date": "2024-01-07"},
            {"start_date": "2024-01-08", "end_date": "2024-01-14"},
            ...
        ]
    }
    """
    start_date_str = event['start_date']
    end_date_str = event['end_date']
    batch_size_days = event.get('batch_size_days', 7)

    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    batches = []
    current_date = start_date

    while current_date <= end_date:
        batch_end = min(current_date + timedelta(days=batch_size_days - 1), end_date)
        batches.append({
            'start_date': current_date.strftime('%Y-%m-%d'),
            'end_date': batch_end.strftime('%Y-%m-%d')
        })
        current_date = batch_end + timedelta(days=1)

    print(f"Generated {len(batches)} batches from {start_date} to {end_date}")

    return {
        'statusCode': 200,
        'batches': batches,
        'total_batches': len(batches)
    }
