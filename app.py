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
        
        # Format response with consistent structure
        return {
            "filename": filename,
            "file_type": file_type,
            "content": extracted_content
        }
            
    except Exception as e:
        return {"error": str(e)}


# ======================================================
# DOCUMENT GENERATION ENDPOINTS
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

