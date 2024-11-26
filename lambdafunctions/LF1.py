import json
import boto3
import base64
import time
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth

def lambda_handler(event, context):
    start_time = time.time()
    photo_id = "Unknown"
    bucket = "Unknown"

    try:
        # Extract bucket and photo key from the event
        bucket = event['Records'][0]['s3']['bucket']['name']
        photo_key = event['Records'][0]['s3']['object']['key']
        photo_id = photo_key.split('/')[-1]
        print(f"Photo upload detected: {photo_id} with key {photo_key} in bucket {bucket}")
        
        # Initialize boto3 clients
        rekognition_client = boto3.client('rekognition')
        s3_client = boto3.client('s3')
        
        # Get the image from S3
        s3_response_time = time.time()
        s3_clientobj = s3_client.get_object(Bucket=bucket, Key=photo_key)
        s3_time_taken = time.time() - s3_response_time
        image_bytes = s3_clientobj['Body'].read()
        print(f"Time taken to retrieve image from S3: {s3_time_taken:.2f} seconds")
        
        # Detect labels in the image using Rekognition
        rekognition_response_time = time.time()
        rekognition_response = rekognition_client.detect_labels(
            Image={'Bytes': image_bytes},
            MaxLabels=15,
            MinConfidence=75
        )
        rekognition_time_taken = time.time() - rekognition_response_time
        labels = rekognition_response['Labels']
        custom_labels = [label['Name'] for label in labels]
        print(f"Detected labels for {photo_id}: {custom_labels}")
        print(f"Time taken for Rekognition to detect labels: {rekognition_time_taken:.2f} seconds")
        
        user_labels = s3_clientobj['Metadata'].get('x-amz-meta-customLabels')
        if user_labels:
            custom_labels.extend(user_labels.split(','))

        # OpenSearch Service host information
        host = "search-photos-aqhp2op6yhzlq4xeitebfbauam.us-west-2.es.amazonaws.com"
        es_index = "photos"
        timeStamp = time.time()
        document = {
            'objectKey': photo_key,
            'bucket': bucket,
            'createdTimestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timeStamp)),
            'labels': custom_labels
        }
        
        # Use SigV4Auth for secure OpenSearch access
        region = "us-west-2"
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            'es',
            session_token=credentials.token
        )
        
        # Initialize OpenSearch client
        es = OpenSearch(
            hosts=[{'host': host, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )
        
        # Index the document in OpenSearch
        es_response_time = time.time()
        response = es.index(index=es_index, body=document)
        es_time_taken = time.time() - es_response_time
        print(f"Document indexed in OpenSearch, took {es_time_taken:.2f} seconds")
        print(f"OpenSearch response: {response}")

    except Exception as e:
        print(f"Error processing file {photo_id} from bucket {bucket}. Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error processing file {photo_id} from bucket {bucket}. Error: {str(e)}")
        }
    
    total_execution_time = time.time() - start_time
    print(f"Total execution time for processing {photo_id}: {total_execution_time:.2f} seconds")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'objectKey': photo_key,
            'bucket': bucket,
            'createdTimestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(timeStamp)),
            'labels': custom_labels
        })
    }
