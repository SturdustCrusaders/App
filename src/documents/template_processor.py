"""
Processes document field extraction based on DocumentType templates.

After a document is classified and assigned a DocumentType, this processor:
1. Checks if the document type has a template defined
2. For each template field, queries stored words within the defined regions
3. Saves DocumentFieldValue for each field
4. Deletes all words outside the defined regions
If no template exists for the document type, all words are kept as-is.
"""

import logging
import re

from django.db import transaction

from documents.models import (
    Document,
    DocumentFieldValue,
    DocumentPage,
    DocumentTypeTemplateField,
    DocumentWord,
)

logger = logging.getLogger(__name__)


def process_document_template(sender, document: Document, **kwargs) -> bool:
    """
    Apply the document type template to a document's extracted words.

    Args:
        document: Document instance, must have document_type and extracted words

    Returns:
        True if template was applied, False if no template exists or extraction not done
    """
    if not document.word_data_extracted:
        logger.debug(f"Document {document.id} has no extracted words, skipping template processing")
        return False

    if not document.document_type:
        logger.debug(f"Document {document.id} has no document type, keeping all words")
        return False

    # Check if this document type has a template
    try:
        template = document.document_type.template
    except Exception:
        logger.debug(f"Document type '{document.document_type}' has no template, keeping all words")
        return False

    logger.info(f"Applying template '{template.name}' to document {document.id}")

    fields = template.fields.all()
    if not fields.exists():
        logger.warning(f"Template '{template.name}' has no fields defined, keeping all words")
        return False

    with transaction.atomic():
        # Process each field — find words within its regions and save as DocumentFieldValue
        all_matched_word_ids = set()

        for field in fields:
            matched_word_ids, value = _extract_field_value(document, field)
            all_matched_word_ids.update(matched_word_ids)

            value = _normalize_field_value(field.name, value)

            # Save or update the field value
            DocumentFieldValue.objects.update_or_create(
                document=document,
                template_field=field,
                defaults={"value": value},
            )

            logger.info(f"Field '{field.name}' extracted value: '{value[:50]}{'...' if len(value) > 50 else ''}'")

        deleted_count = 0
        if all_matched_word_ids:
            # Delete all words that are NOT within any matched region.
            deleted_count, _ = DocumentWord.objects.filter(
                page__document=document,
            ).exclude(
                id__in=all_matched_word_ids,
            ).delete()
        else:
            logger.warning(
                f"Template processing found no matching words for document {document.id}; "
                "keeping all OCR words to avoid data loss."
            )

        logger.info(
            f"Template processing complete for document {document.id}: "
            f"{len(all_matched_word_ids)} words matched, {deleted_count} words deleted"
        )

        # Actualizează titlul documentului acum că field-urile și ID-ul sunt disponibile
        from documents.utils import suggest_title_from_content
        new_title = suggest_title_from_content(document.content, document=document)
        if new_title and document.title != new_title:
            document.title = new_title[:127]
            document.save(update_fields=["title"])
            logger.info(f"Updated document {document.id} title to: '{new_title}'")

    return True


def _extract_field_value(document: Document, field: DocumentTypeTemplateField) -> tuple[set, str]:
    """
    Extract words from all regions of a template field.

    Args:
        document: Document instance
        field: DocumentTypeTemplateField with regions JSON

    Returns:
        Tuple of (set of matched word IDs, joined text value)
    """
    matched_word_ids = set()
    region_texts = []

    for region in field.regions:
        page_number = region.get("page", 1)
        x0 = region.get("x0")
        y0 = region.get("y0")
        x1 = region.get("x1")
        y1 = region.get("y1")

        if None in (x0, y0, x1, y1):
            logger.warning(f"Field '{field.name}' has incomplete region: {region}, skipping")
            continue

        page = DocumentPage.objects.filter(
            document=document,
            page_number=page_number,
        ).only("page_width", "page_height").first()

        # Regions drawn in the FE are normalized (0..1). OCR word boxes are pixel-like,
        # so we convert normalized regions to page coordinates when dimensions are known.
        if (
            0 <= x0 <= 1
            and 0 <= x1 <= 1
            and 0 <= y0 <= 1
            and 0 <= y1 <= 1
            and page is not None
            and page.page_width is not None
            and page.page_height is not None
        ):
            x0 = x0 * page.page_width
            x1 = x1 * page.page_width
            y0 = y0 * page.page_height
            y1 = y1 * page.page_height

        rx0, rx1 = sorted((x0, x1))
        ry0, ry1 = sorted((y0, y1))

        # Match words that overlap region, not only words fully contained in region.
        words = DocumentWord.objects.filter(
            page__document=document,
            page__page_number=page_number,
            bbox_x1__gte=rx0,
            bbox_x0__lte=rx1,
            bbox_y1__gte=ry0,
            bbox_y0__lte=ry1,
        ).order_by("bbox_y0", "bbox_x0")

        word_ids = list(words.values_list("id", flat=True))
        matched_word_ids.update(word_ids)

        region_text = " ".join(words.values_list("text", flat=True))
        if region_text:
            region_texts.append(region_text)

    return matched_word_ids, " ".join(region_texts)


def _normalize_field_value(field_name: str, value: str) -> str:
    """
    Normalize raw extracted text to reduce OCR noise for common field types.

    Heuristics are based on field names used in templates, e.g.:
    - nr_cerere
    - data_efectuare
    - nume_prenume
    """
    if not value:
        return ""

    # Collapse OCR spacing artifacts and trim separator punctuation.
    clean = re.sub(r"\s+", " ", value).strip(" .,:;-/")
    if not clean:
        return ""

    field_key = (field_name or "").strip().lower()

    # Dates: 25.06, 25/06, 25.06.2026 etc.
    if "data" in field_key:
        date_match = re.search(r"\b\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?\b", clean)
        if date_match:
            return date_match.group(0)

    # Numeric IDs: nr_cerere, numar, etc.
    if "nr" in field_key or "numar" in field_key:
        number_match = re.search(r"\b\d{1,10}\b", clean)
        if number_match:
            return number_match.group(0)

    # Full names: try to extract a sequence of capitalized words.
    if "nume" in field_key or "prenume" in field_key:
        candidates = re.findall(
            r"\b[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț-]+(?:[\s.]+[A-ZĂÂÎȘȚ][A-Za-zĂÂÎȘȚăâîșț-]+){1,4}\b",
            clean,
        )
        if candidates:
            stop_tokens = {
                "Ca",
                "Urmare",
                "Din",
                "Data",
                "Se",
                "Atestă",
                "Doamna",
                "Domnul",
            }

            filtered = []
            for candidate in candidates:
                parts = re.split(r'[\s.]+', candidate)
                if any(part in stop_tokens for part in parts):
                    continue
                filtered.append(candidate)

            if filtered:
                return max(filtered, key=len)
            return max(candidates, key=len)

    return clean
