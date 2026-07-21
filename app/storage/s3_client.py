import boto3
import json
import os


from dotenv import load_dotenv

load_dotenv()

class S3Client:

    def __init__(self):

        self.s3 = boto3.client(
            "s3",
            region_name=os.getenv("AWS_REGION", "eu-north-1")
        )

        self.bucket = os.getenv("S3_BUCKET_NAME")

    # -----------------------------
    # UPLOAD JSON OBJECT
    # -----------------------------
    def upload_json(self, data, s3_path):

        self.s3.put_object(
            Bucket=self.bucket,
            Key=s3_path,
            Body=json.dumps(data, indent=2),
            ContentType="application/json"
        )

        print(f"Uploaded → s3://{self.bucket}/{s3_path}")

    # -----------------------------
    # DOWNLOAD JSON OBJECT
    # -----------------------------
    def download_json(self, s3_path):

        obj = self.s3.get_object(
            Bucket=self.bucket,
            Key=s3_path
        )

        return json.loads(obj["Body"].read().decode("utf-8"))
    
    
    
    def upload_file(self, local_path, s3_key):

        self.s3.upload_file(
            local_path,
            self.bucket,
        s3_key
    )
       
    
  