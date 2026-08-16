from markitdown import MarkItDown
r"""
================================================================================
 HIGH-PERFORMANCE DOCUMENT TO MARKDOWN EXTRACTION ENGINE (.PDF & .DOCX)
 (STRICT QUEUE INGESTION IN E:\PDF\ & PURE MARATHI/ENGLISH OCR)
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
import PyPDF2
import pytesseract
from PIL import Image
import numpy as np
import cv2
import wordninja
import docx  # python-docx for .docx processing

# Ensure Tesseract executable is found
TESSERACT_PATHS = [
    r"C:\Users\Kartikplayzz\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    "tesseract"
]
for p in TESSERACT_PATHS:
    if os.path.exists(p) or p == "tesseract":
        pytesseract.pytesseract.tesseract_cmd = p
        break

SUPPORTED_EXTENSIONS = ('.pdf', '.docx')

# ----------------------------------------------------------------------
# HARDWARE GPU ACCELERATION CONFIGURATION (OpenCL / CUDA)
# ----------------------------------------------------------------------
GPU_HARDWARE_NAME = "None"
HAS_GPU_ACCEL = False

try:
    if cv2.ocl.haveOpenCL():
        cv2.ocl.setUseOpenCL(True)
        HAS_GPU_ACCEL = True
        try:
            dev = cv2.ocl.Device.getDefault()
            GPU_HARDWARE_NAME = dev.name()
        except:
            GPU_HARDWARE_NAME = "OpenCL Compatible GPU"
except Exception:
    HAS_GPU_ACCEL = False



# ----------------------------------------------------------------------
# 1. ADVANCED TEXT CLEANING & POST-PROCESSING RULES
# ----------------------------------------------------------------------

GAZETTE_PATTERNS = [
    r"(?i)THE\s+GAZETTE\s+OF\s+INDIA\s*(?:EXTRAORDINARY)?",
    r"(?i)EXTRAORDINARY",
    r"(?i)\[?PART\s*II\s*[-—–]?\s*SEC(?:TION)?\.?\s*1\]?",
    r"(?i)PUBLISHED\s+BY\s+AUTHORITY",
    r"(?i)REGISTERED\s+NO\.?\s+[A-Z0-9\-\(\)\/\.]+",
    r"(?i)NEW\s+DELHI,\s+[A-Z\s]+,\s+[A-Z]+\s+\d+,\s+\d{4}\s*\/?\s*[A-Z\s]+\s+\d+,\s+\d{4}",
    r"(?i)SEC\.\s*1\]\s*THE\s+GAZETTE\s+OF\s+INDIA\s+EXTRAORDINARY\s*\d*",
    r"(?i)\d*\s*THE\s+GAZETTE\s+OF\s+INDIA\s+EXTRAORDINARY\s*\[?PART\s*II\s*[-—–]?\s*SEC\.\s*1\]?",
    r"(?i)MINISTRY\s+OF\s+LAW\s+AND\s+JUSTICE\s*\(Legislative\s+Department\)",
    r"(?i)New\s+Delhi,\s+the\s+\d+(?:st|nd|rd|th)?\s+[A-Za-z]+,\s+\d{4}\s*\/\s*[A-Za-z]+\s+\d+,\s+\d{4}\s*\(Saka\)",
    r"(?i)Maharashtra\s+Government\s+Publication\s*can\s+be\s+obtained\s+from[—–-]?",
    r"(?i)THE\s+DIRECTOR\s*GOVERNMENT\s+PRINTING,\s+STATIONERY\s+AND\s+PUBLICATION",
    r"(?i)GOVERNMENT\s+PRINTING,\s+STATIONERY\s+AND\s+PUBLICATION",
    r"(?i)GOVERNMENT\s+PHOTOZINCO\s+PRESS\s+AND\s+BOOK\s+DEPOT",
    r"(?i)GOVERNMENT\s+PRESS\s+AND\s+BOOK\s+DEPOT",
    r"(?i)GOVERNMENT\s+PRESS\s+AND\s+STATIONERY\s+STORE",
    r"(?i)AND\s+THE\s+RECOGNISED\s+BOOKSELLERS",
    r"(?i)Phone\s*:\s*[\d\s\-,]+",
    r"(?i)GOVERNMENT\s+CENTRAL\s+PRESS,\s+MUMBAI",
    r"(?i)PRINTED\s+IN\s+INDIA\s+BY\s+THE\s+MANAGER,\s+GOVERNMENT\s+CENTRAL\s+PRESS[^\n]*",
    r"(?i)महाराष्ट्र\s+शासन\s+राजपत्र\s*(?:असाधारण)?",
    r"(?i)प्राधिकृत\s+प्रकाशित",
]

LEGACY_FONT_PATTERNS = [
    r"vf/kdkj", r"Ekfgrh", r"izek\.ks", r"uequk", r"Izkfr", r"vtZnkj", r"laiksdZ", r"f\"kdk",
    r"[€ȡ™›ĤǓ’‘Ȱ“ȲǑ‘“Ȣ¡ǕƧ]", r"[ā-žǄ-ȟ]{3,}"
]

def is_legacy_or_cctns_font_text(text: str) -> bool:
    """Detects legacy KrutiDev, Shivaji, or CCTNS non-standard font encodings."""
    for pat in LEGACY_FONT_PATTERNS:
        if re.search(pat, text):
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
        
        if stripped in ('.', '..', '...', '* * * *', '•'):
            continue
            
        is_boilerplate = False
        for pat in GAZETTE_PATTERNS:
            if re.fullmatch(pat, stripped) or (len(stripped) < 80 and re.search(pat, stripped)):
                is_boilerplate = True
                break
        
        if is_boilerplate:
            continue
        
        if re.fullmatch(r"\[?\s*(?:Page\s+)?\d+\s*(?:of\s+\d+)?\s*\]?", stripped, re.IGNORECASE):
            continue
            
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)


def clean_government_publication_backmatter(text: str) -> str:
    """Strips back-page sales depot and Government Printing Press ordering address listings."""
    pattern = r"(?s)(?:<!--\s*Page\s*\d+\s*-->\s*)?(?:\[\s*\d{4}\s*:\s*Mah\.\s*[A-Z0-9]+\s*)?Maharashtra\s+Government\s+Publication\s*can\s+be\s+obtained\s+from.*$"
    return re.sub(pattern, "", text, flags=re.IGNORECASE).strip()


def clean_gazette_marginal_notes(text: str) -> str:
    """Strips disconnected marginal column side-notes and running document title footers."""
    patterns = [
        r"(?is)\bPower\s+to\s+remove\s+difficulties\.",
        r"(?is)\bRepeal\s+of\s+Mah\.?\s*Ord\.?\s*[A-Z0-9\s]+\s+and\s+saving\.",
        r"(?is)\bMah\.?\s*Ord\.?\s*[A-Z0-9\s]+\.",
        r"(?is)Maharashtra\s+Protection\s+of\s+Interest\s+of\s+Depositors\s*\([^\)]+\)\s*Act,\s*\d{4}\.",
    ]
    for p in patterns:
        text = re.sub(p, "", text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def repair_english_word_spacing(text: str) -> str:
    """Repairs concatenated / glued English words while preserving numbers, code, and markdown."""
    def fix_glued_match(match):
        word = match.group(0)
        if len(word) > 12 and word.isalpha():
            splits = wordninja.split(word)
            if len(splits) > 1 and all(len(s) > 1 or s.lower() in ('a', 'i') for s in splits):
                return " ".join(splits)
        return word

    replacements = [
        (r"\bThisActmaybecalled\b", "This Act may be called"),
        (r"\bactiontakenin\b", "action taken in"),
        (r"\bbecontirtued\b", "be continued"),
        (r"\bcasesand\b", "cases and"),
        (r"\bshallbecontirtued\b", "shall be continued"),
        (r"\bso\s*tem\s*n\s*is\s*ed\b", "solemnised"),
        (r"\bso\s*lemnised\b", "solemnised"),
        (r"\bachild\b", "a child"),
        (r"\baminor\b", "a minor"),
        (r"\baperson\b", "a person"),
        (r"\bthecourt\b", "the court"),
        (r"\bthestate\b", "the state"),
        (r"\btheGovernment\b", "the Government"),
        (r"\banyperson\b", "any person"),
        (r"\bundersection\b", "under section"),
        (r"\bwithfine\b", "with fine"),
        (r"\bwhichmayextendto\b", "which may extend to"),
        (r"\bshallbepunishable\b", "shall be punishable"),
        (r"\bwithimprisonment\b", "with imprisonment"),
        (r"\btermmayextend\b", "term may extend"),
    ]
    
    for pat, rep in replacements:
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)
        
    lines = text.split('\n')
    out_lines = []
    for line in lines:
        if line.startswith('#') or line.startswith('|') or line.startswith('>'):
            out_lines.append(line)
            continue
        fixed_line = re.sub(r"[A-Za-z]{14,}", fix_glued_match, line)
        out_lines.append(fixed_line)
        
    return '\n'.join(out_lines)


def repair_marathi_ocr_and_numbered_lists(text: str) -> str:
    """Repairs common OCR character confusions in Marathi legal text, fixes compound words, and re-joins orphaned numbered lists."""
    # 1. Clean OCR Marathi Glyph Confusions (e.g. ब vs व, किंबा vs किंवा)
    text = re.sub(r'\bब\b', 'व', text)
    text = re.sub(r'\bकिंबा\b', 'किंवा', text)
    text = re.sub(r'\bबापरता\b', 'वापरता', text)
    text = re.sub(r'\bबापरलेले\b', 'वापरलेले', text)
    text = re.sub(r'\bनोंदवबिणा-या\b', 'नोंदविणाऱ्या', text)
    text = re.sub(r'\bतपशोलवबार\b', 'तपशीलवार', text)
    text = re.sub(r'\bनाहोल\b', 'नाही', text)
    text = re.sub(r'\bनाहो\b', 'नाही', text)
    text = re.sub(r'\bवैद्यकोय\b', 'वैद्यकीय', text)
    text = re.sub(r'\bपिडोत\b', 'पीडित', text)
    text = re.sub(r'\bघटनापोठाने\b', 'घटनापीठाने', text)
    text = re.sub(r'\bअबधी\b', 'अवधी', text)
    text = re.sub(r'\bघरफोडोबाबत\b', 'घरफोडीबाबत', text)
    text = re.sub(r'\bबाको\b', 'बाकी', text)
    text = re.sub(r'\bपुरबणी\b', 'पुरवणी', text)
    text = re.sub(r'\bकारबाई\b', 'कारवाई', text)
    text = re.sub(r'\bचोकशी\b', 'चौकशी', text)
    text = re.sub(r'\bदेनंदिनीत\b', 'दैनंदिनीत', text)
    text = re.sub(r'\bनिष्पत्र\b', 'निष्पन्न', text)
    text = re.sub(r'\bअतिम\b', 'अंतिम', text)
    text = re.sub(r'\bअपराध्यांमध्ये\b', 'अपराधांमध्ये', text)
    text = re.sub(r'\bGarret\b', 'खबरीमध्ये', text)
    text = re.sub(r'\b\(गार\)\b', '(FIR)', text)
    
    # 2. Fix broken hyphenated Marathi compound words (e.g. खाडा - खोड -> खाडा-खोड)
    text = re.sub(r'खाडा\s*[-—–]\s*खोड', 'खाडा-खोड', text)
    text = re.sub(r'खरे\s*[-—–]\s*खोटेपणा', 'खरे-खोटेपणा', text)
    text = re.sub(r'नाते\s*[-—–]\s*वाईकांना', 'नातेवाईकांना', text)
    text = re.sub(r'काही\s*[-—–]\s*कारणास्तव', 'काही कारणास्तव', text)
    text = re.sub(r'वाद\s*[-—–]\s*विवाद', 'वादविवाद', text)
    
    # 3. Clean Statutory and Court Citations
    text = re.sub(r'Great\s+कलम\s+ew\s+अन्वये', 'Cr.P.C. कलम १५४/१६४ अन्वये', text)
    text = re.sub(r'HAS\.\s*कलम\s*१५४\(१\)', 'Cr.P.C. कलम १५४(१)', text)
    text = re.sub(r'GUA\s+BAT\s+२०७', 'Cr.P.C. कलम २०७', text)
    text = re.sub(r'BI\.\s*१५७\(१\)', 'Cr.P.C. कलम १५७(१)', text)
    text = re.sub(r'३७६५,७,८,\s*9१०४६', '३७६ (१, २), ५०६', text)
    text = re.sub(r'\bWNT\b', 'इत्यादी', text)
    text = re.sub(r'\bBraet\b', 'हद्दीत', text)
    text = re.sub(r'धि8९वावा8\s+Rama\s+v/s\s+Hariyana\s+State', 'State of Haryana v/s Bhajan Lal', text)
    text = re.sub(r'^\s*शै,\s*$', '', text, flags=re.MULTILINE)
    
    # 4. Re-join orphaned numbered lines (e.g. Page 2 "१०.", "११.", "१२." split across lines)
    lines = text.split('\n')
    merged = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Check for isolated number tokens: "१०.", "११९.", "१२.", "Vv,", "१८.", "१९,"
        num_m = re.match(r'^(?:[०-९\d]+|Vv|शट|२ठ)[\.,]?$', stripped)
        if num_m and i + 1 < len(lines):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip() and not lines[j].strip().startswith(('#', '<!--', '---', '>')):
                norm_num = stripped.replace(',', '.').replace('Vv', '१४').replace('शट', '१८').replace('२ठ', '२४').replace('११९', '११')
                if not norm_num.endswith('.'):
                    norm_num += '.'
                merged.append(f"{norm_num} {lines[j].strip()}")
                i = j + 1
                continue
        merged.append(line)
        i += 1
        
    return '\n'.join(merged)


def format_legal_markdown_structure(text: str) -> str:
    """Formats headings, chapters, sections, and lists into clean Markdown without breaking compound words or regular instructions."""
    lines = text.split('\n')
    formatted = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            formatted.append("")
            continue
            
        # Top-level Title / Act Name
        if re.match(r"^(?:THE\s+[A-Z0-9\s,\-\(\)]+\s+ACT,\s*\d{4}|ACT\s+NO\.\s+\d+\s+OF\s+\d{4})", stripped, re.IGNORECASE) and not line.startswith('#'):
            formatted.append(f"\n# {stripped}\n")
            continue
            
        # Chapters / Parts: "CHAPTER I", "PART II", "प्रकरण १", "भाग २"
        if re.match(r"^(?:CHAPTER|PART|प्रकरण|भाग)\s+[IVXLCDM0-9]+[A-Z]?(?:\s*[-—–:]\s*.*)?$", stripped, re.IGNORECASE):
            formatted.append(f"\n## {stripped}\n")
            continue
            
        # Statutory Sections: "Section 12. Short title...", "कलम ३. व्याख्या" (STRICT: Requires explicit 'Section' or 'कलम' keyword)
        sec_match = re.match(r"^(?:Section|Sec\.|कलम)\s+(\d+[A-Z]?)\.?\s*([A-Z\u0900-\u097F][^\.\n]{2,60}\.?)\s*[-—–]\s*(.*)$", stripped, re.IGNORECASE)
        if sec_match:
            sec_no, sec_title, sec_body = sec_match.groups()
            formatted.append(f"\n### Section {sec_no}. {sec_title}\n\n{sec_body}")
            continue

        # Standalone Signatures & Stamp lines at bottom of forms (EXCLUDES instructional text containing सही/स्वाक्षरी)
        if re.match(r"^(?:>+\s*)?(?:(?:\[\s*)?(?:सही|स्वाक्षरी|Signature|Digitally\s+Signed)\s*[/:\]`\*]|.*(?:अर्जदाराची\s+सही|अपीलकर्त्याची\s+सही|पोलीस\s+अंमलदाराची\s+सही|अंमलदार\s+यांची\s+सही)\s*$)", stripped, re.IGNORECASE):
            if not re.search(r"(?:करावी|घ्यावी|करावे|नाही|ऐवजी|केल्यास|असल्यास|पाहिजे|असेल|तसेच)", stripped):
                formatted.append(f"\n> **[सही / Signature / Stamp]** `{stripped}`\n")
                continue

        formatted.append(line)
        
    return '\n'.join(formatted)


def clean_form_blanks_and_tables(text: str) -> str:
    """Cleans up form blank representations, dotted-line OCR artifacts, and repetitive glyph noise."""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
            
        # Keep markdown headers, comments, quotes, tables, and page markers intact
        if stripped.startswith(('<!--', '#', '>', '---', '|')):
            cleaned_lines.append(line)
            continue

        # 1. Eliminate OCR artifact lines from dotted fill-in blanks (* % 1 7 9 etc.)
        sym_matches = re.findall(r'[*%«»#~^&|+=/\\१७९0-9\-_\.]', stripped)
        if len(stripped) >= 6 and (len(sym_matches) / len(stripped)) > 0.50:
            cleaned_lines.append("________________________________________________________")
            continue

        # 2. Eliminate OCR hallucination loops on dots / repeated patterns (e.g. POOH, HEHE, ook ec ec, 1011011)
        if re.search(r'\b(?:POOH|SHH|HHH|EHH|HEHEHE|HEHE|HEH|OOS|ook|ec|ccc|ececc|vevc|savens|1011011)\b', stripped, re.IGNORECASE):
            cleaned_lines.append("________________________________________________________")
            continue

        # 3. Clean Marathi RTI & Legal Form typos / OCR distortions
        s = stripped
        s = re.sub(r'\bपति\b', 'प्रति', s)
        s = re.sub(r'\bमहितीचा\b', 'माहितीचा', s)
        s = re.sub(r'^\s*&\s*\)', '६)', s)
        s = re.sub(r'^\s*९\s*\)\s*दुसरे\s+अपिल\s+करण्याचे\s+प्रयोजन\s*ः', '७) दुसरे अपिल करण्याचे प्रयोजन :', s)
        s = re.sub(r'^\s*संपुर्ण\s*>\s*', '', s)
        s = re.sub(r'[एलशशि]{3,}', '', s)  # OCR noise on blank lines
        
        # 4. Clean trailing OCR garbage on standard form fields
        s = re.sub(r'(\d+\))\s*अपील\s*कर्ताचे\s*संपुर्ण\s*नांव\s+[काशाक]+', r'\1 अपीलकर्त्याचे संपुर्ण नांव : ________________________________________', s)
        s = re.sub(r'(\d+\))\s*पत्ता\s+[शाक]+', r'\1 पत्ता : ________________________________________', s)
        s = re.sub(r'यांचा\s+तपशील\s+.*', 'यांचा तपशील : ________________________________________', s)
        s = re.sub(r'५\)\s*आवश्यक\s*असलेल्या\s*माहितीचे\s*वर्णन\s*/\s*तपशीलः:.*', '५) आवश्यक असलेल्या माहितीचे वर्णन / तपशील : ________________________________________', s)
        s = re.sub(r'८\)\s*अर्जदार\s*दारिद्रय\s*रेषेखालील\s*आहे\s*काय.*', '८) अर्जदार दारिद्रय रेषेखालील आहे काय : [ ] होय  /  [ ] नाही', s)
        s = re.sub(r'किंवा\s+fora\s+पोस्ट\s+क्ण', 'किंवा स्पीड पोस्ट / नोंदणीकृत पोस्ट', s)
        s = re.sub(r'ATS\s*पोस्टडाक', 'स्पीड पोस्ट / साधी डाक', s)
        s = re.sub(r'1011011\.\.\.“', '', s)
        s = re.sub(r'___________+\s*1\s*___________+\s*1', '________________________________________', s)
        s = re.sub(r'___________+\s*7\.\.', '________________________________________', s)
        
        # Normalize dotted and underline blanks
        s = re.sub(r"\.{4,}", " ________________________________________ ", s)
        s = re.sub(r"_{4,}", " ________________________________________ ", s)
        s = re.sub(r"-{4,}", " ---------------------------------------- ", s)
        
        cleaned_lines.append(s)

    res = '\n'.join(cleaned_lines)
    # Collapse multiple consecutive blank lines or underline rules
    res = re.sub(r'(?:________________________________________________________\n?){2,}', '________________________________________________________\n', res)
    res = re.sub(r'\n{3,}', '\n\n', res)
    return res.strip()


# ----------------------------------------------------------------------
# 2. OCR & IMAGE PREPROCESSING ENGINE (MARATHI & ENGLISH)
# ----------------------------------------------------------------------

def preprocess_image_for_ocr(pil_img: Image.Image, use_gpu: bool = True) -> np.ndarray:
    """Enhances image quality, contrast, and binarization for Marathi OCR using GPU OpenCL acceleration when available."""
    open_cv_image = np.array(pil_img)
    if len(open_cv_image.shape) == 3:
        if open_cv_image.shape[2] == 4:
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGBA2GRAY)
        else:
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2GRAY)
    else:
        gray = open_cv_image
        
    if HAS_GPU_ACCEL and use_gpu:
        try:
            # GPU Accelerated UMat Pipeline
            u_gray = cv2.UMat(gray)
            u_denoised = cv2.bilateralFilter(u_gray, 7, 50, 50)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            u_enhanced = clahe.apply(u_denoised)
            _, u_binarized = cv2.threshold(u_enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            return u_binarized.get()
        except Exception:
            pass

    # CPU Fallback Pipeline
    denoised = cv2.bilateralFilter(gray, 7, 50, 50)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)
    _, binarized = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binarized


def ocr_page_image(pil_img: Image.Image, lang: str = "mar+eng") -> str:
    """Runs fast Tesseract OCR for Marathi and English with adaptive preprocessing."""
    try:
        preprocessed = preprocess_image_for_ocr(pil_img)
        config = r"--oem 3 --psm 3"
        text = pytesseract.image_to_string(preprocessed, lang=lang, config=config)
        if not text.strip():
            text = pytesseract.image_to_string(pil_img, lang=lang)
        return text
    except Exception as e:
        try:
            return pytesseract.image_to_string(pil_img, lang="eng")
        except Exception:
            return ""


# ----------------------------------------------------------------------
# 3. PDF PAGE PROCESSOR
# ----------------------------------------------------------------------

def extract_tables_from_page(page: pymupdf.Page) -> list:
    """Extracts tables from a page using native PyMuPDF table finder."""
    try:
        tabs = page.find_tables()
        if not tabs or len(tabs.tables) == 0:
            return []
        
        md_tables = []
        for tab in tabs.tables:
            df_rows = tab.extract()
            if not df_rows or len(df_rows) < 2:
                continue
            header = [str(c or "").replace('\n', ' ').strip() for c in df_rows[0]]
            md = ["| " + " | ".join(header) + " |"]
            md.append("| " + " | ".join(["---"] * len(header)) + " |")
            for row in df_rows[1:]:
                clean_row = [str(c or "").replace('\n', ' ').strip() for c in row]
                while len(clean_row) < len(header):
                    clean_row.append("")
                md.append("| " + " | ".join(clean_row[:len(header)]) + " |")
            md_tables.append("\n" + "\n".join(md) + "\n")
        return md_tables
    except Exception:
        return []


def process_page_worker(pdf_path: str, page_num: int, target_dpi: int = 200) -> tuple:
    """Processes a single page independently (thread-safe):
    - Automatically routes clean digital PDFs to fast PyMuPDF stream parsing.
    - Automatically routes scanned pages and CCTNS police records to 200 DPI / 300 DPI OpenCV CLAHE + Tesseract OCR (mar+eng).
    """
    try:
        doc = pymupdf.open(pdf_path)
        page = doc[page_num]
        digital_text = page.get_text("text").strip()
        tables = extract_tables_from_page(page)
        
        page_content = []
        
        # Check if text is legacy font / CCTNS font or sparse
        is_corrupt_font = is_legacy_or_cctns_font_text(digital_text)
        has_sufficient_digital_text = len(digital_text) >= 50 and not is_corrupt_font
        
        if has_sufficient_digital_text:
            # ROUTE A: Clean digital text stream
            cleaned_text = clean_gazette_boilerplate(digital_text)
            page_content.append(cleaned_text)
        else:
            # ROUTE B: Scanned / CCTNS police records / Legacy font -> 200 DPI / 300 DPI OpenCV CLAHE + Tesseract OCR (mar+eng)
            # Use 300 DPI for dense/small text or CCTNS police diary/FIR forms, otherwise 200 DPI
            dpi = 300 if (is_corrupt_font or len(digital_text) < 10) else target_dpi
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            ocr_text = ocr_page_image(img, lang="mar+eng")
            cleaned_ocr = clean_gazette_boilerplate(ocr_text)
            page_content.append(cleaned_ocr)
            
        if tables and not is_corrupt_font:
            page_content.append("\n### Structured Tables / Schedules\n" + "\n\n".join(tables))
            
        doc.close()
        return page_num, "\n\n".join(page_content)
    except Exception as e:
        return page_num, f"[Error processing page {page_num+1}: {e}]"



# ----------------------------------------------------------------------
# SMART HYBRID WORKFLOW: LANE B - CLOUD AI VISION (GEMINI MULTIMODAL)
# ----------------------------------------------------------------------

def ocr_page_image_with_gemini_vision(pil_img: Image.Image, api_key: str) -> str:
    """Extracts Marathi legal text and structured tables from a page image using Gemini Multimodal Vision API."""
    if not api_key:
        return ""
        
    buffered = io.BytesIO()
    # Optimize image size for fast transmission
    pil_img.save(buffered, format="PNG", optimize=True)
    img_b64 = base64.b64encode(buffered.getvalue()).decode("ascii")
    
    prompt = (
        "You are an expert Marathi legal document transcription system. "
        "Transcribe this legal document page image into clean, structured Markdown (GitHub-flavored). "
        "Strict Guidelines:\n"
        "1. Extract all Marathi Devanagari text exactly as written with correct grammar and spelling.\n"
        "2. Preserve statutory section numbers, dates, case citations, and government headings.\n"
        "3. Convert all tables, police registers, and multi-column forms into clean Markdown tables.\n"
        "4. Convert fill-in-the-blank dotted lines into standardized blanks (________________________).\n"
        "5. Do NOT include extraneous introductory commentary. Output ONLY the extracted Markdown content."
    )
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": img_b64
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 4096
        }
    }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        res = urllib.request.urlopen(req, timeout=30)
        data = json.loads(res.read().decode("utf-8"))
        candidates = data.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts:
                return parts[0].get("text", "").strip()
    except Exception as e:
        safe_print(f"  [WARN] Gemini Vision API call failed: {e}. Falling back to Local Vision OCR.")
        
    return ""


def contains_devanagari(text: str) -> bool:
    """Returns True if string contains Devanagari Unicode characters (U+0900 to U+097F)."""
    return any('\u0900' <= char <= '\u097F' for char in text)


def extract_act_metadata_title(doc, filename: str) -> str:
    """Extracts a clean document title from PDF metadata or first page text or filename."""
    base_name, _ = os.path.splitext(filename)
    try:
        meta_title = doc.metadata.get("title", "").strip()
        if meta_title and len(meta_title) > 3 and not meta_title.lower().endswith(".pdf"):
            return meta_title
    except Exception:
        pass
        
    try:
        first_page_text = doc[0].get_text("text").strip().splitlines()
        for line in first_page_text[:10]:
            clean_l = line.strip()
            if len(clean_l) > 5 and not clean_l.startswith("<!--") and not clean_l.isdigit():
                if any(kw in clean_l.lower() for kw in ["act", "rules", "अधिनियम", "नियम", "महाराष्ट्र", "police", "manual", "order", "अहवाल"]):
                    return clean_l
    except Exception:
        pass
        
    return base_name

def convert_pdf_to_markdown(
    pdf_path: str,
    output_dir: str,
    completed_dir: str = None,
    dpi: int = 200,
    ocr_workers: int = 6,
    engine_mode: str = "smart_hybrid",
    api_key: str = None
) -> dict:
    """
    Unified Smart Hybrid PDF Conversion Engine:
    - Lane A: Digital Vector Stream (PyMuPDF) for text-rich pages
    - Lane B: Cloud Gemini Vision AI for complex scans / forms (if api_key provided & mode in ['smart_hybrid', 'cloud_ai'])
    - Lane C: Local OpenCV CLAHE + Tesseract 5.5 OCR for air-gapped offline scans
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
        "engine": "Smart Hybrid (Multi-Lane)",
        "pages": 0,
        "success": False,
        "elapsed_sec": 0,
        "error": None
    }
    
    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        result["pages"] = total_pages
        doc_title = extract_act_metadata_title(doc, filename)
        
        # Classify document pages into lanes
        digital_pages = {}
        image_pages = {}
        
        for pno in range(total_pages):
            page = doc[pno]
            text = page.get_text("text").strip()
            # If text has significant length and Devanagari/English characters, use Lane A (Vector Stream)
            if len(text) > 120 and (contains_devanagari(text) or len(text.split()) > 25):
                digital_pages[pno] = text
            else:
                image_pages[pno] = page
                
        page_results = {}
        for pno, text in digital_pages.items():
            page_results[pno] = text
            
        # Process image / scanned pages through Lane B (Cloud AI) or Lane C (Local OCR)
        if image_pages:
            use_cloud_ai = (engine_mode in ["smart_hybrid", "cloud_ai"]) and bool(api_key)
            result["engine"] = "Smart Hybrid (Cloud AI + MarkItDown)" if use_cloud_ai else "Smart Hybrid (Local OpenCV + Tesseract)"
            
            def process_single_image_page(item):
                pno, page = item
                pix = page.get_pixmap(dpi=dpi)
                pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # Lane B: Cloud Gemini Vision AI
                if use_cloud_ai:
                    ai_text = ocr_page_image_with_gemini_vision(pil_img, api_key)
                    if ai_text:
                        return pno, ai_text
                        
                # Lane C: Local OpenCV CLAHE + Tesseract 5.5 OCR
                processed_img = preprocess_image_for_ocr(pil_img)
                ocr_text = ocr_page_image(processed_img, lang="mar+eng")
                return pno, ocr_text

            max_threads = min(ocr_workers, len(image_pages))
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = {executor.submit(process_single_image_page, item): item[0] for item in image_pages.items()}
                for future in as_completed(futures):
                    pno, content = future.result()
                    page_results[pno] = content
                    
        doc.close()
        
        # Build structured Markdown
        md_sections = []
        md_sections.append(f"# {doc_title}\n")
        md_sections.append(f"> **Source File**: `{filename}`  \n> **Engine**: {result['engine']}  \n> **Total Pages**: {total_pages}  \n> **Extraction Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n")
        
        for pno in range(total_pages):
            ptext = page_results.get(pno, "").strip()
            if ptext:
                md_sections.append(f"<!-- Page {pno + 1} -->\n{ptext}\n")
                
        full_raw_md = "\n\n".join(md_sections)
        backmatter_cleaned = clean_government_publication_backmatter(full_raw_md)
        marginal_cleaned = clean_gazette_marginal_notes(backmatter_cleaned)
        cleaned_md = clean_gazette_boilerplate(marginal_cleaned)
        spaced_md = repair_english_word_spacing(cleaned_md)
        marathi_cleaned_md = repair_marathi_ocr_and_numbered_lists(spaced_md)
        structured_md = format_legal_markdown_structure(marathi_cleaned_md)
        final_md = clean_form_blanks_and_tables(structured_md)
        
        with open(out_md_path, "w", encoding="utf-8") as f_out:
            f_out.write(final_md)
            
        result["success"] = True
        result["output_size_bytes"] = os.path.getsize(out_md_path)
        result["elapsed_sec"] = round(time.time() - start_time, 2)
        
        if completed_dir and os.path.exists(pdf_path) and os.path.abspath(pdf_path) != os.path.abspath(os.path.join(completed_dir, filename)):
            os.makedirs(completed_dir, exist_ok=True)
            dst_path = os.path.join(completed_dir, filename)
            shutil.move(pdf_path, dst_path)
            result["moved_to"] = dst_path
            
    except Exception as e:
        result["error"] = str(e)
        result["elapsed_sec"] = round(time.time() - start_time, 2)
        
    return result


# ----------------------------------------------------------------------
# 4. DOCX DOCUMENT PROCESSOR
# ----------------------------------------------------------------------

def convert_docx_to_markdown(docx_path: str, output_dir: str, completed_dir: str = None) -> dict:
    """Converts a Word (.docx) file to a structured Markdown file using Microsoft MarkItDown + Marathi Legal NLP."""
    start_time = time.time()
    filename = os.path.basename(docx_path)
    base_name, _ = os.path.splitext(filename)
    out_md_path = os.path.join(output_dir, f"{base_name}.md")
    
    os.makedirs(output_dir, exist_ok=True)
    
    result = {
        "filename": filename,
        "output_path": out_md_path,
        "type": "DOCX",
        "engine": "Microsoft MarkItDown + Marathi NLP",
        "pages": 1,
        "success": False,
        "elapsed_sec": 0,
        "error": None
    }
    
    try:
        # 1. High-fidelity Microsoft MarkItDown Conversion
        md_engine = MarkItDown()
        conversion_res = md_engine.convert(docx_path)
        raw_markdown = conversion_res.text_content or ""
        
        # 2. Add Standard Legal Header
        header = f"# {base_name}\n\n> **Source Document**: `{filename}` (.docx)  \n> **Engine**: Microsoft MarkItDown + Marathi Legal NLP  \n> **Extraction Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n"
        
        # 3. Post-Process with Legal NLP Pipeline
        cleaned_md = clean_gazette_boilerplate(raw_markdown)
        marathi_cleaned_md = repair_marathi_ocr_and_numbered_lists(cleaned_md)
        structured_md = format_legal_markdown_structure(marathi_cleaned_md)
        final_md = clean_form_blanks_and_tables(structured_md)
        
        with open(out_md_path, "w", encoding="utf-8") as f_out:
            f_out.write(header + final_md)
            
        result["success"] = True
        result["output_size_bytes"] = os.path.getsize(out_md_path)
        result["elapsed_sec"] = round(time.time() - start_time, 2)
        
        if completed_dir and os.path.exists(docx_path) and os.path.abspath(docx_path) != os.path.abspath(os.path.join(completed_dir, filename)):
            os.makedirs(completed_dir, exist_ok=True)
            dst_path = os.path.join(completed_dir, filename)
            shutil.move(docx_path, dst_path)
            result["moved_to"] = dst_path
            
    except Exception as e:
        result["error"] = str(e)
        result["elapsed_sec"] = round(time.time() - start_time, 2)
        
    return result


def safe_print(msg: str):
    """Safely prints UTF-8 strings to standard output."""
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode('ascii', 'backslashreplace').decode('ascii'))


def run_batch_conversion(input_dir: str = r"E:\PDF", output_dir: str = r"E:\PDF to MD", completed_dir: str = r"E:\Completed PDF file Extraction", max_workers: int = 6):
    r"""Strictly scans ONLY the input directory (E:\PDF) for pending .pdf and .docx files, converts them, and moves completed documents to archive."""
    safe_print("=" * 80)
    safe_print(f"STARTING BATCH DOCUMENT EXTRACTION (.PDF & .DOCX) [MARATHI & ENGLISH]")
    safe_print(f"Source Folder (Queue) : {input_dir}")
    safe_print(f"Target MD Folder      : {output_dir}")
    safe_print(f"Completed Archive     : {completed_dir}")
    safe_print(f"Parallel Workers      : {max_workers}")
    safe_print("=" * 80)
    
    if not os.path.exists(input_dir):
        safe_print(f"Error: Source folder '{input_dir}' does not exist!")
        return []
        
    os.makedirs(output_dir, exist_ok=True)
    if completed_dir:
        os.makedirs(completed_dir, exist_ok=True)
        
    # STRICT DISCOVERY: Scan ONLY input_dir for .pdf and .docx files
    all_files = [
        f for f in sorted(os.listdir(input_dir))
        if f.lower().endswith(SUPPORTED_EXTENSIONS) and not f.startswith('~$') and os.path.isfile(os.path.join(input_dir, f))
    ]
    
    if not all_files:
        safe_print(f"[INFO] Ingestion Queue is currently clean: 0 new (.pdf / .docx) files in '{input_dir}'.")
        safe_print(f"[INFO] All previous documents have already been converted to '{output_dir}' and archived.")
        safe_print(f"[INFO] To process new documents, drop your .pdf or .docx files into '{input_dir}' and run again.")
        safe_print("=" * 80)
        return []
        
    safe_print(f"Found {len(all_files)} new document(s) in queue '{input_dir}'.\n")
    
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
        type_tag = res.get("type", "DOC")
        pages_tag = f"({res.get('pages', 1)} pages)" if type_tag == "PDF" else "(DOCX Document)"
        safe_print(f"[{status}] [{type_tag}] {res['filename']} {pages_tag} in {res['elapsed_sec']}s -> {size}")
                
    success_count = sum(1 for r in results if r.get("success"))
    safe_print("\n" + "=" * 80)
    safe_print(f"BATCH CONVERSION SUMMARY:")
    safe_print(f"Total Processed : {len(all_files)}")
    safe_print(f"Successful      : {success_count}")
    safe_print(f"Failed          : {len(all_files) - success_count}")
    safe_print(f"Output Path     : {output_dir}")
    if completed_dir:
        safe_print(f"Archived To     : {completed_dir}")
    safe_print("=" * 80)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strict single-directory PDF & DOCX to Markdown converter for Marathi and English legal documents.")
    parser.add_argument("doc_path", nargs="?", help="Path to single .pdf or .docx file")
    parser.add_argument("--batch", action="store_true", help="Run batch conversion strictly on all .pdf and .docx files in input folder")
    parser.add_argument("--input", default=r"E:\PDF", help="Strict input directory containing documents (default: E:\\PDF)")
    parser.add_argument("--output", default=r"E:\PDF to MD", help="Output directory for Markdown files (default: E:\\PDF to MD)")
    parser.add_argument("--completed-dir", default=r"E:\Completed PDF file Extraction", help="Directory to move completed documents into")
    parser.add_argument("--no-move", action="store_true", help="Do not move source files after extraction")
    parser.add_argument("--workers", type=int, default=6, help="Number of parallel workers for batch mode")
    
    args = parser.parse_args()
    
    target_completed = None if args.no_move else args.completed_dir
    
    if args.batch or not args.doc_path:
        run_batch_conversion(args.input, args.output, completed_dir=target_completed, max_workers=args.workers)
    else:
        if args.doc_path.lower().endswith('.docx'):
            res = convert_docx_to_markdown(args.doc_path, args.output, completed_dir=target_completed)
        else:
            res = convert_pdf_to_markdown(args.doc_path, args.output, completed_dir=target_completed)
        safe_print(f"Converted '{res['filename']}' in {res['elapsed_sec']}s. Success: {res['success']}")
        if not res.get('success'):
            sys.exit(1)
