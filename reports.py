import os
from dotenv import load_dotenv
load_dotenv()
import json
import time
import requests
import gzip
import boto3
from io import BytesIO

class ReportExtractor:
    def __init__(self):
        # Load credentials from environment
        self.client_id = os.environ['SP_API_CLIENT']
        self.client_secret = os.environ['SP_API_SECRET']
        self.refresh_token = os.environ['SP_API_REFRESH']
        self.s3 = boto3.client('s3')

    def get_access_token(self):
        url = "https://api.amazon.com/auth/o2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        resp = requests.post(url, headers=headers, data=data)
        resp.raise_for_status()
        return resp.json().get('access_token')

    def get_report_id(
        self,
        access_token,
        report_type="GET_SALES_AND_TRAFFIC_REPORT",
        marketplace_ids=None,
        start_date="2025-05-01T00:00:00Z",
        end_date="2025-05-31T23:59:59Z"
    ):
        if marketplace_ids is None:
            marketplace_ids = ["ATVPDKIKX0DER"]
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
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json().get('reportId')

    def get_report_document(
        self,
        access_token,
        report_id,
        max_retries: int = 10,
        wait_seconds: int = 30
    ) -> str:
        """
        Polls GetReport until processingStatus is DONE, then returns reportDocumentId.
        Raises if the report fails or never becomes ready.
        """
        url = f"https://sellingpartnerapi-na.amazon.com/reports/2021-06-30/reports/{report_id}"
        headers = {
            "accept": "application/json",
            "x-amz-access-token": access_token
        }

        for attempt in range(1, max_retries + 1):
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            status = data.get("processingStatus")
            if status == "DONE":
                doc_id = data.get("reportDocumentId")
                if not doc_id:
                    raise RuntimeError(f"Report {report_id} is DONE but no document ID returned")
                return doc_id

            if status in ("CANCELLED", "FATAL"):
                raise RuntimeError(f"Report {report_id} failed with status: {status}")

            # not ready yet
            print(f"[{attempt}/{max_retries}] Report {report_id} status={status}; retrying in {wait_seconds}s…")
            time.sleep(wait_seconds)

        raise RuntimeError(
            f"Report {report_id} not ready after {max_retries} attempts "
            f"({max_retries * wait_seconds}s total)"
        )

    def get_report_file(self, access_token, report_document_id):
        # Fetch document metadata
        meta_url = f"https://sellingpartnerapi-na.amazon.com/reports/2021-06-30/documents/{report_document_id}"
        headers = {"accept": "application/json", "x-amz-access-token": access_token}
        resp = requests.get(meta_url, headers=headers)
        resp.raise_for_status()
        info = resp.json()
        download_url = info.get("url")
        compression = info.get("compressionAlgorithm")

        # Download the actual report
        file_resp = requests.get(download_url)
        file_resp.raise_for_status()
        return file_resp.content, compression

    def store_raw_file(self, gzip_data, report_id, bucket_name='your-bucket-name'):
        key = f"raw-reports/{report_id}.gz"
        self.s3.upload_fileobj(BytesIO(gzip_data), bucket_name, key)

    def parse_gzip_to_json(self, gzip_data):
        with gzip.GzipFile(fileobj=BytesIO(gzip_data)) as f:
            text = f.read().decode('utf-8')
        return json.loads(text)

    def store_parsed_file(self, parsed_data, report_id, bucket_name='your-bucket-name'):
        key = f"parsed-reports/{report_id}.json"
        self.s3.put_object(Body=json.dumps(parsed_data), Bucket=bucket_name, Key=key)


def lambda_handler(event, context):
    extractor = ReportExtractor()
    access_token = extractor.get_access_token()

    report_id = extractor.get_report_id(access_token)

    time.wait(3600)

    doc_id = extractor.get_report_document(access_token, report_id)

    gzip_data, compression = extractor.get_report_file(access_token, doc_id)
    extractor.store_raw_file(gzip_data, report_id)

    if compression == "GZIP":
        parsed = extractor.parse_gzip_to_json(gzip_data)
        extractor.store_parsed_file(parsed, report_id)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "report_id": report_id,
            "document_id": doc_id
        })
    }

if __name__ == "__main__":
    extractor = ReportExtractor()
    access_token = extractor.get_access_token()

    report_id = extractor.get_report_id(access_token)
    doc_id = extractor.get_report_document(access_token, report_id)

    gzip_data, compression = extractor.get_report_file(access_token, doc_id)
    print(f"{gzip_data}, {compression}")