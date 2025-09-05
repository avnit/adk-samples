FROM python:3.13-slim
WORKDIR /app

# Create a non-root user
RUN adduser --disabled-password --gecos "" myuser

# Copy the application code
COPY . .

# Install dependencies
RUN pip install -r requirements.txt

# Change ownership of /app to myuser
RUN chown -R myuser:myuser /app

# Switch to the non-root user
USER myuser

# Set up environment variables
ENV PATH="/home/myuser/.local/bin:$PATH"

# Expose the port
EXPOSE 8080

# Set the command to run the application
CMD ["adk", "run", "llm_auditor", "--port=8080"]