document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('resume');
    const fileNameDisplay = document.getElementById('file-name');
    const analyzeBtn = document.getElementById('analyze-btn');
    const loading = document.getElementById('loading');
    const resultsSection = document.getElementById('results-section');
    const scoreCircle = document.getElementById('score-circle');
    const scoreText = document.getElementById('score-text');

    // Drag & Drop Handling
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('border-blue-400', 'bg-white/5');
    });
    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('border-blue-400', 'bg-white/5');
    });
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('border-blue-400', 'bg-white/5');
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            updateFileName();
        }
    });
    fileInput.addEventListener('change', updateFileName);

    function updateFileName() {
        if (fileInput.files.length) {
            fileNameDisplay.textContent = `Selected: ${fileInput.files[0].name}`;
            fileNameDisplay.classList.remove('hidden');
        }
    }

    // Analysis Logic
    analyzeBtn.addEventListener('click', async () => {
        const file = fileInput.files[0];
        const jdText = document.getElementById('jd-text').value;

        if (!file || !jdText) {
            alert('Please upload a resume and enter a job description.');
            return;
        }

        // Setup UI for Loading
        analyzeBtn.disabled = true;
        loading.classList.remove('hidden');
        resultsSection.classList.add('hidden');

        const formData = new FormData();
        formData.append('resume', file);
        formData.append('jd_text', jdText);

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (!result.success) {
                throw new Error(result.error || 'Analysis failed');
            }

            // Populate UI
            const data = result.data;
            const score = data.match_score;

            // Score Animation
            resultsSection.classList.remove('hidden');
            // Calculate stroke offset (based on r=56 -> circumference ~351.86)
            const circumference = 351.86;
            const offset = circumference - (score / 100) * circumference;
            // Short delay to ensure transition works
            setTimeout(() => {
                scoreCircle.style.strokeDashoffset = offset;
                scoreText.textContent = `${score}%`;
            }, 100);

            // Colorize Score
            if (score < 50) scoreCircle.classList.add('text-red-500');
            else if (score < 80) scoreCircle.classList.add('text-yellow-500');
            else scoreCircle.classList.add('text-green-500');

            // Render Lists
            document.getElementById('missing-skills').innerHTML = data.match_details.missing_skills.map(s =>
                `<span class="px-3 py-1 bg-red-500/10 border border-red-500/20 text-red-300 rounded-full text-sm">${s}</span>`
            ).join('') || '<span class="text-gray-400">None! Great job.</span>';

            document.getElementById('matched-skills').innerHTML = data.match_details.matched_skills.map(s =>
                `<span class="px-3 py-1 bg-green-500/10 border border-green-500/20 text-green-300 rounded-full text-sm">${s}</span>`
            ).join('');

            // Courses
            const coursesContainer = document.getElementById('courses-list');
            coursesContainer.innerHTML = '';
            for (const [skill, courses] of Object.entries(data.course_recommendations)) {
                if (courses.length === 0) continue;

                const skillBlock = document.createElement('div');
                skillBlock.className = "mb-3";
                skillBlock.innerHTML = `<h4 class="text-sm font-bold text-gray-300 mb-1">${skill}</h4>`;

                courses.forEach(c => {
                    const link = document.createElement('a');
                    link.href = c.link;
                    link.target = "_blank";
                    link.className = "block text-xs text-blue-400 hover:text-blue-300 truncate mb-1";
                    link.innerHTML = `↗ ${c.title}`;
                    skillBlock.appendChild(link);
                });
                coursesContainer.appendChild(skillBlock);
            }
            if (!coursesContainer.innerHTML) coursesContainer.innerHTML = '<span class="text-gray-500 text-sm">No specific course recommendations found.</span>';

            // Report Download
            document.getElementById('download-btn').href = result.report_url;


        } catch (error) {
            alert(`Error: ${error.message}`);
        } finally {
            analyzeBtn.disabled = false;
            loading.classList.add('hidden');
        }
    });
});
