# CareerFit AI

CareerFit AI is an intelligent Applicant Tracking System (ATS) and Resume Analyzer built with Flask and Google Gemini AI. It evaluates resumes against job descriptions (JDs) to provide a comprehensive match analysis, identify missing skills, and recommend personalized learning paths.

## 🚀 Features

-   **Resume Parsing**: Automatically extracts skills, experience, and education from PDF and DOCX resumes.
-   **Job Description Analysis**: Parses job descriptions to identify key requirements.
-   **Intelligent Matching**: Uses Gemini AI to semanticallly match resume skills with JD requirements.
-   **Gap Analysis**: Highlights missing skills and qualifications.
-   **Course Recommendations**: Scrapes the web (DuckDuckGo/Coursera) to find relevant courses for missing skills.
-   **PDF Report Generation**: Creates a detailed downloadable PDF report with the analysis and recommendations.
-   **REST API**: Provides endpoints for analysis and report generation.

## 🛠️ Prerequisites

-   Python 3.8+
-   A [Google Gemini API Key](https://aistudio.google.com/app/apikey)

## 📦 Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd ats_web_app
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    *Note: On Windows, `docx2pdf` requires Microsoft Word to be installed for .docx parsing.*

3.  **Environment Setup:**
    Create a `.env` file in the root directory and add your Gemini API key:
    ```env
    GEMINI_API_KEY=your_actual_api_key_here
    ```

## ▶️ Usage

1.  **Start the application:**
    ```bash
    python app.py
    ```

2.  **Access the Web Interface:**
    Open your browser and navigate to `http://127.0.0.1:5000`.

3.  **Analyze a Resume:**
    -   Upload a Resume (PDF or DOCX).
    -   Paste the Job Description text.
    -   Click **Analyze**.
    -   View the results and download the PDF report.

## 📂 Project Structure

-   `app.py`: Main Flask application handling routes and API endpoints.
-   `ats_logic.py`: Core logic for parsing, AI interaction, matching, and report generation.
-   `templates/`: HTML templates for the UI.
-   `static/`: Static assets (CSS, JS).
-   `uploads/`: Temporary storage for uploaded resumes.
-   `reports/`: Generated PDF reports.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
