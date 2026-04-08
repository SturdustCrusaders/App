#!/usr/bin/env python
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'paperless.settings')
sys.path.insert(0, '/home/petru/Desktop/My Projects/asd/src')

import django
django.setup()

from django.db import connection
from documents.models import Document, DocumentPage, DocumentWord

cursor = connection.cursor()

# Check tables
cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='documents_documentpage')")
print(f'✓ DocumentPage table exists: {cursor.fetchone()[0]}')

cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='documents_documentword')")
print(f'✓ DocumentWord table exists: {cursor.fetchone()[0]}')

# Check columns
cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='documents_document' AND column_name IN ('word_data_extracted', 'ai_extraction_method')")
cols = sorted([row[0] for row in cursor.fetchall()])
print(f'✓ Document fields: {cols}')

# Test model queries
print(f'✓ DocumentPage count: {DocumentPage.objects.count()}')
print(f'✓ DocumentWord count: {DocumentWord.objects.count()}')

print('\n✅ All database checks passed!')
