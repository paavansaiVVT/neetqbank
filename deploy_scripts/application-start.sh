#!/bin/bash
set -e

# --- Config ---
AWS_ACCOUNT_URI="885134767910.dkr.ecr.ap-south-1.amazonaws.com"
REPO_NAME="topallapp"
CONTAINER_NAME="topall-container"
FULL_IMAGE_URI="${AWS_ACCOUNT_URI}/${REPO_NAME}:latest"
DEPLOY_DIR="/home/ubuntu/vvts-code-deploy/neet-clarification-bot-api"
ENV_FILE="${DEPLOY_DIR}/.env"

# --- ECR Login ---
echo "Logging into ECR..."
aws ecr get-login-password --region ap-south-1 | \
    sudo docker login --username AWS --password-stdin "${AWS_ACCOUNT_URI}"

# --- Pull latest image ---
echo "Pulling image: ${FULL_IMAGE_URI}"
sudo docker pull "${FULL_IMAGE_URI}"

# --- Stop old container ---
echo "Stopping and removing old container..."
sudo docker stop "${CONTAINER_NAME}" 2>/dev/null || true
sudo docker rm -f "${CONTAINER_NAME}" 2>/dev/null || true

# --- Start new container ---
echo "Starting new container..."

# Build the docker run command
RUN_CMD="sudo docker run -d"
RUN_CMD="${RUN_CMD} -p 8000:8000"
RUN_CMD="${RUN_CMD} --name ${CONTAINER_NAME}"
RUN_CMD="${RUN_CMD} --restart unless-stopped"
RUN_CMD="${RUN_CMD} -e PYTHONUNBUFFERED=1"

# Pass .env file if it exists on the server
if [ -f "${ENV_FILE}" ]; then
    echo "Loading environment from ${ENV_FILE}"
    # Clean .env file for Docker --env-file compatibility:
    # 1. Remove comment lines and blank lines
    # 2. Remove spaces around '='
    # 3. Strip surrounding double quotes from values (Docker treats them as literal)
    CLEAN_ENV_FILE="/tmp/.env.clean"
    grep -v '^\s*#' "${ENV_FILE}" | grep -v '^\s*$' | sed 's/\s*=\s*/=/' | sed 's/="\(.*\)"$/=\1/' > "${CLEAN_ENV_FILE}"
    RUN_CMD="${RUN_CMD} --env-file ${CLEAN_ENV_FILE}"
else
    echo "WARNING: No .env file found at ${ENV_FILE}"
fi

RUN_CMD="${RUN_CMD} ${FULL_IMAGE_URI}"
eval ${RUN_CMD}

# --- Health check ---
echo "Waiting for health check..."
MAX_RETRIES=15
RETRY_INTERVAL=4
for i in $(seq 1 ${MAX_RETRIES}); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo "Health check passed on attempt ${i}"
        break
    fi
    if [ "$i" -eq "${MAX_RETRIES}" ]; then
        echo "ERROR: Health check failed after ${MAX_RETRIES} attempts"
        echo "--- Container logs ---"
        sudo docker logs "${CONTAINER_NAME}" --tail 50
        exit 1
    fi
    echo "Attempt ${i}/${MAX_RETRIES}: waiting ${RETRY_INTERVAL}s..."
    sleep ${RETRY_INTERVAL}
done

# --- Cleanup ---
echo "Removing unused images..."
sudo docker image prune -f

echo "Backend deployment completed successfully."

# ===================================================================
# --- Frontend Build & Serve ---
# IMPORTANT: This section runs with set +e so frontend failures
# do NOT cause the entire deployment to rollback (backend is already up)
# ===================================================================
set +e

FRONTEND_DIR="${DEPLOY_DIR}/frontend"
if [ -d "${FRONTEND_DIR}" ]; then
    echo "=== Starting frontend deployment ==="
    cd "${FRONTEND_DIR}"

    # Stop any existing frontend server first
    echo "Stopping old frontend server..."
    pkill -f "serve -s dist" || true
    sleep 1

    # Install dependencies
    echo "Installing frontend dependencies..."
    npm install 2>&1
    if [ $? -ne 0 ]; then
        echo "WARNING: npm install failed, trying to serve existing dist..."
    else
        # Build the frontend
        echo "Building frontend..."
        npm run build 2>&1
        if [ $? -ne 0 ]; then
            echo "WARNING: npm run build failed, trying to serve existing dist..."
        fi
    fi

    # Start frontend server if dist directory exists
    if [ -d "${FRONTEND_DIR}/dist" ]; then
        echo "Starting frontend server on port 3000 (SPA mode)..."
        nohup npx serve -s dist -l 3000 > /tmp/frontend.log 2>&1 &
        sleep 2

        # Quick frontend health check
        if curl -sf http://localhost:3000 > /dev/null 2>&1; then
            echo "Frontend server is running on port 3000."
        else
            echo "WARNING: Frontend server may not have started. Check /tmp/frontend.log"
        fi
    else
        echo "WARNING: No dist directory found. Frontend not served."
    fi

    echo "=== Frontend deployment finished ==="
else
    echo "WARNING: No frontend directory found at ${FRONTEND_DIR}, skipping frontend deploy."
fi

set -e
echo "Full deployment completed successfully."
