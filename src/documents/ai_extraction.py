"""
AI-powered word extraction service for documents.

Supports:
- Azure Computer Vision API
- Surya OCR (open source)
"""

import logging
import os
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
    Uses Azure AI Vision API (v4.0) for text extraction.

    Requires:
    - AZURE_VISION_ENDPOINT environment variable
    - AZURE_VISION_KEY environment variable
    """

    def __init__(self):
        try:
            from azure.ai.vision.imageanalysis import ImageAnalysisClient
            from azure.ai.vision.imageanalysis.models import VisualFeatures
            from azure.core.credentials import AzureKeyCredential
        except ImportError:
            raise ImportError(
                "Azure SDK not installed. Install with: "
                "pip install azure-ai-vision-imageanalysis"
            )

        self.endpoint = (
            os.environ.get("PAPERLESS_AZURE_VISION_ENDPOINT")
            or os.environ.get("AZURE_VISION_ENDPOINT")
            or getattr(settings, "AZURE_VISION_ENDPOINT", None)
        )
        self.key = (
            os.environ.get("PAPERLESS_AZURE_VISION_KEY")
            or os.environ.get("AZURE_VISION_KEY")
            or getattr(settings, "AZURE_VISION_KEY", None)
        )

        if not self.endpoint or not self.key:
            raise ValueError(
                "AZURE_VISION_ENDPOINT and AZURE_VISION_KEY must be configured"
            )

        self.client = ImageAnalysisClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key),
        )
        self.VisualFeatures = VisualFeatures

    def extract_from_file(
        self,
        file_path: Path,
        mime_type: str,
    ) -> list[ExtractedPage]:
        logger.info(f"Extracting words from {file_path} using Azure Vision")

        if mime_type == "application/pdf":
            return self._extract_from_pdf(file_path)

        with open(file_path, "rb") as f:
            image_data = f.read()
        return [self._extract_from_image_data(image_data, page_number=1)]

    def _extract_from_pdf(self, file_path: Path) -> list[ExtractedPage]:
        """Convert PDF pages to images and extract from each."""
        try:
            import pdf2image
        except ImportError:
            raise ImportError(
                "pdf2image not installed. Install with: pip install pdf2image"
            )

        import io

        pages = []
        images = pdf2image.convert_from_path(str(file_path), dpi=200)

        for page_num, image in enumerate(images, start=1):
            logger.info(f"Processing page {page_num}/{len(images)}")
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format="JPEG")
            img_bytes = img_byte_arr.getvalue()
            extracted_page = self._extract_from_image_data(img_bytes, page_number=page_num)
            extracted_page.width = image.width
            extracted_page.height = image.height
            pages.append(extracted_page)

        logger.info(f"Successfully extracted {len(pages)} pages from {file_path}")
        return pages

    def _extract_from_image_data(self, image_data: bytes, page_number: int) -> ExtractedPage:
        """Send image bytes to Azure and return ExtractedPage."""
        result = self.client.analyze(
            image_data=image_data,
            visual_features=[self.VisualFeatures.READ],
        )

        extracted_page = ExtractedPage(page_number=page_number)

        if result.read and result.read.blocks:
            for block in result.read.blocks:
                for line in block.lines:
                    for word in line.words:
                        poly = word.bounding_polygon
                        xs = [p.x for p in poly]
                        ys = [p.y for p in poly]
                        extracted_page.words.append(
                            ExtractedWord(
                                text=word.text,
                                bbox_x0=min(xs),
                                bbox_y0=min(ys),
                                bbox_x1=max(xs),
                                bbox_y1=max(ys),
                                confidence=word.confidence,
                                language=None,
                            )
                        )
        else:
            logger.warning(f"No text found on page {page_number}")

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
                model_names=["en"],
                device="cuda",
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
        logger.info(f"Extracting words from {file_path} using Surya OCR")

        pages = []

        try:
            from surya.input_file import load_from_file

            images = load_from_file(str(file_path))
            results = self.reader(images)

            for page_num, result in enumerate(results, start=1):
                extracted_page = self._process_surya_result(page_num, result)
                pages.append(extracted_page)

            logger.info(f"Successfully extracted {len(pages)} pages from {file_path}")

        except Exception as e:
            logger.error(f"Error extracting with Surya OCR: {e}", exc_info=True)
            raise

        return pages

    def _process_surya_result(self, page_num: int, result) -> ExtractedPage:
        extracted_page = ExtractedPage(
            page_number=page_num,
            width=result.image.width if hasattr(result, "image") else None,
            height=result.image.height if hasattr(result, "image") else None,
        )

        if hasattr(result, "text_lines"):
            for line in result.text_lines:
                if hasattr(line, "words"):
                    for idx, word_result in enumerate(line.words):
                        if hasattr(word_result, "bbox") and hasattr(word_result, "text"):
                            bbox = word_result.bbox
                            extracted_page.words.append(
                                ExtractedWord(
                                    text=word_result.text,
                                    bbox_x0=bbox[0],
                                    bbox_y0=bbox[1],
                                    bbox_x1=bbox[2],
                                    bbox_y1=bbox[3],
                                    confidence=getattr(word_result, "confidence", 0.95),
                                    language=result.language if hasattr(result, "language") else None,
                                )
                            )

        return extracted_page


class ExtractionServiceFactory:
    """Factory for creating AI extraction service instances."""

    _services = {
        "azure_vision": AzureVisionExtractionService,
        "surya": SuryaExtractionService,
    }

    @classmethod
    def get_service(cls, method: str) -> AIExtractionService:
        if method not in cls._services:
            raise ValueError(
                f"Unknown extraction method: {method}. "
                f"Supported: {list(cls._services.keys())}"
            )
        return cls._services[method]()

    @classmethod
    def get_default_service(cls) -> AIExtractionService:
        method = (
            os.environ.get("PAPERLESS_AI_EXTRACTION_METHOD")
            or os.environ.get("AI_EXTRACTION_METHOD")
            or getattr(settings, "AI_EXTRACTION_METHOD", "azure_vision")
        )
        return cls.get_service(method)
