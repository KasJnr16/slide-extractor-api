from fastapi import FastAPI, UploadFile, File
from pptx import Presentation
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow your web app to access this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to your domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Extraction helpers (your code)
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


def extract_text_from_pptx_file(file_path_or_obj):
    prs = Presentation(file_path_or_obj)
    all_text = []

    for slide_index, slide in enumerate(prs.slides):
        slide_text = []
        for shape in slide.shapes:
            extract_from_shape(shape, slide_text)

        combined = "\n".join(filter(None, slide_text))
        all_text.append({"slide": slide_index + 1, "text": combined})
    
    return all_text

# ------------------------------
# API endpoint
# ------------------------------
@app.post("/extract_text/")
async def extract_text(file: UploadFile = File(...)):
    # Ensure only .pptx or .ppt
    if not file.filename.endswith((".pptx", ".ppt")):
        return {"error": "File must be a .pptx or .ppt"}

    # Read uploaded file into memory
    contents = await file.read()
    
    # Presentation can take a file-like object
    from io import BytesIO
    file_like = BytesIO(contents)

    try:
        slides_text = extract_text_from_pptx_file(file_like)
        return {"filename": file.filename, "slides": slides_text}
    except Exception as e:
        return {"error": str(e)}
