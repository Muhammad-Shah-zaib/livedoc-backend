# utils/db_helpers.py
from rest_framework.exceptions import NotFound
from document.models import Document, DocumentAccess

def get_document_or_404(document_id):
    try:
        return Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        raise NotFound(detail="Document not found.")

def get_document_access_or_404(access_id):
    try:
        return DocumentAccess.objects.get(id=access_id)
    except DocumentAccess.DoesNotExist:
        raise NotFound(detail="Document access not found.")