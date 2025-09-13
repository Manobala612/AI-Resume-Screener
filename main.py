from flask import Flask, request, render_template
import os
import PyPDF2
import docx2txt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ---------------------- TEXT EXTRACTION ---------------------- #
def extract_text_pdf(file_path):
    text = ""
    with open(file_path, 'rb') as file:
        read_data = PyPDF2.PdfReader(file)
        for page in read_data.pages:
            text += page.extract_text()
    return text

def extract_text_docs(file_path):
    return docx2txt.process(file_path)

def extract_text_txt(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def extract_text(file_path):
    if file_path.endswith('.pdf'):
        return extract_text_pdf(file_path)
    elif file_path.endswith('.docx'):
        return extract_text_docs(file_path)
    elif file_path.endswith('.txt'):
        return extract_text_txt(file_path)
    else:
        return ""

# ---------------------- FLASK APP ---------------------- #
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB

@app.route('/')
def matchresume():
    return render_template("app.html")

@app.route('/upload', methods=['POST'])
def upload():
    if request.method == 'POST':
        jd = request.form.get('resumeText')
        resume_files = request.files.getlist('resumeFile')

        resumes = []
        filenames = []

        for resume_file in resume_files:
            filenamee = os.path.join(app.config['UPLOAD_FOLDER'], resume_file.filename)
            resume_file.save(filenamee)
            text = extract_text(filenamee)

            # ✅ Format compliance check
            required_sections = ["education", "experience", "skills"]
            if all(section in text.lower() for section in required_sections):
                resumes.append(text)
                filenames.append(resume_file.filename)

        if not resumes or not jd:
            return render_template('app.html', message="Please upload resumes and select/paste a job description")

        # ✅ Vectorize JD + resumes
        vec = TfidfVectorizer().fit_transform([jd] + resumes)
        vecs = vec.toarray()
        j_V = vecs[0]
        r_V = vecs[1:]

        sim = cosine_similarity([j_V], r_V)[0]

        # ✅ Only resumes with similarity >= 0.4
        filtered = [(filenames[i], sim[i]) for i in range(len(resumes)) if sim[i] >= 0.3]
        filtered = sorted(filtered, key=lambda x: x[1], reverse=True)
        filtered = filtered[:25]  # Top 25 max

        if not filtered:
            return render_template('app.html', message="No resumes matched above 0.4 similarity")

        # ✅ Prepare results with rank, status, and color class
        results = []
        for idx, (fname, score) in enumerate(filtered, start=1):
            status = "Strong Match ✅" if score > 0.7 else "Good Match 👍" if score >= 0.4 else "Moderate ⚠️"
            color = "bg-green" if score > 0.7 else "bg-orange" if score >= 0.4 else "bg-red"
            results.append({
                "rank": idx,
                "filename": fname,
                "score": round(score, 2),
                "status": status,
                "color": color
            })

        return render_template(
            'app.html',
            message=f"Top {len(results)} matching resumes:",
            results=results
        )

    return render_template('app.html')

# ---------------------- RUN APP ---------------------- #
if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)
