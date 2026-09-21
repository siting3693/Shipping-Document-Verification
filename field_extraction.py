"""
Module for extracting and normalizing canonical shipping fields from parsed document data.
"""

import re
from typing import Dict, Any, Optional

FIELD_ALIASES = {
    'shipper': [
        'shipper', 'shipper/exporter', 'shipper (principal or seller)', 
        'seller', 'exporter',
        'shipper/exporter (principal or seller)',
    ],
    'consignee': [
        'consignee', 'consignee (non-negotiable)', 'consignee (non negotiable)',
        'to the order of', 'buyer',
    ],
    'notify_party': [
        'notify party', 'notify', 'notify party/intermediate consignee',
        'also notify', 'second notify',
    ],
    'port_of_loading': [
        'port of loading', 'port of loading (pol)', 'load port', 'pol',
        'loading port', 'port of shipment',
    ],
    'port_of_discharge': [
        'port of discharge', 'port of discharge (pod)', 'discharge port', 'pod',
        'port of destination', 'final destination',
    ],
    'container_count': [
        'container count', 'total containers', 'containers',
        'number of containers', 'no. of containers or packages',
        'no of containers', 'no. of containers', 'qty',
        'no of containers or packages', 'no. of containers',
    ],
    'gross_weight_kg': [
        'gross weight (kg)', 'gross weight', 'gross wt (kgs)', 'gross wt',
        'total gross weight', 'weight', 'gross weight毛重(kgs)',
        'gross weight (kgs)', 'gross wt (kg)', 'gross weight毛重',
        'total gross wt (kgs)', 'total gross weight (kg)', 'total gross weightnn(kgs)',
    ],
}

def clean_label(label: str) -> str:
    """Clean label for fuzzy matching.
    Strips parenthetical suffixes, punctuation, normalizes whitespace.
    """
    label = label.lower().strip()
    # Remove Chinese characters
    label = re.sub(r'[\u4e00-\u9fff]+', '', label)
    # Strip parenthetical suffixes
    label = re.sub(r'\(.*?\)', '', label).strip()
    # Remove extra punctuation but keep slashes and hyphens for compound labels
    label = re.sub(r'[^a-z0-9\s/\-]', ' ', label).strip()
    # Normalize spaces
    label = ' '.join(label.split())
    return label

def _label_matches(raw_label: str, aliases: list[str], cleaned_aliases: list[str]) -> bool:
    """Check if a raw label matches any of the aliases."""
    raw_lower = raw_label.lower().strip().rstrip(':')
    cleaned_raw = clean_label(raw_label)
    
    # Exact match on lowercase (with colon stripped)
    for alias in aliases:
        if raw_lower == alias or raw_lower.startswith(alias + ' ') or raw_lower == alias.rstrip(':'):
            return True
    
    # Clean match
    if cleaned_raw in cleaned_aliases:
        return True
        
    return False

def map_raw_fields(raw_fields: dict[str, str]) -> dict[str, dict]:
    """Map raw field labels to canonical field names.
    
    Returns dict with canonical field names as keys, values are:
    {
        'value': str,  # the raw value
        'raw_label': str,  # the original label
        'method': 'alias'  # how it was mapped
    }
    """
    mapped_fields = {}
    
    # Pre-process field aliases for cleaned labels
    clean_alias_map = {}
    for canonical, aliases in FIELD_ALIASES.items():
        clean_alias_map[canonical] = [clean_label(alias) for alias in aliases]

    for raw_label, value in raw_fields.items():
        if not value or not value.strip():
            continue
            
        for canonical, aliases in FIELD_ALIASES.items():
            if canonical not in mapped_fields:
                if _label_matches(raw_label, aliases, clean_alias_map[canonical]):
                    mapped_fields[canonical] = {
                        'value': value,
                        'raw_label': raw_label,
                        'method': 'alias'
                    }
                    break

    return mapped_fields

def parse_container_count(raw_value: str) -> Optional[int]:
    """Parse container count from string."""
    if not raw_value or raw_value.strip().upper() == 'N/A':
        return None
        
    # Match the leading number, optionally zero-padded
    match = re.search(r'^\s*0*(\d+)', raw_value)
    if match:
        return int(match.group(1))
    
    return None

def parse_gross_weight(raw_value: str) -> Optional[int]:
    """Parse gross weight from string."""
    if not raw_value or raw_value.strip().upper() == 'N/A' or '_' in raw_value:
        return None
        
    # Find the numeric part
    match = re.search(r'([\d,]+(?:\.\d+)?)', raw_value)
    if match:
        num_str = match.group(1).replace(',', '')
        try:
            return int(float(num_str))
        except ValueError:
            return None
    return None

def normalize_entity(value: str) -> str:
    """Normalize entity names (shipper, consignee, notify_party)."""
    if not value:
        return ""
        
    val = value.strip().upper()
    # Normalize common abbreviations
    val = val.replace('SDN. BHD.', 'SDN BHD')
    val = val.replace('PTE. LTD.', 'PTE LTD')
    val = val.replace('CO. LTD.', 'CO LTD')
    val = val.replace('LTD.', 'LTD')
    val = val.replace('INC.', 'INC')
    
    # Remove address lines (after semicolons, newlines, or pipes)
    val = re.split(r';|\n|\|', val)[0].strip()
    
    return val

def normalize_port(value: str) -> str:
    """Normalize port names."""
    if not value:
        return ""
        
    val = value.strip().upper()
    
    # Strip UN/LOCODE in parentheses like (MYPKG), (PECLL)
    val = re.sub(r'\([A-Z]{5}\)', '', val)
    
    # Clean up extra spaces
    val = ' '.join(val.split()).strip()
    
    return val

def extract_fields(parsed_doc: Dict[str, Any]) -> Dict[str, Dict]:
    """Extract and normalize the 7 canonical fields from a parsed document.
    
    Args:
        parsed_doc: Output from document_parser.parse_document()
    
    Returns:
        Dict with 7 canonical field names, each containing:
        {
            'raw_value': str | None,
            'normalized_value': str | int | None,  
            'raw_label': str | None,
            'method': str,
            'confidence': float  # 0.0-1.0
        }
    """
    raw_fields = parsed_doc.get('raw_fields', {})

    mapped = map_raw_fields(raw_fields)
    
    canonical_fields = [
        'shipper', 'consignee', 'notify_party',
        'port_of_loading', 'port_of_discharge',
        'container_count', 'gross_weight_kg'
    ]
    
    result = {}
    for field in canonical_fields:
        if field in mapped:
            raw_val = mapped[field]['value']
            raw_label = mapped[field]['raw_label']
            method = mapped[field]['method']
            
            normalized_value = None
            if field in ('shipper', 'consignee', 'notify_party'):
                normalized_value = normalize_entity(raw_val)
            elif field in ('port_of_loading', 'port_of_discharge'):
                normalized_value = normalize_port(raw_val)
            elif field == 'container_count':
                normalized_value = parse_container_count(raw_val)
            elif field == 'gross_weight_kg':
                normalized_value = parse_gross_weight(raw_val)
                
            result[field] = {
                'raw_value': raw_val,
                'normalized_value': normalized_value,
                'raw_label': raw_label,
                'method': method,
                'confidence': 1.0 if normalized_value is not None or raw_val is not None else 0.5
            }
        else:
            result[field] = {
                'raw_value': None,
                'normalized_value': None,
                'raw_label': None,
                'method': 'not_found',
                'confidence': 0.0
            }
            
    return result
