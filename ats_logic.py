import json
import os
import io
import base64
import shutil
import tempfile
import re
import random
import time
import requests
import urllib.parse
from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from dotenv import load_dotenv

# Third-party imports
from pydantic import BaseModel
import google.generativeai as genai
from PIL import Image
from bs4 import BeautifulSoup

# PDF Processing
try:
    import pypdfium2 as pdfium
except ImportError:
    pdfium = None

# DOCX Processing (Windows only usually)
try:
    from docx2pdf import convert as docx2pdf_convert
except ImportError:
    docx2pdf_convert = None

# Report Generation
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as ReportLabImage
from reportlab.lib.units import inch

# ════════════════════════════════════════════════
# CONFIGURATION & SETUP
# ════════════════════════════════════════════════

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-2.5-flash"

# Configure GenAI
if API_KEY:
    genai.configure(api_key=API_KEY)

# ════════════════════════════════════════════════
# DATA MODELS
# ════════════════════════════════════════════════

class ResumeInfo(BaseModel):
    skills: List[str] = []
    certificates: List[str] = []
    tools_and_tech: List[str] = []
    years_of_experience: str = ""
    education: str = ""
    document_parsability: bool = True
    file_format: str = ""
    document_structure: bool = True
    document_structure_reason: str = ""
    avoidance_of_non_parseable_elements: bool = True
    avoidance_of_non_parseable_elements_reason: str = ""
    location: str = ""

class JDInfo(BaseModel):
    role: str = ""
    skills_required: List[str] = []
    certificates_required: List[str] = []
    tools_technologies: List[str] = []
    years_of_experience_required: str = ""
    required_qualification: str = ""
    minimum_qualification: str = ""
    location: str = ""

# ════════════════════════════════════════════════
# RESUME PARSING LOGIC
# ════════════════════════════════════════════════

def _get_file_format(path: Path) -> str:
    ext = path.suffix.lower()
    if ext not in {".pdf", ".doc", ".docx"}:
        raise ValueError("Unsupported file format. Accepted: .pdf, .doc, .docx")
    return ext

def _pdf_to_base64_images(pdf_path: Path, dpi: int = 200) -> List[str]:
    if pdfium is None:
        raise RuntimeError("pypdfium2 is required to render PDFs.")
    images_b64 = []
    pdf = pdfium.PdfDocument(str(pdf_path))
    for page_index in range(len(pdf)):
        page = pdf.get_page(page_index)
        bitmap = page.render(scale=dpi / 72.0)
        pil_image = bitmap.to_pil()
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        images_b64.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
        page.close()
    return images_b64

def _doc_to_pdf(src_path: Path) -> Path:
    if docx2pdf_convert is None:
        raise RuntimeError("docx2pdf is not installed or available on this system.")
    
    # Simple check for Windows/Office requirement could be added here
    # For now we assume if the import succeeded, it might work
    
    tmp_dir = Path(tempfile.mkdtemp(prefix="resume_doc2pdf_"))
    out_pdf = tmp_dir / (src_path.stem + ".pdf")
    try:
        docx2pdf_convert(str(src_path), str(tmp_dir))
    except Exception as e:
        raise RuntimeError(f"docx2pdf conversion failed: {e}")
        
    if not out_pdf.exists():
        pdfs = list(tmp_dir.glob("*.pdf"))
        if not pdfs:
            raise RuntimeError("Failed to convert document to PDF.")
        return pdfs[0]
    return out_pdf

def parse_resume(file_path: str, target_location: Optional[str] = None) -> Dict[str, Any]:
    """Parses a resume file and extracts structured data using Gemini."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    file_format = _get_file_format(path)
    images_b64 = []

    # Handle conversion
    if file_format == ".pdf":
        images_b64 = _pdf_to_base64_images(path)
    else:
        tmp_pdf = None
        try:
            tmp_pdf = _doc_to_pdf(path)
            images_b64 = _pdf_to_base64_images(tmp_pdf)
        except Exception as e:
            # Fallback or error if docx fails (common in linux deployments)
            raise RuntimeError(f"DOCX conversion failed (System might lack MS Word): {e}")
        finally:
            if tmp_pdf and tmp_pdf.parent.exists():
                shutil.rmtree(tmp_pdf.parent, ignore_errors=True)

    # Prepare LLM request
    model = genai.GenerativeModel(MODEL_NAME)
    location_clause = f"Target location for proximity assessment: {target_location}. " if target_location else ""
    
    prompt = (
        "You are a resume parser. Analyze the resume images and extract fields for the JSON schema. "
        "Return one valid JSON object. Use 'Null' for unknowns.\n"
        f"{location_clause}\n"
        "Guidelines:\n"
        "- Extract EXPLICIT skills only.\n"
        "- Expand ALL abbreviations (AWS -> Amazon Web Services).\n"
        "- Evaluate document_parsability, document_structure, avoidance_of_non_parseable_elements.\n"
        "- Schema: {skills: [], certificates: [], tools_and_tech: [], years_of_experience: str, education: str, "
        "document_parsability: bool, file_format: str, document_structure: bool, document_structure_reason: str, "
        "avoidance_of_non_parseable_elements: bool, avoidance_of_non_parseable_elements_reason: str, location: str}"
    )

    payload = [{"inline_data": {"mime_type": "image/png", "data": b64}} for b64 in images_b64]
    content = [prompt] + payload

    response = model.generate_content(
        content,
        generation_config=genai.GenerationConfig(response_mime_type="application/json", temperature=0.1)
    )
    
    # Parse Response
    try:
        data = json.loads(response.text)
        # Normalize list fields
        for field in ['skills', 'certificates', 'tools_and_tech']:
            if not isinstance(data.get(field), list):
                data[field] = [data[field]] if data.get(field) else []
        
        # Normalize boolean fields
        def _to_bool(v):
            if isinstance(v, bool): return v
            return str(v).lower() in ('true', 'yes', '1')

        data['document_parsability'] = _to_bool(data.get('document_parsability'))
        data['document_structure'] = _to_bool(data.get('document_structure'))
        data['avoidance_of_non_parseable_elements'] = _to_bool(data.get('avoidance_of_non_parseable_elements'))
        data['file_format'] = file_format
        
        return data
    except Exception as e:
        raise RuntimeError(f"Parsing LLM response failed: {e}")

# ════════════════════════════════════════════════
# JD PARSING LOGIC
# ════════════════════════════════════════════════

def parse_jd(jd_text: str) -> Dict[str, Any]:
    """Parses unstructured JD text into structured JSON."""
    model = genai.GenerativeModel(MODEL_NAME)
    prompt = f"""
    Extract job info from the text below into JSON.
    Schema:
    {{
      "role": "Job Title",
      "skills_required": ["skill1"],
      "certificates_required": ["cert1"],
      "tools_technologies": ["tool1"],
      "years_of_experience_required": "string",
      "required_qualification": "string",
      "minimum_qualification": "string",
      "location": "Location or Null"
    }}
    Rules:
    - Split combined skills.
    - Expand ALL abbreviations.
    - Use 'Null' for empty fields.
    
    JD Text:
    {jd_text}
    """
    
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(response_mime_type="application/json", temperature=0.1)
    )
    
    try:
        data = json.loads(response.text)
        if isinstance(data, list): data = data[0]
        
        # Ensure lists
        for field in ['skills_required', 'certificates_required', 'tools_technologies']:
            if not isinstance(data.get(field), list):
               data[field] = [data[field]] if data.get(field) else ["Null"]
        
        return data
    except Exception as e:
        raise RuntimeError(f"JD Parsing failed: {e}")

# ════════════════════════════════════════════════
# SKILL MATCHING LOGIC
# ════════════════════════════════════════════════

def normalize_skill(s: str) -> str:
    return re.sub(r'\s+', ' ', s.strip().lower())

def match_skills(resume_skills: List[str], jd_skills: List[str]) -> Dict[str, Any]:
    """Matches resume skills against JD skills."""
    res_norm = {normalize_skill(s) for s in resume_skills}
    jd_norm = {normalize_skill(s) for s in jd_skills}
    
    # Filter out "null"
    res_norm.discard('null')
    jd_norm.discard('null')

    # Calculate match
    matched_norm = jd_norm & res_norm
    missing_norm = jd_norm - res_norm
    
    # Convert back to original casing (User's exact logic)
    matched_original = [skill for skill in jd_skills if normalize_skill(skill) in matched_norm]
    missing_original = [skill for skill in jd_skills if normalize_skill(skill) in missing_norm]
    
    total = len(jd_norm)
    match_count = len(matched_norm)
    percent = round((match_count / total) * 100, 1) if total > 0 else 0
    
    return {
        "score_percentage": percent,
        "matched_skills": sorted(matched_original),
        "missing_skills": sorted(missing_original),
        "total_skills_count": total,
        "matched_count": match_count
    }

# ════════════════════════════════════════════════
# COURSE SCRAPING LOGIC
# ════════════════════════════════════════════════

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
]

def _safe_request(url):
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    try:
        return requests.get(url, headers=headers, timeout=5)
    except:
        return None

def fetch_courses_for_skills(skills: List[str]) -> Dict[str, List[Dict[str, str]]]:
    """Fetches course recommendations for a list of missing skills."""
    recommendations = {}
    
    # Limit to top 3 skills to avoid long wait times
    skills_to_search = skills[:3]
    
    for skill in skills_to_search:
        skill_recs = []
        
        # 1. DuckDuckGo Scrape
        try:
            url = f"https://duckduckgo.com/html/?q={'top online courses for ' + skill}".replace(" ", "+")
            resp = _safe_request(url)
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup.select("a.result__a")[:2]:
                    title = tag.get_text(strip=True)
                    link = tag.get("href", "")
                    if "uddg=" in link:
                        parsed = urllib.parse.urlparse(link)
                        link = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
                    if link.startswith("http"):
                        skill_recs.append({"title": title, "link": link})
        except:
            pass

        # 2. Coursera Scrape (Backup)
        if len(skill_recs) < 2:
            try:
                url = f"https://www.coursera.org/search?query={skill.replace(' ','%20')}"
                resp = _safe_request(url)
                if resp and resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a in soup.select('a[data-click-key="search.search.click.search_card"]')[:1]:
                        title = a.get_text(strip=True)
                        link = "https://www.coursera.org" + a.get("href", "")
                        skill_recs.append({"title": title, "link": link})
            except:
                pass
                
        recommendations[skill] = skill_recs
        time.sleep(1) # Be polite
        
    return recommendations

# ════════════════════════════════════════════════
# PDF REPORT GENERATION
# ════════════════════════════════════════════════

def generate_pdf_report(data: Dict[str, Any], output_path: str):
    """Generates a comprehensive PDF report."""
    
    doc = SimpleDocTemplate(output_path, pagesize=letter, topMargin=50, bottomMargin=50)
    styles = getSampleStyleSheet()
    story = []

    # Custom Styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor("#1e1b4b"), alignment=1, spaceAfter=20)
    h2_style = ParagraphStyle('Header2', parent=styles['Heading2'], fontSize=16, textColor=colors.HexColor("#4f46e5"), spaceBefore=15, spaceAfter=10)
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor("#374151"), leading=14)
    
    # Title
    story.append(Paragraph("ATS Analysis Report", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')}", ParagraphStyle('Date', parent=normal_style, alignment=1)))
    story.append(Spacer(1, 20))
    
    # Score Section
    score = data.get('match_score', 0)
    color = colors.green if score >= 80 else (colors.orange if score >= 50 else colors.red)
    story.append(Paragraph(f"Overall Match Score: <font color={color}>{score}%</font>", ParagraphStyle('Score', parent=title_style, fontSize=30)))
    story.append(Spacer(1, 20))
    
    # Candidate Info
    info_data = [
        ["Candidate Role:", data.get('resume_data', {}).get('education', 'N/A')], # Placeholder mapping
        ["JD Role:", data.get('jd_data', {}).get('role', 'N/A')],
        ["Location Match:", data.get('resume_data', {}).get('location', 'N/A')]
    ]
    t = Table(info_data, colWidths=[2.5*inch, 4*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor("#f3f4f6")),
        ('GRID', (0,0), (-1,-1), 1, colors.white),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 20))
    
    # Skills Analysis
    story.append(Paragraph("Skills Analysis", h2_style))
    
    matched = data.get('match_details', {}).get('matched_skills', [])
    missing = data.get('match_details', {}).get('missing_skills', [])
    
    story.append(Paragraph(f"<b>✅ Matched ({len(matched)}):</b> " + ", ".join(matched), normal_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>⚠️ Missing ({len(missing)}):</b> <font color='red'>" + ", ".join(missing) + "</font>", normal_style))
    story.append(Spacer(1, 20))
    
    # AI Summary
    if 'summary' in data:
        story.append(Paragraph("Executive Summary", h2_style))
        story.append(Paragraph(data['summary'], normal_style))
        story.append(Spacer(1, 20))
        
    # Recommendations
    recs = data.get('course_recommendations', {})
    if recs:
        story.append(Paragraph("Recommended Learning Path", h2_style))
        for skill, courses in recs.items():
            if not courses: continue
            story.append(Paragraph(f"<b>{skill}</b>", normal_style))
            for c in courses:
                link = f'<a href="{c["link"]}" color="blue">{c["link"]}</a>'
                story.append(Paragraph(f"• {c['title']}: {link}", ParagraphStyle('Link', parent=normal_style, fontSize=9)))
            story.append(Spacer(1, 5))

    doc.build(story)
