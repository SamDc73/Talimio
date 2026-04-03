#!/usr/bin/env bash
set -e

ENV_FILE="${1:-backend/.env.prod}"
SERVICE="${2:-talimio-backend}"
REGION="${3:-us-west1}"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: File '$ENV_FILE' not found. Please create one."
    exit 1
fi

echo "Syncing variables from $ENV_FILE to Google Cloud Secret Manager..."

SECRETS_MAPPING=""

# Read file line by line, ignoring comments and empty lines
while IFS= read -r line || [ -n "$line" ]; do
    # Skip empty lines and comments
    if [[ -z "$line" ]] || [[ "$line" == \#* ]]; then
        continue
    fi

    # Extract key and value
    if [[ "$line" == *"="* ]]; then
        # Trim whitespace
        KEY=$(echo "$line" | cut -d '=' -f 1 | xargs)
        # Get value and strip surrounding quotes if any
        VALUE=$(echo "$line" | cut -d '=' -f 2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//")

        echo "Processing secret: $KEY"

        # Check if secret exists, create if it doesn't
        if ! gcloud secrets describe "$KEY" >/dev/null 2>&1; then
            echo "  -> Creating new secret: $KEY"
            gcloud secrets create "$KEY" --replication-policy="automatic"
        fi

        # Add new version
        echo -n "$VALUE" | gcloud secrets versions add "$KEY" --data-file=-
        echo "  -> Pushed new version for $KEY"

        # Append to secrets mapping for Cloud Run
        if [ -z "$SECRETS_MAPPING" ]; then
            SECRETS_MAPPING="${KEY}=${KEY}:latest"
        else
            SECRETS_MAPPING="${SECRETS_MAPPING},${KEY}=${KEY}:latest"
        fi
    fi
done < "$ENV_FILE"

if [ -z "$SECRETS_MAPPING" ]; then
    echo "No valid environment variables found in $ENV_FILE."
    exit 1
fi

echo ""
echo "Updating Cloud Run service '$SERVICE'..."

gcloud run services update "$SERVICE" \
    --region="$REGION" \
    --clear-env-vars \
    --set-secrets="$SECRETS_MAPPING"

echo ""
echo "Cloud Run update complete! Your app is now drinking entirely from Secret Manager."
