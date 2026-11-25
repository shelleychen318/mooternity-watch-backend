# Deployment & Operations

How the backend runs on AWS, and how to operate it day to day: deploy, run
migrations, and start/stop to control cost.

> Scope: durable, shareable reference. Account-specific IDs, ARNs, and the full
> step-by-step provisioning commands live in the local-only deploy runbook
> (not committed). This document uses resource **names** and `<ACCOUNT_ID>` /
> `<REGION>` placeholders. Region is **us-east-2**.

## What's deployed

The backend is a FastAPI app (uvicorn, port 8000) packaged as a container and run
on **AWS ECS Fargate** via **ECS Express Mode**. Express provisions the cluster,
the service, an internet-facing Application Load Balancer with an HTTPS listener,
and a stable public hostname.

| Piece | Name / value |
|---|---|
| Container registry | ECR repo `moo-backend` |
| ECS cluster | `default` |
| ECS service | `moo-backend-9479` |
| Task definition family | `default-moo-backend-9479` (Express-managed; container name `Main`) |
| Public hostname | the Express `…​.ecs.us-east-2.on.aws` host (HTTPS) |
| Database | RDS PostgreSQL instance `moo-backend-db` (private) |
| Snapshot bucket | S3 `moo-snapshots-prod` (private) |
| App IAM role (task role) | `moo-backend` — grants the app S3 access |
| Runtime IAM role (execution role) | `moo-ecs-execution` — image pull, logs, read secrets |
| Logs | CloudWatch; the Express service's `/aws/ecs/default/…` group |

### How the app authenticates to AWS
The running container uses the **task role** (`moo-backend`) via boto3's default
credential chain — **no static AWS keys**. In production, leave the S3 endpoint and
key settings **unset** so boto3 falls through to the role:

```
# all three unset => real AWS S3 via the task role
# MW_S3_ENDPOINT_URL        (set only for an S3-compatible mock)
# MW_S3_ACCESS_KEY_ID
# MW_S3_SECRET_ACCESS_KEY
```

These have no code defaults; the local MinIO values (`http://localhost:9000`,
`minioadmin`) live only in `.env`, so they cannot leak into a deploy. Leaving the
three vars unset is the correct prod configuration.

### Secrets
Two values are injected from **AWS Secrets Manager** by the task definition, never
committed or baked into the image:

| Env var | Secret name | Purpose |
|---|---|---|
| `MW_DATABASE_URL` | `moo/database-url` | full SQLAlchemy connection string |
| `MW_AUTH_SECRET` | `moo/auth-secret` | signs user session tokens |

## Cost control: start / stop between sessions

Fargate bills per vCPU/GB-second while a task runs; RDS bills while the instance is
available. For a cost-capped project, stop both when you're not using them.

**Order matters.** The app reports healthy only when it can reach the database, so
on startup bring **RDS up first, then the ECS service**; on shutdown, service down
first is fine.

### ECS service — scale down / up
The service "desired count" is how many task copies ECS keeps running. 0 = stopped
(no compute cost); 1 = one running task. The service config, ALB, and hostname
persist either way; scaling back up launches a fresh task from the same task def.

```bash
# OFF — stop compute billing
aws ecs update-service --cluster default --service moo-backend-9479 \
  --desired-count 0 --region us-east-2

# ON — bring it back (healthy in ~1–2 min)
aws ecs update-service --cluster default --service moo-backend-9479 \
  --desired-count 1 --region us-east-2

# status
aws ecs describe-services --cluster default --services moo-backend-9479 \
  --region us-east-2 --query 'services[0].{running:runningCount,desired:desiredCount}'
```

### RDS — stop / start
RDS has an explicit stop/start (not a desired-count). Stopping pauses compute
billing; you still pay a little for storage + backups.

> **7-day limit:** AWS auto-starts a stopped RDS instance after 7 days. Stopping is
> for short gaps between sessions, not a permanent off switch.

```bash
# OFF
aws rds stop-db-instance --db-instance-identifier moo-backend-db --region us-east-2
# ON (available in ~3–5 min)
aws rds start-db-instance --db-instance-identifier moo-backend-db --region us-east-2
# status
aws rds describe-db-instances --db-instance-identifier moo-backend-db \
  --region us-east-2 --query 'DBInstances[0].DBInstanceStatus'
```

### Each time the service scales back up
Fargate assigns the task a **new** ENI/public IP, and possibly a new security group.
The public hostname is stable (it's on the ALB), so keep using that. But the RDS
security group only allows Postgres (5432) from the task's security group — if the
task SG changes, update the RDS SG ingress or the app will report
`database: unavailable`. Verify after each start:

```bash
curl -sk https://<express-host>.ecs.us-east-2.on.aws/health
# expect: {"status":"ok","environment":"production","database":"ok", ...}
```

## Redeploying a new image

Redeploy **by hand** with an AWS identity that belongs to this account's
organization (the `moo-admin` CLI profile). Keep RDS running during the deploy so
the health check reports `database: ok`. The container is single-platform, so
build for **linux/amd64** to match the Fargate `X86_64` runtime (an Apple-silicon
Mac defaults to arm64, which crash-loops with an exec-format error).

> **The GitHub Actions deploy (`deploy.yml`) does not work on this account.** It
> authenticates with GitHub OIDC, which assumes a role via a principal *outside*
> this AWS organization. The account's managed resource control policy denies
> `sts:*` (and `ecr:*`, `s3:*`, `secretsmanager:*`, ...) to any non-service
> principal whose `aws:PrincipalOrgID` is not this org, so every GitHub OIDC
> `AssumeRoleWithWebIdentity` is denied with "Not authorized to perform
> sts:AssumeRoleWithWebIdentity" — regardless of the role's trust policy. This is
> a guardrail of the free sign-up experience and can't be edited. The `moo-deploy`
> role and `deploy.yml` are kept in place but dormant; a manual deploy from an
> in-org identity (below) is the working path. Lifting this would require
> activating advanced AWS features (a project-owner billing decision in AWS
> Settings), not a repo change.

```bash
# 1. Authenticate Docker to ECR
aws ecr get-login-password --region us-east-2 \
  | docker login --username AWS --password-stdin \
    <ACCOUNT_ID>.dkr.ecr.us-east-2.amazonaws.com

# 2. Build for amd64, tag, push
docker build --platform linux/amd64 -t moo-backend:latest .
docker tag moo-backend:latest <ACCOUNT_ID>.dkr.ecr.us-east-2.amazonaws.com/moo-backend:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-2.amazonaws.com/moo-backend:latest

# 3. Roll the service onto the new image
aws ecs update-service --cluster default --service moo-backend-9479 \
  --force-new-deployment --region us-east-2
```

Verify the image architecture locally if a task crash-loops:
`docker image inspect moo-backend:latest --format '{{.Architecture}}'` → `amd64`.

## Running database migrations

The RDS instance is **private** (no public access), so migrations don't run from a
laptop — they run from inside the VPC on the same image, with the container command
overridden. This uses the same task definition (which already injects
`MW_DATABASE_URL`), the task's subnet, and the task's security group.

```bash
aws ecs run-task \
  --cluster default \
  --task-definition <current-task-def> \
  --launch-type FARGATE \
  --count 1 \
  --network-configuration 'awsvpcConfiguration={subnets=[<task-subnet>],securityGroups=[<task-sg>],assignPublicIp=ENABLED}' \
  --overrides '{"containerOverrides":[{"name":"Main","command":["alembic","upgrade","head"]}]}' \
  --region us-east-2
```

- The container is named **`Main`** in the Express-generated task definition — the
  command override must target that name.
- Swap the command to `["alembic","check"]` to verify there's no schema drift
  (expect "No new upgrade operations detected").
- Watch the task reach `STOPPED` with container `exitCode 0`, and read its log
  stream in the service's CloudWatch log group.

## Seeding a device credential

Edge devices authenticate to the ingestion API with a per-device bearer
credential (see [snapshot-upload-contract.md](snapshot-upload-contract.md)).
There is no self-service registration path, so an operator seeds a device with
`scripts/seed_device.py`, which inserts a `devices` row with a freshly generated,
high-entropy key and prints that key **once**.

Because RDS is private, run the seeder the same way as migrations: as a one-off
Fargate task on the deployed image, with the container command overridden. The
task definition already injects `MW_DATABASE_URL`, so the script connects to RDS
with no extra configuration.

> **Prerequisites.** RDS must be **up** with migrations applied (the `farms` and
> `devices` tables must exist). Seed against a deployed image, not a stale one —
> the same image ships the ingestion endpoints firmware needs, so deploy first,
> then seed.

```bash
# Create a new farm and a device under it (prints the key to the task's logs):
aws ecs run-task \
  --cluster default \
  --task-definition <current-task-def> \
  --launch-type FARGATE \
  --count 1 \
  --network-configuration 'awsvpcConfiguration={subnets=[<task-subnet>],securityGroups=[<task-sg>],assignPublicIp=ENABLED}' \
  --overrides '{"containerOverrides":[{"name":"Main","command":["python","-m","scripts.seed_device","--farm-name","Firmware Test Farm"]}]}' \
  --region us-east-2
```

- Container name is **`Main`** (same as migrations); the override must target it.
- To attach a device to an **existing** farm instead, swap the command to
  `["python","-m","scripts.seed_device","--farm-id","<farm-uuid>"]`.
- The generated `device_key` is written to **stdout**, which lands in the task's
  **CloudWatch log stream** (the service's log group). Watch the task reach
  `STOPPED` with `exitCode 0`, open its log stream, and copy the key from the
  `device key:` line.
- Hand firmware the copied key plus
  [snapshot-upload-contract.md](snapshot-upload-contract.md). They send it as
  `Authorization: Bearer <device_key>` against the Express
  `…​.ecs.us-east-2.on.aws` host.

Locally (against the compose Postgres, not RDS) the same script runs directly:

```bash
export MW_DATABASE_URL="postgresql+psycopg://moo:moo@localhost:5433/mooternity"
python -m scripts.seed_device --farm-name "Local Test Farm"
```

## ECS Express Mode — things to know

Express is the "hand it an image, it wires the rest" experience. A few behaviors
that are easy to trip over:

- **It generates its own task definition** from the console form (image + the fields
  you fill), rather than adopting a task definition you pre-registered. Set the two
  IAM roles (task role `moo-backend`, execution role `moo-ecs-execution`), the
  environment variables, and the secrets in the Express form so they end up in the
  generated definition.
- **Environment vs secrets in the bulk editor:** one `KEY=VALUE` per line; a value
  that is a Secrets Manager **ARN** is wired as a secret (resolved at launch) rather
  than plaintext. Confirm the ARN lines register as secrets, not literal strings.
- **The ALB forwards to the app only for the generated `…​.ecs.us-east-2.on.aws`
  host.** Any other Host header (including the raw ALB DNS name) gets a default
  `404 Not Found` from the listener. Always curl the Express hostname.

## Health endpoint behavior

`GET /health` always returns **200** for liveness, even when the database is
unreachable — it reports `"database": "unavailable"` in the body instead of
erroring. This is deliberate: it keeps an orchestrator from restarting a healthy
process over a transient DB blip. A healthy production response is:

```json
{"status":"ok","version":"0.1.0","environment":"production","database":"ok"}
```

So "the health check passes" only proves the app is up; confirm the `"database"`
field to know the DB path is working.
