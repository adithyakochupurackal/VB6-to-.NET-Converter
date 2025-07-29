from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from server import MCP, OUTPUT_DIR
import time
from sse_starlette.sse import EventSourceResponse
import json
import asyncio
from typing import Optional

# Initialize FastAPI app
app = FastAPI(title="VB6 to .NET Converter", version="2.0.6", description="Convert VB6 projects to .NET 9 Worker Services with enhanced SSE streaming and download endpoint")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MCP
mcp = MCP()

@app.get("/")
async def root():
    return {
        "message": "VB6 to .NET Converter API",
        "version": "2.0.6",
        "status": "running",
        "timestamp": time.time()
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "azure_openai": "configured" if mcp.is_openai_configured() else "not configured"
    }

@app.post("/convert")
async def convert_vb6_to_dotnet(
    zip_file: Optional[UploadFile] = File(None),
    github_link: Optional[str] = Form(None)
):
    if not zip_file and not github_link:
        raise HTTPException(status_code=400, detail="Please provide either a ZIP file or GitHub repository link")
    start_time = time.time()
    try:
        conversion_task = asyncio.create_task(mcp.run(zip_file, github_link))
        result_data, conversion_id = await asyncio.wait_for(conversion_task, timeout=mcp.CONVERSION_TIMEOUT_SECONDS)
        duration = time.time() - start_time
        output_file_path = OUTPUT_DIR / f"{conversion_id}.zip"
        with open(output_file_path, 'wb') as f:
            f.write(result_data)
        mcp.logger.info(f"Conversion completed successfully in {duration:.2f} seconds", extra={"stage": "pipeline", "progress": 100})
        return {
            "status": "success",
            "conversion_id": conversion_id,
            "duration": duration,
            "message": "Conversion completed. Use the conversion_id to download the file.",
            "download_url": f"/download/{conversion_id}"
        }
    except asyncio.TimeoutError:
        duration = time.time() - start_time
        mcp.logger.error(f"Conversion timed out after {duration:.2f} seconds", extra={"stage": "pipeline"})
        raise HTTPException(status_code=504, detail="Conversion process timed out")
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        mcp.logger.error(f"Conversion failed after {duration:.2f} seconds: {str(e)}", extra={"stage": "pipeline"})
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during conversion: {str(e)}"
        )

@app.get("/download/{conversion_id}")
async def download_converted_file(conversion_id: str):
    file_path = OUTPUT_DIR / f"{conversion_id}.zip"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired")
    if file_path.stat().st_size == 0:
        file_path.unlink()
        raise HTTPException(status_code=500, detail="File is empty")
    try:
        return FileResponse(
            file_path,
            filename="MyWindowsService.zip",
            headers={"Content-Disposition": "attachment; filename=MyWindowsService.zip"}
        )
    except Exception as e:
        mcp.logger.error(f"Error serving file {conversion_id}: {str(e)}", extra={"stage": "download"})
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")
    finally:
        try:
            file_path.unlink(missing_ok=True)
            mcp.logger.info(f"Deleted downloaded file: {file_path}", extra={"stage": "download"})
        except Exception as e:
            mcp.logger.error(f"Failed to delete file {file_path}: {str(e)}", extra={"stage": "download"})

@app.get("/stream")
async def stream_conversion_progress():
    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(mcp.log_queue.get(), timeout=30.0)
                yield {
                    "event": event.get("event_type", "log"),
                    "data": json.dumps({
                        "message": event.get("message", ""),
                        "level": event.get("level", "INFO"),
                        "timestamp": event.get("timestamp", time.time()),
                        "stage": event.get("stage", "unknown"),
                        "agent": event.get("agent", None),
                        "state": event.get("state", None),
                        "current_agent": event.get("current_agent", None),
                        "progress": event.get("progress", 0),
                        "details": event.get("details", {})
                    })
                }
                if event.get("stage") == "pipeline" and event.get("state") in ["Completed", "Failed"]:
                    break
            except asyncio.TimeoutError:
                yield {
                    "event": "ping",
                    "data": json.dumps({
                        "message": "Keep-alive ping",
                        "timestamp": time.time(),
                        "progress": mcp.sse_handler.progress
                    })
                }
    return EventSourceResponse(event_generator())