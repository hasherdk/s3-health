from fastapi import FastAPI, HTTPException, Path, Query
from botocore.exceptions import ClientError
import boto3
import os
from datetime import datetime, timezone, timedelta
import re

# Initialize FastAPI with more complete metadata for better Swagger docs
app = FastAPI(
    title="S3 Health Check API",
    description="API for checking the health of S3 buckets by verifying the age of the newest object",
    version="1.0.0",
    docs_url="/",  # Swagger UI endpoint (default is /docs)
    redoc_url="/redoc",  # ReDoc endpoint (default is /redoc)
    openapi_url="/openapi.json",  # OpenAPI schema endpoint
    license_info={
        "name": "GPLv3",
    }
)

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

@app.get(
    "/health/{bucket_name}", 
    status_code=200,
    summary="Check S3 Bucket Health",
    response_description="Health check result with newest object information",
    tags=["Health Checks"]
)
async def check_bucket_health(
    bucket_name: str = Path(
        ..., 
        description="Name of the S3 bucket to check",
        example="my-data-bucket"
    ),
    max_age: str = Query(
        "24h", 
        description="Maximum age of newest object (format: 24h, 30m, 1d)",
        example="12h",
        regex=r"^\d+[hmd]$"
    )
):
    """
    Checks the health of an S3 bucket by verifying the age of the newest object.
    
    ## Operation
    This endpoint performs the following checks:
    - Verifies that the bucket exists and is accessible
    - Confirms the bucket contains at least one object
    - Verifies that the newest object is not older than the specified maximum age
    
    ## Response
    - Returns 200 OK with object details if the check passes
    - Returns 500 Internal Server Error if any check fails
    - Returns 400 Bad Request if input parameters are invalid
    
    ## Example
    ```
    GET /health/my-backup-bucket?max_age=12h
    ```
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