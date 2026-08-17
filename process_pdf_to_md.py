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

SCANNER_WATERMARK_PATTERNS = [
    r"(?i)^[©c\s]*scanned\s+(?:with|by)\s+oken\s+scanner.*$",
    r"(?i)^[©c\s]*scanned\s+(?:with|by)\s+camscanner.*$",
    r"(?i)^[©c\s]*scanned\s+(?:with|by)\s+adobe\s+scan.*$",
    r"(?i)^[©c\s]*scanned\s+(?:with|by)\s+fast\s+scanner.*$",
    r"(?i)^[©c\s]*scanned\s+(?:with|by)\s+doc\s+scanner.*$",
    r"(?i)^[©c\s]*scanned\s+(?:with|by)\s+clear\s+scanner.*$",
    r"(?i)^[©c\s]*scanned\s+(?:with|by)\s+vflat.*$",
    r"(?i)^[©c\s]*scanned\s+with\s+scanner\s+app.*$",
    r"^(?:M\.R\.W\.?|M\s*R\s*W)$",
    r"^(?:CS\s+CamScanner|CamScanner)$",
]


def clean_scanner_watermarks(text: str) -> str:
    """Strips mobile scanner app watermarks and marginal stamp codes."""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
            
        is_watermark = False
        for pat in SCANNER_WATERMARK_PATTERNS:
            if re.fullmatch(pat, stripped, re.IGNORECASE) or (len(stripped) < 60 and re.search(pat, stripped, re.IGNORECASE)):
                is_watermark = True
                break
                
        if is_watermark:
            continue
            
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)


def is_corrupted_or_legacy_font(text: str) -> bool:
    """Detects if extracted PDF text is corrupted non-Unicode, Shivaji, KrutiDev, or ASCII font mappings."""
    if not text or len(text.strip()) < 10:
        return True
    
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
            
        if re.match(r'^(?:कलम|Section|पोट-कलम|अनुसूची|प्रकरण)\s+[०-९\d]+[A-Za-z\.\-\s]+', stripped) and len(stripped) < 80:
            if not stripped.startswith('#'):
                formatted.append(f"### {stripped}")
                continue
                
        if re.match(r'^(?:सही|स्वाक्षरी|Signature|Seal|Stamp)\s*[:\/\-]', stripped, re.IGNORECASE):
            formatted.append(f"\n> **{stripped}**\n")
            continue
            
        formatted.append(line)
        
    return '\n'.join(formatted)


def clean_form_blanks_and_tables(text: str) -> str:
    """Suppresses OCR dotted-line hallucinations and symbol loops into clean blanks."""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
            
        symbol_count = len(re.findall(r'[\*\%\$\#\@\!\?\^\|\_\.\-\~\\\/]', stripped))
        digits_and_dots = len(re.findall(r'[०-९0-9\.\s]', stripped))
        total_len = len(stripped)
        
        if total_len >= 12 and (symbol_count + digits_and_dots) / total_len > 0.70:
            if not any(kw in stripped.lower() for kw in ["कलम", "section", "रुपये", "दिनांक", "act", "rule", "नोंद", "पान"]):
                cleaned_lines.append("________________________________________________________")
                continue
                
        if re.fullmatch(r'[\.\_\-\s]{6,}', stripped):
            cleaned_lines.append("________________________________________________________")
            continue
            
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



def is_ocr_dotted_line_noise(token: str) -> bool:
    """Detects if a token is an OCR hallucination of printed form dotted/blank lines."""
    cleaned = token.strip(" \t\r\n-–—=_:.,*+#$@^~|\\/{}[]()\"'?`0123456789")
    if not cleaned or len(cleaned) < 4:
        return False
        
    # Check for repetitive Marathi characters (like टटटट, पपपप, सससस, शिशिशि, papa, etc.)
    marathi_noise_chars = set("टपसशणरलबडमनिीुूेैोौ्ॅॉाी?\"'”’«»८२९०१२३४५६७")
    noise_count = sum(1 for c in cleaned if c in marathi_noise_chars)
    
    # If 80%+ of characters are from the noise set and length >= 6
    if len(cleaned) >= 6 and (noise_count / len(cleaned)) >= 0.8:
        if re.search(r'(.)\1{2,}', cleaned) or re.search(r'(.{2,3})\1{2,}', cleaned):
            return True
        if len(cleaned) >= 12 and noise_count == len(cleaned):
            return True

    # Check for Latin dotted line noise (like nnn nnn, nanan, eee, wren, etc.)
    if re.fullmatch(r'(?:n|nn|nnn|nnnn|nen|nanan|wren|wana|eee|enn|nena|ooo|soe|sne|poo|vert|wa|ata)+', cleaned, re.IGNORECASE):
        return True

    return False


def clean_marathi_police_form_noise(text: str) -> str:
    """Strips dotted line OCR artifacts, noise sequences, and standardizes Marathi police terminology."""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
            
        # Check if entire line is just dotted line symbols / noise
        if re.fullmatch(r'[\s\-–—=_\:\.\,\*\+\#\$\@\^\~\|\\\/\{\}\[\]\(\)\?0-9a-zA-Z]{5,}', stripped):
            char_set = set(stripped.lower())
            if char_set.issubset(set(" -–—=_:.,*+#$@^~|\\/{}[]()?0123456789newaopt")):
                continue

        # Split line into tokens and filter out noise tokens
        tokens = line.split()
        good_tokens = []
        for t in tokens:
            if is_ocr_dotted_line_noise(t):
                continue
            # Strip trailing/leading long dash/equal chains from tokens
            t_cleaned = re.sub(r'[\-–—=]{3,}', '', t)
            t_cleaned = re.sub(r'[\.]{4,}', '...', t_cleaned)
            if t_cleaned:
                good_tokens.append(t_cleaned)
                
        cleaned_line = " ".join(good_tokens)
        if cleaned_line.strip():
            cleaned_lines.append(cleaned_line)
            
    result = '\n'.join(cleaned_lines)
    
    # Clean standalone lines that became empty or pure symbols
    result = re.sub(r'\n[ \t\-–—=_:\.,\*+#$@^~|\\/{}[]()]+(?=\n)', '', result)
    
    # Standardize Marathi police form legal terminology & OCR typos
    # 1. Investigating Officer / Signature
    result = re.sub(
        r'तपासणी\s+करण[\u0900-\u097F]*\s+अधिकार[\u0900-\u097F]*\s*(?:नांव|नाव)?\s*व?\s*(?:सद्दी|सही)',
        'तपासणी करणाऱ्या अधिकाऱ्याचे नाव व सही',
        result
    )
    result = re.sub(
        r'तपासणी\s+करण[\u0900-\u097F]*\s+अंमलदार[\u0900-\u097F]*\s*(?:नांव|नाव)?\s*व?\s*(?:सद्दी|सही)',
        'तपासणी करणाऱ्या अंमलदाराचे नाव व सही',
        result
    )
    result = re.sub(
        r'तपासणी\s+करण[\u0900-\u097F]*\s+अधिकार[\u0900-\u097F]*',
        'तपासणी करणाऱ्या अधिकाऱ्याचे',
        result
    )
    
    # 2. General Marathi Legal Typos
    replacements = [
        (r'\bकरणार्या\b', 'करणाऱ्या'),
        (r'\bकरणार्‍या\b', 'करणाऱ्या'),
        (r'\bअधिकार्यांच्या\b', 'अधिकाऱ्यांच्या'),
        (r'\bअधिकार्याची\b', 'अधिकाऱ्याची'),
        (r'\bअधिकार्याचे\b', 'अधिकाऱ्याचे'),
        (r'\bसद्दी\b', 'सही'),
        (r'\bनांव\b', 'नाव'),
        (r'\bशल्यचिकीत्सक[\u0900-\u097F]*\b', lambda m: m.group(0).replace('चिकीत्सक', 'चिकित्सक')),
        (r'\bपरिक्षेसाठी\b', 'परीक्षेसाठी'),
        (r'\bसमाविष्ठ\b', 'समाविष्ट'),
        (r'\bसहायभुत\b', 'सहाय्यभूत'),
        (r'\bनैसर्गीक\b', 'नैसर्गिक'),
        (r'\bदयावी\b', 'द्यावी'),
        (r'\bदयावे\b', 'द्यावे'),
        (r'\bदिसुन\b', 'दिसून'),
        (r'\bजावुन\b', 'जाऊन'),
        (r'\bयेवुन\b', 'येऊन'),
        (r'\bआणुन\b', 'आणून'),
        (r'\bकरुन\b', 'करून'),
        (r'\bदेवुन\b', 'देवून'),
    ]
    for pat, rep in replacements:
        if callable(rep):
            result = re.sub(pat, rep, result)
        else:
            result = re.sub(pat, rep, result)
        
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result


def clean_police_form_full(text: str) -> str:
    """Strips dotted blank form OCR noise, scanner stamps, and formats bilingual Maharashtra Police forms."""
    # 1. Strip scanner watermarks & artifacts
    text = re.sub(r'(?i)[(©C@]?\s*scanned\s+with\s+[a-z0-9\s_-]+scanner[)]?', '', text)
    text = re.sub(r'(?i)\b(?:MRW|M\.R\.W|GE|CE|OE)\b', '', text)
    
    # 2. Inquest Form (Pages 18-21)
    body_part_maps = [
        (r'a\)\s*Head[^\n]*', 'a) Head :'),
        (r'अ\)\s*डोके[^\n]*', 'अ) डोके :'),
        (r'b\)\s*Face[^\n]*', 'b) Face :'),
        (r'ब\)\s*चेहरा[^\n]*', 'ब) चेहरा :'),
        (r'[c९]\)\s*Neck[^\n]*', 'c) Neck :'),
        (r'क\)\s*मान[^\n]*', 'क) मान :'),
        (r'd\)\s*Chest[^\n]*', 'd) Chest :'),
        (r'ड\)\s*छाती[^\n]*', 'ड) छाती :'),
        (r'e\)\s*Stomac[a-z]*[^\n]*', 'e) Stomach :'),
        (r'इ\)\s*पोट[^\n]*', 'इ) पोट :'),
        (r'f\)\s*Right\s+Hand[^\n]*', 'f) Right Hand :'),
        (r'ई\)\s*उजवा\s+हात[^\n]*', 'ई) उजवा हात :'),
        (r'g\)\s*Left\s+Hand[^\n]*', 'g) Left Hand :'),
        (r'उ\)\s*डावा\s+हात[^\n]*', 'उ) डावा हात :'),
        (r'h\)\s*Right\s+Leg[^\n]*', 'h) Right Leg :'),
        (r'[एऊ]\)\s*उजवा\s+पाय[^\n]*', 'ऊ) उजवा पाय :'),
        (r'[1i]\)\s*Left\s+Leg[^\n]*', 'i) Left Leg :'),
        (r'[ऐए]\)\s*डावा\s+पाय[^\n]*', 'ए) डावा पाय :'),
        (r'[\{\(]?\s*j\)?\s*Private\s+part[a-z]*[^\n]*', 'j) Private parts :'),
        (r'ओ\)\s*गुप्त\s+भाग[^\n]*', 'ओ) गुप्त भाग :'),
        (r'k\)\s*Back[^\n]*', 'k) Back :'),
        (r'(?:at|औ)\)\s*पाठ[^\n]*', 'औ) पाठ :'),
    ]
    for pat, repl in body_part_maps:
        text = re.sub(pat, repl, text)

    # General form questions
    form_replacements = [
        (r'प्रेतचे?\s+जखमा\s+असल्यास\s+त्याचे\s+वर्णन[^\n]*', 'प्रेतावर जखमा असल्यास त्याचे वर्णन :'),
        (r'10\)\s*Injuries of Dead Body[^\n]*', '10) Injuries of Dead Body Caused By Accidental/Violence :'),
        (r'प्रेताचे\s+अंगावरील\s+जखमा[^\n]*', 'प्रेताचे अंगावरील जखमा अपघाताच्या/ दंग्यातील/ इतरांनी केल्यामुळे झाल्या काय :'),
        (r'11\)\s*Weapon\s*/\s*Means[^\n]*', '11) Weapon / Means (if any) :'),
        (r'जखमा\s+केलेल्या\s+हत्याराचे[^\n]*', 'जखमा केलेल्या हत्याराचे/ साधनाचे वर्णन :'),
        (r'जखमा\s+केलेल्या[^\n]*', 'जखमा केलेल्या हत्याराचे/ साधनाचे वर्णन :'),
        (r'12\)\s*Dead Body Cool\s*/\s*Warm[^\n]*', '12) Dead Body Cool / Warm :'),
        (r'प्रेत\s+थंड\s+आहे/\s*गरम\s+आहे[^\n]*', 'प्रेत थंड आहे/ गरम आहे :'),
        (r'प्रेताची\s+स्थिती\s*\(?विष\s+प्राशन[^\n]*', 'प्रेताची स्थिती (विष प्राशन/ विष प्रयोग झाला असल्यास) :'),
        (r'14\)\s*\(a\)\s*Finger Print[^\n]*', '14) (a) Finger Print taken / Not taken by Doctor (Reason) :'),
        (r'(?:ep\s+Co\s+)?प्रेताचे\s+डॉक्ट[^\n]*बोटा[^\n]*', 'प्रेताचे डॉक्टरांकडून बोटांचे ठसे घेतले/ नाही कारण :'),
        (r'\(b\)\s*Photo taken[^\n]*', '(b) Photo taken / not taken reason (In case of an Unidentified Dead Body) :'),
        (r'अनोळखी\s+प्रेताचे\s+फोटो[^\n]*', 'अनोळखी प्रेताचे फोटो घेतले/ नाही कारण :'),
        (r'प्रेत\s*\(पोस्ट\s+मार्टम\)\s*शल्यचिकित्सेकरीता[^\n]*', 'प्रेत (पोस्ट मार्टम) शल्यचिकित्सेकरीता पाठविले/ नाही कारण :'),
        (r'\(a\)\s*At which Hospital[^\n]*', '(a) At which Hospital Dead Body sent to P.M. :'),
        (r'कोणत्या\s+दवाखान्यात\s+प्रेत\s+पोस्ट\s+मार्टम[^\n]*', 'कोणत्या दवाखान्यात प्रेत पोस्ट मार्टम करीता पाठविले :'),
        (r'\(b\)\s*With whom[^\n]*', '(b) With whom (Name, B.No. and Police Station) :'),
        (r'कोणा\s+बरोबर\s+पाठविले[^\n]*', 'कोणा बरोबर पाठविले (नाव व बक्कल नंबर) :'),
        (r'नाव\s+व?\s*बक्कल\s+नंबर[^\n]*', 'नाव व बक्कल नंबर : ...............\n'),
        (r'16\)\s*Opinion of Panchas[^\n]*', '16) Opinion of Panchas and Police about Death :'),
        (r'पंच\s+व\s+पोलीसांचा\s+मृताविषयी\s+अभिप्राय[^\n]*', 'पंच व पोलीसांचा मृताविषयी अभिप्राय :'),
        (r'17\)\s*More information[^\n]*', '17) More information (if any) :'),
        (r'अधिक\s+माहिती\s+असल्यास[^\n]*', 'अधिक माहिती असल्यास :'),
        (r'18\)\s*Date and Time of panchanama[^\n]*', '18) Date and Time of panchanama :'),
        (r'पंचनामा\s+केल्याची\s+दिनांक[^\n]*', 'पंचनामा केल्याची दिनांक : ............... वेळ : ............... ते ...............'),
        (r'19\)\s*Name of Panchas and Signature[^\n]*', '19) Name of Panchas and Signature :'),
        (r'पंचनामा\s+करणा[^\n]*पंचांची\s+नावे[^\n]*', 'पंचनामा करणाऱ्या पंचांची नावे व सह्या :'),
        (r'Signature of Investigat[a-zA-Z\s]+', 'Signature of Investigating Officer'),
        (r'तपासणी\s+करणा[^\n]*अधिकार[^\n]*नाव[^\n]*', 'तपासणी करणाऱ्या अधिकाऱ्याचे नाव व सही'),
    ]
    for pat, repl in form_replacements:
        text = re.sub(pat, repl, text)

    # 3. Clean line-by-line noise
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
            
        # Drop standalone noise words
        if stripped in ['GE', 'CE', 'OE', 'MRW', 'M.R.W', 'a', 'ro', 'प >', '१', '२', '३', '| ne a er', 'forever sé)']:
            continue
            
        # Drop random disconnected characters from dotted lines
        if re.fullmatch(r'(?:[क-हa-zA-Z0-9\s\.\-]{1,3}\s+){3,}[क-हa-zA-Z0-9\s\.\-]{1,3}', stripped):
            if not any(w in line for w in ['अ.', 'क्र.', 'नाव', 'दिनांक', 'वेळ', 'पत्ता', 'पोलीस', 'कलम', 'फॉर्म']):
                continue
                
        # Drop lines with meaningless gibberish
        if re.search(r'कहता कड क कणा हात|लात डा त पपष कश|केल्यामुळे झाल्या हाड डळ|कह सा या त्वा का सा|पप--पममममपलपस|पलॅलॅलसलललिललललस्सट्श्', stripped):
            continue

        cleaned_lines.append(line)
        
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'Signature of Investigating OfficerOfficer', 'Signature of Investigating Officer', result)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result


def convert_pdf_to_markdown(
    pdf_path: str,
    output_dir: str,
    completed_dir: str = None,
    dpi: int = 300,
    ocr_workers: int = 6
) -> dict:
    """
    100% Robust Local PDF Conversion Engine:
    - Automatically strips scanner watermarks (OKEN Scanner, CamScanner, Adobe Scan, M.R.W).
    - True Unicode Marathi Vector PDFs -> PyMuPDF Instant Text Stream.
    - Scanned Photocopies / Legacy Font PDFs -> 300 DPI OpenCV CLAHE + Tesseract 5.5 OCR.
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
        "engine": "Microsoft MarkItDown + Local Marathi Intelligence",
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
        
        # 1. Run Microsoft MarkItDown for structured document parsing
        md_text = ""
        try:
            md_engine = MarkItDown()
            md_res = md_engine.convert(pdf_path)
            if md_res and hasattr(md_res, 'text_content'):
                md_text = md_res.text_content.strip()
        except Exception:
            md_text = ""

        
        digital_pages = {}
        image_pages = {}
        
        for pno in range(total_pages):
            page = doc[pno]
            raw_text = page.get_text("text").strip()
            
            if len(raw_text) > 120 and contains_devanagari(raw_text) and not is_corrupted_or_legacy_font(raw_text):
                digital_pages[pno] = raw_text
            else:
                image_pages[pno] = page
                
        page_results = {}
        for pno, text in digital_pages.items():
            page_results[pno] = text
            
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
        md_sections.append(f"> **Source File**: `{filename}`  \n> **Engine**: Microsoft MarkItDown + Local Marathi Intelligence  \n> **Total Pages**: {total_pages}  \n> **Extraction Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n")
        
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
        wm_cleaned_md = clean_scanner_watermarks(repaired_md)
        form_cleaned_md = clean_form_blanks_and_tables(wm_cleaned_md)
        final_md = format_legal_markdown_structure(form_cleaned_md)
        
        with open(out_md_path, "w", encoding="utf-8") as f:
            f.write(final_md)
            
        result["success"] = True
        result["output_size_bytes"] = os.path.getsize(out_md_path)
        
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
        "engine": "Microsoft MarkItDown + Local Marathi Intelligence",
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
        
        header = f"# {base_name}\n\n> **Source File**: `{filename}`  \n> **Engine**: Microsoft MarkItDown + Local Marathi Intelligence  \n> **Extraction Date**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n"
        cleaned_text = clean_form_blanks_and_tables(clean_scanner_watermarks(repair_marathi_ocr_and_numbered_lists(raw_text)))
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
