#!/bin/bash
# ZotMCP IAM Setup Script
#
# Creates a custom IAM role with minimum permissions for ZotMCP users
# and provides commands to add/remove principals.
#
# Usage:
#   ./iam_setup.sh create-role     # Create the zotmcp-user custom role
#   ./iam_setup.sh add USER_EMAIL  # Add a user to the role
#   ./iam_setup.sh remove USER_EMAIL # Remove a user from the role
#   ./iam_setup.sh list            # List users with the role
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Owner/IAM Admin permissions on the project

set -e

PROJECT_ID="prosocial-443205"
ROLE_ID="zotmcp_user"
ROLE_TITLE="ZotMCP User"
SECRET_NAME="dev__shared_credentials"
GCS_BUCKET="prosocial-dev"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_usage() {
    echo "ZotMCP IAM Setup Script"
    echo ""
    echo "Usage:"
    echo "  $0 create-role              Create the custom IAM role"
    echo "  $0 add <user@email.com>     Add a user"
    echo "  $0 remove <user@email.com>  Remove a user"
    echo "  $0 list                     List current users"
    echo "  $0 test <user@email.com>    Test user's access"
    echo ""
}

create_role() {
    echo -e "${YELLOW}Creating custom IAM role: ${ROLE_ID}${NC}"

    # Check if role already exists
    if gcloud iam roles describe "$ROLE_ID" --project="$PROJECT_ID" &>/dev/null; then
        echo -e "${YELLOW}Role already exists. Updating...${NC}"
        gcloud iam roles update "$ROLE_ID" \
            --project="$PROJECT_ID" \
            --title="$ROLE_TITLE" \
            --description="Minimal permissions for ZotMCP MCP server access" \
            --permissions="secretmanager.versions.access,aiplatform.endpoints.predict,storage.objects.get,storage.objects.list"
    else
        gcloud iam roles create "$ROLE_ID" \
            --project="$PROJECT_ID" \
            --title="$ROLE_TITLE" \
            --description="Minimal permissions for ZotMCP MCP server access" \
            --permissions="secretmanager.versions.access,aiplatform.endpoints.predict,storage.objects.get,storage.objects.list"
    fi

    echo -e "${GREEN}✅ Role created/updated: projects/${PROJECT_ID}/roles/${ROLE_ID}${NC}"
    echo ""
    echo "Permissions granted:"
    echo "  - secretmanager.versions.access  (read API keys from Secret Manager)"
    echo "  - aiplatform.endpoints.predict   (Vertex AI embeddings)"
    echo "  - storage.objects.get            (download ChromaDB vectors)"
    echo "  - storage.objects.list           (list GCS bucket contents)"
}

add_user() {
    local USER_EMAIL="$1"
    if [ -z "$USER_EMAIL" ]; then
        echo -e "${RED}Error: Please provide a user email${NC}"
        print_usage
        exit 1
    fi

    echo -e "${YELLOW}Adding ${USER_EMAIL} to ZotMCP...${NC}"

    # 1. Grant custom role at project level
    echo "  → Granting custom role..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="user:${USER_EMAIL}" \
        --role="projects/${PROJECT_ID}/roles/${ROLE_ID}" \
        --condition=None \
        --quiet

    # 2. Grant Secret Manager access to specific secret
    echo "  → Granting Secret Manager access..."
    gcloud secrets add-iam-policy-binding "$SECRET_NAME" \
        --project="$PROJECT_ID" \
        --member="user:${USER_EMAIL}" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet

    # 3. Grant GCS bucket read access
    echo "  → Granting GCS bucket access..."
    gsutil iam ch "user:${USER_EMAIL}:objectViewer" "gs://${GCS_BUCKET}"

    echo -e "${GREEN}✅ User ${USER_EMAIL} added successfully${NC}"
    echo ""
    echo "User setup instructions:"
    echo "  1. Run: gcloud auth application-default login"
    echo "  2. Add ZotMCP to Claude Code config (see README.md)"
    echo "  3. Run: ./scripts/package_for_distribution.sh download"
}

remove_user() {
    local USER_EMAIL="$1"
    if [ -z "$USER_EMAIL" ]; then
        echo -e "${RED}Error: Please provide a user email${NC}"
        print_usage
        exit 1
    fi

    echo -e "${YELLOW}Removing ${USER_EMAIL} from ZotMCP...${NC}"

    # Remove custom role binding
    echo "  → Removing custom role..."
    gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
        --member="user:${USER_EMAIL}" \
        --role="projects/${PROJECT_ID}/roles/${ROLE_ID}" \
        --quiet 2>/dev/null || true

    # Remove Secret Manager access
    echo "  → Removing Secret Manager access..."
    gcloud secrets remove-iam-policy-binding "$SECRET_NAME" \
        --project="$PROJECT_ID" \
        --member="user:${USER_EMAIL}" \
        --role="roles/secretmanager.secretAccessor" \
        --quiet 2>/dev/null || true

    # Remove GCS bucket access
    echo "  → Removing GCS bucket access..."
    gsutil iam ch -d "user:${USER_EMAIL}" "gs://${GCS_BUCKET}" 2>/dev/null || true

    echo -e "${GREEN}✅ User ${USER_EMAIL} removed${NC}"
}

list_users() {
    echo -e "${YELLOW}Users with ZotMCP access:${NC}"
    echo ""
    echo "Custom role bindings:"
    gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --format="table(bindings.members)" \
        --filter="bindings.role:projects/${PROJECT_ID}/roles/${ROLE_ID}" 2>/dev/null || echo "  (none)"
    echo ""
    echo "Secret Manager access:"
    gcloud secrets get-iam-policy "$SECRET_NAME" --project="$PROJECT_ID" \
        --flatten="bindings[].members" \
        --format="table(bindings.members)" \
        --filter="bindings.role:roles/secretmanager.secretAccessor" 2>/dev/null || echo "  (none)"
}

test_user() {
    local USER_EMAIL="$1"
    if [ -z "$USER_EMAIL" ]; then
        echo -e "${RED}Error: Please provide a user email${NC}"
        print_usage
        exit 1
    fi

    echo -e "${YELLOW}Testing access for ${USER_EMAIL}...${NC}"
    echo ""

    # Test Secret Manager access
    echo "Secret Manager access:"
    gcloud secrets get-iam-policy "$SECRET_NAME" --project="$PROJECT_ID" \
        --flatten="bindings[].members" \
        --filter="bindings.members:user:${USER_EMAIL}" \
        --format="value(bindings.role)" 2>/dev/null && echo "  ✅ Has access" || echo "  ❌ No access"

    # Test custom role
    echo ""
    echo "Custom role binding:"
    gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --filter="bindings.members:user:${USER_EMAIL} AND bindings.role:projects/${PROJECT_ID}/roles/${ROLE_ID}" \
        --format="value(bindings.role)" 2>/dev/null && echo "  ✅ Has role" || echo "  ❌ No role"
}

# Main
case "${1:-}" in
    create-role)
        create_role
        ;;
    add)
        add_user "$2"
        ;;
    remove)
        remove_user "$2"
        ;;
    list)
        list_users
        ;;
    test)
        test_user "$2"
        ;;
    *)
        print_usage
        exit 1
        ;;
esac
