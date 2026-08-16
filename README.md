# 🏛️ Protocol-4: Maharashtra Police & Legal Document Intelligence Engine

> **Repository**: [kartikplayzz/Protocol-4](https://github.com/kartikplayzz/Protocol-4)  
> **Architecture**: Universal GPU / Multi-Core CPU + Microsoft MarkItDown 0.1.7 + OpenCV CLAHE + Tesseract 5.5 (mar+eng) + Marathi Legal NLP

---

## 🌟 Key Architecture Capabilities

1. **Universal Hardware & GPU Auto-Detection (Silent)**:
   - Automatically detects and leverages OpenCL GPUs (Intel UHD/Iris, AMD Radeon, NVIDIA) or Multi-Core CPUs without requiring manual configuration.
2. **Microsoft MarkItDown 0.1.7 Unified Core**:
   - High-fidelity conversion of `.docx` Word tables, statutory sections, and legal templates directly to clean Markdown.
3. **Marathi Legal NLP Normalizer**:
   - Dotted-line form symbol noise and loop suppressor (`________________________________________`).
   - OCR Devanagari typo and compound word repair (`खाडा-खोड`, `खरे-खोटेपणा`, `किंवा`, `नोंदविणाऱ्या`).
4. **Self-Healing Portability Protocol**:
   - Zero-crash architecture: When opened on any new PC, the web application auto-detects missing libraries and offers a 1-click install dialog.
5. **Strict Ingestion & Auto-Archive**:
   - Monitors `E:\PDF\` (or local fallback `./workspace/PDF`) and automatically moves converted files to `E:\Completed PDF file Extraction\`.

---

## 🚀 Quick Start on Any PC (1-Click)

### Option 1: Double-Click Batch Launcher
Double-click `install_and_run.bat` to automatically install all dependencies, start the background server, and open `http://localhost:8080`.

### Option 2: Command Line
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run background server daemon
python server.py
```
Open **`http://localhost:8080`** in your browser.

---

## 📦 Requirements

- Python 3.10+
- Tesseract OCR 5.5 with `mar` (Marathi) and `eng` (English) traineddata.
- Compatible with Windows, Linux, and macOS.
