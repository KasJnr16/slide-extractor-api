"""
Refactored Slide Extractor API with separation of concerns
"""
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from services.file_router import FileRouter
from services.document_generator import create_exam_package_in_memory
import os

app = FastAPI()

# Allow your web app to access this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ======================================================
# MAIN FILE EXTRACTION ENDPOINT
# ======================================================
@app.post("/extract_file/")
async def extract_file(file: UploadFile = File(...)):
    """
    Universal file extraction endpoint that routes to appropriate extractor
    
    Args:
        file: Uploaded file of any supported type
        
    Returns:
        Structured data based on file type:
        - Excel: sheets with cell-by-cell data
        - PowerPoint: slides with text content
        - Text/Document: extracted text
    """
    try:
        contents = await file.read()
        filename = file.filename
        
        # Route to appropriate extractor
        file_type, extracted_content = FileRouter.extract_file_content(contents, filename)
        
        # Format response based on file type
        if file_type == 'excel':
            return {
                "filename": filename,
                "file_type": "excel",
                "sheets": extracted_content["sheets"]
            }
        elif file_type == 'powerpoint':
            return {
                "filename": filename,
                "file_type": "powerpoint",
                "slides": extracted_content
            }
        else:  # text files
            return {
                "filename": filename,
                "file_type": "text",
                "text": extracted_content
            }
            
    except Exception as e:
        return {"error": str(e)}


# ======================================================
# SPECIALIZED ENDPOINTS (Keep for backward compatibility)
# ======================================================
@app.post("/extract_excel/")
async def extract_excel(file: UploadFile = File(...)):
    """Dedicated Excel extraction endpoint"""
    try:
        contents = await file.read()
        filename = file.filename
        
        excel_data = FileRouter.extract_file_content(contents, filename)[1]
        
        return {
            "filename": filename,
            "sheets": excel_data["sheets"]
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/extract_document_text/")
async def extract_document_text(file: UploadFile = File(...)):
    """Extract text from any document (backward compatibility)"""
    try:
        contents = await file.read()
        filename = file.filename
        
        extracted_text = FileRouter.extract_text_content(contents, filename)
        
        return {
            "filename": filename,
            "text": extracted_text
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/extract_text/")
async def extract_text(file: UploadFile = File(...)):
    """PowerPoint-specific extraction (backward compatibility)"""
    try:
        contents = await file.read()
        filename = file.filename
        
        # Ensure only .pptx or .ppt
        ext = os.path.splitext(filename)[1].lower()
        if ext not in (".pptx", ".ppt"):
            return {"error": "File must be a .pptx or .ppt"}
        
        slides_text = FileRouter.extract_file_content(contents, filename)[1]
        
        return {"filename": filename, "slides": slides_text}
        
    except Exception as e:
        return {"error": str(e)}


# ======================================================
# DOCUMENT GENERATION ENDPOINTS (Keep as they are)
# ======================================================
@app.post("/generate_exam_zip/")
async def generate_exam_zip(
    document_name: str,
    questions_file: UploadFile = File(...),
    answers_file: UploadFile = File(...)
):
    """
    Accepts two text files (questions and answers) and returns a zip
    containing two Word documents (questions + answers) without saving them on disk.
    """
    try:
        # Read uploaded text files
        questions_text = (await questions_file.read()).decode("utf-8").splitlines()
        answers_text = (await answers_file.read()).decode("utf-8").splitlines()

        # Create zip in memory
        zip_io = create_exam_package_in_memory(document_name, questions_text, answers_text)

        # Return as downloadable file
        return StreamingResponse(
            zip_io,
            media_type="application/x-zip-compressed",
            headers={"Content-Disposition": f"attachment; filename={document_name}.zip"}
        )
    except Exception as e:
        return {"error": str(e)}


# ======================================================
# HEALTH CHECK ENDPOINT
# ======================================================
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "slide-extractor-api"}


if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

