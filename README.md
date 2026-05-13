# AWS Environment Assessment Tool

> **Disclaimer:** This is a community sample script provided without support guarantees. It is not an official product and is not covered by any support agreement. Use at your own risk. Review the code before running it in any environment.

A read-only AWS inventory tool that scans your account and produces a single Excel workbook covering every major workload type — EC2, EBS, RDS, S3, EFS, FSx, DynamoDB, EKS, ECS, Lambda, WorkSpaces, ElastiCache, DocumentDB, Redshift, AWS Backup, KMS, Secrets Manager, SQS, and AWS Cost Explorer.

The output is a colour-coded, multi-sheet spreadsheet with a summary dashboard covering workload inventory, risk findings, backup sizing, cost breakdown, and security asset counts.

---

## How to run it

### macOS / Linux

```bash
./start-assessment.sh
```

### Windows (PowerShell)

```powershell
.\Start-Assessment.ps1
```

> Execution policy error? Run:
> `powershell -ExecutionPolicy Bypass -File .\Start-Assessment.ps1`

The launcher checks for Python 3.10+, installs all dependencies, walks you through authentication and region selection, runs the scan, and opens the workbook when done. No flags to remember.

---

## How it works

1. The launcher finds Python 3.10+ (installs it if missing) — or uses an existing `.venv/` for instant startup on repeat runs
2. Dependencies are installed automatically into a virtual environment if needed (`boto3`, `openpyxl`, `tqdm`) — handles PEP 668 / Homebrew Python automatically
3. You choose how to authenticate and which regions to scan
4. The scanner runs in parallel across all selected regions
5. A single `.xlsx` workbook is written to the current directory

The tool is **100% read-only** — it only calls `Describe*`, `List*`, and `Get*` APIs. It never creates, modifies, or deletes anything in your account.

---

## Files

| File | Purpose |
|---|---|
| `start-assessment.sh` | **Entry point** — macOS / Linux launcher |
| `Start-Assessment.ps1` | **Entry point** — Windows PowerShell launcher |
| `aws_assessment.py` | Scanner engine (called by the wizard) |
| `setup_wizard.py` | Interactive wizard (called by the launchers) |
| `requirements.txt` | Python dependencies |
| `QUICKSTART.md` | Step-by-step guide |

---

## What's in the workbook

### Summary dashboard

| Section | What it shows |
|---|---|
| **KPI tiles** | Total resources, total storage (TiB), EC2 running/stopped, RDS count, S3 count, EBS snapshots |
| **Workload inventory** | Every service with resource count, storage in GiB/TiB, encryption %, and regions |
| **EBS snapshot coverage** | Breakdown of volumes by snapshot age: Current / Aging / Stale / No Snapshot |
| **Backup sizing estimate** | Protectable GiB/TiB per service with recommended AWS backup method |
| **Risk & findings** | CRITICAL / HIGH / MEDIUM findings across all services |
| **AWS Backup infrastructure** | Vault count, recovery points, immutable vaults, backup plans, cross-region copies |
| **Region distribution** | Resource count per region |
| **Storage by service** | Which services consume the most storage |
| **Cost & usage** | Last 2 months of AWS spend by service (requires `ce:GetCostAndUsage`) |
| **Security assets** | KMS key counts, Secrets Manager rotation status, SQS queue counts |

### Detail sheets

| Sheet | What you get |
|---|---|
| **EC2 Instances** | Instance ID, type, state, OS, AZ, storage, tags, backup tag |
| **EBS Volumes** | Type, size, IOPS, encryption, attachment, snapshot coverage |
| **EBS Snapshots** | Source volume, size, encryption, age |
| **RDS & Aurora** | Engine, class, storage, backup retention, Multi-AZ, encryption, public access |
| **S3 Buckets** | Size (MiB/GiB/TiB), object count, versioning, replication, encryption, public access |
| **EFS** | Standard + IA tier sizes, throughput mode |
| **FSx** | Type (Windows/Lustre/ONTAP/OpenZFS), capacity, config |
| **DynamoDB** | Table size, item count, PITR status, billing mode, global tables |
| **Redshift** | Cluster/serverless, node type/count, backup retention |
| **EKS** | Cluster version, node groups, total nodes, instance types |
| **ECS** | Services, running/pending tasks, capacity providers |
| **Lambda** | Runtime, memory, timeout, architecture |
| **WorkSpaces** | Bundle, root/user volumes, running mode |
| **DocumentDB** | Members, storage, backup retention, encryption |
| **ElastiCache** | Redis/Memcached, node type/count, backup retention, encryption |
| **AWS Backup Vaults** | Recovery points, WORM lock, retention limits |
| **AWS Backup Plans** | Schedule, vault, retention, cross-region copy rules |
| **Cost by Service** | Monthly AWS spend broken down by service |
| **KMS Keys** | Customer vs AWS managed keys, state, spec, multi-region |
| **Secrets Manager** | Rotation status, rotation interval, last rotated/accessed |
| **SQS Queues** | Type, message depth, in-flight count, dead-letter queue |

---

## Colour coding

| Colour | Meaning |
|---|---|
| 🔴 Red | Critical gap — unencrypted EBS, public S3/RDS, no backup, no snapshot |
| 🟡 Yellow | Warning — stopped EC2, single-AZ RDS, versioning off, aging snapshot |
| 🟢 Green | Protected / compliant |

---

## IAM permissions

Simplest: attach the AWS managed `ReadOnlyAccess` policy:
```
arn:aws:iam::aws:policy/ReadOnlyAccess
```

Tighter scope — custom policy with only the actions this tool uses:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:Describe*",
        "rds:Describe*",
        "s3:ListAllMyBuckets", "s3:GetBucket*", "s3:ListBucket",
        "efs:Describe*",
        "fsx:Describe*",
        "dynamodb:List*", "dynamodb:Describe*",
        "redshift:Describe*", "redshift-serverless:List*",
        "eks:List*", "eks:Describe*",
        "ecs:List*", "ecs:Describe*",
        "lambda:ListFunctions",
        "workspaces:Describe*",
        "docdb:Describe*",
        "elasticache:Describe*",
        "backup:List*", "backup:Get*",
        "kms:ListKeys", "kms:DescribeKey", "kms:ListAliases",
        "secretsmanager:ListSecrets",
        "sqs:ListQueues", "sqs:GetQueueAttributes",
        "ce:GetCostAndUsage",
        "cloudwatch:GetMetricStatistics",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Security

### 100% read-only

Every API call made by this tool is a read operation. There are no `Create`, `Put`, `Update`, `Delete`, or `Patch` calls anywhere in the code.

Verify yourself:
```bash
grep -E "(create_|delete_|update_|patch_|put_)" aws_assessment.py
# Returns nothing
```

### Credentials stay on your machine

- Credentials are passed directly to `boto3` — the AWS SDK handles authentication
- Credentials are never printed, logged, written to disk, or transmitted anywhere other than AWS API endpoints
- Access keys entered in the wizard are set as environment variables for that process only — they are never persisted

### No data leaves your machine

- The only output is the `.xlsx` file written locally
- No HTTP calls are made to any server other than official AWS endpoints (`*.amazonaws.com`)
- No telemetry, analytics, or call-home behaviour

### What's in the output file

The workbook contains only resource **metadata** — the same information visible in the AWS Console:
- Resource names, types, sizes, SKUs, and states
- Configuration flags (encryption: yes/no, public access: yes/no, backup: yes/no)
- Regions and tags
- Counts and storage totals
- Cost data from Cost Explorer (aggregate spend per service — no line items)

It does **not** contain:
- AWS credentials, access keys, or session tokens
- S3 object contents or database rows
- Any data stored inside your resources

---

## Direct usage (advanced)

Power users who want to skip the wizard and run the scanner directly:

```bash
python aws_assessment.py [OPTIONS]

  --regions REGION [REGION ...]   Regions to scan (default: current region)
  --all-regions                   Scan all enabled regions
  --profile PROFILE               AWS CLI profile name
  --output FILENAME               Output .xlsx filename
  --workers N                     Parallel workers (default: 4)
  --skip-snapshots                Skip EBS snapshot enumeration (faster)
  --verbose                       Show detailed logging
```

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `NoCredentialsError` | No credentials found | Use auth option in wizard, or run `aws configure` |
| `AccessDenied` on a service | Missing IAM permission | Add that service's `Describe*` / `List*` action to your policy |
| `ExpiredTokenException` | Session expired | Re-authenticate using the launcher |
| S3 sizes show `N/A` | CloudWatch metrics update daily | Values appear the following day for new buckets |
| Scan is slow | Large account or many regions | Enable skip snapshots + increase workers in Step 6 |
| `pip install` blocked (PEP 668) | Homebrew or system-managed Python | Wizard auto-creates a `.venv/` — no action needed |
| `No module named venv` | Minimal Linux install missing venv | `sudo apt-get install python3-venv python3-pip` |
