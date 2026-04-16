import os
import urllib.parse
import traceback
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from modules.pdf_reader import is_valid_pdf, get_pdf_page_texts, get_pdf_filename_stem
from modules.ai_extractor import extract_fund_names, extract_fund_details
from modules.ai_word_generator import ai_markdown_to_docx
from main import get_openai_client
from fastapi.responses import FileResponse, Response
import io

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOCS_DIR = os.path.join(os.path.dirname(__file__), "Documents")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "Output")
os.makedirs(DOCS_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

class ExtractFundsRequest(BaseModel):
    filename: str

class ProcessFundRequest(BaseModel):
    filename: str
    fund_name: str

class WordDownloadRequest(BaseModel):
    markdown_content: str
    fund_name: str

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    file_path = os.path.join(DOCS_DIR, file.filename)
    with open(file_path, "wb") as f:
        f.write(await file.read())
        
    return {"filename": file.filename, "message": "File uploaded successfully"}

@app.post("/extract-funds")
async def extract_funds(req: ExtractFundsRequest):
    file_path = os.path.join(DOCS_DIR, req.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    page_texts = get_pdf_page_texts(file_path)
    client = get_openai_client()
    try:
        fund_names = extract_fund_names(client, file_path, page_texts)
        return {"funds": fund_names}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-fund")
async def process_fund(req: ProcessFundRequest):
    file_path = os.path.join(DOCS_DIR, req.filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
        
    page_texts = get_pdf_page_texts(file_path)
    client = get_openai_client()
    try:
        markdown_content, used_pages = extract_fund_details(client, file_path, req.fund_name, page_texts)
        
        current_time_str = datetime.now().strftime("%d%m%Y_%H%M%S")
        output_filename = f"{req.fund_name}_{current_time_str}"
        
        # word_path = os.path.join(OUTPUT_DIR, f"{output_filename}.docx")
        # markdown_to_docx(markdown_content, word_path)
        
        return {
            "markdown_content": markdown_content,
            "used_pages": used_pages
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/download-word")
async def download_word(req: WordDownloadRequest):
    try:
        client = get_openai_client()
        buffer = ai_markdown_to_docx(client, req.markdown_content)

        current_time_str = datetime.now().strftime("%d%m%Y_%H%M%S")
        safe_name = req.fund_name.replace("/", "-").replace("\\", "-")
        output_filename = f"{safe_name}_{current_time_str}.docx"

        # HTTP headers are latin-1 only; percent-encode the filename via RFC 5987
        # so Unicode characters (smart quotes, ₹, etc.) never crash the header.
        encoded_filename = urllib.parse.quote(output_filename.encode("utf-8"), safe="")
        content_disposition = f"attachment; filename*=UTF-8''{encoded_filename}"

        # Use Response (not StreamingResponse) — BytesIO iterated line-by-line
        # corrupts binary .docx content. Read all bytes at once instead.
        return Response(
            content=buffer.read(),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": content_disposition}
        )
    except Exception as e:
        traceback.print_exc()   # full traceback in server console
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=filename)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
