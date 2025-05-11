from typing import Dict, List, Optional

class TagFormatter:
    def __init__(self, tags_data: Optional[Dict[int, Dict[str, str]]] = None):
        self.tags_data = tags_data or {}

    def format_tags(self, tag_names: List[str]) -> str:
        """Formatta una lista di nomi di tag con le relative icone"""
        if not self.tags_data:
            return ", ".join(tag_names)
            
        formatted_tags = []
        for tag_name in tag_names:
            # Cerca il tag nei dati
            tag_info = next(
                (t for t in self.tags_data.values() if t['name'] == tag_name), 
                None
            )
            if tag_info:
                formatted_tags.append(f"{tag_info['icon']} {tag_name}")
            else:
                formatted_tags.append(tag_name)
        return ", ".join(formatted_tags)