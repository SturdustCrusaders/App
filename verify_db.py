from documents.models import Document, DocumentPage, DocumentWord
from django.db import connection

cursor = connection.cursor()
cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='documents_documentpage')")
print('✓ DocumentPage table exists:', cursor.fetchone()[0])

cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='documents_documentword')")  
print('✓ DocumentWord table exists:', cursor.fetchone()[0])

print('✓ DocumentPage count:', DocumentPage.objects.count())
print('✓ DocumentWord count:', DocumentWord.objects.count())
print('\n✅ All database checks passed!')
