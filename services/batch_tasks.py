"""
Background task handler for batch file extraction
"""
from services.job_processor import task_handler
from services.file_router import FileRouter


@task_handler("extract_batch")
async def extract_batch_task(parameters: dict, progress_callback=None) -> dict:
    """Background batch file extraction task."""
    files_data = parameters["files"]
    request_id = parameters.get("request_id")
    results = []
    
    for i, file_data in enumerate(files_data):
        if progress_callback:
            await progress_callback((i / len(files_data)) * 100.0)
        
        try:
            # Extract content for each file
            file_type, content = await FileRouter.extract_file_content(
                file_data["contents"],
                file_data["filename"],
                request_id=request_id
            )
            
            results.append({
                "filename": file_data["filename"],
                "file_type": file_type,
                "content": content,
                "success": True
            })
        
        except Exception as e:
            results.append({
                "filename": file_data["filename"],
                "error": str(e),
                "success": False
            })
    
    if progress_callback:
        await progress_callback(100.0)
    
    return {
        "total_files": len(files_data),
        "successful": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"]),
        "results": results
    }
