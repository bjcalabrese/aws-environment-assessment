# AWS Environment Assessment Tool — Quick Start

RVTools-equivalent for AWS. Produces a multi-sheet Excel workbook covering every
major workload type, colour-coded for backup gaps.

## Install

```bash
pip install -r requirements.txt
```

## Minimum IAM Permissions

The IAM user/role running this needs **read-only** access. Attach the AWS managed
policy `ReadOnlyAccess`, or use this minimal custom policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "rds:Describe*",
        "s3:ListAllMyBuckets",
        "s3:GetBucket*",
        "efs:Describe*",
        "fsx:Describe*",
        "dynamodb:List*",
        "dynamodb:Describe*",
        "redshift:Describe*",
        "redshift-serverless:List*",
        "eks:List*",
        "eks:Describe*",
        "ecs:List*",
        "ecs:Describe*",
        "lambda:ListFunctions",
        "workspaces:Describe*",
        "docdb:Describe*",
        "elasticache:Describe*",
        "backup:List*",
        "backup:Get*",
        "cloudwatch:GetMetricStatistics",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

## Usage

```bash
# Scan current region using default AWS profile
python aws_assessment.py

# Scan specific regions
python aws_assessment.py --regions us-east-1 us-west-2 eu-west-1

# Scan ALL enabled regions (thorough — can take 10-20 min on large accounts)
python aws_assessment.py --all-regions

# Use a named AWS CLI profile
python aws_assessment.py --profile customer-prod --all-regions

# Custom output filename
python aws_assessment.py --output Acme_Corp_Assessment_2024.xlsx

# Skip slow EBS snapshot enumeration on massive accounts
python aws_assessment.py --all-regions --skip-snapshots

# Increase parallel workers for faster multi-region scans
python aws_assessment.py --all-regions --workers 8
```

## Output Workbook Sheets

| Sheet | Contents |
|-------|----------|
| **Summary** | Executive overview — counts, storage totals, backup coverage % |
| **EC2 Instances** | All instances — type, storage, OS, environment tags |
| **EBS Volumes** | Every volume — type, size, IOPS, encryption, attachment |
| **EBS Snapshots** | All account-owned snapshots |
| **RDS & Aurora** | Instances + Aurora clusters — backup retention, Multi-AZ |
| **S3 Buckets** | Size, object count, versioning, replication, public access |
| **EFS** | File systems — size breakdown (Standard vs IA) |
| **FSx** | All FSx types — Windows, Lustre, ONTAP, OpenZFS |
| **DynamoDB** | Tables — PITR status, size, billing mode |
| **Redshift** | Clusters + Serverless — backup retention |
| **EKS** | Clusters — version, node groups, node counts |
| **ECS** | Clusters — running tasks, registered instances |
| **Lambda** | Functions — runtime, package size |
| **WorkSpaces** | Users — volume sizes, compute type |
| **DocumentDB** | Clusters — storage, backup retention |
| **ElastiCache** | Redis/Memcached — backup retention |
| **AWS Backup Vaults** | Existing vaults — recovery points, lock status |
| **AWS Backup Plans** | Existing policies — schedules, retention, cross-region copy |

## Colour Coding

- **Red** = backup gap or security risk (no backup, public S3, 0-day retention)
- **Yellow** = warning (instance stopped, large volumes, no versioning)
- **Green** = protected

## Sizing Reference

The Summary sheet includes a sizing guidance block. Key rules of thumb:

- **Repository size** = Source × change_rate⁻¹ × (retention + 1) × 0.6 compression
- **Workers**: 1 per 10 concurrent jobs; 4 vCPU / 8 GB RAM each
- **Immutable repo**: Enable S3 Object Lock on the backup bucket
- **EKS**: Size Kasten K10 repository = total PVC data × retention multiplier
