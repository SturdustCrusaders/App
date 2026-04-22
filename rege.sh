#!/bin/bash

# Step 0, stop any running docker
echo "Stopping container"
cd paperless-ngx/
docker compose down

# First we remove the the cached dist and .angular/cache files
cd ..
echo "Removing old cache"
rm -rf .angular/cache dist
echo "Done removing cache"

# Then we rebuild the whole dist again with the changes
echo "rebuilding"
cd src-ui/
pnpm run build --configuration production

# Restart the docker
cd ../paperless-ngx/
docker compose up -d
