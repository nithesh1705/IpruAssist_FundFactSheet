import os
import re
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def add_formatted_text(paragraph, text: str):
    """Parses simple **markdown** and adds it to the paragraph as formatted runs."""
    parts = text.split('**')
    for idx, part in enumerate(parts):
        if not part:
            continue
        run = paragraph.add_run(part)
        if idx % 2 == 1: # Odd elements are inside ** **
            run.bold = True

def flush_table(doc, table_rows):
    """Creates a Word table from the accumulated rows."""
    if not table_rows:
        return
    num_cols = max((len(r) for r in table_rows), default=0)
    if num_cols > 0:
        table = doc.add_table(rows=len(table_rows), cols=num_cols)
        table.style = 'Table Grid'
        for r_idx, row_data in enumerate(table_rows):
            for c_idx, cell_value in enumerate(row_data):
                if c_idx < num_cols:
                    cell = table.cell(r_idx, c_idx)
                    cell.text = "" 
                    p = cell.paragraphs[0]
                    add_formatted_text(p, cell_value)
        doc.add_paragraph()  # add space after table
    table_rows.clear()

def markdown_to_docx(markdown_content: str, output_path: str):
    doc = Document()
    
    lines = markdown_content.split('\n')
    
    in_table = False
    table_rows = []
    
    for line in lines:
        line = line.strip()
        
        # Determine if current line is part of a table
        is_table_line = line.startswith('|') and line.endswith('|')
        
        # If we exit a table or hit an empty line, flush the stored rows
        if (not is_table_line and in_table) or (not line and in_table):
            flush_table(doc, table_rows)
            in_table = False
            
        if not line:
            continue
            
        # Tables
        if is_table_line:
            in_table = True
            # Split and clean row
            row = [cell.strip() for cell in line.split('|')[1:-1]]
            # ignore separator
            if all(set(c) == {'-'} or set(c) == {':', '-'} or not c for c in row):
                continue
            table_rows.append(row)
            continue
            
        # Headers
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            text = line.lstrip('#').strip()
            # Clean up potential bold markers in headers just in case
            text = text.replace('**', '')
            heading = doc.add_heading(text, level=min(level, 9))
            continue
            
        # Lists
        if line.startswith('- ') or line.startswith('* '):
            text = line[2:]
            p = doc.add_paragraph(style='List Bullet')
            add_formatted_text(p, text)
            continue
            
        # Normal Text
        p = doc.add_paragraph()
        add_formatted_text(p, line)
        
    # Check if a table was left at the end
    if in_table and table_rows:
        flush_table(doc, table_rows)

    doc.save(output_path)
    return output_path
