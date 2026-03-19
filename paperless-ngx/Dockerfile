FROM ghcr.io/paperless-ngx/paperless-ngx:latest
RUN apt-get update && apt-get install -y poppler-utils
RUN pip install azure-ai-vision-imageanalysis pdf2image
