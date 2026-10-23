# 3D printer remote-monitoring web app

A hands-on DevOps project: an AWS EKS cluster built with Terraform, with GitHub Actions self-hosted runners on the cluster that deploy infrastructure and applications. The application is a 3D printer remote-monitoring web app, built to learn infrastructure design, CI/CD and operations end to end.

<!-- STATUS:START -->
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