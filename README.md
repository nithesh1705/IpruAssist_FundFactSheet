# IpruAssist FundFactSheet Extractor

A Python tool that extracts structured information from mutual fund factsheet PDFs and generates formatted Markdown reports using GPT-4o vision analysis.

## Features

- **PDF Processing**: Efficiently converts PDF pages to high-quality images for AI analysis
- **AI-Powered Extraction**: Uses OpenAI's GPT-4o vision API to intelligently extract fund details
- **Multi-Fund Support**: Automatically detects multiple fund schemes in a single document and lets you select which one to process
- **Batched Processing**: Handles large PDFs (100+ pages) by processing pages in configurable batches to respect API rate limits
- **Markdown Output**: Generates clean, structured reports ready for documentation or sharing

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

1. **Load & Validate**: Reads the PDF and validates the file format
2. **Scan for Funds**: Processes pages in batches to identify all fund schemes
3. **User Selection**: Displays found funds and lets you choose which to extract
4. **Extract Details**: Performs a focused extraction on relevant pages only
5. **Generate Report**: Outputs a structured Markdown file to `/Output`

## Limitations

- Large PDFs may take time due to batch processing delays (respects OpenAI TPM limits)
- Requires active OpenAI API account with sufficient credits
- Works best with clearly formatted factsheets

## Made for ICICI Pru AMC
