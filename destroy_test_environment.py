#!/usr/bin/env python3
"""
Destroys everything created by create_test_environment.py.
Reads test_env_manifest.json to know exactly what to delete.
"""

import boto3
import json
import sys
import time

def log(msg):  print(f"  {msg}")
def ok(msg):   print(f"  ✓ {msg}")
def warn(msg): print(f"  ⚠  {msg}")

def load_manifest():
    try:
        with open("test_env_manifest.json") as f:
            return json.load(f)
    except FileNotFoundError:
        print("ERROR: test_env_manifest.json not found. Run create_test_environment.py first.")
        sys.exit(1)

def delete_s3(s3, name):
    try:
        # Delete all object versions first
        paginator = s3.get_paginator("list_object_versions")
        for page in paginator.paginate(Bucket=name):
            versions = page.get("Versions", []) + page.get("DeleteMarkers", [])
            if versions:
                s3.delete_objects(Bucket=name, Delete={
                    "Objects": [{"Key": v["Key"], "VersionId": v["VersionId"]} for v in versions]
                })
        # Delete all regular objects
        paginator2 = s3.get_paginator("list_objects_v2")
        for page in paginator2.paginate(Bucket=name):
            objs = page.get("Contents", [])
            if objs:
                s3.delete_objects(Bucket=name, Delete={
                    "Objects": [{"Key": o["Key"]} for o in objs]
                })
        s3.delete_bucket(Bucket=name)
        ok(f"S3 bucket deleted: {name}")
    except s3.exceptions.NoSuchBucket:
        ok(f"S3 bucket already gone: {name}")
    except Exception as e:
        warn(f"S3 {name}: {e}")

def delete_dynamodb(ddb, name):
    try:
        ddb.delete_table(TableName=name)
        waiter = ddb.get_waiter("table_not_exists")
        waiter.wait(TableName=name, WaiterConfig={"Delay": 3, "MaxAttempts": 20})
        ok(f"DynamoDB table deleted: {name}")
    except ddb.exceptions.ResourceNotFoundException:
        ok(f"DynamoDB table already gone: {name}")
    except Exception as e:
        warn(f"DynamoDB {name}: {e}")

def delete_lambda(lm, name):
    try:
        lm.delete_function(FunctionName=name)
        ok(f"Lambda deleted: {name}")
    except lm.exceptions.ResourceNotFoundException:
        ok(f"Lambda already gone: {name}")
    except Exception as e:
        warn(f"Lambda {name}: {e}")

def delete_iam_role(iam, name):
    try:
        # Detach all policies first
        attached = iam.list_attached_role_policies(RoleName=name)["AttachedPolicies"]
        for p in attached:
            iam.detach_role_policy(RoleName=name, PolicyArn=p["PolicyArn"])
        iam.delete_role(RoleName=name)
        ok(f"IAM role deleted: {name}")
    except iam.exceptions.NoSuchEntityException:
        ok(f"IAM role already gone: {name}")
    except Exception as e:
        warn(f"IAM role {name}: {e}")

def delete_sqs(sqs, url):
    try:
        sqs.delete_queue(QueueUrl=url)
        ok(f"SQS queue deleted: {url.split('/')[-1]}")
    except Exception as e:
        if "NonExistentQueue" in str(e):
            ok(f"SQS queue already gone")
        else:
            warn(f"SQS {url}: {e}")

def delete_ecs(ecs, name):
    try:
        ecs.delete_cluster(cluster=name)
        ok(f"ECS cluster deleted: {name}")
    except Exception as e:
        if "ClusterNotFoundException" in str(e):
            ok(f"ECS cluster already gone: {name}")
        else:
            warn(f"ECS {name}: {e}")

def delete_log_group(cw, name):
    try:
        cw.delete_log_group(logGroupName=name)
        ok(f"Log group deleted: {name}")
    except cw.exceptions.ResourceNotFoundException:
        ok(f"Log group already gone: {name}")
    except Exception as e:
        warn(f"Log group {name}: {e}")

def delete_ec2(ec2c, iid):
    try:
        ec2c.terminate_instances(InstanceIds=[iid])
        ok(f"EC2 instance terminating: {iid}")
    except Exception as e:
        warn(f"EC2 {iid}: {e}")

def delete_rds(rds, db_id):
    try:
        rds.delete_db_instance(
            DBInstanceIdentifier=db_id,
            SkipFinalSnapshot=True,
            DeleteAutomatedBackups=True,
        )
        ok(f"RDS instance deleting: {db_id} (takes ~3 min)")
    except rds.exceptions.DBInstanceNotFoundFault:
        ok(f"RDS instance already gone: {db_id}")
    except Exception as e:
        warn(f"RDS {db_id}: {e}")

def main():
    manifest = load_manifest()
    account  = manifest["account"]
    region   = manifest["region"]
    resources = manifest["resources"]

    print(f"\n{'═'*55}")
    print(f"  Destroying test environment")
    print(f"  Account  : {account}")
    print(f"  Region   : {region}")
    print(f"  Resources: {len(resources)}")
    print(f"{'═'*55}")

    confirm = input("\n  Type 'destroy' to confirm: ").strip()
    if confirm != "destroy":
        print("  Aborted."); sys.exit(0)

    session = boto3.Session(region_name=region)
    s3   = session.client("s3")
    ddb  = session.client("dynamodb")
    lm   = session.client("lambda")
    iam  = session.client("iam")
    sqs  = session.client("sqs")
    ecs  = session.client("ecs")
    cw   = session.client("logs")
    ec2c = session.client("ec2")
    rds  = session.client("rds")

    dispatch = {
        "s3_bucket":        lambda r: delete_s3(s3, r["id"]),
        "dynamodb_table":   lambda r: delete_dynamodb(ddb, r["id"]),
        "lambda_function":  lambda r: delete_lambda(lm, r["id"]),
        "iam_role":         lambda r: delete_iam_role(iam, r["id"]),
        "sqs_queue":        lambda r: delete_sqs(sqs, r["id"]),
        "ecs_cluster":      lambda r: delete_ecs(ecs, r["id"]),
        "log_group":        lambda r: delete_log_group(cw, r["id"]),
        "ec2_instance":     lambda r: delete_ec2(ec2c, r["id"]),
        "rds_instance":     lambda r: delete_rds(rds, r["id"]),
    }

    # Delete in safe order (lambdas before IAM roles)
    order = ["ec2_instance","rds_instance","lambda_function","ecs_cluster",
             "sqs_queue","dynamodb_table","s3_bucket","log_group","iam_role"]

    for rtype in order:
        items = [r for r in resources if r["type"] == rtype]
        if items:
            print(f"\n  [{rtype}]")
        for r in items:
            fn = dispatch.get(rtype)
            if fn:
                fn(r)

    import os
    os.rename("test_env_manifest.json", "test_env_manifest.json.destroyed")
    print(f"\n{'═'*55}")
    print("  ✓ All test resources destroyed.")
    print(f"{'═'*55}\n")

if __name__ == "__main__":
    main()
