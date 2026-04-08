"""
Utilities for processing and storing extracted word data in the database.
"""

import logging
from pathlib import Path
from typing import Optional

from django.db import transaction

from documents.ai_extraction import (
    AIExtractionService,
    ExtractionServiceFactory,
    ExtractedPage,
)
from documents.models import Document, DocumentPage, DocumentWord

logger = logging.getLogger(__name__)


class WordDataProcessor:
    """
    Processes extracted word data and stores it in the database.
    """

    def __init__(self, extraction_service: Optional[AIExtractionService] = None):
        """
        Initialize the processor.

        Args:
            extraction_service: AI extraction service instance.
                               If None, uses the default from settings.
        """
        self.extraction_service = (
            extraction_service or ExtractionServiceFactory.get_default_service()
        )

    def extract_and_store(
        self,
        document: Document,
        file_path: Path,
        mime_type: str,
    ) -> bool:
        """
        Extract word data from a document and store it in the database.

        Args:
            document: Document instance to process
            file_path: Path to the document file
            mime_type: MIME type of the file

        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract words from the file
            logger.info(f"Extracting words from document {document.id}")
            extracted_pages = self.extraction_service.extract_from_file(
                file_path,
                mime_type,
            )

            if not extracted_pages:
                logger.warning(f"No words extracted from document {document.id}")
                return False

            # Store in database
            self._store_pages_and_words(document, extracted_pages)

            # Update document to mark word data as extracted
            document.word_data_extracted = True
            document.ai_extraction_method = self._get_method_name()
            document.save(update_fields=["word_data_extracted", "ai_extraction_method"])

            logger.info(
                f"Successfully extracted and stored {sum(len(p.words) for p in extracted_pages)} "
                f"words from document {document.id} across {len(extracted_pages)} pages"
            )

            return True

        except Exception as e:
            logger.error(
                f"Error extracting words from document {document.id}: {e}",
                exc_info=True,
            )
            return False

    def _get_method_name(self) -> str:
        """Get the method name from the extraction service."""
        service_class = self.extraction_service.__class__.__name__
        if "Azure" in service_class:
            return "azure_vision"
        elif "Surya" in service_class:
            return "surya"
        return "unknown"

    @transaction.atomic
    def _store_pages_and_words(
        self,
        document: Document,
        extracted_pages: list[ExtractedPage],
    ) -> None:
        """
        Store extracted pages and words in the database.

        Uses atomic transaction to ensure consistency.

        Args:
            document: Document instance
            extracted_pages: List of ExtractedPage objects
        """
        # Delete existing pages and words for this document
        DocumentPage.objects.filter(document=document).delete()

        # Store new pages and words
        for extracted_page in extracted_pages:
            page = DocumentPage.objects.create(
                document=document,
                page_number=extracted_page.page_number,
                page_width=extracted_page.width,
                page_height=extracted_page.height,
            )

            # Bulk create words for this page
            words = [
                DocumentWord(
                    page=page,
                    text=word.text,
                    bbox_x0=word.bbox_x0,
                    bbox_y0=word.bbox_y0,
                    bbox_x1=word.bbox_x1,
                    bbox_y1=word.bbox_y1,
                    confidence=word.confidence,
                    language=word.language or "",
                    word_index=idx,
                )
                for idx, word in enumerate(extracted_page.words)
            ]

            DocumentWord.objects.bulk_create(words, batch_size=1000)

    def rebuild_text_content(self, document: Document) -> str:
        """
        Rebuild the text content of a document from extracted words.

        This can be used to repopulate the Document.content field for searching.

        Args:
            document: Document instance with extracted word data

        Returns:
            Reconstructed text content (words separated by spaces per page/line)
        """
        text_parts = []

        pages = (
            DocumentPage.objects.filter(document=document)
            .prefetch_related("words")
            .order_by("page_number")
        )

        for page in pages:
            words = page.words.all().order_by("word_index")
            page_text = " ".join(word.text for word in words)
            text_parts.append(page_text)

        return "\n".join(text_parts)

    def get_high_confidence_content(
        self,
        document: Document,
        min_confidence: float = 0.8,
    ) -> str:
        """
        Get text content from only high-confidence word extractions.

        Useful for full-text search on reliable data.

        Args:
            document: Document instance
            min_confidence: Minimum confidence threshold (0-1)

        Returns:
            Text from words meeting confidence threshold
        """
        words = DocumentWord.objects.filter(
            page__document=document,
            confidence__gte=min_confidence,
        ).order_by("page__page_number", "word_index")

        return " ".join(word.text for word in words)
