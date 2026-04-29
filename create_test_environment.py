#!/usr/bin/env python3
"""
AWS Free-Tier Test Environment Creator
Creates realistic resources for testing the AWS assessment script.

Always-Free (no expiry):
  - S3 buckets (empty buckets = $0)
  - DynamoDB tables (25 GB / 25 RCU / 25 WCU always free)
  - Lambda functions (1M requests/month always free)
  - SQS queues (1M requests/month always free)
  - IAM roles
  - ECS cluster (control plane free; no tasks launched)
  - CloudWatch log groups

12-Month Free Tier (skipped by default, opt-in with --include-compute):
  - EC2 t2.micro + 8 GiB EBS gp2 (750 hrs/month)
  - RDS db.t2.micro MySQL single-AZ (750 hrs/month)
"""

import boto3
import json
import time
import argparse
import sys
import zipfile
import io
import datetime

REGION  = "us-east-1"
PREFIX  = "aws-assess-test"
ACCOUNT = None   # filled at runtime

CREATED = []   # track everything for teardown manifest

def log(msg):    print(f"  {msg}")
def ok(msg):     print(f"  ✓ {msg}")
def warn(msg):   print(f"  ⚠  {msg}")
def section(s):  print(f"\n{'─'*55}\n  {s}\n{'─'*55}")

def tag(name):
    return [
        {"Key": "Name",        "Value": name},
        {"Key": "Project",     "Value": "aws-assessment-test"},
        {"Key": "ManagedBy",   "Value": "create_test_environment.py"},
        {"Key": "Environment", "Value": "test"},
    ]

def record(rtype, rid, region=REGION, extra=None):
    CREATED.append({"type": rtype, "id": rid, "region": region, "extra": extra or {}})

# ── S3 ────────────────────────────────────────────────────────────────────────

def create_s3(s3):
    section("S3 Buckets")
    buckets = [
        (f"{PREFIX}-prod-data-{ACCOUNT}",    True,  "aws:kms",  True),
        (f"{PREFIX}-app-logs-{ACCOUNT}",     False, "AES256",   False),
        (f"{PREFIX}-terraform-state-{ACCOUNT}", True, "aws:kms", False),
        (f"{PREFIX}-assets-cdn-{ACCOUNT}",   False, "AES256",  False),
    ]
    for name, versioning, enc_algo, replication_flag in buckets:
        try:
            if REGION == "us-east-1":
                s3.create_bucket(Bucket=name)
            else:
                s3.create_bucket(
                    Bucket=name,
                    CreateBucketConfiguration={"LocationConstraint": REGION},
                )

            # Block public access
            s3.put_public_access_block(
                Bucket=name,
                PublicAccessBlockConfiguration={
                    "BlockPublicAcls": True, "IgnorePublicAcls": True,
                    "BlockPublicPolicy": True, "RestrictPublicBuckets": True,
                },
            )

            # Encryption
            if enc_algo == "aws:kms":
                s3.put_bucket_encryption(
                    Bucket=name,
                    ServerSideEncryptionConfiguration={"Rules": [{
                        "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "aws:kms"},
                        "BucketKeyEnabled": True,
                    }]},
                )
            else:
                s3.put_bucket_encryption(
                    Bucket=name,
                    ServerSideEncryptionConfiguration={"Rules": [{
                        "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"},
                    }]},
                )

            # Versioning
            if versioning:
                s3.put_bucket_versioning(
                    Bucket=name,
                    VersioningConfiguration={"Status": "Enabled"},
                )

            # Lifecycle rule (simulate real-world config)
            s3.put_bucket_lifecycle_configuration(
                Bucket=name,
                LifecycleConfiguration={"Rules": [{
                    "ID": "move-to-ia",
                    "Status": "Enabled",
                    "Filter": {"Prefix": ""},
                    "Transitions": [{"Days": 30, "StorageClass": "STANDARD_IA"}],
                    "Expiration": {"Days": 365},
                }]},
            )

            # Tagging
            s3.put_bucket_tagging(Bucket=name, Tagging={"TagSet": tag(name)})

            record("s3_bucket", name)
            ok(f"s3://{name}  (versioning={'on' if versioning else 'off'}, enc={enc_algo})")

        except s3.exceptions.BucketAlreadyOwnedByYou:
            ok(f"s3://{name}  (already exists)")
            record("s3_bucket", name)
        except Exception as e:
            warn(f"{name}: {e}")


# ── DynamoDB ──────────────────────────────────────────────────────────────────

def create_dynamodb(ddb):
    section("DynamoDB Tables  (Always Free: 25 GB / 25 RCU / 25 WCU)")
    tables = [
        ("users",    "userId",   "S", True,  "PAY_PER_REQUEST"),
        ("sessions", "sessionId","S", True,  "PAY_PER_REQUEST"),
        ("products", "productId","S", False, "PROVISIONED"),
        ("audit-log","eventId",  "S", False, "PAY_PER_REQUEST"),
    ]
    for tname, pk, pk_type, pitr, billing in tables:
        full = f"{PREFIX}-{tname}"
        try:
            kwargs = {
                "TableName": full,
                "KeySchema": [{"AttributeName": pk, "KeyType": "HASH"}],
                "AttributeDefinitions": [{"AttributeName": pk, "AttributeType": pk_type}],
                "BillingMode": billing,
                "Tags": tag(full),
            }
            if billing == "PROVISIONED":
                kwargs["ProvisionedThroughput"] = {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}

            ddb.create_table(**kwargs)

            # Wait for table to be active
            waiter = ddb.get_waiter("table_exists")
            waiter.wait(TableName=full, WaiterConfig={"Delay": 3, "MaxAttempts": 20})

            # Enable PITR on some (retry — new tables need a few seconds)
            if pitr:
                for attempt in range(6):
                    try:
                        ddb.update_continuous_backups(
                            TableName=full,
                            PointInTimeRecoverySpecification={"PointInTimeRecoveryEnabled": True},
                        )
                        break
                    except Exception:
                        if attempt < 5:
                            time.sleep(5)
                        else:
                            warn(f"PITR enable timed out for {full} — retry later")

            record("dynamodb_table", full)
            ok(f"{full}  (PITR={'on' if pitr else 'off'}, billing={billing})")

        except ddb.exceptions.ResourceInUseException:
            ok(f"{full}  (already exists)")
            record("dynamodb_table", full)
        except Exception as e:
            warn(f"{full}: {e}")


# ── Lambda ────────────────────────────────────────────────────────────────────

def make_lambda_zip(code):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("handler.py", code)
    return buf.getvalue()

def ensure_lambda_role(iam):
    role_name = f"{PREFIX}-lambda-exec-role"
    try:
        r = iam.get_role(RoleName=role_name)
        return r["Role"]["Arn"]
    except iam.exceptions.NoSuchEntityException:
        pass

    trust = json.dumps({
        "Version": "2012-10-17",
        "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"},
                       "Action": "sts:AssumeRole"}],
    })
    role = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=trust,
        Tags=tag(role_name),
    )
    iam.attach_role_policy(
        RoleName=role_name,
        PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )
    time.sleep(10)  # IAM propagation
    record("iam_role", role_name)
    return role["Role"]["Arn"]

def create_lambda(lm, iam):
    section("Lambda Functions  (Always Free: 1M requests/month)")
    role_arn = ensure_lambda_role(iam)

    functions = [
        ("data-processor",    "python3.12", "Handler processes S3 events and writes to DynamoDB"),
        ("api-authorizer",    "python3.12", "Custom Lambda authorizer for API Gateway"),
        ("scheduled-cleanup", "python3.12", "Scheduled function: purge expired sessions"),
        ("health-check",      "python3.12", "Returns service health status"),
    ]
    for fname, runtime, desc in functions:
        full = f"{PREFIX}-{fname}"
        code = f"""
import json, datetime

def handler(event, context):
    return {{
        "statusCode": 200,
        "body": json.dumps({{
            "function": "{full}",
            "description": "{desc}",
            "timestamp": str(datetime.datetime.utcnow()),
            "event": event,
        }})
    }}
"""
        try:
            lm.create_function(
                FunctionName=full,
                Runtime=runtime,
                Role=role_arn,
                Handler="handler.handler",
                Code={"ZipFile": make_lambda_zip(code)},
                Description=desc,
                Timeout=30,
                MemorySize=128,
                Architectures=["x86_64"],
                Tags={t["Key"]: t["Value"] for t in tag(full)},
            )
            record("lambda_function", full)
            ok(f"{full}  ({runtime}, 128 MB)")
        except lm.exceptions.ResourceConflictException:
            ok(f"{full}  (already exists)")
            record("lambda_function", full)
        except Exception as e:
            warn(f"{full}: {e}")


# ── SQS ───────────────────────────────────────────────────────────────────────

def create_sqs(sqs):
    section("SQS Queues  (Always Free: 1M requests/month)")
    queues = [
        (f"{PREFIX}-job-queue",        False),
        (f"{PREFIX}-notifications",    False),
        (f"{PREFIX}-dead-letter-queue",False),
    ]
    for qname, fifo in queues:
        try:
            resp = sqs.create_queue(
                QueueName=qname,
                Attributes={
                    "MessageRetentionPeriod": "86400",
                    "VisibilityTimeout":      "30",
                },
                tags={t["Key"]: t["Value"] for t in tag(qname)},
            )
            record("sqs_queue", resp["QueueUrl"])
            ok(f"{qname}")
        except Exception as e:
            if "QueueAlreadyExists" in str(e):
                ok(f"{qname}  (already exists)")
            else:
                warn(f"{qname}: {e}")


# ── ECS ───────────────────────────────────────────────────────────────────────

def ensure_ecs_service_linked_role(iam):
    try:
        iam.create_service_linked_role(AWSServiceName="ecs.amazonaws.com")
        time.sleep(8)
    except Exception as e:
        if "already exists" in str(e).lower():
            pass

def create_ecs(ecs_client, iam_client):
    section("ECS Clusters  (Control plane free — no tasks launched)")
    ensure_ecs_service_linked_role(iam_client)
    clusters = [
        f"{PREFIX}-prod-web",
        f"{PREFIX}-prod-api",
        f"{PREFIX}-staging",
    ]
    for cname in clusters:
        try:
            ecs_client.create_cluster(
                clusterName=cname,
                capacityProviders=["FARGATE", "FARGATE_SPOT"],
                defaultCapacityProviderStrategy=[
                    {"capacityProvider": "FARGATE",      "weight": 1, "base": 1},
                    {"capacityProvider": "FARGATE_SPOT", "weight": 3, "base": 0},
                ],
                tags=[{"key": t["Key"], "value": t["Value"]} for t in tag(cname)],
            )
            record("ecs_cluster", cname)
            ok(f"{cname}  (FARGATE + FARGATE_SPOT, 0 tasks running)")
        except Exception as e:
            if "already exists" in str(e).lower() or "ACTIVE" in str(e):
                ok(f"{cname}  (already exists)")
                record("ecs_cluster", cname)
            else:
                warn(f"{cname}: {e}")


# ── CloudWatch Log Groups ─────────────────────────────────────────────────────

def create_log_groups(cw):
    section("CloudWatch Log Groups  (5 GB/month free)")
    groups = [
        (f"/aws/lambda/{PREFIX}-data-processor",    7),
        (f"/aws/lambda/{PREFIX}-api-authorizer",    7),
        (f"/app/{PREFIX}/prod/application",         30),
        (f"/app/{PREFIX}/prod/access",              14),
    ]
    for gname, retention in groups:
        try:
            cw.create_log_group(logGroupName=gname,
                                tags={t["Key"]: t["Value"] for t in tag(gname)})
            cw.put_retention_policy(logGroupName=gname, retentionInDays=retention)
            record("log_group", gname)
            ok(f"{gname}  (retention={retention}d)")
        except cw.exceptions.ResourceAlreadyExistsException:
            ok(f"{gname}  (already exists)")
            record("log_group", gname)
        except Exception as e:
            warn(f"{gname}: {e}")


# ── EC2 (12-month free tier only) ─────────────────────────────────────────────

def create_ec2(ec2_client, ec2_resource):
    section("EC2 t2.micro  (12-month free tier: 750 hrs/month)")

    # Find latest Amazon Linux 2023 AMI (free)
    try:
        resp = ec2_client.describe_images(
            Filters=[
                {"Name": "name",             "Values": ["al2023-ami-*-x86_64"]},
                {"Name": "owner-alias",      "Values": ["amazon"]},
                {"Name": "state",            "Values": ["available"]},
                {"Name": "architecture",     "Values": ["x86_64"]},
            ],
            Owners=["amazon"],
        )
        images = sorted(resp["Images"], key=lambda x: x["CreationDate"], reverse=True)
        ami_id = images[0]["ImageId"]
        log(f"Using AMI: {ami_id} ({images[0]['Name']})")
    except Exception as e:
        warn(f"Could not find AMI: {e}"); return

    instances_config = [
        ("web-server-01",  "Linux/Unix",  "Production", "web-team"),
        ("app-server-01",  "Linux/Unix",  "Production", "app-team"),
        ("bastion-host",   "Linux/Unix",  "Production", "infra-team"),
    ]

    for name, _, env, owner in instances_config:
        full = f"{PREFIX}-{name}"
        try:
            instances = ec2_resource.create_instances(
                ImageId=ami_id,
                InstanceType="t3.micro",
                MinCount=1,
                MaxCount=1,
                BlockDeviceMappings=[{
                    "DeviceName": "/dev/xvda",
                    "Ebs": {
                        "VolumeSize": 30,
                        "VolumeType": "gp2",
                        "DeleteOnTermination": True,
                        "Encrypted": True,
                    },
                }],
                TagSpecifications=[{
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name",        "Value": full},
                        {"Key": "Project",     "Value": "aws-assessment-test"},
                        {"Key": "ManagedBy",   "Value": "create_test_environment.py"},
                        {"Key": "Environment", "Value": env},
                        {"Key": "Owner",       "Value": owner},
                        {"Key": "backup",      "Value": "true" if "bastion" not in name else ""},
                    ],
                }, {
                    "ResourceType": "volume",
                    "Tags": tag(f"{full}-root"),
                }],
            )
            iid = instances[0].id
            record("ec2_instance", iid)
            ok(f"{full}  ({iid}, t2.micro, 8 GiB gp2)")

        except Exception as e:
            warn(f"{full}: {e}")


# ── RDS (12-month free tier only) ─────────────────────────────────────────────

def create_rds(rds_client):
    section("RDS db.t3.micro MySQL  (12-month free tier: 750 hrs/month)")
    db_id = f"{PREFIX}-mysql-01"
    try:
        rds_client.create_db_instance(
            DBInstanceIdentifier=db_id,
            DBInstanceClass="db.t3.micro",
            Engine="mysql",
            EngineVersion="8.0",
            MasterUsername="admin",
            MasterUserPassword="AwsAssess2024",
            AllocatedStorage=20,
            StorageType="gp2",
            StorageEncrypted=True,
            BackupRetentionPeriod=0,
            MultiAZ=False,
            PubliclyAccessible=False,
            DeletionProtection=False,
            Tags=tag(db_id),
        )
        record("rds_instance", db_id)
        ok(f"{db_id}  (db.t3.micro, MySQL 8.0, 20 GiB, backup=7d)")
        warn("RDS takes ~5 minutes to provision — assessment script will find it once Available")
    except rds_client.exceptions.DBInstanceAlreadyExistsFault:
        ok(f"{db_id}  (already exists)")
        record("rds_instance", db_id)
    except Exception as e:
        warn(f"{db_id}: {e}")


# ── Manifest ──────────────────────────────────────────────────────────────────

def save_manifest():
    manifest = {
        "created_at": datetime.datetime.utcnow().isoformat(),
        "account":    ACCOUNT,
        "region":     REGION,
        "resources":  CREATED,
    }
    with open("test_env_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    ok("Manifest saved → test_env_manifest.json  (used by destroy script)")


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Create free-tier AWS test environment")
    p.add_argument("--include-compute", action="store_true",
                   help="Also create EC2 t2.micro + RDS db.t3.micro (12-month free tier)")
    p.add_argument("--region", default="us-east-1")
    return p.parse_args()

def main():
    global REGION, ACCOUNT
    args = parse_args()
    REGION = args.region

    session = boto3.Session(region_name=REGION)
    ACCOUNT = session.client("sts").get_caller_identity()["Account"]

    print(f"\n{'═'*55}")
    print(f"  AWS Free-Tier Test Environment Creator")
    print(f"  Account : {ACCOUNT}")
    print(f"  Region  : {REGION}")
    print(f"  Compute : {'YES (EC2 + RDS)' if args.include_compute else 'NO (always-free only)'}")
    print(f"{'═'*55}")

    s3    = session.client("s3")
    ddb   = session.client("dynamodb")
    lm    = session.client("lambda")
    iam   = session.client("iam")
    sqs   = session.client("sqs")
    ecs   = session.client("ecs")
    cw    = session.client("logs")

    create_s3(s3)
    create_dynamodb(ddb)
    create_lambda(lm, iam)
    create_sqs(sqs)
    create_ecs(ecs, iam)
    create_log_groups(cw)

    if args.include_compute:
        ec2c = session.client("ec2")
        ec2r = session.resource("ec2")
        rdsc = session.client("rds")
        create_ec2(ec2c, ec2r)
        create_rds(rdsc)
    else:
        print(f"\n  ℹ  Skipped EC2 + RDS (add --include-compute to create them)")
        print(f"     Both are free on new accounts (12-month free tier)")

    save_manifest()

    print(f"\n{'═'*55}")
    print(f"  ✓ Done! Run your assessment:")
    print(f"    python aws_assessment.py --regions {REGION}")
    print(f"\n  ✓ To tear down everything:")
    print(f"    python destroy_test_environment.py")
    print(f"{'═'*55}\n")


if __name__ == "__main__":
    main()
