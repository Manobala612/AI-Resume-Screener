import os
from flask import Flask, request, render_template, send_from_directory
from werkzeug.utils import secure_filename
import docx2txt
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

# Upload folder
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Allowed file types
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Extract text from resume
def extract_text(filepath):
    ext = filepath.rsplit(".", 1)[1].lower()
    text = ""
    if ext == "pdf":
        try:
            reader = PdfReader(filepath)
            for page in reader.pages:
                text += page.extract_text() or ""
        except Exception as e:
            print(f"PDF extraction error: {e}")
    elif ext == "docx":
        try:
            text = docx2txt.process(filepath)
        except Exception as e:
            print(f"DOCX extraction error: {e}")
    elif ext == "txt":
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception as e:
            print(f"TXT extraction error: {e}")
    return text


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    jd = (request.form.get("resumeText") or "").strip()
    resume_files = request.files.getlist("resumeFile")

    if not jd:
        return render_template("index.html", message="⚠️ Please paste or auto-fill a Job Description.")

    if not resume_files or all(f.filename.strip() == "" for f in resume_files):
        return render_template("index.html", message="⚠️ Please upload at least one resume.")

    resumes_text, filenames = [], []

    for file in resume_files:
        if not file or file.filename.strip() == "":
            continue
        if not allowed_file(file.filename):
            continue

        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(save_path)

        text = extract_text(save_path)
        if text.strip():
            resumes_text.append(text)
            filenames.append(filename)

    if not resumes_text:
        return render_template("index.html", message="⚠️ Could not read any resumes.")

    # ---------- TF-IDF Matching ----------
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform([jd] + resumes_text)
    scores = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

    results = []
    for i, score in enumerate(scores):
        pct = round(float(score) * 100, 2)

        if score > 0.6:
            status = "Strong Match"
            color = "bg-green"
            suggestion = "Highly aligned with job requirements. Candidate is a great fit."
        elif score > 0.4:
            status = "Good Match"
            color = "bg-orange"
            suggestion = "Meets many requirements but could be improved."
        else:
            status = "Needs Improvement"
            color = "bg-red"
            suggestion = "Resume does not align well. Candidate may not be a fit."

        results.append({
            "filename": filenames[i],
            "score": pct,
            "status": status,
            "color": color,
            "suggestion": suggestion
        })

    # ✅ Sort by score
    results = sorted(results, key=lambda x: x["score"], reverse=True)

    # ✅ Add S.No in order
    for idx, r in enumerate(results, start=1):
        r["sno"] = idx

    return render_template("index.html", message="✅ Resumes matched successfully!", results=results)


@app.route("/resume/<filename>")
def resume_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


if __name__ == "__main__":
    app.run(debug=True)
