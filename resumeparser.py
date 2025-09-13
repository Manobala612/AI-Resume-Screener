import re
from typing import List, Dict, Any

# --------- Helpers

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
GITHUB_RE = re.compile(r"(https?://)?(www\.)?github\.com/[A-Za-z0-9_.-]+", re.IGNORECASE)
LINKEDIN_RE = re.compile(r"(https?://)?(www\.)?linkedin\.com/(in|pub|company)/[A-Za-z0-9\-_/]+", re.IGNORECASE)

# Support both month-year and numeric date formats
DATE_RANGE_RE = re.compile(
    r"((\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{4})|(\d{1,2}/\d{4})|\d{4})"
    r"\s*[-–—]\s*"
    r"((Present)|(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*\d{4})|(\d{1,2}/\d{4})|\d{4})",
    re.IGNORECASE
)

HEADERS = {
    "experience": re.compile(r"\b(experience|work experience|employment|professional experience)\b", re.IGNORECASE),
    "education": re.compile(r"\b(education|academics)\b", re.IGNORECASE),
    "projects": re.compile(r"\b(projects?)\b", re.IGNORECASE),
    "skills": re.compile(r"\b(skills|technical skills|tech skills|technologies|tooling)\b", re.IGNORECASE),
    "summary": re.compile(r"\b(summary|profile|about)\b", re.IGNORECASE),
}

SOFT_SKILL_KWS = [
    "communication", "teamwork", "problem solving", "leadership", "adaptability",
    "time management", "collaboration", "critical thinking", "creativity",
    "attention to detail", "ownership", "mentorship", "stakeholder management",
    "presentation", "negotiation", "empathy", "conflict resolution"
]

# --------- Utility functions

def _clean(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()

def _first_nonempty_lines(text: str, n=8) -> List[str]:
    lines = [l.strip() for l in text.splitlines()]
    return [l for l in lines if l][:n]

def _guess_full_name(text: str) -> str:
    for line in _first_nonempty_lines(text, n=8):
        words = [w for w in re.split(r"[^A-Za-z]+", line) if w]
        if 2 <= len(words) <= 4 and (all(w[0].isupper() for w in words) or all(w.isupper() for w in words)):
            if not HEADERS["summary"].search(line) and not HEADERS["experience"].search(line):
                return " ".join(words)
    email = _extract_email(text)
    if email and "." in email.split("@")[0]:
        parts = email.split("@")[0].replace("_", " ").replace(".", " ").split()
        parts = [p.capitalize() for p in parts if p]
        if 1 <= len(parts) <= 3:
            return " ".join(parts)
    return ""

def _extract_email(text: str) -> str:
    m = EMAIL_RE.search(text)
    return m.group(0) if m else ""

def _extract_linkedin(text: str) -> str:
    m = LINKEDIN_RE.search(text)
    return "https://" + m.group(0) if m and not m.group(0).startswith("http") else (m.group(0) if m else "")

def _extract_github(text: str) -> str:
    m = GITHUB_RE.search(text)
    return "https://" + m.group(0) if m and not m.group(0).startswith("http") else (m.group(0) if m else "")

def _split_sections(text: str) -> Dict[str, str]:
    lines = text.splitlines()
    idxs = []
    for i, line in enumerate(lines):
        for key, rx in HEADERS.items():
            if rx.search(line):
                idxs.append((i, key))
    idxs.sort()
    parts = {}
    for j, (start, key) in enumerate(idxs):
        end = idxs[j+1][0] if j+1 < len(idxs) else len(lines)
        parts[key] = "\n".join(lines[start:end]).strip()
    return parts

# --------- Section extractors

def _extract_skills(section_text: str, full_text: str) -> List[str]:
    candidates = []
    src = section_text if section_text else full_text
    for line in src.splitlines():
        if len(line) > 2:
            if "," in line or "|" in line or "/" in line or "•" in line:
                tokens = re.split(r"[,\|/•;∙·\t]+", line)
                for t in tokens:
                    t = _clean(t)
                    if 1 < len(t) <= 40:
                        candidates.append(t)
    seen, out = set(), []
    for c in candidates:
        lc = c.lower()
        if lc not in seen:
            seen.add(lc)
            out.append(c)
    return out[:50]

def _extract_soft_skills(full_text: str) -> List[str]:
    found = []
    low = full_text.lower()
    for kw in SOFT_SKILL_KWS:
        if re.search(rf"\b{re.escape(kw)}\b", low):
            found.append(kw.title())
    return found[:25]

def _extract_experience(section_text: str, full_text: str) -> List[Dict[str, Any]]:
    src = section_text if section_text else full_text
    lines = [l.strip("•*- \t") for l in src.splitlines() if l.strip()]
    jobs, buffer = [], []

    def flush(buf: List[str]):
        if not buf:
            return
        block = " ".join(buf)
        duration = DATE_RANGE_RE.search(block).group(0) if DATE_RANGE_RE.search(block) else ""
        role, company = "", ""
        first = buf[0]
        if "|" in first or "-" in first:
            parts = re.split(r"[|–—-]", first)
            if len(parts) >= 2:
                role, company = _clean(parts[0]), _clean(parts[1])
        elif "," in first:
            role, company = _clean(first.split(",")[0]), _clean(first.split(",")[1])
        else:
            role = _clean(first)
        achievements = [_clean(l) for l in buf[1:] if len(l) > 3]
        jobs.append({"role": role, "company": company, "duration": duration, "achievements": achievements[:8]})

    for l in lines:
        if HEADERS["education"].search(l) or HEADERS["projects"].search(l):
            break
        if DATE_RANGE_RE.search(l):
            buffer.append(l)
            flush(buffer)
            buffer = []
        else:
            buffer.append(l)
    flush(buffer)
    return jobs[:8]

def _extract_education(section_text: str) -> List[Dict[str, Any]]:
    edu_list = []
    for line in section_text.splitlines():
        if any(x in line.lower() for x in ["bachelor", "master", "phd", "diploma", "degree"]):
            degree = re.findall(r"(Bachelor|Master|PhD|Diploma)[^,;\n]*", line, re.IGNORECASE)
            year = re.findall(r"\b(19|20)\d{2}\b", line)
            edu_list.append({"degree": degree[0] if degree else "", "details": _clean(line), "year": year[0] if year else ""})
    return edu_list[:5]

def _extract_projects(section_text: str) -> List[str]:
    projects = []
    for line in section_text.splitlines():
        if len(line) > 5 and not HEADERS["skills"].search(line):
            projects.append(_clean(line))
    return projects[:5]

# --------- Suggestions

def _generate_suggestions(parsed: Dict[str, Any], status: str) -> List[str]:
    suggestions = []
    if status == "Moderate ⚠️":
        if not parsed["technical_skills"]:
            suggestions.append("Add a clear Technical Skills section with tools and technologies.")
        if not parsed["employment_details"]:
            suggestions.append("Include detailed Work Experience with roles and achievements.")
        if not parsed["education"]:
            suggestions.append("Mention your Education with degree and year.")
    elif status == "Good Match 👍":
        suggestions.append("Highlight measurable achievements in your work experience.")
        suggestions.append("Add links to LinkedIn or GitHub if available.")
    elif status == "Strong Match ✅":
        suggestions.append("Your resume is strong. Keep it updated with new projects and skills.")
    return suggestions

# --------- Public API

def ats_extractor(resume_text: str, status: str = "") -> Dict[str, Any]:
    text = resume_text or ""
    sections = _split_sections(text)

    email = _extract_email(text)
    linkedin = _extract_linkedin(text)
    github = _extract_github(text)
    full_name = _guess_full_name(text)

    tech_skills = _extract_skills(sections.get("skills", ""), text)
    soft_skills = _extract_soft_skills(text)
    employment = _extract_experience(sections.get("experience", ""), text)
    education = _extract_education(sections.get("education", ""))
    projects = _extract_projects(sections.get("projects", ""))

    return {
        "full_name": full_name or "Not Found",
        "email": email or "Not Found",
        "linkedin": linkedin,
        "github": github,
        "technical_skills": tech_skills,
        "soft_skills": soft_skills,
        "employment_details": employment,
        "education": education,
        "projects": projects,
        "suggestions": _generate_suggestions(
            {
                "technical_skills": tech_skills,
                "employment_details": employment,
                "education": education
            },
            status
        )
    }
