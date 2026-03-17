"""
AI-powered word extraction service for documents.

Supports:
- Azure Computer Vision API
- Surya OCR (open source)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class ExtractedWord:
    """Represents a single extracted word with position and confidence."""

    text: str
    bbox_x0: float
    bbox_y0: float
    bbox_x1: float
    bbox_y1: float
    confidence: float
    language: Optional[str] = None


@dataclass
class ExtractedPage:
    """Represents all words extracted from a single page."""

    page_number: int
    width: Optional[float] = None
    height: Optional[float] = None
    words: list[ExtractedWord] = None

    def __post_init__(self):
        if self.words is None:
            self.words = []


class AIExtractionService(ABC):
    """Abstract base class for AI extraction services."""

    @abstractmethod
    def extract_from_file(
        self,
        file_path: Path,
        mime_type: str,
    ) -> list[ExtractedPage]:
        """
        Extract words and bounding boxes from a document file.

        Args:
            file_path: Path to the document file
            mime_type: MIME type of the file (e.g., 'application/pdf', 'image/png')

        Returns:
            List of ExtractedPage objects, one per page
        """
        pass


class AzureVisionExtractionService(AIExtractionService):
    """
    Uses Azure Computer Vision API for text extraction.

    Requires:
    - AZURE_VISION_ENDPOINT environment variable
    - AZURE_VISION_KEY environment variable
    """

    def __init__(self):
        try:
            from azure.cognitiveservices.vision.computervision import (
                ComputerVisionClient,
            )
            from msrest.authentication import CognitiveServicesCredentials
        except ImportError:
            raise ImportError(
                "Azure SDK not installed. Install with: "
                "pip install azure-cognitiveservices-vision-computervision msrest"
            )

        self.endpoint = getattr(settings, "AZURE_VISION_ENDPOINT", None)
        self.key = getattr(settings, "AZURE_VISION_KEY", None)

        if not self.endpoint or not self.key:
            raise ValueError(
                "AZURE_VISION_ENDPOINT and AZURE_VISION_KEY must be configured"
            )

        self.client = ComputerVisionClient(
            self.endpoint,
            CognitiveServicesCredentials(self.key),
        )

    def extract_from_file(
        self,
        file_path: Path,
        mime_type: str,
    ) -> list[ExtractedPage]:
        """
        Extract words from a document using Azure Computer Vision API.

        Handles PDFs, images, and other formats supported by Azure.
        """
        logger.info(f"Extracting words from {file_path} using Azure Vision")

        pages = []

        try:
            # Read the file and detect print text
            with open(file_path, "rb") as image_file:
                read_operation = self.client.read_in_stream(image_file)

            operation_location = read_operation.operation_location
            operation_id = operation_location.split("/")[-1]

            # Wait for the operation to complete
            import time

            while True:
                result = self.client.get_read_result(operation_id)
                if result.status not in ["notStarted", "running"]:
                    break
                time.sleep(1)

            # Extract text results
            if result.status == "succeeded":
                for page_num, page in enumerate(
                    result.analyze_result.read_results,
                    start=1,
                ):
                    extracted_page = self._process_azure_page(page_num, page)
                    pages.append(extracted_page)

                logger.info(f"Successfully extracted {len(pages)} pages from {file_path}")
            else:
                logger.error(
                    f"Azure extraction failed with status: {result.status}"
                )

        except Exception as e:
            logger.error(f"Error extracting with Azure Vision: {e}", exc_info=True)
            raise

        return pages

    def _process_azure_page(self, page_num: int, page) -> ExtractedPage:
        """
        Process a single page from Azure ReadResult.

        Args:
            page_num: 1-indexed page number
            page: Azure page object from read_result.analyze_result.read_results

        Returns:
            ExtractedPage with extracted words
        """
        extracted_page = ExtractedPage(
            page_number=page_num,
            width=page.width,
            height=page.height,
        )

        word_index = 0
        for line in page.lines:
            for word_info in line.words:
                # Azure provides bounding box as list of points
                bbox = word_info.bounding_box
                bbox_x0 = min(p.x for p in bbox)
                bbox_y0 = min(p.y for p in bbox)
                bbox_x1 = max(p.x for p in bbox)
                bbox_y1 = max(p.y for p in bbox)

                # Azure doesn't provide confidence directly, assume high confidence
                confidence = 0.95

                extracted_word = ExtractedWord(
                    text=word_info.text,
                    bbox_x0=bbox_x0,
                    bbox_y0=bbox_y0,
                    bbox_x1=bbox_x1,
                    bbox_y1=bbox_y1,
                    confidence=confidence,
                    language=None,
                )
                extracted_page.words.append(extracted_word)
                word_index += 1

        return extracted_page


class SuryaExtractionService(AIExtractionService):
    """
    Uses Surya OCR for text extraction (open source alternative).

    Requires:
    - surya library: pip install surya-ocr
    """

    def __init__(self):
        try:
            from surya.ocr import Reader
            from surya.model_registry import get_model

            self.reader = Reader(
                model_names=["en"],  # Default to English
                device="cuda",  # Use GPU if available
            )
            self.model = get_model("text_recognition")

        except ImportError:
            raise ImportError(
                "Surya OCR not installed. Install with: pip install surya-ocr"
            )

    def extract_from_file(
        self,
        file_path: Path,
        mime_type: str,
    ) -> list[ExtractedPage]:
        """
        Extract words from a document using Surya OCR.

        Handles PDFs and common image formats.
        """
        logger.info(f"Extracting words from {file_path} using Surya OCR")

        pages = []

        try:
            # Convert to images if needed
            from surya.input_file import load_from_file

            images = load_from_file(str(file_path))

            # Extract text using Surya
            results = self.reader(images)

            # Process results
            for page_num, result in enumerate(results, start=1):
                extracted_page = self._process_surya_result(page_num, result)
                pages.append(extracted_page)

            logger.info(f"Successfully extracted {len(pages)} pages from {file_path}")

        except Exception as e:
            logger.error(f"Error extracting with Surya OCR: {e}", exc_info=True)
            raise

        return pages

    def _process_surya_result(self, page_num: int, result) -> ExtractedPage:
        """
        Process a single page result from Surya.

        Args:
            page_num: 1-indexed page number
            result: Surya OCR result object

        Returns:
            ExtractedPage with extracted words
        """
        extracted_page = ExtractedPage(
            page_number=page_num,
            width=result.image.width if hasattr(result, "image") else None,
            height=result.image.height if hasattr(result, "image") else None,
        )

        word_index = 0
        if hasattr(result, "text_lines"):
            for line in result.text_lines:
                # Process each word in the line
                if hasattr(line, "words"):
                    for word_result in line.words:
                        if hasattr(word_result, "bbox") and hasattr(word_result, "text"):
                            bbox = word_result.bbox
                            confidence = getattr(word_result, "confidence", 0.95)

                            extracted_word = ExtractedWord(
                                text=word_result.text,
                                bbox_x0=bbox[0],
                                bbox_y0=bbox[1],
                                bbox_x1=bbox[2],
                                bbox_y1=bbox[3],
                                confidence=confidence,
                                language=result.language
                                if hasattr(result, "language")
                                else None,
                            )
                            extracted_page.words.append(extracted_word)
                            word_index += 1

        return extracted_page


class ExtractionServiceFactory:
    """Factory for creating AI extraction service instances."""

    _services = {
        "azure_vision": AzureVisionExtractionService,
        "surya": SuryaExtractionService,
    }

    @classmethod
    def get_service(cls, method: str) -> AIExtractionService:
        """
        Get an extraction service instance by method name.

        Args:
            method: One of 'azure_vision' or 'surya'

        Returns:
            An AIExtractionService instance

        Raises:
            ValueError: If method is not supported
        """
        if method not in cls._services:
            raise ValueError(
                f"Unknown extraction method: {method}. "
                f"Supported: {list(cls._services.keys())}"
            )

        service_class = cls._services[method]
        return service_class()

    @classmethod
    def get_default_service(cls) -> AIExtractionService:
        """Get the default extraction service from settings."""
        method = getattr(settings, "AI_EXTRACTION_METHOD", "surya")
        return cls.get_service(method)
