# AWS Environment Assessment Tool

RVTools-equivalent for AWS. Connects to your AWS account and produces a multi-sheet Excel workbook inventorying every major workload type — colour-coded for backup gaps, encryption posture, and risk findings.

## What it collects

| Sheet | Service |
|---|---|
| EC2 Instances | Instance type, storage, OS, tags, state |
| EBS Volumes | Type, size, IOPS, encryption, attachment |
| EBS Snapshots | All account-owned snapshots |
| RDS & Aurora | Engine, storage, backup retention, Multi-AZ |
| S3 Buckets | Size, object count, versioning, encryption, public access |
| EFS | Size (Standard + IA), throughput mode |
| FSx | Windows, Lustre, ONTAP, OpenZFS |
| DynamoDB | Size, PITR status, billing mode |
| Redshift | Clusters + Serverless, backup retention |
| EKS | Clusters, node groups, node counts |
| ECS | Clusters, running tasks, capacity providers |
| Lambda | Runtime, memory, package size |
| WorkSpaces | Users, volume sizes, compute type |
| DocumentDB | Clusters, storage, backup retention |
| ElastiCache | Redis/Memcached, backup retention |
| AWS Backup Vaults | Recovery points, lock (WORM) status |
| AWS Backup Plans | Schedules, retention, cross-region copy |

## Dashboard (Summary sheet)

- **KPI tiles** — total resources, total storage, EC2/RDS state, S3 object count, snapshot count  
- **Workload inventory** — count, GiB, TiB, encryption % per service  
- **Risk & Findings** — CRITICAL / HIGH / MEDIUM findings (unencrypted volumes, public buckets, missing backup tags, no PITR, etc.)  
- **AWS Backup infrastructure** — vault count, locked vaults, recovery points, cross-region copy rules  
- **Region distribution** — resource count per region with visual bar  
- **Storage by service** — ranked GiB breakdown  
- **EC2 state breakdown** — by state, instance type, OS  

## Colour coding

- 🔴 **Red** — backup gap or security risk (public S3, unencrypted EBS, 0-day RDS retention)
- 🟡 **Yellow** — warning (stopped instances, no versioning, unattached volumes)
- 🟢 **Green** — protected

## Install

```bash
pip install -r requirements.txt
```

## IAM Permissions

Attach the AWS managed `ReadOnlyAccess` policy, or use the minimal policy in [QUICKSTART.md](QUICKSTART.md).

## Usage

```bash
# Current region
python aws_assessment.py

# Specific regions
python aws_assessment.py --regions us-east-1 us-west-2 eu-west-1

# All enabled regions
python aws_assessment.py --all-regions

# Named AWS CLI profile
python aws_assessment.py --profile my-profile --all-regions

# Custom output filename
python aws_assessment.py --output "CustomerName_$(date +%Y%m%d).xlsx"

# Skip snapshot enumeration (faster on large accounts)
python aws_assessment.py --all-regions --skip-snapshots

# More parallel workers
python aws_assessment.py --all-regions --workers 8
```

## Test environment

Spin up realistic free-tier AWS resources to test the script against:

```bash
# Always-free resources only (S3, DynamoDB, Lambda, ECS, SQS)
python create_test_environment.py

# Include EC2 t3.micro + RDS db.t3.micro (12-month free tier)
python create_test_environment.py --include-compute

# Tear everything down when done
python destroy_test_environment.py
```

## Generate a sample report (no AWS account needed)

```bash
python generate_sample_report.py
# → SAMPLE_AWS_Assessment_ACMECorp.xlsx
```

## Files

| File | Purpose |
|---|---|
| `aws_assessment.py` | Main assessment script |
| `create_test_environment.py` | Creates free-tier test resources |
| `destroy_test_environment.py` | Tears down all test resources |
| `generate_sample_report.py` | Generates a sample report with fake data |
| `requirements.txt` | Python dependencies |
| `QUICKSTART.md` | IAM policy + detailed usage reference |

## Requirements

- Python 3.10+
- `boto3`, `openpyxl`, `tqdm`
- AWS credentials configured (`aws configure` or IAM role)
