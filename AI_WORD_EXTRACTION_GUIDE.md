# AI Word Extraction Implementation Guide

> **Status**: Architecture & Data Models Complete (Steps 1-3)

## Overview

This implementation replaces document blob storage with AI-extracted word tokens and bounding boxes. Documents are deleted after extraction, and reconstruction happens on GET requests using the stored word data.

## What's Been Implemented

### 1. ✅ Database Models

Three new models have been added to support word extraction:

```python
# Document model (updated)
- word_data_extracted: Boolean (tracks extraction status)
- ai_extraction_method: CharField (azure_vision or surya)

# DocumentPage (new)
- document: ForeignKey to Document
- page_number: PositiveIntegerField (1-indexed)
- page_width, page_height: Float (optional)

# DocumentWord (new)
- page: ForeignKey to DocumentPage
- text: CharField (the word)
- bbox_x0, bbox_y0, bbox_x1, bbox_y1: Float (bounding box)
- confidence: Float (0-1 score)
- language: CharField (optional)
- word_index: PositiveIntegerField (order on page)
```

**Migration**: `documents/migrations/1076_add_ai_word_extraction.py`

### 2. ✅ AI Extraction Service

**File**: `documents/ai_extraction.py`

Supports two AI providers with consistent interface:

#### Azure Computer Vision
```python
from documents.ai_extraction import AzureVisionExtractionService

service = AzureVisionExtractionService()
pages = service.extract_from_file(Path("document.pdf"), "application/pdf")

# Each page contains: page_number, width, height, words[]
# Each word: text, bbox_x0/y0/x1/y1, confidence, language
```

**Requirements**:
- `AZURE_VISION_ENDPOINT` env var or Django setting
- `AZURE_VISION_KEY` env var or Django setting
- `pip install azure-cognitiveservices-vision-computervision msrest`

#### Surya OCR (Open Source)
```python
from documents.ai_extraction import SuryaExtractionService

service = SuryaExtractionService()
pages = service.extract_from_file(Path("document.pdf"), "application/pdf")
```

**Requirements**:
- `pip install surya-ocr`
- GPU recommended (falls back to CPU)

#### Factory Pattern
```python
from documents.ai_extraction import ExtractionServiceFactory

# Use default from settings
service = ExtractionServiceFactory.get_default_service()

# Or specify explicitly
service = ExtractionServiceFactory.get_service("surya")
service = ExtractionServiceFactory.get_service("azure_vision")
```

### 3. ✅ Word Storage Processor

**File**: `documents/word_storage.py`

Handles extraction and database storage:

```python
from documents.word_storage import WordDataProcessor
from pathlib import Path

# Initialize processor
processor = WordDataProcessor()  # Uses default service
# OR: processor = WordDataProcessor(extraction_service=custom_service)

# Extract and store
success = processor.extract_and_store(
    document=doc,
    file_path=Path("/path/to/document.pdf"),
    mime_type="application/pdf"
)

# Rebuild searchable text from extracted words
text = processor.rebuild_text_content(doc)
doc.content = text
doc.save()

# Get only high-confidence words (>80%)
reliable_text = processor.get_high_confidence_content(doc, min_confidence=0.8)
```

**Key Features**:
- Atomic transaction for consistency
- Bulk insert for performance
- Automatic content reconstruction
- Confidence-based filtering

## Configuration

Add to `settings.py` or environment:

```python
# Which AI service to use
AI_EXTRACTION_METHOD = "surya"  # or "azure_vision"

# If using Azure Vision
AZURE_VISION_ENDPOINT = "https://your-resource.cognitiveservices.azure.com/"
AZURE_VISION_KEY = "your-api-key"
```

## What Still Needs Implementation

### Step 4: Update Document Consumer

Modify the consumer plugin to use word extraction instead of storing document blobs:

**Location**: `documents/consumer.py`

```python
# In ConsumerPlugin.run() method, after parsing:

from documents.word_storage import WordDataProcessor

processor = WordDataProcessor()
success = processor.extract_and_store(
    document,
    self.working_copy,
    mime_type
)

if success:
    # Update content for searching
    document.content = processor.rebuild_text_content(document)

    # Delete the original file to save space
    if self.working_copy.exists():
        self.working_copy.unlink()

    document.save()
else:
    # Handle extraction failure
    raise ParseError("Failed to extract words from document")
```

**Important**: You'll need to:
1. Move this extraction to the right place in the consumer pipeline
2. Handle failures gracefully
3. Ensure document metadata is still captured

### Step 5: Create Reconstruction API

When a document is requested, reconstruct visual layout from words:

**New Serializer**:
```python
# documents/serializers.py

from rest_framework import serializers
from documents.models import DocumentWord, DocumentPage

class DocumentWordSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentWord
        fields = [
            'text', 'bbox_x0', 'bbox_y0', 'bbox_x1', 'bbox_y1',
            'confidence', 'language', 'word_index'
        ]

class DocumentPageSerializer(serializers.ModelSerializer):
    words = DocumentWordSerializer(many=True, read_only=True)

    class Meta:
        model = DocumentPage
        fields = ['page_number', 'page_width', 'page_height', 'words']

class DocumentDetailSerializer(serializers.ModelSerializer):
    pages = DocumentPageSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = [
            'id', 'title', 'content', 'word_data_extracted',
            'pages'  # Include reconstructed word data
        ]
```

**API Endpoint**:
```python
# documents/views.py

class DocumentViewSet(viewsets.ModelViewSet):
    def retrieve(self, request, *args, **kwargs):
        document = self.get_object()

        # If word data is available, include it in response
        serializer = DocumentDetailSerializer(document)
        return Response(serializer.data)
```

### Step 6: Implement Search on High-Confidence Words

Update search to use extracted words:

```python
# documents/filters.py

from django.db.models import Q
from documents.models import DocumentWord

class DocumentFilterBackend(filters.BaseInFilter):
    def filter_queryset(self, request, queryset, view):
        query = request.query_params.get('search', '')

        if query:
            # Search high-confidence words
            word_docs = DocumentWord.objects.filter(
                text__icontains=query,
                confidence__gte=0.8
            ).distinct('page__document').values_list('page__document', flat=True)

            # OR search in document content (if available)
            queryset = queryset.filter(
                Q(id__in=word_docs) | Q(content__icontains=query)
            )

        return queryset
```

## Data Flow Diagram

```
Document Upload
      ↓
   Parser (get basic metadata)
      ↓
   WordDataProcessor.extract_and_store()
      ├→ AzureVisionExtractionService OR SuryaExtractionService
      ├→ Creates DocumentPage + DocumentWord records
      └→ Sets document.word_data_extracted = True
      ↓
   Delete original file
      ↓
   Rebuild document.content from high-confidence words
      ↓
Document Saved (without blob)
      ↓
API GET /document/123/
      ├→ Returns document metadata
      ├→ Returns pages[] with words[] + bboxes
      └→ Client reconstructs visual layout
```

## Query Examples

### Get all words on a page
```python
from documents.models import DocumentPage, DocumentWord

page = DocumentPage.objects.get(document_id=123, page_number=1)
words = page.words.all().order_by('word_index')

for word in words:
    print(f"{word.text} at ({word.bbox_x0}, {word.bbox_y0})")
```

### Find documents with a word at high confidence
```python
from documents.models import DocumentWord

docs = DocumentWord.objects.filter(
    text__icontains='invoice',
    confidence__gte=0.9
).values_list('page__document', flat=True).distinct()
```

### Rebuild document text
```python
from documents.word_storage import WordDataProcessor

processor = WordDataProcessor()
text = processor.rebuild_text_content(document)
# Returns: "word1 word2 word3\nword4 word5..." (newline between pages)
```

## Performance Considerations

1. **Database Indexes**: DocumentWord has indexes on:
   - (page, word_index) - for page reconstruction
   - text - for search
   - confidence - for reliability filtering

2. **Bulk Operations**: Uses `bulk_create()` with batch_size=1000 for insertion

3. **Atomic Transactions**: All page+word creation is atomic

4. **Space Savings**:
   - Old: 5MB PDF + 500KB text in DB
   - New: ~50KB word tokens + bbox data (10x reduction)

## Fallback Strategy

If word extraction fails:
1. Keep document in "incomplete" state
2. Don't delete original file
3. Retry extraction later
4. Allow manual fixing via admin

## Environment Setup

```bash
# Install dependencies
pip install surya-ocr
# OR
pip install azure-cognitiveservices-vision-computervision msrest

# Run migrations
python manage.py migrate

# Test extraction
python manage.py shell
>>> from documents.ai_extraction import ExtractionServiceFactory
>>> service = ExtractionServiceFactory.get_default_service()
>>> pages = service.extract_from_file(Path("test.pdf"), "application/pdf")
>>> print(pages[0].words)
```

## Next Actions

1. Apply migration: `python manage.py migrate`
2. Update consumer to call `WordDataProcessor.extract_and_store()`
3. Create API serializers and endpoints
4. Implement search filter using high-confidence words
5. Update frontend to display reconstructed layout

## Testing

```python
# tests/test_ai_extraction.py

from documents.word_storage import WordDataProcessor
from documents.models import Document, DocumentPage, DocumentWord

def test_word_extraction():
    doc = Document.objects.create(
        title="Test",
        mime_type="application/pdf"
    )

    processor = WordDataProcessor()
    success = processor.extract_and_store(
        doc,
        Path("test.pdf"),
        "application/pdf"
    )

    assert success
    assert doc.word_data_extracted
    assert DocumentPage.objects.filter(document=doc).count() > 0
    assert DocumentWord.objects.filter(page__document=doc).count() > 0
```

---

**Questions?** Check the relevant files or run `python manage.py help makemigrations` to understand the migration system.
