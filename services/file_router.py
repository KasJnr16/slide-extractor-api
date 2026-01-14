"""
File routing service to determine appropriate extractor for different file types
"""
from typing import Dict, Any, Tuple
from .text_extractor import extract_text_from_any, extract_excel_from_bytes
from .powerpoint_extractor import extract_powerpoint_text


class FileRouter:
    """Routes files to appropriate extractors based on file type"""
    
    @staticmethod
    def get_file_type(filename: str) -> str:
        """Determine file type category from filename"""
        filename = filename.lower()
        
        if filename.endswith(('.xlsx', '.xls', '.xlsm')):
            return 'excel'
        elif filename.endswith(('.pptx', '.ppt')):
            return 'powerpoint'
        elif filename.endswith(('.pdf', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.tiff')):
            return 'text'
        else:
            return 'unknown'
    
    @staticmethod
    def extract_file_content(file_bytes: bytes, filename: str) -> Tuple[str, Any]:
        """
        Route file to appropriate extractor and return content with type
        
        Args:
            file_bytes: File content as bytes
            filename: Name of the file
            
        Returns:
            Tuple of (file_type, extracted_content)
        """
        file_type = FileRouter.get_file_type(filename)
        
        if file_type == 'excel':
            content = extract_excel_from_bytes(file_bytes, filename)
        elif file_type == 'powerpoint':
            content = extract_powerpoint_text(file_bytes, filename)
        elif file_type == 'text':
            content = extract_text_from_any(file_bytes, filename)
        else:
            raise ValueError(f"Unsupported file type: {filename}")
        
        return file_type, content
    
    @staticmethod
    def extract_text_content(file_bytes: bytes, filename: str) -> str:
        """
        Extract text content from any supported file type
        
        Args:
            file_bytes: File content as bytes
            filename: Name of the file
            
        Returns:
            String containing extracted text
        """
        file_type = FileRouter.get_file_type(filename)
        
        if file_type == 'excel':
            excel_data = extract_excel_from_bytes(file_bytes, filename)
            # Convert Excel data to text format
            from .text_extractor import clean_text
            all_text = []
            for sheet in excel_data["sheets"]:
                all_text.append(f"=== Sheet: {sheet['name']} ===")
                for cell in sheet["data"]:
                    if cell["value"].strip():
                        all_text.append(f"{cell['cell']}: {cell['value']}")
            return clean_text("\n".join(all_text))
        
        elif file_type == 'powerpoint':
            slides = extract_powerpoint_text(file_bytes, filename)
            combined = "\n\n".join(
                f"Slide {s['slide']}:\n{s['text']}" for s in slides
            )
            return combined.strip()
        
        elif file_type == 'text':
            return extract_text_from_any(file_bytes, filename)
        
        else:
            raise ValueError(f"Unsupported file type: {filename}")
