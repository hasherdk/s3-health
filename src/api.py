from fastapi import FastAPI, HTTPException, Path, Query
from botocore.exceptions import ClientError
import boto3
import os
from datetime import datetime, timezone, timedelta
import re

app = FastAPI(title="S3 Health Check API")

def parse_duration(duration_str):
    """Parse duration strings like '24h', '30m', '1d' into timedelta objects"""
    if not duration_str:
        return timedelta(hours=24)  # Default 24 hours
    
    match = re.match(r'^(\d+)([hmd])$', duration_str)
    if not match:
        raise ValueError(f"Invalid duration format: {duration_str}. Use format like '24h', '60m', or '2d'")
    
    value, unit = match.groups()
    value = int(value)
    
    if unit == 'h':
        return timedelta(hours=value)
    elif unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'd':
        return timedelta(days=value)

@app.get("/health/{bucket_name}", status_code=200)
async def check_bucket_health(
    bucket_name: str = Path(..., description="Name of the S3 bucket to check"),
    max_age: str = Query("24h", description="Maximum age of newest object (format: 24h, 30m, 1d)")
):
    """
    Check if the newest object in the bucket is younger than the specified maximum age.
    Returns 200 OK if check passes, 500 Internal Server Error otherwise.
    """
    try:
        # Parse max age duration
        max_age_delta = parse_duration(max_age)
        
        # Create S3 client
        s3 = boto3.client(
            "s3",
            endpoint_url=os.environ.get("S3_ENDPOINT"),
            aws_access_key_id=os.environ.get("S3_KEY"),
            aws_secret_access_key=os.environ.get("S3_SECRET"),
        )
        
        # First check if we can access the bucket at all
        try:
            # Get all objects using pagination to ensure we don't miss any
            all_objects = []
            paginator = s3.get_paginator('list_objects_v2')
            
            # Iterate through each page of objects
            for page in paginator.paginate(Bucket=bucket_name):
                if 'Contents' in page:
                    all_objects.extend(page['Contents'])
            
            if not all_objects:
                raise HTTPException(
                    status_code=500, 
                    detail={"status": "fail", "reason": f"Bucket '{bucket_name}' is empty"}
                )
            
            # Sort objects by LastModified (newest first)
            objects = sorted(all_objects, key=lambda obj: obj['LastModified'], reverse=True)
            
            # Get the newest object
            newest_object = objects[0]
            
            # Calculate age
            now = datetime.now(timezone.utc)
            last_modified = newest_object['LastModified']
            age = now - last_modified
            
            # Check if the newest object is older than the maximum allowed age
            if age > max_age_delta:
                raise HTTPException(
                    status_code=500,
                    detail={
                        "status": "fail",
                        "reason": f"Newest object is too old ({age.total_seconds():.0f} seconds, max age: {max_age_delta.total_seconds():.0f} seconds)",
                        "newest_object": {
                            "key": newest_object['Key'],
                            "last_modified": last_modified.isoformat(),
                            "age_seconds": age.total_seconds()
                        }
                    }
                )
            
            return {
                "status": "ok",
                "newest_object": {
                    "key": newest_object['Key'],
                    "last_modified": last_modified.isoformat(),
                    "age_seconds": age.total_seconds()
                }
            }
            
        except ClientError as e:
            if "AccessDenied" in str(e) and "ListObjects" in str(e):
                # Try fallback to check if the bucket exists at least
                try:
                    s3.get_bucket_location(Bucket=bucket_name)
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "status": "fail", 
                            "reason": "Cannot check newest object age. The 's3:ListBucket' permission is required."
                        }
                    )
                except ClientError as e2:
                    raise HTTPException(
                        status_code=500, 
                        detail={"status": "fail", "reason": f"Error accessing bucket: {str(e2)}"}
                    )
            else:
                raise HTTPException(
                    status_code=500, 
                    detail={"status": "fail", "reason": f"Error accessing bucket: {str(e)}"}
                )
                
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"status": "fail", "reason": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "fail", "reason": f"Unexpected error: {str(e)}"})