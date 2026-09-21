import re
from typing import Any, Dict, List, Optional

def _normalize_string(val: Any) -> str:
    if not isinstance(val, str):
        return str(val) if val is not None else ""
    return val.strip()

def _normalize_entity(val: Any) -> str:
    if not val:
        return ""
    val = _normalize_string(val).upper()
    
    # Remove address portions (everything after semicolons, or multi-line content)
    val = val.split(';')[0]
    val = val.split('\n')[0]
    
    # Normalize corp suffixes
    val = val.replace('SDN. BHD.', 'SDN BHD')
    val = val.replace('PTE. LTD.', 'PTE LTD')
    val = val.replace('LTD.', 'LTD')
    val = val.replace('INC.', 'INC')
    val = val.replace('CO.', 'CO')
    val = val.replace('CORP.', 'CORP')
    
    # Remove trailing periods and extra whitespace
    val = re.sub(r'\s+', ' ', val)
    val = val.strip().rstrip('.')
    
    return val

def _normalize_port(val: Any) -> str:
    if not val:
        return ""
    val = _normalize_string(val).upper()
    
    # Remove UN/LOCODE in parentheses: (MYPKG), (PECLL), (CNSHA), etc.
    val = re.sub(r'\([A-Z]{5}\)', '', val)
    val = re.sub(r'\s+', ' ', val)
    val = val.strip()
    return val

def _normalize_int(val: Any) -> Optional[int]:
    if val is None or val == "":
        return None
    try:
        # Convert to string, strip whitespace, remove non-numeric chars if needed or just parse
        if isinstance(val, str):
            val = re.sub(r'[^\d]', '', val)
            if not val:
                return None
        return int(val)
    except (ValueError, TypeError):
        return None

def compare_field(field_name: str, si_value: Any, bl_value: Any) -> dict:
    """Compare a single field between SI and BL.
    
    Returns:
        {
            'field': str,
            'si_value': the normalized SI value,
            'bl_value': the normalized BL value,  
            'si_raw': the raw SI value,
            'bl_raw': the raw BL value,
            'status': 'MATCH' | 'MISMATCH' | 'MISSING' | 'UNCERTAIN',
            'reason': str  # explanation
        }
    """
    
    si_raw = si_value
    bl_raw = bl_value
    
    is_missing_si = si_value is None or str(si_value).strip() == "" or str(si_value).strip() in ["TBA", "TBC"] or "___" in str(si_value)
    is_missing_bl = bl_value is None or str(bl_value).strip() == "" or str(bl_value).strip() in ["TBA", "TBC"] or "___" in str(bl_value)
    
    if is_missing_si and is_missing_bl:
        return {
            'field': field_name,
            'si_value': None,
            'bl_value': None,
            'si_raw': si_raw,
            'bl_raw': bl_raw,
            'status': 'MISSING',
            'reason': 'Both values are missing'
        }
    elif is_missing_si or is_missing_bl:
        return {
            'field': field_name,
            'si_value': None if is_missing_si else si_value,
            'bl_value': None if is_missing_bl else bl_value,
            'si_raw': si_raw,
            'bl_raw': bl_raw,
            'status': 'MISSING',
            'reason': 'Missing in one document'
        }
        
    status = 'UNCERTAIN'
    reason = ''
    si_norm: Any = None
    bl_norm: Any = None

    if field_name in ['container_count', 'gross_weight_kg']:
        si_norm = _normalize_int(si_value)
        bl_norm = _normalize_int(bl_value)
        if si_norm is None or bl_norm is None:
            status = 'MISSING'
            reason = 'Could not parse as integer'
        elif si_norm == bl_norm:
            status = 'MATCH'
            reason = 'Exact integer match'
        else:
            status = 'MISMATCH'
            reason = f'Mismatch: {si_norm} != {bl_norm}'
            
    elif field_name in ['shipper', 'consignee', 'notify_party']:
        si_norm = _normalize_entity(si_value)
        bl_norm = _normalize_entity(bl_value)
        if si_norm == bl_norm:
            status = 'MATCH'
            reason = 'Normalized strings match'
        else:
            status = 'MISMATCH'
            reason = f'Mismatch: {si_norm} != {bl_norm}'
            
    elif field_name in ['port_of_loading', 'port_of_discharge']:
        si_norm = _normalize_port(si_value)
        bl_norm = _normalize_port(bl_value)
        if si_norm == bl_norm:
            status = 'MATCH'
            reason = 'Normalized ports match'
        else:
            status = 'MISMATCH'
            reason = f'Mismatch: {si_norm} != {bl_norm}'
    else:
        # Generic string comparison fallback
        si_norm = str(si_value).strip().upper()
        bl_norm = str(bl_value).strip().upper()
        if si_norm == bl_norm:
            status = 'MATCH'
            reason = 'Strings match'
        else:
            status = 'MISMATCH'
            reason = 'Strings differ'

    return {
        'field': field_name,
        'si_value': si_norm,
        'bl_value': bl_norm,
        'si_raw': si_raw,
        'bl_raw': bl_raw,
        'status': status,
        'reason': reason
    }

def compare_documents(si_fields: dict, bl_fields: dict) -> dict:
    """Compare all 7 fields between SI and BL extracted data.
    
    Args:
        si_fields: Output from field_extraction.extract_fields() for SI
        bl_fields: Output from field_extraction.extract_fields() for BL
    
    Returns:
        {
            'status': 'OK' | 'MISMATCH' | 'NEEDS_REVIEW',
            'has_defect': bool,
            'defect_fields': list[str],  # list of canonical field names with mismatches
            'review_reason': str | None,  # 'missing_value' if any field is MISSING
            'field_results': list[dict],  # per-field comparison results
            'summary': str  # human-readable summary
        }
    """
    
    fields_to_compare = [
        'shipper', 'consignee', 'notify_party',
        'port_of_loading', 'port_of_discharge',
        'container_count', 'gross_weight_kg'
    ]
    
    field_results = []
    defect_fields = []
    has_missing = False
    
    for field in fields_to_compare:
        si_entry = si_fields.get(field, {})
        bl_entry = bl_fields.get(field, {})
        
        # Extract normalized values for comparison; fall back to raw_value
        if isinstance(si_entry, dict):
            si_val = si_entry.get('normalized_value')
            si_raw = si_entry.get('raw_value')
        else:
            si_val = si_entry
            si_raw = si_entry
            
        if isinstance(bl_entry, dict):
            bl_val = bl_entry.get('normalized_value')
            bl_raw = bl_entry.get('raw_value')
        else:
            bl_val = bl_entry
            bl_raw = bl_entry
        
        result = compare_field(field, si_val, bl_val)
        # Override raw values for evidence display
        result['si_raw'] = si_raw
        result['bl_raw'] = bl_raw
        field_results.append(result)
        
        if result['status'] == 'MISMATCH':
            defect_fields.append(field)
        elif result['status'] in ['MISSING', 'UNCERTAIN']:
            has_missing = True
            
    has_defect = len(defect_fields) > 0
    
    if has_missing:
        status = 'NEEDS_REVIEW'
        review_reason = 'missing_value'
        summary = "Some fields are missing or uncertain and require manual review."
    elif has_defect:
        status = 'MISMATCH'
        review_reason = None
        summary = f"Documents mismatch in {len(defect_fields)} field(s)."
    else:
        status = 'OK'
        has_defect = False
        review_reason = None
        summary = "All fields match successfully."
        
    return {
        'status': status,
        'has_defect': has_defect,
        'defect_fields': defect_fields,
        'review_reason': review_reason,
        'field_results': field_results,
        'summary': summary
    }
