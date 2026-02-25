# Hybrid RAG AI Agent - Complete Deployment Guide

This guide provides step-by-step instructions for deploying a three-tier RAG (Retrieval-Augmented Generation) AI agent system to Google Cloud Platform.

## Architecture Overview

```
┌─────────────────────────┐
│   React Frontend        │  → Cloud Run (Public)
│   (adk-agent-ui/)       │     Users interact here
└───────────┬─────────────┘
            │ HTTPS API calls
            ▼
┌─────────────────────────┐
│   FastAPI Backend       │  → Cloud Run (Public)
│   (backend.py)          │     Session management
└───────────┬─────────────┘
            │ Vertex AI SDK
            ▼
┌─────────────────────────┐
│   ADK Hybrid Agent      │  → Vertex AI Agent Engine (Managed)
│   (rag_agent/)          │     RAG + Pandas tools
└─────────────────────────┘
```

## Prerequisites

Before starting the deployment, ensure you have:

- Google Cloud Platform account with billing enabled
- `gcloud` CLI installed and configured
- Docker installed on your local machine
- `adk` (Agent Development Kit) CLI installed
- Project ID: `osa-rag-ai-agent`
- Access to create and manage Cloud Run services
- Access to Vertex AI services

## Project Configuration

### Environment Variables

Set the following environment variables for your deployment session:

**Windows Command Prompt:**
```cmd
set GOOGLE_CLOUD_PROJECT=osa-rag-ai-agent
set GOOGLE_CLOUD_LOCATION=asia-southeast1
set STAGING_BUCKET=gs://osa-rag-ai-agent-bucket #not neccessary anymore has been depricated
```

**Linux/macOS:**
```bash
export GOOGLE_CLOUD_PROJECT=osa-rag-ai-agent
export GOOGLE_CLOUD_LOCATION=asia-southeast1
export STAGING_BUCKET=gs://osa-rag-ai-agent-bucket
```

### Initial Authentication

Authenticate with Google Cloud:

```cmd
gcloud auth login
```

Configure default project and region:

```cmd
gcloud config set project osa-rag-ai-agent
gcloud config set run/region asia-southeast1
```

### Enable Required APIs

Enable all necessary Google Cloud APIs:

```cmd
gcloud services enable aiplatform.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable storage.googleapis.com
```

### Application Default Credentials

Set up application default credentials for local development and deployment:

```cmd
gcloud auth application-default login
```

This command is critical for allowing the ADK and other tools to authenticate properly with Google Cloud services.

## Deployment Steps

### Step 1: Deploy the Agent to Vertex AI Agent Engine

The agent layer handles RAG operations and pandas-based data processing through Vertex AI's managed Agent Engine.

Navigate to your project root:

```cmd
cd osa-rag-ai-agent
```

Deploy the agent using the ADK CLI:

**Windows Command Prompt:**
```cmd
adk deploy agent_engine rag_agent ^
  --project=osa-rag-ai-agent ^
  --region=asia-southeast1 ^
  --display_name="Hybrid RAG AI Agent"
```

**Linux/macOS:**
```bash
adk deploy agent_engine rag_agent \
  --project=osa-rag-ai-agent \
  --region=asia-southeast1 \
  --display_name="Hybrid RAG AI Agent"
```

After successful deployment, note the `REASONING_ENGINE_ID` from the output. You'll need this for the backend deployment.

**Expected Output:**
- Reasoning Engine ID (example: `452562646435235235`)
- Deployment status confirmation
- Agent endpoint information

### Step 2: Deploy the Backend to Cloud Run

The backend layer provides session management and acts as an intermediary between the frontend and the Vertex AI agent.

#### Build the Docker Image

From the project root directory:

```cmd
docker build -t gcr.io/osa-rag-ai-agent/rag-backend .
```

#### Push to Google Container Registry

```cmd
docker push gcr.io/osa-rag-ai-agent/rag-backend
```

#### Deploy to Cloud Run

**Windows Command Prompt:**
```cmd
gcloud run deploy rag-backend ^
  --image gcr.io/osa-rag-ai-agent/rag-backend ^
  --region asia-southeast1 ^
  --allow-unauthenticated ^
  --set-env-vars GOOGLE_CLOUD_PROJECT=osa-rag-ai-agent,GOOGLE_CLOUD_LOCATION=asia-southeast1,REASONING_ENGINE_ID=452562646435235235 ^
  --timeout 300s
```

**Linux/macOS:**
```bash
gcloud run deploy rag-backend \
  --image gcr.io/osa-rag-ai-agent/rag-backend \
  --region asia-southeast1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=osa-rag-ai-agent,GOOGLE_CLOUD_LOCATION=asia-southeast1,REASONING_ENGINE_ID=452562646435235235 \
  --timeout 300s
```

**Important:** Replace `4021309846962831360` with your actual Reasoning Engine ID from Step 1.

**Expected Output:**
- Service URL (example: `https://rag-backend-525626464.asia-southeast1.run.app`)
- Deployment status

#### Test the Backend

Test the status endpoint:

**Windows Command Prompt:**
```cmd
curl -X POST "https://rag-backend-525626464.asia-southeast1.run.app/api/status"
```

Test the chat endpoint:

**Windows Command Prompt:**
```cmd
curl -X POST "https://rag-backend-525626464.asia-southeast1.run.app/api/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Hello, just say hi back\"}"
```

**Linux/macOS:**
```bash
curl -X POST "https://rag-backend-525626464.asia-southeast1.run.app/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello, just say hi back"}'
```

**Expected Response:**
- Status endpoint should return service health information
- Chat endpoint should return an AI-generated response

#### Check Backend Logs

If you encounter issues, check the logs:

```cmd
gcloud run services logs read rag-backend --region=asia-southeast1 --limit=50
```

### Step 3: Deploy the Frontend to Cloud Run

The frontend layer provides the user interface for interacting with the RAG agent.

#### Navigate to Frontend Directory

```cmd
cd adk-agent-ui
```

#### Build the Docker Image

Build the image with the backend API URL as a build argument:

**Windows Command Prompt:**
```cmd
docker build -t gcr.io/osa-rag-ai-agent/rag-frontend ^
  --build-arg REACT_APP_API_URL=https://rag-backend-525626464.asia-southeast1.run.app .
```

**Linux/macOS:**
```bash
docker build -t gcr.io/osa-rag-ai-agent/rag-frontend \
  --build-arg REACT_APP_API_URL=https://rag-backend-525626464.asia-southeast1.run.app .
```

**Important:** Replace the URL with your actual backend URL from Step 2.

#### Push to Google Container Registry

```cmd
docker push gcr.io/osa-rag-ai-agent/rag-frontend
```

#### Deploy to Cloud Run

**Windows Command Prompt:**
```cmd
gcloud run deploy rag-frontend ^
  --image gcr.io/osa-rag-ai-agent/rag-frontend ^
  --region asia-southeast1 ^
  --project osa-rag-ai-agent ^
  --allow-unauthenticated ^
  --port 8080
```

**Linux/macOS:**
```bash
gcloud run deploy rag-frontend \
  --image gcr.io/osa-rag-ai-agent/rag-frontend \
  --region asia-southeast1 \
  --project osa-rag-ai-agent \
  --allow-unauthenticated \
  --port 8080
```

**Expected Output:**
- Service URL for the frontend (example: `https://rag-frontend-1243423535.asia-southeast1.run.app`)
- Deployment status

## Post-Deployment Verification

### Complete System Test

1. Open the frontend URL in your web browser
2. Verify the UI loads correctly
3. Send a test message through the chat interface
4. Confirm you receive a response from the AI agent

### Endpoint Summary

After successful deployment, you should have three endpoints:

- **Frontend:** `https://rag-frontend-[hash].asia-southeast1.run.app`
- **Backend API:** `https://rag-backend-[hash].asia-southeast1.run.app`
- **Vertex AI Agent:** Managed endpoint (accessed via backend)

## Troubleshooting

### Common Issues

**Authentication Errors:**
- Re-run `gcloud auth application-default login`
- Verify your account has necessary IAM permissions

**API Not Enabled:**
- Double-check all required APIs are enabled
- Wait a few minutes after enabling APIs before deploying

**Container Build Failures:**
- Ensure Docker is running
- Check Dockerfile syntax
- Verify all dependencies are listed

**Deployment Timeout:**
- Increase timeout value using `--timeout` flag
- Check backend logs for performance bottlenecks

**Frontend Can't Connect to Backend:**
- Verify the `REACT_APP_API_URL` build argument is correct
- Check CORS settings in backend
- Ensure backend service is publicly accessible

### Viewing Logs

**Backend logs:**
```cmd
gcloud run services logs read rag-backend --region=asia-southeast1 --limit=100
```

**Frontend logs:**
```cmd
gcloud run services logs read rag-frontend --region=asia-southeast1 --limit=100
```

**Agent logs:**
```cmd
gcloud logging read "resource.type=aiplatform.googleapis.com/Endpoint" --limit=50
```

## Updating the Deployment

### Update Agent

```cmd
cd osa-rag-ai-agent
adk deploy agent_engine rag_agent --project=osa-rag-ai-agent --region=asia-southeast1
```

### Update Backend

```cmd
docker build -t gcr.io/osa-rag-ai-agent/rag-backend .
docker push gcr.io/osa-rag-ai-agent/rag-backend
gcloud run deploy rag-backend --image gcr.io/osa-rag-ai-agent/rag-backend --region asia-southeast1
```

### Update Frontend

```cmd
cd adk-agent-ui
docker build -t gcr.io/osa-rag-ai-agent/rag-frontend --build-arg REACT_APP_API_URL=https://rag-backend-12341412341324.asia-southeast1.run.app .
docker push gcr.io/osa-rag-ai-agent/rag-frontend
gcloud run deploy rag-frontend --image gcr.io/osa-rag-ai-agent/rag-frontend --region asia-southeast1
```

## Security Considerations

- The current deployment uses `--allow-unauthenticated` for simplicity. For production, implement proper authentication.
- Consider using Cloud IAM for service-to-service authentication
- Implement rate limiting on the backend API
- Use Secret Manager for sensitive configuration values
- Enable Cloud Armor for DDoS protection

## Cost Optimization

- Set appropriate min/max instance counts for Cloud Run services
- Monitor usage through Cloud Billing reports
- Consider using Cloud Run CPU throttling for cost savings
- Implement request caching where appropriate

## Next Steps

- Configure custom domain names for your services
- Set up CI/CD pipelines for automated deployments
- Implement monitoring and alerting with Cloud Monitoring
- Add authentication and user management
- Configure backup and disaster recovery procedures

---

**Deployment Complete!** Your Hybrid RAG AI Agent is now running on Google Cloud Platform.