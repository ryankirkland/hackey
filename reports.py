import os
import json
import requests
import gzip
import boto3
from io import BytesIO

client_id = SP_API_CLIENT
client_secret = SP_API_SECRET
refresh_token = SP_API_REFRESH

def get_access_token(client_id, client_secret, refresh_token):
    url = "https://api.amazon.com/auth/o2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret
    }

    response = requests.post(url, headers=headers, data=data)

    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"Failed to retrieve access token: {response.status_code} - {response.text}") from e

    return response.json().get('access_token')


access_token = get_access_token(client_id, client_secret, refresh_token)

def get_report_id(access_token, report_type = "GET_SALES_AND_TRAFFIC_REPORT", marketplace_ids = ["ATVPDKIKX0DER"], start_date = "2025-05-01T00:00:00Z", end_date = "2025-05-31T23:59:59Z"):
    url = "https://sellingpartnerapi-na.amazon.com/reports/2021-06-30/reports"
    
    payload = {
        "marketplaceIds": marketplace_ids,
        "reportType": report_type,
        "dataStartTime": start_date,
        "dataEndTime": end_date
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "x-amz-access-token": access_token
    }
    
    response = requests.post(url, json=payload, headers=headers)
    
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"Failed to retrieve report_id for report_type: {report_type}, marketplace IDs: {marketplace_ids}, between dates {start_date} and {end_date} - {response.status_code} - {response.text}") from e
    
    return response.json().get('reportId')

def get_report_document(access_token, report_id):
    report_url = f"https://sellingpartnerapi-na.amazon.com/reports/2021-06-30/reports/{report_id}"

    report_headers = {"accept": "application/json", "x-amz-access-token": access_token}

    get_report_response = requests.get(report_url, headers=report_headers)
    
    try:
        response.raise_for_status()
    except requests.HTTPError as e:
        raise RuntimeError(f"Failed to retrieve report document ID for {report_id} - {response.status_code} - {response.text}") from e
    
    if get_report_response.json().get('reportDocumentId') == None:
        raise RuntimeError(f"Failed to retrieve report document ID for {report_id} - report document id was null")
    
    return get_report_response.json().get('reportDocumentId')

def get_report_file(access_token, report_document_id="amzn1.spdoc.1.4.na.e70da460-53ed-46fb-a010-0459812e7355.T11WUU4596GICO.44900"):
    report_doc_url = f"https://sellingpartnerapi-na.amazon.com/reports/2021-06-30/documents/{report_document_id}"
    report_doc_headers = {"accept": "application/json", "x-amz-access-token": access_token}
    
    response = requests.get(report_doc_url, headers=report_doc_headers)
    response.raise_for_status()
    
    doc_info = response.json()
    download_url = doc_info.get("url")
    compression_algorithm = doc_info.get("compressionAlgorithm", None)

    file_response = requests.get(download_url)
    file_response.raise_for_status()

    return file_response.content, compression_algorithm

def store_raw_file(gzip_data, report_id, bucket_name='your-bucket-name'):
    s3 = boto3.client('s3')
    key = f"raw-reports/{report_id}.gz"
    s3.upload_fileobj(BytesIO(gzip_data), bucket_name, key)
    
def parse_gzip_to_json(gzip_data):
    with gzip.GzipFile(fileobj=BytesIO(gzip_data)) as f:
        content = f.read().decode('utf-8')
        return json.loads(content)
    
def store_parsed_file(parsed_data, report_id, bucket_name='your-bucket-name'):
    s3 = boto3.client('s3')
    key = f"parsed-reports/{report_id}.json"
    s3.put_object(Body=json.dumps(parsed_data), Bucket=bucket_name, Key=key)

def lambda_handler(event, context):
    access_token = get_access_token(client_id, client_secret, refresh_token)
    report_id = get_report_id(access_token)
    report_document_id = get_report_document(access_token, report_id)
    
    gzip_data, compression = get_report_file(access_token, report_document_id)
    
    store_raw_file(gzip_data, report_id)
    
    if compression == "GZIP":
        parsed_data = parse_gzip_to_json(gzip_data)
        store_parsed_file(parsed_data, report_id)
    
    return {
        "statusCode": 200,
        "body": json.dumps({"report_id": report_id, "document_id": report_document_id})
    }