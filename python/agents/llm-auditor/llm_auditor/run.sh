gcloud run deploy capital-agent-service \
--source . \
--region $GOOGLE_CLOUD_LOCATION \
--project atus-sandbox-hackathon-2025 \
--allow-unauthenticated \
--set-env-vars="GOOGLE_CLOUD_PROJECT=atus-sandbox-hackathon-2025,GOOGLE_CLOUD_LOCATION=us-east1,GOOGLE_GENAI_USE_VERTEXAI=$GOOGLE_GENAI_USE_VERTEXAI"