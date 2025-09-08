#!/bin/bash
# Setup script for dedicated AlphaMind transparency repository

echo "🔧 AlphaMind Transparency Repository Setup"
echo "=========================================="

# Check if GitHub token is provided
if [ -z "$GITHUB_TOKEN" ]; then
    echo "❌ Please set GITHUB_TOKEN environment variable"
    echo "   Get token from: https://github.com/settings/personal-access-tokens/tokens"
    echo "   Required scope: public_repo"
    echo ""
    echo "Usage: GITHUB_TOKEN=your_token_here bash setup_transparency_repo.sh"
    exit 1
fi

echo "📋 Creating dedicated transparency repository..."

# Create the repository via GitHub API
REPO_RESPONSE=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/user/repos \
  -d '{
    "name": "alphamind-transparency",
    "description": "AlphaMind TAO20 Emissions Transparency Data - Real-time subnet emissions from Bittensor Finney network",
    "public": true,
    "auto_init": true,
    "has_issues": false,
    "has_projects": false,
    "has_wiki": false
  }')

# Check if repository was created successfully
if echo "$REPO_RESPONSE" | grep -q '"clone_url"'; then
    CLONE_URL=$(echo "$REPO_RESPONSE" | grep '"clone_url"' | cut -d'"' -f4)
    echo "✅ Repository created successfully!"
    echo "🔗 Clone URL: $CLONE_URL"
    
    # Extract repository details
    REPO_NAME=$(echo "$REPO_RESPONSE" | grep '"full_name"' | cut -d'"' -f4)
    echo "📂 Repository: $REPO_NAME"
    
else
    echo "❌ Failed to create repository"
    echo "Response: $REPO_RESPONSE"
    exit 1
fi

echo ""
echo "🔑 Next steps for VPS setup:"
echo "1. SSH to your VPS: ssh root@138.68.69.71"
echo "2. Set the GitHub token:"
echo "   export GITHUB_TOKEN='$GITHUB_TOKEN'"
echo "   echo 'export GITHUB_TOKEN=\"$GITHUB_TOKEN\"' >> /opt/alphamind/secrets/.env"
echo ""
echo "3. Update the transparency script to use new repository:"
echo "   TRANSPARENCY_REPO='https://\$GITHUB_TOKEN@github.com/$REPO_NAME.git'"
echo ""
echo "4. Test the setup:"
echo "   cd /opt/alphamind/src"
echo "   bash deployment/vps/update_transparency.sh"

echo ""
echo "🛡️ Security benefits:"
echo "✅ Dedicated repository (isolated from main codebase)"
echo "✅ Limited token scope (public_repo only)"  
echo "✅ Public transparency (anyone can verify emissions data)"
echo "✅ Automated daily updates"
