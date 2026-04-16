# IpruAssist FundFactSheet Extractor

A web-based tool with a React frontend and Python/FastAPI backend that extracts structured information from mutual fund factsheet PDFs. It generates formatted Word (.docx) reports using a blazing fast, hybrid text and GPT-4o vision architecture.

## Features

- **Interactive Web UI**: Modern, responsive React frontend (Vite + Tailwind CSS) with drag-and-drop PDF uploads and interactive fund selection.
- **Hybrid Extraction Architecture**: Employs a 3-tier strategy for instant fact sheet lookup: zero-API index regex parsing, text-only `gpt-4o-mini` scanning, and targeted `gpt-4o` vision fallback.
- **Embedded Text & High-Res Vision**: Combines direct PDF text extraction with high-resolution image rendering to achieve maximum accuracy on numbers while understanding complex table layouts.
- **Multi-Fund Support**: Automatically detects multiple fund schemes in a single document (using fast Index/TOC scanning) and lets you choose which one to process directly from the UI.
- **Strict Anti-Hallucination**: Data is extracted with forensic accuracy; it outputs only what is explicitly printed, with no invented values.
- **Word Document Output**: Generates cleanly formatted `.docx` reports with proper tables and typography, ready for documentation or sharing. Option to preview Markdown directly in the frontend UI.

## Project Structure

```
├── main.py                    # Legacy CLI entry point
├── api.py                     # FastAPI backend application
├── modules/
│   ├── pdf_reader.py          # PDF validation and image conversion
│   ├── ai_extractor.py        # GPT-4o vision-based extraction logic
│   ├── word_writer.py         # Word (.docx) generation
│   ├── output_writer.py       # Markdown file generation (legacy)
├── frontend/                  # React + Vite web application
├── Documents/                 # Uploaded PDF files directory
├── Output/                    # Generated Word (.docx) reports directory
└── .env                       # Environment variables (API keys)
```

## Requirements

- Python 3.10+
- Node.js 18+ (for frontend)
- OpenAI API key (with GPT-4o access)
- Required Python packages: see `requirements.txt`

## Installation

1. Clone or download this repository.
2. Setup the **Backend**:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory and add your OpenAI API key:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```
4. Setup the **Frontend**:
   ```bash
   cd frontend
   npm install
   ```

## Usage

You must run both the backend API and the frontend application simultaneously.

### 1. Start the Backend API
From the root directory, run:
```bash
python api.py
# Or run via uvicorn directly:
# uvicorn api:app --reload --host 0.0.0.0 --port 8000
```
This will start the FastAPI server on `http://localhost:8000`.

### 2. Start the Frontend App
Open a new terminal window, navigate to the `frontend` directory, and run:
```bash
cd frontend
npm run dev
```
This will start the Vite development server (usually on `http://localhost:5173`). Open that URL in your browser to interact with the application.

## How It Works

1. **Upload**: User uploads a PDF factsheet through the React UI, which validates and stores it in `/Documents`.
2. **Scan for Funds**: The backend rapidly scans the internal Index/TOC using pure text to dynamically identify all fund schemes.
3. **User Selection**: The UI displays found funds and lets the user choose which to extract.
4. **Locate Pages (3-Tier)**: Lightning-fast location of target pages via index regex matching, falling back to text-only scanning, and then vision if necessary.
5. **Detailed Extraction**: Performs deep, focused data extraction strictly on the target pages using `gpt-4o` combined with text-layer checks.
6. **Generate Report**: The Markdown is securely converted into a structured Word `.docx` file and saved to `/Output`. The user can instantly download it or preview the data in the UI.

## Limitations

- Large PDFs may take time due to batch processing delays (respects OpenAI TPM limits).
- Requires active OpenAI API account with sufficient credits.
- Works best with clearly formatted factsheets.

## Made for ICICI Pru AMC
