#!/usr/bin/env python
"""
Test script for AI word extraction service.

Usage:
    python test_ai_extraction.py <path_to_pdf>
    
Example:
    python test_ai_extraction.py /path/to/sample.pdf
"""

import os
import sys
import django
from pathlib import Path

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless.settings")
sys.path.insert(0, str(Path(__file__).parent / "src"))
django.setup()

from documents.ai_extraction import ExtractionServiceFactory
from documents.word_storage import WordDataProcessor
from documents.models import Document


def test_ai_extraction(file_path: str):
    """Test AI word extraction on a sample file."""
    
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"❌ File not found: {file_path}")
        return False
    
    print(f"📄 Testing AI extraction on: {file_path.name}")
    print(f"📊 File size: {file_path.stat().st_size / 1024:.1f} KB")
    print()
    
    try:
        # Get the AI service
        print("🤖 Initializing AI extraction service...")
        service = ExtractionServiceFactory.get_default_service()
        print(f"✅ Using: {service.__class__.__name__}")
        print()
        
        # Extract words
        print("🔍 Extracting words and bounding boxes...")
        mime_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else "image/png"
        pages = service.extract_from_file(file_path, mime_type)
        
        if not pages:
            print("❌ No pages extracted!")
            return False
        
        print(f"✅ Successfully extracted {len(pages)} page(s)")
        print()
        
        # Show results
        for page in pages:
            print(f"📑 Page {page.page_number}:")
            if page.width and page.height:
                print(f"   Size: {page.width:.0f} x {page.height:.0f}")
            print(f"   Words extracted: {len(page.words)}")
            
            # Show first 5 words
            if page.words:
                print(f"   First 5 words:")
                for word in page.words[:5]:
                    print(f"      • '{word.text}' (confidence: {word.confidence:.1%}) at ({word.bbox_x0:.1f}, {word.bbox_y0:.1f})")
                if len(page.words) > 5:
                    print(f"      ... and {len(page.words) - 5} more")
            print()
        
        # Test database storage (optional)
        print("💾 Testing database storage...")
        test_doc = Document.objects.create(
            title=f"Test: {file_path.name}",
            mime_type=mime_type,
            checksum="test_checksum_" + str(file_path.stat().st_mtime),
        )
        print(f"✅ Created test document: {test_doc.id}")
        
        processor = WordDataProcessor(service)
        success = processor.extract_and_store(test_doc, file_path, mime_type)
        
        if success:
            print(f"✅ Successfully stored {sum(len(p.words) for p in pages)} words in database")
            
            # Show info
            reconstructed_text = processor.rebuild_text_content(test_doc)
            print(f"✅ Reconstructed text length: {len(reconstructed_text)} characters")
            print(f"   Preview: {reconstructed_text[:100]}...")
        else:
            print("❌ Failed to store in database")
            test_doc.delete()
            return False
        
        print()
        print("✅ All tests passed!")
        print(f"📊 Document ID for reference: {test_doc.id}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_ai_extraction.py <path_to_pdf_or_image>")
        print()
        print("Example:")
        print("  python test_ai_extraction.py /path/to/sample.pdf")
        sys.exit(1)
    
    file_path = sys.argv[1]
    success = test_ai_extraction(file_path)
    sys.exit(0 if success else 1)
