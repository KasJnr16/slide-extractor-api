from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pptx import Presentation
import subprocess
from io import BytesIO
import os

app = FastAPI()

# Allow your web app to access this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Python .pptx extraction
# ------------------------------
def extract_from_shape(shape, collected):
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
    prs = Presentation(file_like)
    all_text = []

    for slide_index, slide in enumerate(prs.slides):
        slide_text = []
        for shape in slide.shapes:
            extract_from_shape(shape, slide_text)

        combined = "\n".join(filter(None, slide_text))
        all_text.append({"slide": slide_index + 1, "text": combined})
    
    return all_text

# ------------------------------
# Java .ppt extraction
# ------------------------------
def extract_text_from_ppt_file(file_path):
    jar_path = os.path.join(os.path.dirname(__file__), "ppt_converter/target/ppt-converter-1.0-jar-with-dependencies.jar")

    
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

# ------------------------------
# API endpoint
# ------------------------------
@app.post("/extract_text/")
async def extract_text(file: UploadFile = File(...)):
    # Ensure only .pptx or .ppt
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".pptx", ".ppt"):
        return {"error": "File must be a .pptx or .ppt"}

    # Save uploaded file temporarily if it's a .ppt (Java needs a file path)
    if ext == ".ppt":
        temp_path = os.path.join(os.path.dirname(__file__), file.filename)
        with open(temp_path, "wb") as f:
            f.write(await file.read())

        slides_text = extract_text_from_ppt_file(temp_path)

        # Optionally remove temp file
        os.remove(temp_path)

        return {"filename": file.filename, "slides": slides_text}

    # For .pptx, read in memory
    contents = await file.read()
    file_like = BytesIO(contents)
    slides_text = extract_text_from_pptx_file(file_like)
    
    return {"filename": file.filename, "slides": slides_text}
