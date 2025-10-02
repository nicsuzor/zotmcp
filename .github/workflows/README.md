# GitHub Actions Workflows

## build.yml - Build and Push Docker Image

**Triggers:**
- Push to `main` branch
- Pull requests to `main`
- Manual dispatch (Actions tab → "Run workflow")

**What it does:**
1. Authenticates to GCP using Workload Identity Federation
2. Downloads ChromaDB from `gs://prosocial-dev/data/zotero-prosocial-fulltext/files`
3. Builds Docker image with monthly ChromaDB cache
4. Pushes to Google Artifact Registry (on push events only)

**Tags created:**
- `zotmcp:main` - Latest from main branch
- `zotmcp:latest` - Alias for main
- `zotmcp:main-<sha>` - Specific commit

**Required repository variables:**
- `GCP_WIF_PROVIDER` - Workload Identity Federation provider
- `SERVICE_ACCOUNT_EMAIL` - Service account email

**Cache strategy:**
- ChromaDB cached monthly using `CACHE_DATE=$(date +%Y-%m)`
- Docker build cache via GitHub Actions cache
- Layer caching optimized for fast rebuilds

**Manual run:**
Go to Actions → Build and Push ZotMCP Docker Image → Run workflow

**Estimated run time:**
- First run: ~10-15 minutes (download ChromaDB + build)
- Cached runs: ~5-8 minutes (ChromaDB cached, only rebuild changed layers)
