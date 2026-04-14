# IpruAssist FundFactSheet Extractor

A Python tool that extracts structured information from mutual fund factsheet PDFs and generates formatted Markdown reports using a blazing fast, hybrid text and GPT-4o vision architecture.

## Features

- **Hybrid Extraction Architecture**: Employs a 3-tier strategy for instant fact sheet lookup: zero-API index regex parsing, text-only `gpt-4o-mini` scanning, and targeted `gpt-4o` vision fallback.
- **Embedded Text & High-Res Vision**: Combines direct PDF text extraction with high-resolution image rendering to achieve maximum accuracy on numbers while understanding complex table layouts.
- **Multi-Fund Support**: Automatically detects multiple fund schemes in a single document (using fast Index/TOC scanning) and lets you choose which one to process.
- **Strict Anti-Hallucination**: Data is extracted with forensic accuracy; it outputs only what is explicitly printed, with no invented values.
- **Markdown Output**: Generates clean, structured reports ready for documentation or sharing.
## Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

## Usage

### Basic Usage
```bash
python main.py
```
You'll be prompted to enter the path to a PDF factsheet.

### Direct File Input
```bash
python main.py --file "Documents/<filename>.pdf"
```

## Project Structure

```
├── main.py                    # Entry point
├── modules/
│   ├── pdf_reader.py         # PDF validation and image conversion
│   ├── ai_extractor.py       # GPT-4o vision-based extraction logic
│   ├── output_writer.py      # Markdown file generation
├── Documents/                # Place your PDF files here
├── Output/                   # Generated Markdown reports
└── .env                      # Environment variables (API keys)
```

## Requirements

- Python 3.10+
- OpenAI API key (with GPT-4o vision access)
- Required packages: see `requirements.txt`

## How It Works

1. **Load & Validate**: Reads the PDF, validates format, and extracts both the embedded text layer and high-res images.
2. **Scan for Funds**: Rapidly scans the Index/TOC using pure text to dynamically identify all fund schemes.
3. **User Selection**: Displays found funds and lets you choose which to extract.
4. **Locate Pages (3-Tier)**: Lightning-fast location of target pages via index regex matching, falling back to text-only scanning, and then vision if necessary.
5. **Detailed Extraction**: Performs deep, focused data extraction strictly on the target pages using `gpt-4o` combined with text-layer checks.
6. **Generate Report**: Outputs a structured Markdown file to `/Output`.

## Limitations

- Large PDFs may take time due to batch processing delays (respects OpenAI TPM limits)
- Requires active OpenAI API account with sufficient credits
- Works best with clearly formatted factsheets

## Made for ICICI Pru AMC
