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

from django.db import transaction

from documents.models import Document, DocumentFieldValue, DocumentTypeTemplateField, DocumentWord

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

            # Save or update the field value
            DocumentFieldValue.objects.update_or_create(
                document=document,
                template_field=field,
                defaults={"value": value},
            )

            logger.info(f"Field '{field.name}' extracted value: '{value[:50]}{'...' if len(value) > 50 else ''}'")

        # Delete all words that are NOT within any matched region
        deleted_count, _ = DocumentWord.objects.filter(
            page__document=document,
        ).exclude(
            id__in=all_matched_word_ids,
        ).delete()

        logger.info(
            f"Template processing complete for document {document.id}: "
            f"{len(all_matched_word_ids)} words kept, {deleted_count} words deleted"
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

        # Query words within this region
        words = DocumentWord.objects.filter(
            page__document=document,
            page__page_number=page_number,
            bbox_x0__gte=x0,
            bbox_y0__gte=y0,
            bbox_x1__lte=x1,
            bbox_y1__lte=y1,
        ).order_by("bbox_y0", "bbox_x0")

        word_ids = list(words.values_list("id", flat=True))
        matched_word_ids.update(word_ids)

        region_text = " ".join(words.values_list("text", flat=True))
        if region_text:
            region_texts.append(region_text)

    return matched_word_ids, " ".join(region_texts)
