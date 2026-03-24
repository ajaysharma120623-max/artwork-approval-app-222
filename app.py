import streamlit as st
import pdfplumber
import re
import os
from openai import OpenAI

# Load API key securely
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- PDF TEXT EXTRACTION ----------
def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"
    return text.lower()

# ---------- RULE CHECK ----------
def validate_rules(text):
    issues = []

    if "batch" not in text:
        issues.append(("Missing batch number", "High"))

    if "expiry" not in text:
        issues.append(("Missing expiry date", "High"))

    if "license" not in text:
        issues.append(("Missing AYUSH license number", "High"))

    if not re.search(r"(manufactured by|mfg by)", text):
        issues.append(("Missing manufacturer details", "High"))

    if "dosage" not in text:
        issues.append(("Missing dosage instructions", "Medium"))

    return issues

# ---------- CLAIM CHECK ----------
def detect_claims(text):
    banned = [
        "cure diabetes",
        "guaranteed results",
        "instant relief",
        "100% cure"
    ]

    found = []
    for claim in banned:
        if claim in text:
            found.append(claim)

    return found

# ---------- AI ANALYSIS ----------
def ai_analysis(text):
    try:
        response = client.chat.completions.create(
            model="gpt-5.3",
            messages=[
                {"role": "system", "content": "You are an AYUSH compliance expert."},
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
            score -= 15
        else:
            score -= 8
    return max(score, 0)

# ---------- UI ----------
st.title("🧾 Ayurvedic Artwork Approval Tool")

uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded_file:
    st.info("Analyzing...")

    text = extract_text(uploaded_file)

    rule_issues = validate_rules(text)
    claims = detect_claims(text)
    score = calculate_score(rule_issues)

    st.subheader("📊 Compliance Score")
    st.metric("Score", f"{score}/100")

    if score > 80:
        st.success("Good compliance")
    elif score > 50:
        st.warning("Needs improvement")
    else:
        st.error("High risk")

    st.subheader("⚠️ Issues")

    for issue, severity in rule_issues:
        if severity == "High":
            st.error(issue)
        else:
            st.warning(issue)

    st.subheader("🚫 Prohibited Claims")
    if claims:
        for c in claims:
            st.error(c)
    else:
        st.success("No bad claims found")

    st.subheader("🤖 AI Analysis")
    st.write(ai_analysis(text))
