import json
import logging
import boto3
import random
from elasticsearch import Elasticsearch, RequestsHttpConnection

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

region = 'us-west-2'
lex = boto3.client('lex-runtime', region_name=region)

def lambda_handler(event, context):
    q1 = event['queryStringParameters']['q'] if event.get('queryStringParameters') else ''

    print(q1);

    # Validate the query is not empty
    if not q1.strip():
        return {
            'statusCode': 400,  # Bad Request status code
            "headers": {"Access-Control-Allow-Origin": "*"},
            'body': json.dumps('Query cannot be empty')
        }

    labels = get_labels(q1)
    img_paths = get_photo_path(labels) if labels else []

    if not img_paths:
        return {
            'statusCode': 200,
            "headers": {"Access-Control-Allow-Origin": "*"},
            'body': json.dumps('No Results found')
        }
    else:
        return {
            'statusCode': 200,
            'headers': {"Access-Control-Allow-Origin": "*"},
            'body': json.dumps({
                'imagePaths': img_paths,
                'userQuery': q1,
                'labels': labels,
            }),
            'isBase64Encoded': False
        }

def get_labels(query):
    # Generate a random userID for the Lex session
    sample_string = 'pqrstuvwxyabdsfbc'
    userid = ''.join(random.choice(sample_string) for x in range(8))
    
    try:
        # Post text to Lex bot to get the response
        response = lex.post_text(
            botName='photobot',  # Replace with your actual bot name
            botAlias='prod',  # Replace with your actual bot alias
            userId=userid,
            inputText=query
        )
        
        logger.info(f"Lex response: {response}")
        
        # Extracting the 'Animal' slot value if it exists in the response
        labels = []
        if 'slots' in response:
            animal_slot = response['slots'].get('Animal', None)
            if animal_slot:
                labels.append(animal_slot)
        
        return labels

    except lex.exceptions.DependencyFailedException as e:
        # Specific exception for DependencyFailedException from AWS Lex
        logger.error(f"Lex DependencyFailedException: {str(e)}")
        # You may want to implement specific logic here, such as a retry or a fallback procedure
        return []
        
    except Exception as e:
        # General exception for any other errors that may occur
        logger.error(f"Error posting text to Lex bot: {str(e)}", exc_info=True)
        # You can handle general exceptions or perform some cleanup here if necessary
        return []  # Return an empty list in case of any error

def get_photo_path(keys):
    host = "search-photos-aqhp2op6yhzlq4xeitebfbauam.us-west-2.es.amazonaws.com"  # Replace with your actual domain endpoint
    http_auth = ('es-user', 'Password@12')
    
    es = Elasticsearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=http_auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )

    output = []
    for key in keys:
        searchData = es.search(index="photos", body={"query": {"match": {"labels": key}}})  # Adjust the index name as necessary
        for hit in searchData['hits']['hits']:
            object_key = hit['_source']['objectKey']
            if object_key not in output:
                output.append(f'https://photos-storage-bucke.s3.amazonaws.com/{object_key}')  # Adjust your bucket name as necessary
    return output
