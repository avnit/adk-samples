
FROM python:3.11-slim
WORKDIR /app

# Create a non-root user
RUN adduser --disabled-password --gecos "" myuser

# Change ownership of /app to myuser
RUN chown -R myuser:myuser /app

# Switch to the non-root user
USER myuser

# Set up environment variables - Start
ENV PATH="/home/myuser/.local/bin:$PATH"

ENV GOOGLE_GENAI_USE_VERTEXAI=1
ENV GOOGLE_CLOUD_PROJECT=atus-sandbox-hackathon-2025
ENV GOOGLE_CLOUD_LOCATION=us-east1

# Set up environment variables - End
FROM python:3.13-slim
WORKDIR /app

RUN adduser --disabled-password --gecos "" myuser && \
    chown -R myuser:myuser /app

COPY . .
# Install ADK - Start
RUN pip install -r requirements.txt

EXPOSE 8080

CMD adk run llm_auditor --port=8080 
