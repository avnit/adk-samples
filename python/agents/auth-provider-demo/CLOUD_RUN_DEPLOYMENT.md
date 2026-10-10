# Cloud Run Deployment Guide — Auth Provider Demo

This guide explains how to deploy the auth-provider-demo to Google Cloud Run using Cloud Build.

## Prerequisites

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and authenticated:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```
3. **Required APIs enabled**:
   ```bash
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable containerregistry.googleapis.com
   ```

## Quick Start

### Option 1: Deploy from GitHub (Recommended)

1. Push your code to GitHub
2. Connect Cloud Build to your repo:
   ```bash
   gcloud builds connect --repository-name=adk-samples \
     --repository-owner=avnit \
     --region=us-central1
   ```
3. Create a Cloud Build trigger in the Google Cloud Console:
   - Repository: `avnit/adk-samples`
   - Branch: `main` (or your branch)
   - Build config location: `python/agents/auth-provider-demo/cloudbuild.yaml`

### Option 2: Deploy from Local Machine

```bash
cd python/agents/auth-provider-demo

# Submit build to Cloud Build
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_MEMORY=512Mi,_CPU=1 \
  .
```

### Option 3: Deploy via gcloud run deploy (Quick)

```bash
cd python/agents/auth-provider-demo

gcloud run deploy auth-provider-demo \
  --source=. \
  --region=us-central1 \
  --memory=512Mi \
  --cpu=1 \
  --allow-unauthenticated \
  --port=8080
```

## Manual Docker Build & Push

If you prefer to build locally:

```bash
cd python/agents/auth-provider-demo

# Build image
docker build -t gcr.io/$PROJECT_ID/auth-provider-demo:latest .

# Push to Container Registry
docker push gcr.io/$PROJECT_ID/auth-provider-demo:latest

# Deploy to Cloud Run
gcloud run deploy auth-provider-demo \
  --image=gcr.io/$PROJECT_ID/auth-provider-demo:latest \
  --region=us-central1 \
  --memory=512Mi \
  --cpu=1 \
  --allow-unauthenticated
```

## Cloud Build Configuration

The `cloudbuild.yaml` file defines:

1. **Build step**: Builds Docker image
2. **Push step**: Pushes to Google Container Registry
3. **Deploy step**: Deploys to Cloud Run

### Customize Deployment

Edit the substitution variables in `cloudbuild.yaml`:

```yaml
substitutions:
  _REGION: "us-central1"        # Cloud Run region
  _MEMORY: "512Mi"              # RAM allocation
  _CPU: "1"                     # CPU cores
  _TIMEOUT: "3600"              # Request timeout in seconds
```

Or override at build time:

```bash
gcloud builds submit \
  --config=cloudbuild.yaml \
  --substitutions=_REGION=us-east1,_MEMORY=1Gi,_CPU=2 \
  .
```

## Environment Variables

The Flask server reads these environment variables:

```env
# 2-Legged Auth (client credentials)
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
TOKEN_URL=https://your-oauth-server.com/token

# 3-Legged Auth (authorization code)
OAUTH_CLIENT_ID=your-oauth-client-id
OAUTH_CLIENT_SECRET=your-oauth-secret
AUTHORIZATION_URL=https://your-oauth-server.com/authorize
OAUTH_TOKEN_URL=https://your-oauth-server.com/token
REDIRECT_URI=https://your-redirect-uri.com/callback

# Server
PORT=8080 (set automatically by Cloud Run)
```

### Set Environment Variables

```bash
gcloud run deploy auth-provider-demo \
  --image=gcr.io/$PROJECT_ID/auth-provider-demo:latest \
  --set-env-vars=CLIENT_ID=xxx,CLIENT_SECRET=yyy \
  ...
```

Or via Cloud Console → auth-provider-demo → Edit & Deploy New Revision → Environment Variables

## API Endpoints

Once deployed, access these endpoints:

### Health Check
```bash
curl https://auth-provider-demo-xxxxx.run.app/health
```

### List Providers
```bash
curl https://auth-provider-demo-xxxxx.run.app/api/v1/auth/providers
```

### Get 2-Legged Token (Machine Auth)
```bash
curl -X POST \
  https://auth-provider-demo-xxxxx.run.app/api/v1/auth/machine-auth/token \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Get 3-Legged Token (User Auth)
```bash
curl -X POST \
  https://auth-provider-demo-xxxxx.run.app/api/v1/auth/user-auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice"}'
```

### Get Auth Headers
```bash
curl -X POST \
  https://auth-provider-demo-xxxxx.run.app/api/v1/auth/machine-auth/headers \
  -H "Content-Type: application/json" \
  -d '{}'
```

## Monitoring & Logs

### View Cloud Run Service
```bash
gcloud run services describe auth-provider-demo --region=us-central1
```

### Stream Logs
```bash
gcloud run logs read auth-provider-demo --limit=100 --region=us-central1

# Or tail live
gcloud alpha run logs stream auth-provider-demo --region=us-central1
```

### Cloud Logging Dashboard
Open the [Cloud Logging Console](https://console.cloud.google.com/logs) and filter by:
- Resource: Cloud Run Revision
- Service name: `auth-provider-demo`

## Troubleshooting

### Build Fails
```bash
# Check build logs
gcloud builds log $(gcloud builds list --limit=1 --format='value(id)')

# Or check Cloud Build history in console
# Cloud Build → History
```

### Deployment Fails
```bash
# Check service details
gcloud run describe auth-provider-demo --region=us-central1

# Check recent revisions
gcloud run revisions list --service=auth-provider-demo --region=us-central1
```

### Service Returns 500 Error
```bash
# Check logs
gcloud run logs read auth-provider-demo --limit=50

# Verify environment variables are set
gcloud run services describe auth-provider-demo --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env)'
```

### Cold Start Issues
Increase min instances:
```bash
gcloud run deploy auth-provider-demo \
  --min-instances=1 \
  ...
```

## Security Best Practices

1. **Don't use `--allow-unauthenticated` in production**
   ```bash
   gcloud run deploy auth-provider-demo \
     --no-allow-unauthenticated \
     ...
   ```

2. **Use Secret Manager for credentials**
   ```bash
   gcloud secrets create oauth-client-secret --data-file=secret.txt
   gcloud run deploy auth-provider-demo \
     --set-env-vars=CLIENT_SECRET=projects/$PROJECT_ID/secrets/oauth-client-secret/latest \
     ...
   ```

3. **Enable VPC Connector for private networks**
   ```bash
   gcloud run deploy auth-provider-demo \
     --vpc-connector=my-vpc-connector \
     ...
   ```

4. **Require authentication via Cloud IAM**
   ```bash
   gcloud run services add-iam-policy-binding auth-provider-demo \
     --member=user:email@example.com \
     --role=roles/run.invoker
   ```

## Cleanup

Delete the Cloud Run service:
```bash
gcloud run services delete auth-provider-demo --region=us-central1
```

Delete the Container Registry image:
```bash
gcloud container images delete gcr.io/$PROJECT_ID/auth-provider-demo --quiet
```

## Advanced: CI/CD Pipeline

### GitHub Actions Example

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [main]
    paths:
      - "python/agents/auth-provider-demo/**"

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
      - uses: google-github-actions/setup-gcloud@v1
      - name: Build and Deploy
        run: |
          gcloud builds submit \
            --config=python/agents/auth-provider-demo/cloudbuild.yaml \
            python/agents/auth-provider-demo
```

## Support & Documentation

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Build Documentation](https://cloud.google.com/build/docs)
- [Auth Provider Demo README](./README.md)
