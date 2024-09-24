import argparse
import boto3
import json
from botocore.exceptions import ClientError


class AWSManager:
    def __init__(self):
        self.ec2 = boto3.client('ec2')
        self.s3 = boto3.client('s3')
        self.route53 = boto3.client('route53')

    # EC2 Management
    def create_ec2_instance(self, instance_type='t3.nano', ami_id='ami-0a0e5d9c7acc336f1'):
        if instance_type not in ['t3.nano', 't4g.nano']:
            print(f"Invalid instance type: {instance_type}")
            return
        try:
            response = self.ec2.run_instances(
                ImageId=ami_id,
                InstanceType=instance_type,
                MaxCount=1,
                MinCount=1,
                NetworkInterfaces=[
                    {
                        'AssociatePublicIpAddress': True,
                        'DeviceIndex': 0,
                        'SubnetId': 'subnet-0532609ba3d9e75a5',
                        'Groups': ['sg-0bcf72bd953300830'],
                    }
                ],
                TagSpecifications=[
                    {
                        'ResourceType': 'instance',
                        'Tags': [
                            {'Key': 'CreatedBy', 'Value': 'alon_tool'}
                        ]
                    }
                ]
            )

            instance_id = response['Instances'][0]['InstanceId']
            print(f"Created EC2 instance: {instance_id}")
            return instance_id
        except ClientError as e:
            print(f"Error creating EC2 instance: {e}")

    def list_instances(self):
        try:
            response = self.ec2.describe_instances(
                Filters=[
                    {'Name': 'tag:CreatedBy', 'Values': ['alon_tool']}
                ]
            )
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    print(f"Instance ID: {instance['InstanceId']}, State: {instance['State']['Name']}")
        except ClientError as e:
            print(f"Error listing EC2 instances: {e}")

    def manage_instance(self, action, instance_id):
        if action not in ['start', 'stop']:
            print(f"Invalid action: {action}")
            return
        try:
            if action == 'start':
                self.ec2.start_instances(InstanceIds=[instance_id])
                print(f"Started EC2 instance: {instance_id}")
            elif action == 'stop':
                self.ec2.stop_instances(InstanceIds=[instance_id])
                print(f"Stopped EC2 instance: {instance_id}")
        except ClientError as e:
            print(f"Error managing EC2 instance: {e}")

    # S3 Management
    def create_bucket(self, bucket_name, public=False):
        try:
            self.s3.create_bucket(Bucket=bucket_name)
            if public:
                confirmation = input(
                    f"Are you sure you want to create a public S3 bucket named '{bucket_name}'? (yes/no): ").strip().lower()
                if confirmation != 'yes':
                    print("creation of your s3 bucket is canceled")
                    return
                # Configure public access block settings
                self.s3.put_public_access_block(
                    Bucket=bucket_name,
                    PublicAccessBlockConfiguration={
                        'BlockPublicAcls': False,
                        'IgnorePublicAcls': False,
                        'BlockPublicPolicy': False,
                        'RestrictPublicBuckets': False
                    }
                )

                # Create and apply the bucket policy
                bucket_policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Sid": "PublicReadGetObject",
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": "s3:GetObject",
                            "Resource": f"arn:aws:s3:::{bucket_name}/*"
                        }
                    ]
                }
                bucket_policy = json.dumps(bucket_policy)
                self.s3.put_bucket_policy(Bucket=bucket_name, Policy=bucket_policy)

            self.s3.put_bucket_tagging(
                    Bucket=bucket_name,
                    Tagging={
                        'TagSet': [
                            {'Key': 'CreatedBy', 'Value': 'alon_tool'}
                        ]
                    }
            )
            print(f"Created S3 bucket: {bucket_name}")
        except ClientError as e:
            print(f"Error creating S3 bucket: {e}")

    def list_s3_buckets(self):
        try:
            response = self.s3.list_buckets()
            for bucket in response['Buckets']:
                tags = self.s3.get_bucket_tagging(Bucket=bucket['Name'])
                tag_set = tags.get('TagSet', [])
                for tag in tag_set:
                    if tag['Key'] == 'CreatedBy' and tag['Value'] == 'alon_tool':
                        print(f"Bucket Name: {bucket['Name']}")
                        break
        except ClientError as e:
            print(f"Error listing S3 buckets: {e}")

    def upload_file_to_s3(self, file_path, bucket_name, object_key):
        try:
            # Upload the file
            self.s3.upload_file(file_path, bucket_name, object_key)
            print(
                f"Uploaded file '{file_path}' to bucket '{bucket_name}' with key '{object_key}'")
        except FileNotFoundError:
            print(f"File '{file_path}' not found")
        except ClientError as e:
            print(f"Error uploading file to S3: {e}")

    # Route53 Management
    def create_route53_zone(self, domain_name):
        try:
            response = self.route53.create_hosted_zone(
                Name=domain_name,
                CallerReference=str(hash(domain_name))
            )
            print(f"Created Route53 hosted zone: {domain_name}")
        except ClientError as e:
            print(f"Error creating Route53 hosted zone: {e}")

    def manage_route53_record(self, zone_id, action, record_name, record_type, record_value):
        if action != 'create':
            print(f"Invalid action: {action}")
            return
        try:
            self.route53.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={
                    'Changes': [
                        {
                            'Action': 'CREATE',
                            'ResourceRecordSet': {
                                'Name': record_name,
                                'Type': record_type,
                                'TTL': 60,
                                'ResourceRecords': [{'Value': record_value}]
                            }
                        }
                    ]
                }
            )
            print(f"Created DNS record: {record_name} -> {record_value}")
        except ClientError as e:
            print(f"Error managing Route53 record: {e}")


def main():
    parser = argparse.ArgumentParser(description="AWS CLI Tool")
    parser.add_argument('--resource', choices=['ec2', 's3', 'route53'],
                        help='AWS resource to manage')
    parser.add_argument('--action',
                        choices=['create', 'list', 'start', 'stop','upload'],
                        help='Action to perform')
    parser.add_argument('--instance_type', help='EC2 instance type',
                        default='t3.nano')
    parser.add_argument('--bucket_name', help='S3 bucket name')
    parser.add_argument('--public', help='Make S3 bucket public',
                        action='store_true')
    parser.add_argument('--domain_name', help='Domain name for Route53')
    parser.add_argument('--zone_id', help='Route53 hosted zone ID')
    parser.add_argument('--record_name', help='DNS record name')
    parser.add_argument('--record_type', help='DNS record type', default='A')
    parser.add_argument('--record_value', help='DNS record value')
    parser.add_argument('--instance_id', help='EC2 instance ID')
    parser.add_argument('--file_path', help='Path to the file to upload')
    parser.add_argument('--object_key',
                        help='S3 object key (file name) in the bucket')

    args = parser.parse_args()
    manager = AWSManager()

    # EC2 management
    if args.resource == 'ec2':
        if args.action == 'create':
            manager.create_ec2_instance(instance_type=args.instance_type)
        elif args.action == 'list':
            manager.list_ec2_instances()
        elif args.action in ['start', 'stop'] and args.instance_id:
            manager.manage_ec2_instance(args.action, args.instance_id)
        else:
            print("For 'start' or 'stop' action, --instance_id is required.")

    # S3 management
    elif args.resource == 's3':
        if args.action == 'create' and args.bucket_name:
            manager.create_s3_bucket(args.bucket_name, public=args.public)
        elif args.action == 'list':
            manager.list_s3_buckets()
        elif args.action == 'upload' and args.file_path and args.bucket_name and args.object_key:
            manager.upload_file_to_s3(args.file_path, args.bucket_name,
                                      args.object_key)
        else:
            print(
                "For 'create' action, --bucket_name is required. For 'upload' action, --file_path, --bucket_name, and --object_key are required.")


    # Route53 management
    elif args.resource == 'route53':
        if args.action == 'create' and args.domain_name:
            manager.create_route53_zone(args.domain_name)
        elif args.action == 'create' and args.zone_id and args.record_name and args.record_value:
            manager.manage_route53_record(args.zone_id, args.action,
                                          args.record_name, args.record_type,
                                          args.record_value)
        else:
            print("For 'create' action, --domain_name (for hosted zone) or "
                  "--zone_id, --record_name, and --record_value (for record) "
                  "are required.")


if __name__ == "__main__":
    main()
