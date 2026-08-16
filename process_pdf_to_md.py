# -*- coding: utf-8 -*-
r"""
================================================================================
 HIGH-PERFORMANCE LOCAL MARATHI LEGAL DOCUMENT EXTRACTION ENGINE (.PDF & .DOCX)
 (100% OFFLINE, PRIVATE, STRICT QUEUE INGESTION, OPENCV CLAHE & TESSERACT 5.5)
================================================================================
"""

import os
import re
import sys
import time
import shutil
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure UTF-8 output on Windows consoles
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

import pymupdf
import pymupdf as fitz
fitz = pymupdf

import pytesseract
from PIL import Image
import numpy as np
import cv2
import wordninja
from markitdown import MarkItDown

# Configure Tesseract 5.5 binary path for Windows
TESSERACT_EXE = r"C:\Users\Kartikplayzz\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_EXE):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

SUPPORTED_EXTENSIONS = ('.pdf', '.docx')

# Legacy / Non-Unicode CCTNS font character set
CORRUPT_FONT_CHARS = set("¯ÖÓ®´ê£ôû¤ü¸ßµÝãæ¥¿²Öî•§Ö×ÛÎú¾ÖÂ™Ò†Ö™ü‡ÝÖÏÀ±ȡĤš“ǓĆȨ¡ǕƧ‘ȰȲǑɉǔÛƻæȶ•œ×ǽ¢œ¡ȾÍ")

GAZETTE_PATTERNS = [
    r"^.*महाराष्ट्र शासन राजपत्र.*$",
    r"^.*असाधारण भाग.*$",
    r"^.*प्राधिकृत प्रकाशन.*$",
    r"^.*भाग (?:चार|एक|दोन|तीन|पाच|सहा|सात|आठ).*$",
    r"^.*MAHARASHTRA GOVERNMENT GAZETTE.*$",
    r"^.*RNI No\. MAHMRA/\d+/\d+.*$",
    r"^.*Reg\. No\. MH/MR/South-\d+/\d+.*$",
    r"^.*Postal Reg\. No\..*$",
    r"^\s*\[\s*किंमत\s*:\s*रुपये.*\]\s*$",
    r"^\s*\[\s*पृष्ठे\s*\d+\s*\]\s*$",
    r"^\s*\[\s*Pages\s*\d+\s*\]\s*$",
]


def is_corrupted_or_legacy_font(text: str) -> bool:
    """Detects if extracted PDF text is corrupted non-Unicode, Shivaji, KrutiDev, or ASCII font mappings."""
    if not text or len(text.strip()) < 10:
        return True
    
    # Check corrupted non-Unicode symbol density
    corrupt_count = sum(1 for c in text if c in CORRUPT_FONT_CHARS)
    if len(text) > 0 and (corrupt_count / len(text)) > 0.02:
        return True
        
    devanagari_count = sum(1 for c in text if '\u0900' <= c <= '\u097F')
    latin_symbol_count = sum(1 for c in text if ord(c) > 127 and (ord(c) < 0x0900 or ord(c) > 0x097F))
    
    if latin_symbol_count > 10 and devanagari_count < (latin_symbol_count * 0.5):
        return True
        
    return False


def clean_gazette_boilerplate(text: str) -> str:
    """Removes official gazette headers, registration numbers, and repetitive noise."""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        
        if stripped in ('.', '..', '...', '* * * *', ''):
            continue
            
        is_boilerplate = False
        for pat in GAZETTE_PATTERNS:
            if re.fullmatch(pat, stripped, re.IGNORECASE) or (len(stripped) < 80 and re.search(pat, stripped, re.IGNORECASE)):
                is_boilerplate = True
                break
        
        if is_boilerplate:
            continue
        
        if re.fullmatch(r"\[?\s*(?:Page\s+)?\d+\s*(?:of\s+\d+)?\s*\]?", stripped, re.IGNORECASE):
            continue
            
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)


def clean_government_publication_backmatter(text: str) -> str:
    """Strips trailing government printing press and stationery boilerplate."""
    patterns = [
        r"(?i)ON BEHALF OF GOVERNMENT PRINTING, STATIONERY AND PUBLICATION.*$",
        r"(?i)PRINTED AT GOVERNMENT CENTRAL PRESS.*$",
        r"(?i)DIRECTORATE OF GOVERNMENT PRINTING.*$",
        r"शासकीय मध्यवर्ती मुद्रणालय.*$",
        r"मुद्रक व प्रकाशक.*शासकीय मुद्रणालय.*$",
    ]
    cleaned = text
    for pat in patterns:
        cleaned = re.sub(pat, "", cleaned, flags=re.DOTALL | re.MULTILINE)
    return cleaned.strip()


def clean_gazette_marginal_notes(text: str) -> str:
    """Removes disconnected English marginal notes from Marathi gazette text."""
    lines = text.split('\n')
    cleaned = []
    
    for line in lines:
        stripped = line.strip()
        if re.fullmatch(r"^[A-Z][a-z]+(?:\s+[a-z]+){0,3}\.$", stripped) and len(stripped) < 35:
            continue
        if re.fullmatch(r"^(?:Short title|Extent and commencement|Definitions|Power to make rules|Repeal and saving)\.?$", stripped, re.IGNORECASE):
            continue
        cleaned.append(line)
        
    return '\n'.join(cleaned)


def repair_english_word_spacing(text: str) -> str:
    """Uses WordNinja to split fused English statutory legal citations."""
    def fix_glued_match(match):
        token = match.group(0)
        if len(token) > 16 and not token.startswith("http") and not token.startswith("www"):
            parts = wordninja.split(token)
            if len(parts) > 1 and all(len(p) > 1 for p in parts):
                return " ".join(parts)
        return token

    return re.sub(r'\b[A-Za-z]{15,}\b', fix_glued_match, text)


def repair_marathi_ocr_and_numbered_lists(text: str) -> str:
    """Repairs common Marathi Devanagari OCR glyph confusions and un-splits compound words."""
    replacements = [
        (r'\bकिंबा\b', 'किंवा'),
        (r'\bनोंदविणा-या\b', 'नोंदविणाऱ्या'),
        (r'\bनोंदविणा-याचे\b', 'नोंदविणाऱ्याचे'),
        (r'\bअंमत्रदार\b', 'अंमलदार'),
        (r'\bआंमतलदार\b', 'अंमलदार'),
        (r'\bआंमलदार\b', 'अंमलदार'),
        (r'\bपोल्लीस\b', 'पोलीस'),
        (r'\bपोल्रीस\b', 'पोलीस'),
        (r'\bशनिंगणापुर\b', 'शनिशिंगणापूर'),
        (r'\bशनंगणापूर\b', 'शनिशिंगणापूर'),
        (r'\bशनंगनापुर\b', 'शनिशिंगणापूर'),
        (r'\bशिगंणापुर\b', 'शनिशिंगणापूर'),
        (r'\bखाडा\s+खोड\b', 'खाडा-खोड'),
        (r'\bखरे\s+खोटेपणा\b', 'खरे-खोटेपणा'),
        (r'\bदखल\s+पात्र\b', 'दखलपात्र'),
        (r'\bअदखल\s+पात्र\b', 'अदखलपात्र'),
        (r'\bअदखलपाञ\b', 'अदखलपात्र'),
        (r'\bस्वातंञ्यदिनानिमित्त\b', 'स्वातंत्र्यदिनानिमित्त'),
        (r'\bत्रॉकअप\b', 'लॉकअप'),
        (r'\bवायरत्रेस\b', 'वायरलेस'),
        (r'\bवावात\b', 'बाबत'),
        (r'\bसाहेव\b', 'साहेब'),
        (r'\bदाखत्र\b', 'दाखल'),
        (r'\bदित्रा\b', 'दिला'),
        (r'\bतित्रा\b', 'तिला'),
        (r'\bकळवित्रे\b', 'कळविले'),
        (r'\bघेतत्रा\b', 'घेतला'),
    ]
    cleaned = text
    for pattern, repl in replacements:
        cleaned = re.sub(pattern, repl, cleaned)

    # Rejoin orphaned numbered list headers (e.g. "१०.\n\nमजकूर" -> "१०. मजकूर")
    cleaned = re.sub(r'(\n(?:[०-९\d]{1,3}|[a-zA-Z\(\)]+)\.)\s*\n\s*([^\n])', r'\1 \2', cleaned)
    return cleaned


def format_legal_markdown_structure(text: str) -> str:
    """Enforces clean Markdown structure with Section headers and table integrity."""
    lines = text.split('\n')
    formatted = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            formatted.append("")
            continue
            
        # Format standalone Section headers: e.g. "कलम ४. व्याख्या" -> "### कलम ४. व्याख्या"
        if re.match(r'^(?:कलम|Section|पोट-कलम|अनुसूची|प्रकरण)\s+[०-९\d]+[A-Za-z\.\-\s]+', stripped) and len(stripped) < 80:
            if not stripped.startswith('#'):
                formatted.append(f"### {stripped}")
                continue
                
        # Format true signature blocks
        if re.match(r'^(?:सही|स्वाक्षरी|Signature|Seal|Stamp)\s*[:\/\-]', stripped, re.IGNORECASE):
            formatted.append(f"\n> **{stripped}**\n")
            continue
            
        formatted.append(line)
        
    return '\n'.join(formatted)


def clean_form_blanks_and_tables(text: str) -> str:
    """Suppresses OCR dotted-line hallucinations and symbol loops (* % 1 7 9) into clean blanks."""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
            
        # Detect hallucinated dotted-line symbol noise (e.g. "* ***१*१*%*१*१*१**")
        symbol_count = len(re.findall(r'[\*\%\$\#\@\!\?\^\|\_\.\-\~\\\/]', stripped))
        digits_and_dots = len(re.findall(r'[०-९0-9\.\s]', stripped))
        total_len = len(stripped)
        
        if total_len >= 12 and (symbol_count + digits_and_dots) / total_len > 0.70:
            if not any(kw in stripped.lower() for kw in ["कलम", "section", "रुपये", "दिनांक", "act", "rule", "नोंद", "पान"]):
                cleaned_lines.append("________________________________________________________")
                continue
                
        # Suppress repetitive dotted line underscores
        if re.fullmatch(r'[\.\_\-\s]{6,}', stripped):
            cleaned_lines.append("________________________________________________________")
            continue
            
        # Suppress repetitive syllable loops (e.g. "POOH POOH POOH")
        cleaned_line = re.sub(r'\b([A-Za-z]{2,8})\b(?:\s+\1\b){3,}', r'\1', stripped)
        cleaned_lines.append(cleaned_line)
        
    return '\n'.join(cleaned_lines)


def contains_devanagari(text: str) -> bool:
    """Returns True if string contains Devanagari Unicode characters (U+0900 to U+097F)."""
    return any('\u0900' <= char <= '\u097F' for char in text)


def extract_act_metadata_title(doc, filename: str) -> str:
    """Extracts a clean document title from PDF metadata, first page text, or filename."""
    base_name, _ = os.path.splitext(filename)
    try:
        meta_title = doc.metadata.get("title", "").strip()
        if meta_title and len(meta_title) > 3 and not meta_title.lower().endswith(".pdf") and not is_corrupted_or_legacy_font(meta_title):
            return meta_title
    except Exception:
        pass
        
    try:
        first_page_text = doc[0].get_text("text").strip().splitlines()
        for line in first_page_text[:10]:
            clean_l = line.strip()
            if len(clean_l) > 5 and not clean_l.startswith("<!--") and not clean_l.isdigit():
                if not is_corrupted_or_legacy_font(clean_l) and any(kw in clean_l.lower() for kw in ["act", "rules", "अधिनियम", "नियम", "महाराष्ट्र", "police", "manual", "order", "पंचनामा"]):
                    return clean_l
    except Exception:
        pass
        
    return base_name


def preprocess_image_for_ocr(np_image: np.ndarray) -> np.ndarray:
    """Hardware-accelerated image preprocessing using OpenCV OpenCL & CLAHE."""
    try:
        if cv2.ocl.haveOpenCL():
            cv2.ocl.setUseOpenCL(True)
            u_img = cv2.UMat(np_image)
            u_gray = cv2.cvtColor(u_img, cv2.COLOR_RGB2GRAY)
            u_denoised = cv2.bilateralFilter(u_gray, d=5, sigmaColor=50, sigmaSpace=50)
            clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
            u_enhanced = clahe.apply(u_denoised)
            return u_enhanced.get()
    except Exception:
        pass

    # CPU Fallback
    gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)
    denoised = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    return enhanced


def ocr_page_image(pil_img: Image.Image) -> str:
    """Executes high-accuracy Tesseract 5.5 OCR configured strictly for mar+eng."""
    np_img = np.array(pil_img)
    processed = preprocess_image_for_ocr(np_img)
    custom_config = r'--oem 3 --psm 6'
    try:
        text = pytesseract.image_to_string(processed, lang='mar+eng', config=custom_config)
        return text.strip()
    except Exception as e:
        return f"[OCR Error: {e}]"


def convert_pdf_to_markdown(
    pdf_path: str,
    output_dir: str,
    completed_dir: str = None,
    dpi: int = 300,
    ocr_workers: int = 6
) -> dict:
    """
    100% Robust Local PDF Conversion Engine:
    - Analyzes font integrity on every page (auto-detects Shivaji / CCTNS / non-Unicode corruptions).
    - True Unicode Marathi Vector PDFs -> PyMuPDF Instant Text Stream.
    - Scanned Photocopies / Legacy Font PDFs -> 300 DPI OpenCV CLAHE + Tesseract 5.5 (mar+eng) OCR.
    - Post-processes with full Marathi Legal NLP Sanitizer.
    """
    start_time = time.time()
    filename = os.path.basename(pdf_path)
    base_name, _ = os.path.splitext(filename)
    out_md_path = os.path.join(output_dir, f"{base_name}.md")
    
    os.makedirs(output_dir, exist_ok=True)
    
    result = {
        "filename": filename,
        "output_path": out_md_path,
        "type": "PDF",
        "engine": "Pure Local OCR & Legal NLP",
        "pages": 0,
        "success": False,
        "elapsed_sec": 0,
        "error": None,
        "moved_to": None
    }
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        result["pages"] = total_pages
        doc_title = extract_act_metadata_title(doc, filename)
        
        digital_pages = {}
        image_pages = {}
        
        # Analyze font integrity page by page
        for pno in range(total_pages):
            page = doc[pno]
            raw_text = page.get_text("text").strip()
            
            # If text is clean Unicode Devanagari / English without font corruption, use digital stream
            if len(raw_text) > 120 and contains_devanagari(raw_text) and not is_corrupted_or_legacy_font(raw_text):
                digital_pages[pno] = raw_text
            else:
                # Page is either a scanned image OR has corrupted non-Unicode font -> Route to 300 DPI OCR!
                image_pages[pno] = page
                
        page_results = {}
        for pno, text in digital_pages.items():
            page_results[pno] = text
            
        # Process OCR image pages in parallel
        if image_pages:
            def process_single_image_page(item):
                pno, page = item
                pix = page.get_pixmap(dpi=dpi)
                pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                ocr_text = ocr_page_image(pil_img)
                return pno, ocr_text

            max_threads = min(ocr_workers, len(image_pages), 8)
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = {executor.submit(process_single_image_page, item): item[0] for item in image_pages.items()}
                completed_img_pages = 0
                total_img_pages = len(image_pages)
                for future in as_completed(futures):
                    pno, content = future.result()
                    page_results[pno] = content
                    completed_img_pages += 1
                    if total_img_pages >= 5 and (completed_img_pages % 5 == 0 or completed_img_pages == total_img_pages):
                        safe_print(f"PROGRESS: Processed {completed_img_pages}/{total_img_pages} pages ({int((completed_img_pages / total_img_pages) * 100)}%)...")
                    
        doc.close()
        
        # Build structured Markdown
        md_sections = []
        md_sections.append(f"# {doc_title}\n")
        md_sections.append(f"> **Source File**: `{filename}`  \n> **Engine**: Pure Local Marathi Intelligence (Tesseract 5.5 + OpenCV)  \n> **Total Pages**: {total_pages}  \n> **Extraction Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n")
        
        for pno in range(total_pages):
            ptext = page_results.get(pno, "").strip()
            if ptext:
                md_sections.append(f"<!-- Page {pno + 1} -->\n{ptext}\n")
                
        full_raw_md = "\n\n".join(md_sections)
        backmatter_cleaned = clean_government_publication_backmatter(full_raw_md)
        marginal_cleaned = clean_gazette_marginal_notes(backmatter_cleaned)
        cleaned_md = clean_gazette_boilerplate(marginal_cleaned)
        spaced_md = repair_english_word_spacing(cleaned_md)
        repaired_md = repair_marathi_ocr_and_numbered_lists(spaced_md)
        form_cleaned_md = clean_form_blanks_and_tables(repaired_md)
        final_md = format_legal_markdown_structure(form_cleaned_md)
        
        with open(out_md_path, "w", encoding="utf-8") as f:
            f.write(final_md)
            
        result["success"] = True
        result["output_size_bytes"] = os.path.getsize(out_md_path)
        
        # Move processed file to archive
        if completed_dir and os.path.exists(pdf_path):
            os.makedirs(completed_dir, exist_ok=True)
            target_dest = os.path.join(completed_dir, filename)
            if os.path.abspath(pdf_path) != os.path.abspath(target_dest):
                shutil.move(pdf_path, target_dest)
                result["moved_to"] = target_dest
                
    except Exception as e:
        result["error"] = str(e)
        result["success"] = False
        
    result["elapsed_sec"] = round(time.time() - start_time, 2)
    return result


def convert_docx_to_markdown(docx_path: str, output_dir: str, completed_dir: str = None) -> dict:
    """Converts Word .docx documents to Markdown using Microsoft MarkItDown."""
    start_time = time.time()
    filename = os.path.basename(docx_path)
    base_name, _ = os.path.splitext(filename)
    out_md_path = os.path.join(output_dir, f"{base_name}.md")
    
    os.makedirs(output_dir, exist_ok=True)
    
    result = {
        "filename": filename,
        "output_path": out_md_path,
        "type": "DOCX",
        "engine": "Microsoft MarkItDown 0.1.7",
        "pages": 1,
        "success": False,
        "elapsed_sec": 0,
        "error": None,
        "moved_to": None
    }
    
    try:
        md = MarkItDown()
        conv_res = md.convert(docx_path)
        raw_text = conv_res.text_content if hasattr(conv_res, "text_content") else str(conv_res)
        
        header = f"# {base_name}\n\n> **Source File**: `{filename}`  \n> **Engine**: Microsoft MarkItDown 0.1.7  \n> **Extraction Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n"
        
        cleaned_text = clean_form_blanks_and_tables(repair_marathi_ocr_and_numbered_lists(raw_text))
        final_md = header + cleaned_text
        
        with open(out_md_path, "w", encoding="utf-8") as f:
            f.write(final_md)
            
        result["success"] = True
        result["output_size_bytes"] = os.path.getsize(out_md_path)
        
        if completed_dir and os.path.exists(docx_path):
            os.makedirs(completed_dir, exist_ok=True)
            target_dest = os.path.join(completed_dir, filename)
            if os.path.abspath(docx_path) != os.path.abspath(target_dest):
                shutil.move(docx_path, target_dest)
                result["moved_to"] = target_dest
                
    except Exception as e:
        result["error"] = str(e)
        result["success"] = False
        
    result["elapsed_sec"] = round(time.time() - start_time, 2)
    return result


def safe_print(msg: str):
    """Safely prints to stdout without raising encoding errors on Windows."""
    try:
        print(msg)
    except UnicodeEncodeError:
        try:
            print(msg.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass


def run_batch_conversion(input_dir: str, output_dir: str, completed_dir: str = None, max_workers: int = 6):
    """Batch converter for all PDF and DOCX files in input queue."""
    if not os.path.exists(input_dir):
        safe_print(f"[ERROR] Input directory '{input_dir}' does not exist.")
        return []
        
    all_files = [
        f for f in sorted(os.listdir(input_dir))
        if f.lower().endswith(SUPPORTED_EXTENSIONS) and not f.startswith('~$') and os.path.isfile(os.path.join(input_dir, f))
    ]
    
    safe_print("=" * 80)
    safe_print(f"LEGAL DOCUMENT INGESTION PROTOCOL (100% LOCAL & PRIVATE)")
    safe_print(f"Input Queue Directory  : {input_dir}")
    safe_print(f"Target Output Directory: {output_dir}")
    if completed_dir:
        safe_print(f"Archive Completed To   : {completed_dir}")
    safe_print("=" * 80)
    
    if not all_files:
        safe_print(f"[INFO] Ingestion Queue is clean: 0 new (.pdf / .docx) files in '{input_dir}'.")
        return []
        
    safe_print(f"Found {len(all_files)} document(s) in queue '{input_dir}'.\n")
    results = []
    
    for f in all_files:
        full_path = os.path.join(input_dir, f)
        if f.lower().endswith('.docx'):
            res = convert_docx_to_markdown(full_path, output_dir, completed_dir=completed_dir)
        else:
            res = convert_pdf_to_markdown(full_path, output_dir, completed_dir=completed_dir, ocr_workers=max_workers)
            
        results.append(res)
        status = "SUCCESS" if res["success"] else "FAILED"
        size = f"{res.get('output_size_bytes', 0):,} bytes" if res["success"] else f"Error: {res.get('error')}"
        safe_print(f"[{status}] [{res.get('type')}] {res['filename']} in {res['elapsed_sec']}s -> {size}")
                
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pure Local PDF & DOCX to Markdown converter for Marathi and English legal documents.")
    parser.add_argument("doc_path", nargs="?", help="Path to single .pdf or .docx file")
    parser.add_argument("--batch", action="store_true", help="Run batch conversion on all files in input folder")
    parser.add_argument("--input", default=r"E:\PDF", help="Input directory")
    parser.add_argument("--output", default=r"E:\PDF to MD", help="Output directory")
    parser.add_argument("--completed-dir", default=r"E:\Completed PDF file Extraction", help="Archive directory")
    parser.add_argument("--no-move", action="store_true", help="Do not move source files after extraction")
    parser.add_argument("--workers", type=int, default=6, help="Parallel OCR workers")
    
    args = parser.parse_args()
    target_completed = None if args.no_move else args.completed_dir
    
    if args.batch or not args.doc_path:
        run_batch_conversion(args.input, args.output, completed_dir=target_completed, max_workers=args.workers)
    else:
        if args.doc_path.lower().endswith('.docx'):
            res = convert_docx_to_markdown(args.doc_path, args.output, completed_dir=target_completed)
        else:
            res = convert_pdf_to_markdown(args.doc_path, args.output, completed_dir=target_completed, ocr_workers=args.workers)
        safe_print(f"Converted '{res['filename']}' in {res['elapsed_sec']}s. Success: {res['success']}")
        if not res.get("success"):
            sys.exit(1)
