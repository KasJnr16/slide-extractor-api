"""
PowerPoint extraction services for both .pptx and .ppt formats
"""
import os
import subprocess
from io import BytesIO
from pptx import Presentation


def extract_from_shape(shape, collected):
    """Extract text from PowerPoint shapes recursively"""
    if shape.has_text_frame:
        for paragraph in shape.text_frame.paragraphs:
            collected.append(paragraph.text)

    if shape.has_table:
        table = shape.table
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.text_frame.paragraphs:
                    collected.append(paragraph.text)

    if shape.shape_type == 6:  # GROUPED SHAPE
        for subshape in shape.shapes:
            extract_from_shape(subshape, collected)


def extract_text_from_pptx_file(file_like):
    """
    Extract text from modern PowerPoint files (.pptx)
    
    Args:
        file_like: File-like object containing PowerPoint data
        
    Returns:
        List of dictionaries with slide number and text content
    """
    prs = Presentation(file_like)
    all_text = []

    for slide_index, slide in enumerate(prs.slides):
        slide_text = []
        for shape in slide.shapes:
            extract_from_shape(shape, slide_text)

        combined = "\n".join(filter(None, slide_text))
        all_text.append({"slide": slide_index + 1, "text": combined})
    
    return all_text


def extract_text_from_ppt_file(file_path):
    """
    Extract text from legacy PowerPoint files (.ppt) using Java converter
    
    Args:
        file_path: Path to the .ppt file
        
    Returns:
        List of dictionaries with slide number and text content
    """
    jar_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ppt_converter/target/ppt-converter-1.0-jar-with-dependencies.jar")

    try:
        result = subprocess.run(
            ["java", "-jar", jar_path, file_path],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print("❌ Java extraction failed:", e)
        print("stdout:", e.stdout)
        print("stderr:", e.stderr)
        return []

    slides_text = []
    current_slide = 0
    slide_lines = []

    for line in result.stdout.splitlines():
        if line.startswith("--- Slide"):
            if slide_lines:
                slides_text.append({"slide": current_slide, "text": "\n".join(slide_lines)})
                slide_lines = []

            current_slide = int(line.replace("--- Slide", "").replace("---", "").strip())
        else:
            slide_lines.append(line)

    if slide_lines:
        slides_text.append({"slide": current_slide, "text": "\n".join(slide_lines)})

    return slides_text


def extract_powerpoint_text(file_bytes: bytes, filename: str):
    """
    Universal PowerPoint text extraction
    
    Args:
        file_bytes: PowerPoint file content as bytes
        filename: Name of the file
        
    Returns:
        List of dictionaries with slide number and text content
    """
    filename = filename.lower()
    
    if filename.endswith(".pptx"):
        file_like = BytesIO(file_bytes)
        return extract_text_from_pptx_file(file_like)
    
    elif filename.endswith(".ppt"):
        # Save temp file for Java extractor
        temp_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), filename)
        with open(temp_path, "wb") as f:
            f.write(file_bytes)
        
        try:
            slides = extract_text_from_ppt_file(temp_path)
            return slides
        finally:
            # Clean temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
    
    else:
        raise ValueError("File must be a .pptx or .ppt file")
