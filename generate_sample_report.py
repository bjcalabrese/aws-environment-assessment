#!/usr/bin/env python3
"""Generates a realistic sample AWS Assessment report with fake data."""

import sys
import datetime
import random

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    print("pip install openpyxl"); sys.exit(1)

random.seed(42)

# ── Palette ───────────────────────────────────────────────────────────────────
C_HEADER_FILL  = "1A5276"
C_HEADER_FONT  = "FFFFFF"
C_SUBHDR_FILL  = "2E86C1"
C_ALT_ROW      = "EBF5FB"
C_WARN         = "F9E79F"
C_CRITICAL     = "FADBD8"
C_GOOD         = "D5F5E3"
C_SUMMARY_FILL = "1E8449"
C_SUMMARY_FONT = "FFFFFF"

def hf(c): return PatternFill("solid", fgColor=c)
def fn(c=C_HEADER_FONT, bold=True, sz=10): return Font(color=c, bold=bold, size=sz)

def hdr(ws, cols, row=1, fill=C_HEADER_FILL, fc=C_HEADER_FONT):
    for ci, h in enumerate(cols, 1):
        c = ws.cell(row=row, column=ci, value=h)
        c.fill = hf(fill); c.font = fn(fc)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

def autowidth(ws, mn=8, mx=52):
    for col in ws.columns:
        ltr = get_column_letter(col[0].column)
        best = mn
        for cell in col:
            if cell.value:
                best = max(best, min(mx, len(str(cell.value)) + 2))
        ws.column_dimensions[ltr].width = best

def write_rows(ws, cols, rows, start=2, color_fn=None):
    for i, row in enumerate(rows):
        r = start + i
        bg = hf(C_ALT_ROW) if i % 2 == 0 else None
        for j, col in enumerate(cols):
            cell = ws.cell(row=r, column=j+1, value=row.get(col, ""))
            if bg: cell.fill = bg
            cell.alignment = Alignment(vertical="center")
            if color_fn: color_fn(cell, col, row)

# ── Fake data ─────────────────────────────────────────────────────────────────
ACCOUNT   = "123456789012"
REGIONS   = ["us-east-1", "us-west-2", "eu-west-1"]
ASSESSED  = "2026-04-28 14:32 UTC"
ENVS      = ["Production", "Production", "Production", "Staging", "Dev"]
OWNERS    = ["platform-team", "data-team", "app-team", "infra-team", "security-team"]

def rnd_date(days_back=730):
    d = datetime.date.today() - datetime.timedelta(days=random.randint(0, days_back))
    return str(d)

def rnd_region(): return random.choice(REGIONS)
def rnd_az(region): return region + random.choice(["a","b","c"])
def rnd_env(): return random.choice(ENVS)
def rnd_owner(): return random.choice(OWNERS)

INSTANCE_TYPES = [
    "t3.micro","t3.small","t3.medium","t3.large",
    "m5.large","m5.xlarge","m5.2xlarge","m5.4xlarge",
    "c5.xlarge","c5.2xlarge","c5.4xlarge",
    "r5.large","r5.xlarge","r5.2xlarge","r5.4xlarge",
    "i3.xlarge","i3.2xlarge",
]
APP_NAMES = [
    "web-frontend","api-gateway","auth-service","payment-processor",
    "data-pipeline","ml-training","analytics-worker","log-aggregator",
    "db-primary","db-replica","cache-node","bastion-host",
    "jenkins-master","build-agent","monitoring-server","vault-server",
]

def make_ec2(n=45):
    rows = []
    for i in range(n):
        region = rnd_region()
        name   = f"{random.choice(APP_NAMES)}-{i+1:02d}"
        itype  = random.choice(INSTANCE_TYPES)
        state  = random.choices(["running","stopped","running","running","running"], k=1)[0]
        root   = random.choice([30, 50, 100, 200])
        data   = random.choice([0, 0, 100, 200, 500, 1000, 2000, 4000])
        backup = random.choices(["true","","","true","true"], k=1)[0]
        rows.append({
            "Region": region,
            "Name": name,
            "Instance ID": f"i-{random.randint(10**16,10**17-1):017x}"[:20],
            "State": state,
            "Instance Type": itype,
            "OS / Platform": random.choice(["Linux/Unix","Linux/Unix","Linux/Unix","Windows"]),
            "AZ": rnd_az(region),
            "Environment": rnd_env(),
            "Owner": rnd_owner(),
            "Volume Count": 1 + (1 if data > 0 else 0),
            "Root Disk (GiB)": root,
            "Data Disks (GiB)": data,
            "Total Storage (GiB)": root + data,
            "VPC ID": f"vpc-{random.randint(10**8,10**9):09x}",
            "Subnet ID": f"subnet-{random.randint(10**8,10**9):09x}",
            "AMI ID": f"ami-{random.randint(10**11,10**12):012x}",
            "Launch Time": rnd_date(400),
            "Tag:Backup": backup,
            "Notes": "",
        })
    return rows

def make_ebs(n=80):
    rows = []
    types = ["gp3","gp3","gp3","gp2","io1","io2","st1","sc1"]
    for i in range(n):
        region = rnd_region()
        vtype  = random.choice(types)
        size   = random.choice([30,50,100,200,500,1000,2000,4000])
        iops   = random.randint(3000,16000) if vtype in ("io1","io2","gp3") else ""
        rows.append({
            "Region": region,
            "Volume ID": f"vol-{random.randint(10**16,10**17-1):017x}"[:21],
            "Name": f"vol-{random.choice(APP_NAMES)}-{i+1:02d}",
            "State": random.choices(["in-use","in-use","in-use","available"], k=1)[0],
            "Type": vtype,
            "Size (GiB)": size,
            "IOPS": iops,
            "Throughput": 125 if vtype == "gp3" else "",
            "Encrypted": random.choice([True, True, True, False]),
            "Multi-Attach": False,
            "AZ": rnd_az(region),
            "Attached To": f"i-{random.randint(10**16,10**17-1):017x}"[:20] if random.random() > 0.1 else "",
            "Snapshot ID": f"snap-{random.randint(10**16,10**17-1):017x}"[:22] if random.random() > 0.4 else "",
            "Created": rnd_date(),
        })
    return rows

def make_rds(n=12):
    engines = [
        ("mysql","8.0.35"),("mysql","5.7.44"),
        ("postgres","15.4"),("postgres","14.9"),
        ("aurora-mysql","8.0.mysql_aurora.3.04"),
        ("aurora-postgresql","15.4"),
        ("mariadb","10.11.6"),("oracle-ee","19.0.0.0"),
        ("sqlserver-ee","15.00.4355.3"),
    ]
    classes = ["db.t3.medium","db.t3.large","db.m5.large","db.m5.xlarge",
               "db.m5.2xlarge","db.r5.large","db.r5.2xlarge","db.r5.4xlarge"]
    rows = []
    for i in range(n):
        region = rnd_region()
        eng, ver = random.choice(engines)
        is_aurora = eng.startswith("aurora")
        retention = random.choice([0, 7, 7, 14, 14, 30, 30])
        storage   = random.choice([20, 100, 500, 1000, 2000])
        rows.append({
            "Region": region,
            "DB Identifier": f"{'cluster-' if is_aurora else ''}{random.choice(['prod','stg','dev'])}-db-{i+1:02d}",
            "Engine": eng,
            "Engine Version": ver,
            "Instance Class": "N/A (cluster)" if is_aurora else random.choice(classes),
            "Status": random.choices(["available","available","available","stopped"], k=1)[0],
            "Multi-AZ": random.choice([True, True, False]),
            "Storage Type": "aurora" if is_aurora else random.choice(["gp2","gp3","io1"]),
            "Allocated Storage (GiB)": storage,
            "Max Allocated (GiB)": storage * 2 if not is_aurora else "",
            "Encrypted": random.choice([True, True, True, False]),
            "Backup Retention (days)": retention,
            "Automated Backups": "Yes" if retention > 0 else "No",
            "DB Cluster ID": f"cluster-{i+1:02d}" if is_aurora else "",
            "VPC": f"vpc-{random.randint(10**8,10**9):09x}",
            "AZ": rnd_az(region),
            "License Model": "license-included" if "sqlserver" in eng or "oracle" in eng else "general-public-license",
            "Public": random.choice([False, False, False, True]),
            "Created": rnd_date(600),
            "Notes": "",
        })
    return rows

def make_s3(n=28):
    prefixes = ["data","logs","archive","backup","assets","ml-models","terraform-state",
                "cloudtrail","access-logs","media","reports","configs","datalake"]
    rows = []
    for i in range(n):
        region = rnd_region()
        name   = f"acme-{random.choice(prefixes)}-{random.choice(['prod','stg','dev'])}-{ACCOUNT[:6]}"
        size_gib = random.choice([0.1, 5, 50, 200, 800, 2000, 8000, 15000, 50000])
        enc    = random.choice(["AES256","aws:kms","aws:kms",""])
        pub    = random.choices(["Blocked","Blocked","Blocked","Partial/Open"], k=1)[0]
        rows.append({
            "Region": region,
            "Bucket Name": f"{name}-{i:02d}",
            "Created": rnd_date(1000),
            "Size (GiB)": round(size_gib, 2),
            "Size (TiB)": round(size_gib / 1024, 4),
            "Object Count": random.randint(100, 50_000_000),
            "Versioning": random.choices(["Enabled","Enabled","Disabled","Suspended"], k=1)[0],
            "Replication": random.choice(["Yes","No","No","No"]),
            "Lifecycle Rules": random.choice(["None","1 rules","2 rules","3 rules"]),
            "Encryption": enc,
            "Public Access": pub,
            "Notes": "SENSITIVE" if "terraform-state" in name or "configs" in name else "",
        })
    return rows

def make_efs(n=6):
    rows = []
    for i in range(n):
        region = rnd_region()
        size   = random.choice([50, 200, 500, 1200, 3000, 8000])
        rows.append({
            "Region": region,
            "File System ID": f"fs-{random.randint(10**8,10**9):09x}",
            "Name": f"efs-{random.choice(['shared','jenkins','home','app'])}-{i+1:02d}",
            "State": "available",
            "Performance Mode": random.choice(["generalPurpose","maxIO"]),
            "Throughput Mode": random.choice(["bursting","elastic","provisioned"]),
            "Provisioned Throughput (MiBps)": random.choice(["", "", 128, 256]),
            "Encrypted": random.choice([True, True, False]),
            "Size (GiB)": size,
            "IA Size (GiB)": round(size * 0.3, 1),
            "Standard Size (GiB)": round(size * 0.7, 1),
            "Created": rnd_date(500),
        })
    return rows

def make_fsx(n=4):
    types = [("WINDOWS","SSD"),("ONTAP","SSD"),("LUSTRE","SSD"),("OPENZFS","SSD")]
    rows = []
    for i, (ftype, stype) in enumerate(types):
        region = rnd_region()
        cap    = random.choice([1024, 2048, 4096, 8192])
        rows.append({
            "Region": region,
            "File System ID": f"fs-{random.randint(10**8,10**9):09x}",
            "Name": f"fsx-{ftype.lower()}-{i+1:02d}",
            "Type": ftype,
            "State": "AVAILABLE",
            "Storage Type": stype,
            "Capacity (GiB)": cap,
            "Encrypted": True,
            "VPC": f"vpc-{random.randint(10**8,10**9):09x}",
            "AZs": rnd_az(rnd_region()),
            "Configuration": f"Throughput: {random.choice([64,128,256,512])} MBps | Deployment: MULTI_AZ_1",
            "Created": rnd_date(400),
        })
    return rows

def make_dynamodb(n=10):
    tables = ["users","sessions","products","orders","events",
              "audit-log","feature-flags","rate-limits","notifications","analytics"]
    rows = []
    for i, tname in enumerate(tables[:n]):
        size = random.choice([0.5, 2, 10, 50, 200, 800])
        rows.append({
            "Region": rnd_region(),
            "Table Name": f"{tname}-{'prod' if i < 6 else 'stg'}",
            "Status": "ACTIVE",
            "Billing Mode": random.choice(["PAY_PER_REQUEST","PAY_PER_REQUEST","PROVISIONED"]),
            "Size (GiB)": round(size, 2),
            "Item Count": random.randint(1000, 50_000_000),
            "RCU": random.choice(["on-demand","on-demand",100,500]),
            "WCU": random.choice(["on-demand","on-demand",50,200]),
            "PITR Enabled": random.choices(["ENABLED","DISABLED"], weights=[7,3], k=1)[0],
            "Global Tables": random.choice([True, False, False]),
            "Streams": random.choice([True, False]),
            "Encrypted": True,
            "Created": rnd_date(600),
        })
    return rows

def make_eks(n=3):
    rows = []
    configs = [
        ("prod-eks-cluster","1.29","3 node groups","m5.xlarge×6 | c5.2xlarge×4 | r5.xlarge×2"),
        ("staging-eks","1.28","2 node groups","m5.large×4 | t3.medium×2"),
        ("ml-eks-cluster","1.29","2 node groups","g4dn.xlarge×3 | m5.2xlarge×4"),
    ]
    for cname, ver, ng_label, details in configs[:n]:
        region = rnd_region()
        rows.append({
            "Region": region,
            "Cluster Name": cname,
            "Status": "ACTIVE",
            "K8s Version": ver,
            "Platform Version": f"eks.{random.randint(5,12)}",
            "Node Groups": int(ng_label[0]),
            "Total Nodes": random.randint(6, 20),
            "Node Details": details,
            "VPC": f"vpc-{random.randint(10**8,10**9):09x}",
            "Private Endpoint": True,
            "Logging": "api, audit, authenticator",
            "Created": rnd_date(400),
        })
    return rows

def make_ecs(n=5):
    names = ["prod-web","prod-api","prod-workers","staging","batch-processing"]
    rows = []
    for i, name in enumerate(names[:n]):
        rows.append({
            "Region": rnd_region(),
            "Cluster Name": name,
            "Status": "ACTIVE",
            "Active Services": random.randint(2, 20),
            "Running Tasks": random.randint(4, 60),
            "Pending Tasks": random.randint(0, 3),
            "Registered Instances": random.randint(0, 10),
            "Capacity Providers": random.choice(["FARGATE, FARGATE_SPOT","EC2","FARGATE"]),
            "Notes": "",
        })
    return rows

def make_workspaces(n=15):
    bundles = ["Value","Standard","Performance","Power","PowerPro"]
    users   = [f"user{i:03d}@acme.com" for i in range(1, n+1)]
    rows = []
    for u in users[:n]:
        bundle = random.choice(bundles)
        rows.append({
            "Region": rnd_region(),
            "Workspace ID": f"ws-{random.randint(10**8,10**9):09x}",
            "User": u,
            "State": random.choices(["AVAILABLE","AVAILABLE","STOPPED"], k=1)[0],
            "Bundle ID": f"wsb-{random.randint(10**8,10**9):09x}",
            "Directory ID": "d-9067d39a23",
            "Running Mode": random.choice(["AUTO_STOP","ALWAYS_ON"]),
            "Root Volume (GiB)": 80,
            "User Volume (GiB)": random.choice([10, 50, 100]),
            "Compute Type": bundle,
            "Protocol": "WSP",
        })
    return rows

def make_lambda(n=20):
    runtimes = ["python3.11","python3.12","nodejs20.x","nodejs18.x","java17","go1.x","dotnet8"]
    fn_names = ["resize-image","send-notification","etl-trigger","auth-validator",
                "cleanup-s3","report-generator","webhook-handler","cost-optimizer",
                "data-sync","slack-bot","alerting","billing-calc","api-authorizer",
                "rotation-fn","db-backup-trigger","cw-metric-forwarder",
                "dns-update","secret-rotator","scheduled-report","health-check"]
    rows = []
    for i, name in enumerate(fn_names[:n]):
        rows.append({
            "Region": rnd_region(),
            "Function Name": name,
            "Runtime": random.choice(runtimes),
            "Memory (MB)": random.choice([128,256,512,1024,2048,3008]),
            "Timeout (sec)": random.choice([3,10,30,60,300,900]),
            "Package Size (MB)": round(random.uniform(0.5, 45), 2),
            "Architecture": random.choice(["x86_64","arm64"]),
            "Last Modified": rnd_date(90),
            "Handler": "handler.main",
            "Description": f"Lambda function: {name.replace('-',' ')}",
        })
    return rows

def make_documentdb(n=3):
    rows = []
    for i in range(n):
        region = rnd_region()
        retention = random.choice([0, 7, 14])
        rows.append({
            "Region": region,
            "Cluster ID": f"docdb-{'prod' if i == 0 else 'stg'}-{i+1:02d}",
            "Engine": "docdb",
            "Engine Version": "5.0.0",
            "Status": "available",
            "Members": random.choice([1, 2, 3]),
            "Storage (GiB)": random.choice([10, 20, 100]),
            "Encrypted": True,
            "Backup Retention (days)": retention,
            "Multi-AZ": random.choice([True, False]),
            "VPC": f"vpc-{random.randint(10**8,10**9):09x}",
            "Created": rnd_date(500),
        })
    return rows

def make_elasticache(n=6):
    rows = []
    engines = [("redis","7.0.12"),("redis","6.2.14"),("redis","7.0.12"),
               ("memcached","1.6.22"),("redis","7.0.12"),("redis","6.2.14")]
    node_types = ["cache.t3.micro","cache.t3.medium","cache.m5.large",
                  "cache.m5.xlarge","cache.r6g.large","cache.r6g.xlarge"]
    for i in range(n):
        eng, ver = engines[i]
        region = rnd_region()
        retention = random.choice([0, 0, 1, 7])
        rows.append({
            "Region": region,
            "Cluster ID": f"ec-{eng}-{i+1:02d}",
            "Engine": eng,
            "Engine Version": ver,
            "Node Type": random.choice(node_types),
            "Status": "available",
            "Nodes": random.choice([1, 2, 3, 6]),
            "AZ": rnd_az(region),
            "Replication Group": f"rg-{eng}-{i+1:02d}" if eng == "redis" else "",
            "Encrypted at Rest": random.choice([True, True, False]),
            "Encrypted in Transit": random.choice([True, False]),
            "Backup Retention (days)": retention,
            "Created": rnd_date(400),
        })
    return rows

def make_redshift(n=3):
    rows = []
    configs = [
        ("prod-analytics","ra3.4xlarge",4),
        ("staging-dw","dc2.large",2),
        ("serverless-ns [SERVERLESS]","serverless","N/A"),
    ]
    for cid, ntype, nodes in configs[:n]:
        region = rnd_region()
        is_serverless = "SERVERLESS" in cid
        retention = random.choice([1, 7, 14])
        rows.append({
            "Region": region,
            "Cluster ID": cid,
            "Status": "available",
            "Node Type": ntype,
            "Nodes": nodes,
            "DB Name": "analytics",
            "Encrypted": True,
            "Backup Retention (days)": "" if is_serverless else retention,
            "Automated Backups": "" if is_serverless else ("Yes" if retention > 0 else "No"),
            "Public": False,
            "VPC": f"vpc-{random.randint(10**8,10**9):09x}",
            "AZ": "" if is_serverless else rnd_az(region),
            "Serverless": is_serverless,
            "Created": rnd_date(400),
        })
    return rows

def make_backup_vaults(n=5):
    names = ["Default","prod-vault","dr-vault-us-west-2","compliance-vault-7yr","staging-vault"]
    rows = []
    for i, name in enumerate(names[:n]):
        locked = "compliance" in name
        rows.append({
            "Region": rnd_region(),
            "Vault Name": name,
            "Recovery Points": random.randint(10, 4000),
            "Encrypted": True,
            "Locked": locked,
            "Min Retention (days)": 365 if locked else "",
            "Max Retention (days)": 2555 if locked else "",
            "Created": rnd_date(500),
        })
    return rows

def make_backup_plans(n=4):
    plans = [
        ("prod-daily-backup","DailyBackup","prod-vault","cron(0 5 * * ? *)","35","35"),
        ("prod-weekly-backup","WeeklyBackup","prod-vault","cron(0 5 ? * SUN *)","90","90"),
        ("dr-cross-region","DailyDR","dr-vault-us-west-2","cron(0 6 * * ? *)","14","14"),
        ("compliance-annual","AnnualCompliance","compliance-vault-7yr","cron(0 0 1 1 ? *)","2555","2555"),
    ]
    rows = []
    for pname, rname, vault, sched, delete, cold in plans[:n]:
        rows.append({
            "Region": "us-east-1",
            "Plan Name": pname,
            "Rule Name": rname,
            "Target Vault": vault,
            "Schedule": sched,
            "Start Window (min)": 60,
            "Completion Window (min)": 180,
            "Delete After (days)": delete,
            "Cold After (days)": cold,
            "Copy To Region": "us-west-2" if "dr" in pname else "",
            "Created": rnd_date(300),
        })
    return rows

# ── Summary sheet ─────────────────────────────────────────────────────────────

def build_summary(wb, data):
    ws = wb.active
    ws.title = "Summary"
    ws.sheet_properties.tabColor = C_SUMMARY_FILL

    # Title
    ws.merge_cells("A1:H1")
    t = ws["A1"]
    t.value = "AWS Environment Assessment  —  ACME Corp"
    t.font  = Font(bold=True, size=18, color=C_SUMMARY_FONT)
    t.fill  = hf(C_SUMMARY_FILL)
    t.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 38

    ws.merge_cells("A2:H2")
    s = ws["A2"]
    s.value = (f"Account: {ACCOUNT}  |  "
               f"Regions: {', '.join(REGIONS)}  |  "
               f"Generated: {ASSESSED}")
    s.font  = Font(size=10, italic=True)
    s.alignment = Alignment(horizontal="center")
    ws.row_dimensions[2].height = 18

    # Sub-header
    cols = ["Workload Type","Count","Total Storage (GiB)","Total Storage (TiB)",
            "Encrypted %","Backup Coverage","Notes"]
    hdr(ws, cols, row=4, fill=C_SUBHDR_FILL)
    ws.row_dimensions[4].height = 26

    def pct_enc(rows, key):
        if not rows: return "N/A"
        e = sum(1 for r in rows if r.get(key) in (True,"True","AES256","aws:kms","ENABLED"))
        return f"{round(e/len(rows)*100)}%"

    def bk_cov(rows, key):
        if not rows: return "N/A"
        ok = sum(1 for r in rows if str(r.get(key,"")) not in ("","No","DISABLED","0","False","Disabled"))
        return f"{round(ok/len(rows)*100)}%  ({ok}/{len(rows)})"

    ec2  = data["EC2 Instances"]
    ebs  = data["EBS Volumes"]
    snap = data["EBS Snapshots"]
    rds  = data["RDS & Aurora"]
    s3   = data["S3 Buckets"]
    efs  = data["EFS"]
    fsx  = data["FSx"]
    ddb  = data["DynamoDB"]
    rs   = data["Redshift"]
    eks  = data["EKS"]
    ecs  = data["ECS"]
    lam  = data["Lambda"]
    ws2  = data["WorkSpaces"]
    doc  = data["DocumentDB"]
    ec   = data["ElastiCache"]

    ec2_gib  = sum(r.get("Total Storage (GiB)", 0) for r in ec2)
    ebs_gib  = sum(r.get("Size (GiB)", 0) for r in ebs)
    rds_gib  = sum(r.get("Allocated Storage (GiB)", 0) or 0 for r in rds)
    s3_gib   = sum(r["Size (GiB)"] for r in s3 if isinstance(r.get("Size (GiB)"), (int,float)))
    efs_gib  = sum(r.get("Size (GiB)", 0) or 0 for r in efs)
    fsx_gib  = sum(r.get("Capacity (GiB)", 0) or 0 for r in fsx)
    ddb_gib  = sum(r.get("Size (GiB)", 0) or 0 for r in ddb)
    ws_gib   = sum((r.get("Root Volume (GiB)",0) or 0)+(r.get("User Volume (GiB)",0) or 0) for r in ws2)

    summary_rows = [
        ["EC2 Instances",    len(ec2),  round(ec2_gib,1),  round(ec2_gib/1024,3),
         pct_enc(ebs,"Encrypted"), bk_cov(ec2,"Tag:Backup"),
         "Image-level backup; app-aware processing; incremental forever"],
        ["EBS Volumes",      len(ebs),  ebs_gib,           round(ebs_gib/1024,3),
         pct_enc(ebs,"Encrypted"), "Included with EC2 policy",
         "Snapshot-based; direct-to-S3; immutable optional"],
        ["EBS Snapshots",    len(snap), 0, 0,
         "N/A", "N/A", "Review for orphaned/untagged snapshots → cost savings"],
        ["RDS / Aurora",     len(rds),  rds_gib,           round(rds_gib/1024,3),
         pct_enc(rds,"Encrypted"), bk_cov(rds,"Automated Backups"),
         "Automated snapshot management"],
        ["S3 Buckets",       len(s3),   round(s3_gib,1),   round(s3_gib/1024,3),
         pct_enc(s3,"Encryption"), bk_cov(s3,"Versioning"),
         "S3 Object backup (cross-account/region copy)"],
        ["EFS",              len(efs),  round(efs_gib,1),  round(efs_gib/1024,3),
         pct_enc(efs,"Encrypted"), "0%  (0/6)  ← GAP",
         "EFS (NFS-consistent snapshots)"],
        ["FSx",              len(fsx),  fsx_gib,           round(fsx_gib/1024,3),
         "N/A", "N/A",
         "FSx ONTAP → SnapVault; FSx Windows → VBA Windows agent"],
        ["DynamoDB",         len(ddb),  round(ddb_gib,2),  round(ddb_gib/1024,4),
         pct_enc(ddb,"Encrypted"), bk_cov(ddb,"PITR Enabled"),
         "AWS Backup + PITR; compliance monitored via API"],
        ["Redshift",         len(rs),   0, 0,
         pct_enc(rs,"Encrypted"), bk_cov(rs,"Automated Backups"),
         "AWS native snapshots; cross-region via snapshot copy"],
        ["EKS Clusters",     len(eks),  0, 0,
         "N/A", "0%  (0/3)  ← GAP",
         "Kasten K10 — PVC backup, RBAC-aware, GitOps"],
        ["ECS Clusters",     len(ecs),  0, 0,
         "N/A", "N/A",
         "Protect underlying EBS/EFS via respective policies"],
        ["Lambda Functions", len(lam),  0, 0,
         "N/A", "N/A",
         "Version pinning + IaC (Terraform/CDK) is DR strategy"],
        ["WorkSpaces",       len(ws2),  ws_gib,            round(ws_gib/1024,3),
         "N/A", "0%  (0/15)  ← GAP",
         "WorkSpaces volume snapshots"],
        ["DocumentDB",       len(doc),  0, 0,
         pct_enc(doc,"Encrypted"), bk_cov(doc,"Backup Retention (days)"),
         "AWS Backup integration; export to S3 for long-term"],
        ["ElastiCache",      len(ec),   0, 0,
         pct_enc(ec,"Encrypted at Rest"), bk_cov(ec,"Backup Retention (days)"),
         "Native snapshot only — in-memory, reconstruct from source DB"],
    ]

    for i, row_data in enumerate(summary_rows):
        r = 5 + i
        bg = hf(C_ALT_ROW) if i % 2 == 0 else None
        for j, val in enumerate(row_data):
            cell = ws.cell(row=r, column=j+1, value=val)
            if bg: cell.fill = bg
            cell.alignment = Alignment(vertical="center", wrap_text=(j==6))

        cov = ws.cell(row=r, column=6)
        cv  = str(cov.value or "")
        if "GAP" in cv or "0%" in cv:
            cov.fill = hf(C_CRITICAL); cov.font = Font(bold=True, color="8B0000")
        elif "100%" in cv:
            cov.fill = hf(C_GOOD)
        elif "N/A" not in cv:
            cov.fill = hf(C_WARN)

    # Totals
    tr = 5 + len(summary_rows)
    ws.cell(row=tr, column=1, value="TOTAL")
    ws.cell(row=tr, column=2, value=sum(r[1] for r in summary_rows))
    total_gib = sum(r[2] for r in summary_rows if isinstance(r[2],(int,float)))
    ws.cell(row=tr, column=3, value=round(total_gib,1))
    ws.cell(row=tr, column=4, value=round(total_gib/1024,3))
    for col in range(1, 8):
        c = ws.cell(row=tr, column=col)
        c.fill = hf(C_SUMMARY_FILL); c.font = Font(bold=True, color="FFFFFF")
        c.alignment = Alignment(vertical="center")

    # Sizing guidance
    nr = tr + 3
    ws.cell(row=nr, column=1, value="Sizing Guidance").font = Font(bold=True, size=12, color=C_SUMMARY_FILL)
    notes = [
        "Repo Size = Source_GiB × (1 / daily_change_rate) × (retention_days + 1) × compression_factor(0.5–0.7)",
        "Workers (Proxies): 1 worker per 10 concurrent backup tasks; 4 vCPU / 8 GB RAM per worker recommended",
        "Change Rate: Use 2–5% for EC2/EBS; 1–3% for RDS; 5–10% for DynamoDB; plan repository for 10% peak",
        "S3 Object Backup: Repository ≈ 110% of source bucket size (object metadata overhead)",
        "Immutable Storage: Enable S3 Object Lock (WORM) on backup repository bucket — critical for ransomware protection",
        "Cross-Region DR: Secondary repository sized at 100% of primary; use Backup Copy jobs with encryption",
        "EKS / Kasten K10: Repository = total PVC size × retention_days × (1 + change_rate); 1 K10 instance per cluster",
        "Backup Reporting Server: 8 vCPU / 16 GB RAM; SQL Express for <500 resources; SQL Standard/Enterprise above that",
        "ESTIMATED REPO SIZE (35-day retention, 3% change, 0.6 compression): ~"
        + str(round(total_gib * 35 * 0.03 / (1-0.6) / 1024, 1)) + " TiB",
    ]
    for i, note in enumerate(notes):
        cell = ws.cell(row=nr+1+i, column=1, value=f"  {'▶' if 'ESTIMATED' in note else '•'}  {note}")
        cell.alignment = Alignment(wrap_text=True)
        if "ESTIMATED" in note:
            cell.fill = hf(C_SUMMARY_FILL); cell.font = Font(bold=True, color="FFFFFF", size=11)
        elif i % 2 == 0:
            cell.fill = hf(C_ALT_ROW)
        ws.merge_cells(start_row=nr+1+i, start_column=1, end_row=nr+1+i, end_column=8)
        ws.row_dimensions[nr+1+i].height = 22

    autowidth(ws)
    ws.column_dimensions["G"].width = 55
    ws.column_dimensions["F"].width = 24
    ws.freeze_panes = "A5"

# ── Generic sheet ─────────────────────────────────────────────────────────────

SHEET_COLS = {
    "EC2 Instances": [
        "Region","Name","Instance ID","State","Instance Type","OS / Platform",
        "AZ","Environment","Owner","Volume Count","Root Disk (GiB)",
        "Data Disks (GiB)","Total Storage (GiB)","VPC ID","Launch Time","Tag:Backup","Notes",
    ],
    "EBS Volumes": [
        "Region","Volume ID","Name","State","Type","Size (GiB)","IOPS",
        "Throughput","Encrypted","Multi-Attach","AZ","Attached To","Snapshot ID","Created",
    ],
    "EBS Snapshots": [
        "Region","Snapshot ID","Name","Volume ID","State","Size (GiB)","Encrypted","Description","Start Time",
    ],
    "RDS & Aurora": [
        "Region","DB Identifier","Engine","Engine Version","Instance Class","Status",
        "Multi-AZ","Storage Type","Allocated Storage (GiB)","Max Allocated (GiB)",
        "Encrypted","Backup Retention (days)","Automated Backups","DB Cluster ID",
        "VPC","AZ","License Model","Public","Created","Notes",
    ],
    "S3 Buckets": [
        "Region","Bucket Name","Created","Size (GiB)","Size (TiB)",
        "Object Count","Versioning","Replication","Lifecycle Rules","Encryption","Public Access","Notes",
    ],
    "EFS": [
        "Region","File System ID","Name","State","Performance Mode","Throughput Mode",
        "Provisioned Throughput (MiBps)","Encrypted","Size (GiB)","IA Size (GiB)","Standard Size (GiB)","Created",
    ],
    "FSx": [
        "Region","File System ID","Name","Type","State","Storage Type",
        "Capacity (GiB)","Encrypted","VPC","AZs","Configuration","Created",
    ],
    "DynamoDB": [
        "Region","Table Name","Status","Billing Mode","Size (GiB)","Item Count",
        "RCU","WCU","PITR Enabled","Global Tables","Streams","Encrypted","Created",
    ],
    "Redshift": [
        "Region","Cluster ID","Status","Node Type","Nodes","DB Name",
        "Encrypted","Backup Retention (days)","Automated Backups","Public","VPC","AZ","Serverless","Created",
    ],
    "EKS": [
        "Region","Cluster Name","Status","K8s Version","Platform Version","Node Groups",
        "Total Nodes","Node Details","VPC","Private Endpoint","Logging","Created",
    ],
    "ECS": [
        "Region","Cluster Name","Status","Active Services","Running Tasks",
        "Pending Tasks","Registered Instances","Capacity Providers","Notes",
    ],
    "Lambda": [
        "Region","Function Name","Runtime","Memory (MB)","Timeout (sec)",
        "Package Size (MB)","Architecture","Last Modified","Handler","Description",
    ],
    "WorkSpaces": [
        "Region","Workspace ID","User","State","Bundle ID","Directory ID",
        "Running Mode","Root Volume (GiB)","User Volume (GiB)","Compute Type","Protocol",
    ],
    "DocumentDB": [
        "Region","Cluster ID","Engine","Engine Version","Status","Members",
        "Storage (GiB)","Encrypted","Backup Retention (days)","Multi-AZ","VPC","Created",
    ],
    "ElastiCache": [
        "Region","Cluster ID","Engine","Engine Version","Node Type","Status","Nodes","AZ",
        "Replication Group","Encrypted at Rest","Encrypted in Transit","Backup Retention (days)","Created",
    ],
    "AWS Backup Vaults": [
        "Region","Vault Name","Recovery Points","Encrypted","Locked",
        "Min Retention (days)","Max Retention (days)","Created",
    ],
    "AWS Backup Plans": [
        "Region","Plan Name","Rule Name","Target Vault","Schedule",
        "Start Window (min)","Completion Window (min)","Delete After (days)",
        "Cold After (days)","Copy To Region","Created",
    ],
}

def ec2_color(cell, col, row):
    if col == "State" and row.get("State") == "stopped":
        cell.fill = hf(C_WARN)
    if col == "Tag:Backup" and not row.get("Tag:Backup"):
        cell.fill = hf(C_CRITICAL); cell.font = Font(bold=True, color="8B0000")
    if col == "Total Storage (GiB)" and (row.get("Total Storage (GiB)",0) or 0) > 2000:
        cell.fill = hf(C_WARN)

def rds_color(cell, col, row):
    if col == "Automated Backups" and row.get("Automated Backups") == "No":
        cell.fill = hf(C_CRITICAL); cell.font = Font(bold=True, color="8B0000")
    if col == "Backup Retention (days)" and (row.get("Backup Retention (days)") or 0) == 0:
        cell.fill = hf(C_CRITICAL)
    if col == "Public" and row.get("Public") == True:
        cell.fill = hf(C_CRITICAL)
    if col == "Multi-AZ" and not row.get("Multi-AZ"):
        cell.fill = hf(C_WARN)

def s3_color(cell, col, row):
    if col == "Public Access" and row.get("Public Access") not in ("Blocked",""):
        cell.fill = hf(C_CRITICAL); cell.font = Font(bold=True, color="8B0000")
    if col == "Versioning" and row.get("Versioning") in ("Disabled","Suspended",""):
        cell.fill = hf(C_WARN)
    if col == "Encryption" and not row.get("Encryption"):
        cell.fill = hf(C_CRITICAL)

def ddb_color(cell, col, row):
    if col == "PITR Enabled" and row.get("PITR Enabled") == "DISABLED":
        cell.fill = hf(C_CRITICAL); cell.font = Font(bold=True, color="8B0000")

def ebs_color(cell, col, row):
    if col == "Encrypted" and not row.get("Encrypted"):
        cell.fill = hf(C_WARN)
    if col == "State" and row.get("State") == "available":
        cell.fill = hf(C_WARN)  # unattached volume — potential cost waste

COLOR_FNS = {
    "EC2 Instances": ec2_color,
    "EBS Volumes":   ebs_color,
    "RDS & Aurora":  rds_color,
    "S3 Buckets":    s3_color,
    "DynamoDB":      ddb_color,
}

def add_sheet(wb, name, rows, cols, color_fn=None):
    ws = wb.create_sheet(title=name[:31])
    ws.sheet_properties.tabColor = "2E86C1"

    ws.merge_cells(f"A1:{get_column_letter(len(cols))}1")
    title_cell = ws["A1"]
    title_cell.value = f"{name}  —  {len(rows)} resources"
    title_cell.font  = Font(bold=True, size=12, color=C_SUMMARY_FILL)
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 24

    hdr(ws, cols, row=2)
    ws.row_dimensions[2].height = 28
    write_rows(ws, cols, rows, start=3, color_fn=color_fn)
    ws.freeze_panes = ws.cell(row=3, column=1)
    autowidth(ws)
    return ws

# ── Main ──────────────────────────────────────────────────────────────────────

def make_snaps(n=60):
    rows = []
    for i in range(n):
        size = random.choice([30,50,100,200,500,1000])
        rows.append({
            "Region": rnd_region(),
            "Snapshot ID": f"snap-{random.randint(10**16,10**17-1):017x}"[:22],
            "Name": random.choice(["","","","automated","pre-patch","prod-backup"]),
            "Volume ID": f"vol-{random.randint(10**16,10**17-1):017x}"[:21],
            "State": "completed",
            "Size (GiB)": size,
            "Encrypted": random.choice([True,True,True,False]),
            "Description": random.choice(["Created by CreateImage","Automated snapshot","",""]),
            "Start Time": rnd_date(90),
        })
    return rows

def main():
    data = {
        "EC2 Instances":    make_ec2(45),
        "EBS Volumes":      make_ebs(80),
        "EBS Snapshots":    make_snaps(60),
        "RDS & Aurora":     make_rds(12),
        "S3 Buckets":       make_s3(28),
        "EFS":              make_efs(6),
        "FSx":              make_fsx(4),
        "DynamoDB":         make_dynamodb(10),
        "Redshift":         make_redshift(3),
        "EKS":              make_eks(3),
        "ECS":              make_ecs(5),
        "Lambda":           make_lambda(20),
        "WorkSpaces":       make_workspaces(15),
        "DocumentDB":       make_documentdb(3),
        "ElastiCache":      make_elasticache(6),
        "AWS Backup Vaults": make_backup_vaults(5),
        "AWS Backup Plans":  make_backup_plans(4),
    }

    wb = openpyxl.Workbook()
    build_summary(wb, data)

    for sheet_name, cols in SHEET_COLS.items():
        rows = data.get(sheet_name, [])
        add_sheet(wb, sheet_name, rows, cols, COLOR_FNS.get(sheet_name))

    out = "SAMPLE_AWS_Assessment_ACMECorp.xlsx"
    wb.save(out)
    print(f"✓ Sample report saved: {out}")
    print(f"\nSheets: {len(wb.sheetnames)}")
    for name in wb.sheetnames:
        print(f"  {name}")

if __name__ == "__main__":
    main()
