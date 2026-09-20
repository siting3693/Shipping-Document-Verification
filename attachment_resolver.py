import os
import logging
from typing import Optional, Dict, Any, List

import document_parser

logger = logging.getLogger(__name__)

def identify_from_filename(attachment_path: str) -> Optional[str]:
    """Return 'SI', 'BL', or None based on filename."""
    filename = os.path.basename(attachment_path).upper()
    name, ext = os.path.splitext(filename)
    
    if name.endswith("_SI") or name == "SI":
        return "SI"
    if name.endswith("_BL") or name == "BL":
        return "BL"
        
    # Additional common patterns
    if "SHIPPING INSTRUCTION" in name or "SHIPPING_INSTRUCTION" in name:
        return "SI"
    if "BILL OF LADING" in name or "BILL_OF_LADING" in name:
        return "BL"
        
    return None

def resolve_attachments(email: Dict[str, Any], inbox: Any) -> Dict[str, Any]:
    """Resolve SI and BL attachments for a BL_COMPARISON email.
    
    Args:
        email: Email dict with 'attachments' list
        inbox: Inbox object for reading attachment content
    
    Returns:
        {
            'si_path': str | None,
            'bl_path': str | None,
            'si_doc': dict | None,  # parsed document from document_parser
            'bl_doc': dict | None,  # parsed document from document_parser
            'status': 'OK' | 'NEEDS_REVIEW',
            'review_reason': str | None,  # 'missing_attachment', 'wrong_doc_type', 'unreadable'
            'details': str  # explanation
        }
    """
    result = {
        'si_path': None,
        'bl_path': None,
        'si_doc': None,
        'bl_doc': None,
        'status': 'NEEDS_REVIEW',
        'review_reason': None,
        'details': ''
    }
    
    attachments: List[str] = email.get('attachments', [])
    
    if not attachments:
        result['review_reason'] = 'missing_attachment'
        result['details'] = 'No attachments found in the email.'
        return result
        
    if len(attachments) == 1:
        att_path = attachments[0]
        try:
            content_bytes = inbox.read_bytes(att_path)
            doc = document_parser.parse_document(att_path, content_bytes)
        except Exception as e:
            logger.error(f"Failed to read/parse {att_path}: {e}")
            doc = {'doc_type': 'UNREADABLE'}
            
        doc_type = doc.get('doc_type', 'UNREADABLE')
        
        if doc_type == 'SI':
            result['si_path'] = att_path
            result['si_doc'] = doc
            result['review_reason'] = 'missing_attachment'
            result['details'] = 'Found SI but BL is missing.'
        elif doc_type == 'BL':
            result['bl_path'] = att_path
            result['bl_doc'] = doc
            result['review_reason'] = 'missing_attachment'
            result['details'] = 'Found BL but SI is missing.'
        elif doc_type == 'UNREADABLE':
            result['review_reason'] = 'unreadable'
            result['details'] = f'Attachment {os.path.basename(att_path)} is unreadable.'
        else:
            result['review_reason'] = 'wrong_doc_type'
            result['details'] = f'Found single attachment of type {doc_type}, expected SI or BL.'
            
        return result

    # 2+ attachments
    candidates = {}
    for att_path in attachments:
        file_type = identify_from_filename(att_path)
        if file_type:
            if file_type not in candidates:
                candidates[file_type] = []
            candidates[file_type].append(att_path)
            
    si_paths = candidates.get('SI', [])
    bl_paths = candidates.get('BL', [])
    
    # Parse all documents to ensure content matches
    parsed_docs = {}
    for att_path in attachments:
        try:
            content_bytes = inbox.read_bytes(att_path)
            doc = document_parser.parse_document(att_path, content_bytes)
            parsed_docs[att_path] = doc
        except Exception as e:
            logger.error(f"Failed to parse {att_path}: {e}")
            parsed_docs[att_path] = {'doc_type': 'UNREADABLE'}
            
    # Check for failure conditions early among files named _BL or _SI
    wrong_types = ['COMMERCIAL_INVOICE', 'PACKING_LIST', 'CERTIFICATE_OF_ORIGIN']
    for path in (si_paths + bl_paths):
        if path in parsed_docs:
            doc_type = parsed_docs[path].get('doc_type')
            if doc_type in wrong_types:
                result['review_reason'] = 'wrong_doc_type'
                result['details'] = f'Attachment {os.path.basename(path)} has wrong document type: {doc_type}'
                return result
            if doc_type == 'UNREADABLE':
                result['review_reason'] = 'unreadable'
                result['details'] = f'Attachment {os.path.basename(path)} is unreadable.'
                return result
                
    # Figure out SI
    final_si_path = None
    final_si_doc = None
    
    for path in si_paths:
        doc = parsed_docs[path]
        if doc.get('doc_type') == 'SI':
            final_si_path = path
            final_si_doc = doc
            break
            
    if not final_si_path:
        for path, doc in parsed_docs.items():
            if doc.get('doc_type') == 'SI' and path not in bl_paths:
                final_si_path = path
                final_si_doc = doc
                break

    # Figure out BL
    final_bl_path = None
    final_bl_doc = None
    
    for path in bl_paths:
        doc = parsed_docs[path]
        if doc.get('doc_type') == 'BL':
            final_bl_path = path
            final_bl_doc = doc
            break
            
    if not final_bl_path:
        for path, doc in parsed_docs.items():
            if doc.get('doc_type') == 'BL' and path != final_si_path:
                final_bl_path = path
                final_bl_doc = doc
                break
                
    result['si_path'] = final_si_path
    result['si_doc'] = final_si_doc
    result['bl_path'] = final_bl_path
    result['bl_doc'] = final_bl_doc
    
    # Validation
    if final_si_path and final_bl_path:
        result['status'] = 'OK'
        result['details'] = 'Successfully resolved both SI and BL attachments.'
        return result
        
    # If we didn't return above, we are missing one or both
    result['review_reason'] = 'missing_attachment'
    if not final_si_path and not final_bl_path:
        result['details'] = 'Could not find either SI or BL attachments.'
    elif not final_si_path:
        result['details'] = 'Found BL but could not resolve SI attachment.'
    else:
        result['details'] = 'Found SI but could not resolve BL attachment.'
        
    return result
