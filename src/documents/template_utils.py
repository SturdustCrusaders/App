"""
Utility functions for creating and managing DocumentType templates.
"""

import logging
from django.db import transaction
from documents.models import (
    DocumentType,
    DocumentTypeTemplate,
    DocumentTypeTemplateField,
)

logger = logging.getLogger(__name__)


def create_document_type_with_template(
    name: str,
    template_json: dict | None = None,
    matching_algorithm: int = 0,
    match: str = "",
    is_insensitive: bool = True,
    owner=None,
) -> DocumentType:
    """
    Create a DocumentType and optionally a linked template with bbox fields.

    Args:
        name: Name of the document type
        template_json: Optional dict defining matching config and fields:
            {
                "match": "Anexa nr. 9",
                "matching_algorithm": 3,
                "is_insensitive": true,
                "fields": [
                    {
                        "name": "field_name",
                        "regions": [
                            {"page": 1, "x0": 150, "y0": 400, "x1": 500, "y1": 440}
                        ]
                    }
                ]
            }
            Matching algorithms:
                0 = None (manual only)
                1 = Any word
                2 = All words
                3 = Exact match
                4 = Regular expression
                5 = Fuzzy
                6 = Auto (ML)

        matching_algorithm: Fallback if not in template_json (default 0 = None)
        match: Fallback match string if not in template_json
        is_insensitive: Fallback case sensitivity if not in template_json
        owner: Optional User instance to set as owner

    Returns:
        The created DocumentType instance

    Raises:
        ValueError: If template_json is malformed
    """
    with transaction.atomic():
        # template_json matching config takes priority over function args
        resolved_match = template_json.get("match", match) if template_json else match
        resolved_algorithm = template_json.get("matching_algorithm", matching_algorithm) if template_json else matching_algorithm
        resolved_insensitive = template_json.get("is_insensitive", is_insensitive) if template_json else is_insensitive

        # Validate matching algorithm
        valid_algorithms = {0, 1, 2, 3, 4, 5, 6}
        if resolved_algorithm not in valid_algorithms:
            raise ValueError(
                f"Invalid matching_algorithm: {resolved_algorithm}. "
                f"Must be one of {valid_algorithms}"
            )

        # Require match string if algorithm is not None or Auto
        if resolved_algorithm not in {0, 6} and not resolved_match:
            raise ValueError(
                f"matching_algorithm {resolved_algorithm} requires a 'match' string"
            )

        doc_type = DocumentType.objects.create(
            name=name,
            matching_algorithm=resolved_algorithm,
            match=resolved_match,
            is_insensitive=resolved_insensitive,
            owner=owner,
        )

        if template_json and template_json.get("fields"):
            _create_template_for_document_type(doc_type, template_json)

        if template_json and template_json.get("blank_document_id"):
            from documents.models import Document as Doc
            try:
                blank_doc = Doc.objects.get(pk=template_json["blank_document_id"])
                set_blank_document(doc_type, blank_doc)
            except Doc.DoesNotExist:
                raise ValueError(f"Document {template_json['blank_document_id']} not found")

        logger.info(
            f"Created DocumentType '{name}' "
            f"(algorithm={resolved_algorithm}, match='{resolved_match}')"
            + (" with template" if template_json and template_json.get("fields") else " without template")
        )

        return doc_type


def update_document_type_template(
    doc_type: DocumentType,
    template_json: dict,
) -> DocumentTypeTemplate:
    """
    Create or replace the template for an existing DocumentType.
    Also updates matching config if provided in template_json.

    Args:
        doc_type: Existing DocumentType instance
        template_json: Dict defining matching config and fields

    Returns:
        The created/updated DocumentTypeTemplate instance
    """
    with transaction.atomic():
        # Update matching config if provided
        updated = False
        if "match" in template_json:
            doc_type.match = template_json["match"]
            updated = True
        if "matching_algorithm" in template_json:
            doc_type.matching_algorithm = template_json["matching_algorithm"]
            updated = True
        if "is_insensitive" in template_json:
            doc_type.is_insensitive = template_json["is_insensitive"]
            updated = True
        if updated:
            doc_type.save(update_fields=["match", "matching_algorithm", "is_insensitive"])

        # Delete existing template if present
        try:
            doc_type.template.delete()
            logger.info(f"Deleted existing template for '{doc_type.name}'")
        except DocumentTypeTemplate.DoesNotExist:
            pass

        template = _create_template_for_document_type(doc_type, template_json)

        if template_json and template_json.get("blank_document_id"):
            from documents.models import Document as Doc
            try:
                blank_doc = Doc.objects.get(pk=template_json["blank_document_id"])
                set_blank_document(doc_type, blank_doc)
            except Doc.DoesNotExist:
                raise ValueError(f"Document {template_json['blank_document_id']} not found")

        logger.info(f"Updated template for DocumentType '{doc_type.name}'")
        return template


def _create_template_for_document_type(
    doc_type: DocumentType,
    template_json: dict,
) -> DocumentTypeTemplate:
    """
    Internal helper — creates template and fields for a document type.

    Raises:
        ValueError: If template_json is malformed
    """
    fields = template_json.get("fields", [])
    if not fields:
        raise ValueError("template_json must contain at least one field in 'fields'")

    template = DocumentTypeTemplate.objects.create(
        document_type=doc_type,
        name=f"{doc_type.name} Template",
    )

    for field in fields:
        field_name = field.get("name")
        regions = field.get("regions", [])

        if not field_name:
            raise ValueError(f"Field is missing 'name': {field}")
        if not regions:
            raise ValueError(f"Field '{field_name}' has no regions defined")

        for region in regions:
            for key in ("page", "x0", "y0", "x1", "y1"):
                if key not in region:
                    raise ValueError(
                        f"Region in field '{field_name}' is missing key '{key}': {region}"
                    )

        DocumentTypeTemplateField.objects.create(
            template=template,
            name=field_name,
            regions=regions,
        )

    return template


def get_template_json(doc_type: DocumentType) -> dict | None:
    """
    Serialize the template of a DocumentType back to JSON format,
    including matching config.
    Returns None if no template exists.

    Args:
        doc_type: DocumentType instance

    Returns:
        Dict with matching config, fields and regions, or None
    """
    try:
        template = doc_type.template
    except DocumentTypeTemplate.DoesNotExist:
        return None

    return {
        "match": doc_type.match,
        "matching_algorithm": doc_type.matching_algorithm,
        "is_insensitive": doc_type.is_insensitive,
        "blank_document_id": template.blank_document.id if template.blank_document else None,
        "fields": [
            {
                "name": field.name,
                "regions": field.regions,
            }
            for field in template.fields.all()
        ],
    }

def set_blank_document(
    doc_type: DocumentType,
    document,
) -> None:
    """
    Link an existing paperless Document as the blank template for a DocumentType.
    The FE uses the document preview endpoint to render it for bbox drawing.

    Args:
        doc_type: DocumentType instance
        document: Document instance to use as the blank template
    """
    try:
        template = doc_type.template
    except DocumentTypeTemplate.DoesNotExist:
        raise ValueError(
            f"DocumentType '{doc_type.name}' has no template. "
            f"Create a template first using create_document_type_with_template."
        )

    template.blank_document = document
    template.save(update_fields=["blank_document"])

    logger.info(f"Set blank document {document.id} for DocumentType '{doc_type.name}'")
