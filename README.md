# 3D printer remote-monitoring web app

A hands-on DevOps/IoT project to create a cloud based dashboard for our FDM 3D printer:
1. IoT hardware:
- [Phase 1] Serial port connection to the printer enabling read/command capability (Anycubic Kobra 2 Neo, Marlin based OEM Firmware)
- [Phase 2] 2x ADXL345 accelerometers (on extruder and table), USB webcam connected via STM32 (Arduino Uno Q)
2. Cloud dashboard:
AWS EKS cluster built with Terraform, with GitHub Actions self-hosted runners on the cluster that deploy infrastructure and applications. 

<!-- STATUS:START -->
**Goal:** Goal not stated yet, add it to docs/status-notes.md  

**Where I am now:** The repository now includes EKS cluster Terraform configuration, NAT egress for cluster subnets, DNS hostnames enabled for the VPC, and a repo‑agent integration with associated workflows and CODEOWNER. Recent work has focused on merging the repo‑agent feature and fixing the README status.  

**In progress**
- Integrating the repo agent (multiple PR merges #3‑#8)  
- Updating the README status file  

**Up next**
- Bootstrap: remote state in S3  
- Apply network and EKS cluster from the pipeline  
- Deploy runners (infra‑runner, app‑runner) with separate IAM roles  
- Build and push the app image to ECR  

**Done recently**
- Add repo agent (PR #8)  
- Merge pull request #

_Last updated by the status agent on 2026-10-24 using openai/gpt-oss-120b._
<!-- STATUS:END -->

## Architecture

- **Network:** VPC, subnets and NAT (`Network/`)
- **Cluster:** EKS with managed node groups, IRSA and KMS secrets encryption (`eks-cluster/`)
- **Bootstrap:** S3 remote state and base resources (`bootstrap/`)
- **CI/CD:** GitHub Actions on self-hosted runners (infra-runner and app-runner) via ARC
- **App:** Python API, MQTT telemetry in, DynamoDB storage, Cognito auth, Cloudflare in front

## Repository layout

| Path | What it holds |
|---|---|
| `bootstrap/` | Terraform state bucket and first-time setup |
| `Network/` | VPC and networking |
| `eks-cluster/` | EKS cluster, node groups and IAM |
| `k8s/runners/` | Runner manifests (infra-runner, app-runner) |
| `.github/workflows/` | CI/CD and repo-agent workflows |
| `docs/` | Notes, including `status-notes.md` |

## Roadmap

- [ ] Bootstrap: remote state in S3
- [ ] Network and EKS cluster applied from the pipeline
- [ ] Runners deployed (infra-runner, app-runner) with separate IAM roles
- [ ] App image build and push to ECR
- [ ] Deploy the app to Kubernetes
- [ ] Cognito auth and Cloudflare in front
- [ ] Monitoring and alerts
- [ ] Simulated printer sending telemetry end to end

## How to run it

1. Prerequisites: AWS account, Terraform, kubectl, Helm and the GitHub CLI.
2. Bootstrap: `cd bootstrap && terraform init && terraform apply`
3. Network: `cd Network && terraform init && terraform apply`
4. Cluster: `cd eks-cluster && terraform init && terraform plan`
5. Runners: `kubectl apply -f k8s/runners/`

## Security notes

- No secrets, sensitive `.tfvars`, plan files or state are stored in this repo.
- Runner pods use IRSA roles scoped to what each one needs.
- Every change goes through a pull request.
