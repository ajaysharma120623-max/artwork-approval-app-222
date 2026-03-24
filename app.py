import streamlit as st
import pdfplumber
import re
import os
from openai import OpenAI
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Load API key
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    st.error("Please set OPENAI_API_KEY in Streamlit secrets")
    st.stop()

client = OpenAI(api_key=api_key)

# ---------- PDF TEXT ----------
def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
    return text

# ---------- CHECKS ----------
def run_checks(text):
    issues = []
    text_lower = text.lower()

    # 🔴 Pre-print empty fields
    if "batch" in text_lower and "____" in text:
        issues.append(("Batch number box is empty", "High"))

    if "expiry" in text_lower and "____" in text:
        issues.append(("Expiry date box is empty", "High"))

    if "mfg" in text_lower and "____" in text:
        issues.append(("Manufacturing date box is empty", "High"))

    # 🔴 Mandatory headings
    headings = [
        "composition",
        "dose",
        "storage",
        "indications"
    ]

    for h in headings:
        if h not in text_lower:
            issues.append((f"Missing heading: {h}", "Medium"))

    # 🔴 Strength formats
    patterns = [
        r"each\s*250\s*mg",
        r"each\s*500\s*mg",
        r"each\s*10\s*ml",
        r"each\s*10\s*g"
    ]

    if not any(re.search(p, text_lower) for p in patterns):
        issues.append(("Missing standard strength format (e.g. Each 500 mg contains)", "Medium"))

    return issues

# ---------- BOTANICAL CHECK ----------
def check_botanical(text):
    issues = []

    # simple pattern: two-word latin names
    matches = re.findall(r"\b[A-Z][a-z]+\s[a-z]+\b", text)

    for name in matches:
        if not re.search(rf"\*{name}\*|_{name}_", text):
            issues.append((f"Botanical name not italic: {name}", "Low"))

    return issues

# ---------- CLAIM CHECK ----------
def detect_claims(text):
    patterns = [
        r"cure[s]?\s+diabetes",
        r"100\s*%\s*cure",
        r"instant\s+relief",
        r"guaranteed\s+results"
    ]

    issues = []
    for p in patterns:
        if re.search(p, text.lower()):
            issues.append((f"Prohibited claim detected: {p}", "High"))

    return issues

# ---------- AI ----------
def ai_analysis(text):
    try:
        response = client.chat.completions.create(
            model="gpt-5.3",
            messages=[
                {
                    "role": "system",
                    "content": """You are an AYUSH artwork compliance expert.

Check:
- Missing fields
- Label mistakes
- Formatting issues
- Suggest corrections

Keep answer structured and clear."""
                },
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content
    except:
        return "AI analysis failed"

# ---------- SCORE ----------
def calculate_score(issues):
    score = 100
    for _, severity in issues:
        if severity == "High":
            score -= 20
        elif severity == "Medium":
            score -= 10
        else:
            score -= 5
    return max(score, 0)

# ---------- PDF REPORT ----------
def generate_pdf(issues, ai_text):
    doc = SimpleDocTemplate("report.pdf")
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("Artwork Compliance Report", styles["Title"]))
    content.append(Spacer(1, 10))

    for issue, severity in issues:
        content.append(Paragraph(f"{severity}: {issue}", styles["Normal"]))
        content.append(Spacer(1, 5))

    content.append(Spacer(1, 10))
    content.append(Paragraph("AI Analysis:", styles["Heading2"]))
    content.append(Paragraph(ai_text, styles["Normal"]))

    doc.build(content)

    with open("report.pdf", "rb") as f:
        return f.read()

# ---------- UI ----------
st.set_page_config(layout="wide")

st.title("🧾 Artwork Approval System (AYUSH)")

tabs = st.tabs(["📊 Summary", "⚠️ Issues", "🤖 AI Report"])

uploaded_file = st.file_uploader("Upload Artwork PDF", type=["pdf"])

if uploaded_file:
    text = extract_text(uploaded_file)

    issues = []
    issues += run_checks(text)
    issues += check_botanical(text)
    issues += detect_claims(text)

    score = calculate_score(issues)
    ai_text = ai_analysis(text)

    # ---------- TAB 1 ----------
    with tabs[0]:
        st.subheader("Compliance Score")
        st.metric("Score", f"{score}/100")
        st.progress(score / 100)

    # ---------- TAB 2 ----------
    with tabs[1]:
        for issue, severity in issues:
            if severity == "High":
                st.error(issue)
            elif severity == "Medium":
                st.warning(issue)
            else:
                st.info(issue)

    # ---------- TAB 3 ----------
    with tabs[2]:
        st.write(ai_text)

    # ---------- DOWNLOAD ----------
    pdf = generate_pdf(issues, ai_text)

    st.download_button(
        "📥 Download PDF Report",
        pdf,
        file_name="compliance_report.pdf"
    )
