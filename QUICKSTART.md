# Quick Start Guide

> **Disclaimer:** This is a community sample script provided without support guarantees. It is not an official product and is not covered by any support agreement. Use at your own risk.

Gets you from zero to a completed AWS assessment in under 10 minutes.

---

## Run it

### macOS / Linux

```bash
./start-assessment.sh
```

### Windows (PowerShell)

```powershell
.\Start-Assessment.ps1
```

> If you get an execution policy error, run:
> ```powershell
> powershell -ExecutionPolicy Bypass -File .\Start-Assessment.ps1
> ```

That's it. The launcher checks for Python, installs dependencies, walks you through credentials and region selection, runs the scan, and opens the workbook when done.

---

## What the wizard asks

| Step | What it does |
|---|---|
| **1 — Python check** | Confirms Python 3.10+ is available; shows upgrade instructions if not |
| **2 — AWS CLI check** | Checks for the AWS CLI; shows install instructions if missing |
| **3 — Dependencies** | Runs `pip install -r requirements.txt` with live output |
| **4 — Authentication** | Choose: IAM Identity Center login, named profile, environment variables, or enter access keys |
| **5 — Regions** | Choose: all regions, specific regions, or current default only |
| **6 — Scan options** | Skip snapshots toggle, worker count, output filename, verbose mode |
| **7 — Run** | Executes the scan with live output, then offers to open the workbook |

---

## Authentication options (Step 4)

| Option | When to use |
|---|---|
| **IAM Identity Center** | You use `aws login` for access (AWS SSO / Identity Center) |
| **Named profile** | You have a named profile in `~/.aws/credentials` or `~/.aws/config` |
| **Environment variables** | `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are already set in your shell |
| **Access key / secret key** | Enter credentials directly — set for this session only, never written to disk |
| **Already authenticated** | Boto3 will pick up existing credentials automatically |

---

## IAM permissions

The tool is **100% read-only** — it never creates, modifies, or deletes anything.

Simplest option — attach the AWS managed policy to your IAM user or role:
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

## Tips for large accounts

| Situation | What to do in the wizard |
|---|---|
| Account with many snapshots | Enable "Skip EBS snapshot enumeration" in Step 6 |
| Scanning 10+ regions | Increase workers to 8–10 in Step 6 |
| First run / debugging | Enable verbose mode in Step 6 |

---

## Troubleshooting

**`NoCredentialsError`**
No credentials found. Choose a different authentication option in Step 4, or run `aws configure` before launching.

**`AccessDenied` on a specific service**
Your IAM policy is missing that service's `Describe*` / `List*` action. Add it from the policy above.

**FSx / Redshift warnings**
These services require explicit opt-in. If your account hasn't subscribed to them, the warnings are suppressed automatically — nothing to fix.

**S3 sizes show `N/A` or `0`**
CloudWatch S3 metrics update once every 24 hours. Values will appear the following day for newly created buckets.

**Scan is slow**
Enable "Skip EBS snapshots" and increase workers in Step 6.

**`pip install` blocked — "externally managed environment"**
This happens on macOS with Homebrew Python or modern Linux distros (Ubuntu 23.04+, Debian 12+). The wizard detects this automatically and creates a `.venv/` folder in the project directory. No action needed — subsequent runs use the venv directly.

**`No module named venv` on Linux**
Some minimal Linux installs don't include the venv module. Install it first:
```bash
# Debian / Ubuntu
sudo apt-get install python3-venv python3-pip

# RHEL / CentOS
sudo dnf install python3-venv
```

---

## Direct usage (advanced)

If you prefer to skip the wizard and run the scanner directly:

```bash
python aws_assessment.py [OPTIONS]

Options:
  --regions REGION [REGION ...]   Regions to scan (default: current region)
  --all-regions                   Scan all enabled regions
  --profile PROFILE               AWS CLI profile name
  --output FILENAME               Output .xlsx filename
  --workers N                     Parallel workers (default: 4)
  --skip-snapshots                Skip EBS snapshot enumeration
  --verbose                       Show detailed logging
```

Examples:

```bash
# All regions, date-stamped output
python aws_assessment.py --all-regions --output "Assessment_$(date +%Y%m%d).xlsx"

# Named profile, specific regions, fastest scan
python aws_assessment.py --profile acme-corp --regions us-east-1 us-west-2 --skip-snapshots --workers 8
```
