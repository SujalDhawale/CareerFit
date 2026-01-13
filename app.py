from flask import Flask, render_template, request, jsonify, send_file
import os
import secrets
from werkzeug.utils import secure_filename
from ats_logic import parse_resume, parse_jd, match_skills, fetch_courses_for_skills, generate_pdf_report

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['REPORT_FOLDER'] = 'reports'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    try:
        # 1. Validation
        if 'resume' not in request.files:
            return jsonify({'error': 'No resume file uploaded'}), 400
        
        file = request.files['resume']
        jd_text = request.form.get('jd_text', '').strip()
        
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        if not jd_text:
            return jsonify({'error': 'Job Description is required'}), 400

        # 2. Save File
        filename = secure_filename(file.filename)
        unique_id = secrets.token_hex(4)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{unique_id}_{filename}")
        file.save(save_path)

        # 3. Processing
        resume_data = parse_resume(save_path)
        jd_data = parse_jd(jd_text)
        
        # 4. Matching
        match_results = match_skills(resume_data.get('skills', []), jd_data.get('skills_required', []))
        
        # 5. Course Recommendations
        recommendations = {}
        if match_results['missing_skills']:
            recommendations = fetch_courses_for_skills(match_results['missing_skills'])

        # 6. Generate Report
        report_filename = f"ATS_Report_{unique_id}.pdf"
        report_path = os.path.join(app.config['REPORT_FOLDER'], report_filename)
        
        full_data = {
            "resume_data": resume_data,
            "jd_data": jd_data,
            "match_details": match_results,
            "match_score": match_results['score_percentage'],
            "course_recommendations": recommendations,
            "summary": f"Analysis for {resume_data.get('years_of_experience', 'N/A')} experience candidate."
        }
        
        generate_pdf_report(full_data, report_path)

        # 7. Cleanup (Optional, keep for debugging for now)
        # os.remove(save_path)

        return jsonify({
            'success': True,
            'data': full_data,
            'report_url': f"/api/download/{report_filename}"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>')
def download_report(filename):
    return send_file(os.path.join(app.config['REPORT_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
