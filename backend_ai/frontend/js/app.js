/**
 * EquiGrade AI - Frontend JavaScript
 * Connects to FastAPI backend at http://localhost:8000
 */

const API_BASE = '/api/v1';

// ==================== STATE ====================
let currentUser = null;
let authToken = null;
let refreshToken = null;
let currentExamId = null;
let currentSubmissionId = null;
let currentSubmissionData = null;
let notificationInterval = null;
let examTimerInterval = null;
let examTimeLeft = 0;
let gradingPollingInterval = null;

// ==================== INIT ====================
document.addEventListener('DOMContentLoaded', () => {
    // Check stored auth
    authToken = localStorage.getItem('equigrade_token');
    refreshToken = localStorage.getItem('equigrade_refresh');
    const storedUser = localStorage.getItem('equigrade_user');

    if (authToken && storedUser) {
        currentUser = JSON.parse(storedUser);
        if (currentUser.role === 'teacher') {
            showPage('teacher-dashboard');
            loadTeacherDashboard();
        } else {
            showPage('student-dashboard');
            loadStudentDashboard();
        }
        startNotificationPolling();
    } else {
        showPage('login-page');
    }
});

// ==================== API HELPER ====================
async function apiCall(method, endpoint, data = null, isForm = false) {
    const headers = {};
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
    if (!isForm) headers['Content-Type'] = 'application/json';

    const config = {
        method,
        headers,
    };

    if (data) {
        config.body = isForm ? data : JSON.stringify(data);
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, config);

        // Handle token expiry
        if (response.status === 401 && refreshToken) {
            const refreshed = await tryRefreshToken();
            if (refreshed) {
                headers['Authorization'] = `Bearer ${authToken}`;
                const retry = await fetch(`${API_BASE}${endpoint}`, { ...config, headers });
                return handleResponse(retry);
            } else {
                logout();
                return null;
            }
        }

        return handleResponse(response);
    } catch (err) {
        console.error('API Error:', err);
        showToast('Connection error. Please check if the server is running.', 'error');
        return null;
    }
}

async function handleResponse(response) {
    const text = await response.text();
    let data;
    try { data = JSON.parse(text); } catch { data = text; }

    if (!response.ok) {
        const msg = data?.detail || 'An error occurred';
        showToast(typeof msg === 'string' ? msg : JSON.stringify(msg), 'error');
        return null;
    }
    return data;
}

async function tryRefreshToken() {
    try {
        const resp = await fetch(`${API_BASE}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        if (resp.ok) {
            const data = await resp.json();
            authToken = data.access_token;
            refreshToken = data.refresh_token;
            currentUser = data.user;
            localStorage.setItem('equigrade_token', authToken);
            localStorage.setItem('equigrade_refresh', refreshToken);
            localStorage.setItem('equigrade_user', JSON.stringify(currentUser));
            return true;
        }
    } catch (e) {}
    return false;
}

// ==================== AUTH ====================
async function handleLogin(event) {
    event.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const btn = event.target.querySelector('button[type="submit"]');

    setButtonLoading(btn, true, 'Signing in...');

    const data = await apiCall('POST', '/auth/login', { email, password });

    setButtonLoading(btn, false, '<i class="fas fa-sign-in-alt me-2"></i>Sign In');

    if (data) {
        authToken = data.access_token;
        refreshToken = data.refresh_token;
        currentUser = data.user;

        localStorage.setItem('equigrade_token', authToken);
        localStorage.setItem('equigrade_refresh', refreshToken);
        localStorage.setItem('equigrade_user', JSON.stringify(currentUser));

        showToast(`Welcome back, ${currentUser.full_name}!`, 'success');

        if (currentUser.role === 'teacher') {
            showPage('teacher-dashboard');
            loadTeacherDashboard();
        } else {
            showPage('student-dashboard');
            loadStudentDashboard();
        }

        startNotificationPolling();
    }
}

function logout() {
    authToken = null;
    refreshToken = null;
    currentUser = null;
    localStorage.clear();
    if (notificationInterval) clearInterval(notificationInterval);
    if (examTimerInterval) clearInterval(examTimerInterval);
    document.querySelectorAll('.page-section').forEach(p => p.classList.remove('active'));
    document.getElementById('login-page').classList.add('active');
    window.scrollTo(0, 0);
    showToast('Logged out successfully', 'info');
}

// ==================== PAGE NAVIGATION ====================
function showPage(pageId, data = null) {
    document.querySelectorAll('.page-section').forEach(p => p.classList.remove('active'));
    const page = document.getElementById(pageId);
    if (page) {
        page.classList.add('active');
        window.scrollTo(0, 0);
    }

    // Update sidebar active states
    updateSidebarActive(pageId);

    // Load page data
    switch (pageId) {
        case 'teacher-dashboard': loadTeacherDashboard(); break;
        case 'create-exam': initCreateExamPage(); break;
        case 'ai-results': loadAIResults(); break;
        case 'student-page': loadStudentsList(); break;
        case 'analytics-page': loadAnalytics(); break;
        case 'student-dashboard': loadStudentDashboard(); break;
        case 'student-exams': loadStudentExams(); break;
        case 'student-results': loadStudentResults(data); break;
        case 'student-exam': if (data) startExamPage(data); break;
        case 'profile-page': loadProfilePage(); break;
    }
}

function updateSidebarActive(pageId) {
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    const pageToNav = {
        'teacher-dashboard': 0, 'create-exam': 1, 'ai-results': 2,
        'student-page': 3, 'analytics-page': 4, 'profile-page': 5,
        'student-dashboard': 0, 'student-exams': 1, 'student-results': 2
    };
}

// ==================== TEACHER DASHBOARD ====================
async function loadTeacherDashboard() {
    updateUserUI();
    const stats = await apiCall('GET', '/submissions/dashboard/teacher-stats');
    if (!stats) return;

    setTextContent('stat-total-exams', stats.total_exams);
    setTextContent('stat-total-students', stats.total_students);
    setTextContent('stat-essays-evaluated', stats.essays_evaluated?.toLocaleString());
    setTextContent('stat-average-score', stats.average_score);
    setTextContent('stat-pending-reviews', stats.pending_reviews || 0);

    // Recent activity table
    const tbody = document.getElementById('recent-activity-tbody');
    if (tbody && stats.recent_submissions) {
        tbody.innerHTML = stats.recent_submissions.map(sub => `
            <tr>
                <td>
                    <div class="d-flex align-items-center gap-2">
                        <img src="https://ui-avatars.com/api/?name=${encodeURIComponent(sub.student_name)}&background=${sub.student_avatar_color}&color=fff"
                             width="32" height="32" class="rounded-circle">
                        <span class="fw-medium">${escapeHtml(sub.student_name)}</span>
                    </div>
                </td>
                <td>${escapeHtml(sub.exam_title)}</td>
                <td>${formatDate(sub.submitted_at)}</td>
                <td><span class="status-badge ${getStatusClass(sub.status)}">${formatStatus(sub.status)}</span></td>
                <td>
                    ${sub.status === 'ai_graded' || sub.status === 'needs_review' ?
                        `<button class="btn-action btn-action-primary" onclick="openReviewModal(${sub.submission_id})">Review</button>` :
                        `<button class="btn-action btn-action-outline" onclick="openReviewModal(${sub.submission_id})">View</button>`
                    }
                </td>
            </tr>
        `).join('');
    }

    // Load notifications count
    loadNotificationCount();
}

// ==================== CREATE EXAM ====================
let rubricRows = [];
let examQuestions = [];
let currentEditingExamId = null;

function initCreateExamPage() {
    currentEditingExamId = null;
    rubricRows = [
        { name: 'Content Accuracy', description: 'Accuracy and relevance of information presented', weight: 30 },
        { name: 'Completeness', description: 'Coverage of all required points and topics', weight: 25 },
        { name: 'Reasoning', description: 'Logical flow and coherent argumentation', weight: 25 },
        { name: 'Writing Quality', description: 'Grammar, spelling, and style', weight: 20 },
    ];
    renderRubricTable();
    updateExamClassOptions();
}

function updateExamClassOptions() {
    const level = document.getElementById('exam-level')?.value || 'SMA';
    const classSelect = document.getElementById('exam-class');
    if (!classSelect) return;
    classSelect.innerHTML = '';

    let classes = [];
    if (level === 'SD') {
        classes = ['Kelas 1', 'Kelas 2', 'Kelas 3', 'Kelas 4', 'Kelas 5', 'Kelas 6'];
    } else if (level === 'SMP') {
        classes = ['Kelas 7', 'Kelas 8', 'Kelas 9'];
    } else if (level === 'SMA') {
        classes = ['Kelas 10', 'Kelas 11', 'Kelas 12'];
    }

    classes.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c;
        opt.innerText = c;
        classSelect.appendChild(opt);
    });
}

function renderRubricTable() {
    const tbody = document.getElementById('rubric-tbody');
    if (!tbody) return;
    tbody.innerHTML = rubricRows.map((row, idx) => `
        <tr>
            <td><input type="text" value="${escapeHtml(row.name)}" onchange="updateRubric(${idx}, 'name', this.value)" placeholder="Criteria name"></td>
            <td><input type="text" value="${escapeHtml(row.description)}" onchange="updateRubric(${idx}, 'description', this.value)" placeholder="Description"></td>
            <td><input type="number" value="${row.weight}" onchange="updateRubric(${idx}, 'weight', this.value)" placeholder="Weight" min="1" max="100"></td>
            <td class="text-center">
                <button class="btn-action btn-action-outline" style="padding: 0.375rem 0.75rem;" onclick="removeRubricRow(${idx})">
                    <i class="fas fa-trash-alt"></i>
                </button>
            </td>
        </tr>
    `).join('');

    // Show total weight
    const total = rubricRows.reduce((sum, r) => sum + Number(r.weight || 0), 0);
    const weightIndicator = document.getElementById('weight-total');
    if (weightIndicator) {
        weightIndicator.textContent = `Total: ${total}%`;
        weightIndicator.style.color = total === 100 ? '#10B981' : '#EF4444';
    }
}

function updateRubric(idx, field, value) {
    rubricRows[idx][field] = value;
    renderRubricTable();
}

function addRubricRow() {
    rubricRows.push({ name: '', description: '', weight: 0 });
    renderRubricTable();
}

function removeRubricRow(idx) {
    rubricRows.splice(idx, 1);
    renderRubricTable();
}

async function generateAIRubric() {
    const questionText = document.getElementById('exam-question')?.value;
    const answerKey = document.getElementById('exam-answer-key')?.value;
    const subject = document.getElementById('exam-subject')?.value;
    const maxScore = parseFloat(document.getElementById('exam-max-score')?.value || '100');

    if (!questionText || !answerKey) {
        showToast('Please enter the question and answer key first', 'warning');
        return;
    }

    const btn = document.getElementById('btn-generate-rubric');
    setButtonLoading(btn, true, 'Generating...');

    // We need a question_id for rubric generation - first create a temp call
    // For now, return generated criteria directly
    const data = await apiCall('POST', '/exams/0/questions/0/rubric/generate', {
        question_text: questionText,
        answer_key: answerKey,
        max_score: maxScore,
        subject: subject,
        education_level: document.getElementById('exam-level')?.value || 'SMA',
        education_class: document.getElementById('exam-class')?.value || 'Kelas 11'
    });

    setButtonLoading(btn, false, '<i class="fas fa-magic me-1"></i>Generate with AI');

    if (data && data.criteria) {
        rubricRows = data.criteria.map(c => ({
            name: c.name,
            description: '',
            weight: c.weight
        }));
        renderRubricTable();
        showToast('AI rubric generated!', 'success');
    }
}

async function saveExam(status = 'draft') {
    const title = document.getElementById('exam-title')?.value?.trim();
    const subject = document.getElementById('exam-subject')?.value;
    const className = document.getElementById('exam-class')?.value;
    const duration = document.getElementById('exam-duration')?.value;
    const endTime = document.getElementById('exam-end-time')?.value;
    const questionText = document.getElementById('exam-question')?.value?.trim();
    const answerKey = document.getElementById('exam-answer-key')?.value?.trim();
    const maxScore = parseFloat(document.getElementById('exam-max-score')?.value || '100');

    if (!title) { showToast('Please enter exam title', 'warning'); return; }
    if (!questionText) { showToast('Please enter the essay question', 'warning'); return; }
    if (!answerKey) { showToast('Please enter the answer key', 'warning'); return; }

    const totalWeight = rubricRows.reduce((sum, r) => sum + Number(r.weight || 0), 0);
    if (totalWeight !== 100) {
        showToast(`Rubric weights must total 100%. Currently: ${totalWeight}%`, 'warning');
        return;
    }

    const examData = {
        title,
        subject,
        class_name: className,
        education_level: document.getElementById('exam-level')?.value || 'SMA',
        duration_minutes: parseInt(duration),
        end_time: endTime ? new Date(endTime).toISOString() : null,
        ai_grading_enabled: true,
        questions: [{
            order_num: 1,
            question_text: questionText,
            answer_key: answerKey,
            max_score: maxScore,
            question_type: 'essay',
            rubric_criteria: rubricRows.map(r => ({
                criteria_name: r.name,
                description: r.description,
                weight_percent: Number(r.weight)
            }))
        }]
    };

    const btn = status === 'draft' ? document.getElementById('btn-save-draft') : document.getElementById('btn-publish-exam');
    setButtonLoading(btn, true, 'Saving...');

    let exam;
    if (currentEditingExamId) {
        exam = await apiCall('PUT', `/exams/${currentEditingExamId}`, examData);
    } else {
        exam = await apiCall('POST', '/exams/', examData);
    }

    setButtonLoading(btn, false);

    if (exam) {
        currentEditingExamId = exam.id;
        if (status === 'published') {
            const published = await apiCall('POST', `/exams/${exam.id}/publish`);
            if (published) {
                showToast(`Exam published! ${published.students_notified} students notified.`, 'success');
                showPage('teacher-dashboard');
            }
        } else {
            showToast('Exam saved as draft', 'success');
        }
    }
}

// ==================== AI RESULTS ====================
async function loadAIResults() {
    const examFilter = document.getElementById('ai-results-exam-filter');
    const examId = examFilter?.value || '';

    let endpoint = '/submissions/exam/';
    // Load all AI graded submissions across all exams
    const stats = await apiCall('GET', '/submissions/dashboard/teacher-stats');
    if (!stats) return;

    // Load exams for filter
    const exams = await apiCall('GET', '/exams/');
    if (exams && examFilter) {
        examFilter.innerHTML = '<option value="">All Exams</option>' +
            exams.map(e => `<option value="${e.id}">${escapeHtml(e.title)}</option>`).join('');
        if (examId) {
            examFilter.value = examId;
        }
    }

    const btnCloseAI = document.getElementById('btn-close-exam-ai');
    if (btnCloseAI) {
        btnCloseAI.style.display = examId ? 'block' : 'none';
    }

    let isGrading = false;

    // Load submissions needing review
    if (exams) {
        const tbody = document.getElementById('ai-results-tbody');
        if (!tbody) return;
        tbody.innerHTML = '';

        for (const exam of exams) {
            if (examId && exam.id != examId) continue;
            const submissions = await apiCall('GET', `/submissions/exam/${exam.id}`);
            if (!submissions) continue;

            for (const sub of submissions) {
                if (sub.status === 'draft') continue;
                tbody.innerHTML += `
                    <tr>
                        <td>
                            <div class="d-flex align-items-center gap-2">
                                <img src="https://ui-avatars.com/api/?name=${encodeURIComponent(sub.student_name || 'S')}&background=10B981&color=fff"
                                     width="32" height="32" class="rounded-circle">
                                <span class="fw-medium">${escapeHtml(sub.student_name || 'Unknown')}</span>
                            </div>
                        </td>
                        <td>${escapeHtml(exam.title)}</td>
                        <td><span class="fw-bold text-primary">${sub.percentage ? sub.percentage.toFixed(1) + '/100' : 'Pending'}</span></td>
                        <td><span class="status-badge ${getStatusClass(sub.status)}">${formatStatus(sub.status)}</span></td>
                        <td>
                            <button class="btn-action btn-action-primary" onclick="openReviewModal(${sub.id})">
                                ${sub.status === 'ai_graded' ? 'Review' : 'View'}
                            </button>
                        </td>
                    </tr>
                `;
                if (sub.status === 'ai_grading') isGrading = true;
            }
        }

        if (!tbody.innerHTML) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No submissions found</td></tr>';
        }
    }

    if (isGrading && examId) {
        startGradingPolling(examId);
    } else {
        stopGradingPolling();
    }
}

function stopGradingPolling() {
    if (gradingPollingInterval) {
        clearInterval(gradingPollingInterval);
        gradingPollingInterval = null;
    }
    const container = document.getElementById('ai-grading-progress-container');
    if (container) container.style.display = 'none';
}

async function startGradingPolling(examId) {
    stopGradingPolling(); // clear existing
    const container = document.getElementById('ai-grading-progress-container');
    const bar = document.getElementById('ai-grading-progress-bar');
    const text = document.getElementById('ai-grading-progress-text');

    if (container) container.style.display = 'block';

    const checkProgress = async () => {
        const progress = await apiCall('GET', `/exams/${examId}/grading-progress`);
        if (progress) {
            if (bar) bar.style.width = `${progress.percentage}%`;
            if (text) text.textContent = `${progress.percentage}% (${progress.graded}/${progress.total})`;

            if (progress.percentage >= 100 || progress.status === 'completed') {
                stopGradingPolling();
                showToast('AI Grading completed!', 'success');
                loadAIResults(); // Reload to show Review buttons
            }
        }
    };

    checkProgress();
    gradingPollingInterval = setInterval(checkProgress, 3000);
}

// ==================== REVIEW MODAL ====================
async function closeExamAndGrade() {
    const examId = document.getElementById('ai-results-exam-filter')?.value;
    if (!examId) return;

    if (!confirm('Are you sure you want to close this exam and trigger AI grading? Students will no longer be able to submit.')) {
        return;
    }

    const btnCloseAI = document.getElementById('btn-close-exam-ai');
    if (btnCloseAI) setButtonLoading(btnCloseAI, true, 'Processing...');

    const result = await apiCall('POST', `/exams/${examId}/close`);

    if (btnCloseAI) setButtonLoading(btnCloseAI, false, '<i class="fas fa-play me-2"></i>Close Exam & Grade');

    if (result) {
        showToast('Exam closed! AI is now grading submissions...', 'success');
        // Give backend a moment to update statuses to 'ai_grading' before reloading
        setTimeout(() => {
            loadAIResults();
        }, 1000);
    }
}

async function openReviewModal(submissionId) {
    currentSubmissionData = await apiCall('GET', `/submissions/${submissionId}`);
    if (!currentSubmissionData) return;

    const modal = document.getElementById('reviewModal');
    const sub = currentSubmissionData;

    // Populate modal content
    const studentAnswer = sub.answers?.[0];
    document.getElementById('modal-student-name').textContent = sub.student_name || 'Student';
    document.getElementById('modal-exam-title').textContent = sub.exam_title || 'Exam';
    document.getElementById('modal-student-answer').textContent = studentAnswer?.answer_text || 'No answer text (file submitted)';
    document.getElementById('modal-total-score').textContent = `${sub.total_score || 0}/${sub.max_score || 100}`;
    document.getElementById('modal-percentage').textContent = `${sub.percentage?.toFixed(1) || 0}%`;

    // AI Feedback
    if (studentAnswer?.ai_feedback) {
        const fb = studentAnswer.ai_feedback;
        document.getElementById('modal-strengths').innerHTML = fb.strengths?.map(s => `<li><i class="fas fa-check-circle"></i><span>${escapeHtml(s)}</span></li>`).join('') || '';
        document.getElementById('modal-weaknesses').innerHTML = fb.weaknesses?.map(s => `<li><i class="fas fa-times-circle"></i><span>${escapeHtml(s)}</span></li>`).join('') || '';
        document.getElementById('modal-missing').innerHTML = fb.missing_concepts?.map(s => `<li><i class="fas fa-lightbulb"></i><span>${escapeHtml(s)}</span></li>`).join('') || '';
        document.getElementById('modal-ai-comment').textContent = fb.comment || '';
    } else {
        document.getElementById('modal-strengths').innerHTML = '<li class="text-muted">Not evaluated yet</li>';
        document.getElementById('modal-weaknesses').innerHTML = '<li class="text-muted">Not evaluated yet</li>';
        document.getElementById('modal-missing').innerHTML = '<li class="text-muted">Not evaluated yet</li>';
        document.getElementById('modal-ai-comment').textContent = 'AI has not graded this submission yet.';
    }

    // Score breakdown
    const breakdown = document.getElementById('modal-score-breakdown-list');
    if (breakdown) {
        if (studentAnswer?.ai_feedback?.per_criteria) {
            breakdown.innerHTML = studentAnswer.ai_feedback.per_criteria.map(c => `
                <div class="score-item">
                    <span class="score-label">${escapeHtml(c.criteria_name)}</span>
                    <span class="score-value">${c.score}/${c.max_score}</span>
                </div>
            `).join('');
        } else {
            breakdown.innerHTML = '<div class="text-muted text-center p-3">Score breakdown will appear after AI evaluation.</div>';
        }
    }

    // Teacher score override fields
    const overrideField = document.getElementById('modal-teacher-score');
    if (overrideField) {
        overrideField.value = studentAnswer?.teacher_score || studentAnswer?.ai_score || '';
    }

    // Show/hide action buttons based on status
    const approveBtn = document.getElementById('btn-approve-submission');
    const releaseBtn = document.getElementById('btn-release-submission');
    if (approveBtn) approveBtn.style.display = sub.status === 'ai_graded' ? 'block' : 'none';
    if (releaseBtn) releaseBtn.style.display = sub.status === 'approved' ? 'block' : 'none';

    // Show modal
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

async function approveSubmission() {
    if (!currentSubmissionData) return;
    const teacherScore = document.getElementById('modal-teacher-score')?.value;
    const teacherComment = document.getElementById('modal-teacher-comment')?.value;

    const reviewData = {
        action: 'approve',
        teacher_notes: teacherComment,
        answer_overrides: currentSubmissionData.answers?.length > 0 ? [{
            answer_id: currentSubmissionData.answers[0].id,
            teacher_comment: teacherComment
        }] : []
    };

    if (teacherScore) {
        reviewData.answer_overrides[0].teacher_score = parseFloat(teacherScore);
    }

    const result = await apiCall('PUT', `/submissions/${currentSubmissionData.id}/review`, reviewData);
    if (result) {
        showToast('Submission approved!', 'success');
        bootstrap.Modal.getInstance(document.getElementById('reviewModal'))?.hide();
        loadAIResults();
    }
}

async function releaseSubmissionGrade() {
    if (!currentSubmissionData) return;
    const result = await apiCall('POST', `/submissions/${currentSubmissionData.id}/release`);
    if (result) {
        showToast('Grade released to student!', 'success');
        bootstrap.Modal.getInstance(document.getElementById('reviewModal'))?.hide();
        loadAIResults();
    }
}

// ==================== STUDENTS PAGE ====================
async function loadStudentsList() {
    const students = await apiCall('GET', '/users/?role=student&limit=200');
    if (!students) return;

    const tbody = document.getElementById('students-tbody');
    if (!tbody) return;

    tbody.innerHTML = students.map((s, idx) => `
        <tr>
            <td>${idx + 1}</td>
            <td>
                <div class="d-flex align-items-center gap-2">
                    <img src="https://ui-avatars.com/api/?name=${encodeURIComponent(s.full_name)}&background=${s.avatar_color}&color=fff"
                         width="32" height="32" class="rounded-circle">
                    <span>${escapeHtml(s.full_name)}</span>
                </div>
            </td>
            <td>${escapeHtml(s.email)}</td>
            <td>${escapeHtml(s.class_name || '-')}</td>
            <td><span class="status-badge ${s.is_active ? 'approved' : 'pending'}">${s.is_active ? 'Active' : 'Inactive'}</span></td>
            <td>
                <button class="btn-action btn-action-outline" onclick="editStudent(${s.id})">Edit</button>
            </td>
        </tr>
    `).join('');
}

// ==================== ANALYTICS ====================
async function loadAnalytics() {
    const data = await apiCall('GET', '/analytics/overview');
    if (!data) return;

    setTextContent('analytics-total-scores', data.total_scores || 0);
    setTextContent('analytics-overall-avg', (data.overall_average || 0).toFixed(1) + '%');

    // Score distribution chart
    renderBarChart('score-dist-chart', data.score_distribution || [], 'grade', 'count');

    // Subject averages
    const subjectTable = document.getElementById('subject-averages-tbody');
    if (subjectTable && data.subject_averages) {
        subjectTable.innerHTML = data.subject_averages.map(s => `
            <tr>
                <td>${escapeHtml(s.subject)}</td>
                <td>${s.avg_score.toFixed(1)}%</td>
                <td>${s.total_submissions}</td>
            </tr>
        `).join('');
    }
}

function renderBarChart(containerId, data, labelKey, valueKey) {
    const container = document.getElementById(containerId);
    if (!container || !data.length) return;

    const maxVal = Math.max(...data.map(d => d[valueKey]), 1);
    container.innerHTML = data.map(d => `
        <div class="chart-bar" style="height: ${Math.max((d[valueKey] / maxVal) * 100, 5)}%">
            <span class="bar-value">${d[valueKey]}</span>
            <span class="bar-label">${d[labelKey]}</span>
        </div>
    `).join('');
}

// ==================== STUDENT DASHBOARD ====================
async function loadStudentDashboard() {
    updateUserUI();
    const stats = await apiCall('GET', '/submissions/dashboard/student-stats');
    if (!stats) return;

    setTextContent('student-stat-available', stats.exams_available);
    setTextContent('student-stat-completed', stats.exams_completed);
    setTextContent('student-stat-avg', stats.average_score?.toFixed(1));

    // Upcoming exams
    const upcomingContainer = document.getElementById('upcoming-exams-container');
    if (upcomingContainer && stats.upcoming_exams) {
        upcomingContainer.innerHTML = stats.upcoming_exams.map(exam => `
            <div class="exam-card mb-3">
                <span class="exam-subject">${escapeHtml(exam.subject)}</span>
                <h5>${escapeHtml(exam.title)}</h5>
                <div class="exam-meta-info">
                    <span><i class="far fa-clock"></i> ${exam.duration_minutes} min</span>
                    <span><i class="far fa-calendar"></i> ${exam.end_time ? 'Due: ' + formatDate(exam.end_time) : 'No deadline'}</span>
                </div>
                <button class="btn-start" onclick="startExam(${exam.exam_id})">Start Exam</button>
            </div>
        `).join('') || '<p class="text-muted">No upcoming exams</p>';
    }

    // Recent results
    const recentTable = document.getElementById('student-recent-results-tbody');
    if (recentTable && stats.recent_results) {
        recentTable.innerHTML = stats.recent_results.map(r => `
            <tr>
                <td>${escapeHtml(r.exam_title)}</td>
                <td><span class="fw-bold text-primary">${r.total_score?.toFixed(0)}/${r.max_score?.toFixed(0)}</span></td>
                <td><span class="status-badge approved">Released</span></td>
                <td><button class="btn-action btn-action-primary" onclick="viewResult(${r.submission_id})">View</button></td>
            </tr>
        `).join('') || '<tr><td colspan="4" class="text-center text-muted">No results yet</td></tr>';
    }

    loadNotificationCount();
}

// ==================== STUDENT EXAMS ====================
async function loadStudentExams() {
    const exams = await apiCall('GET', '/exams/');
    const mySubmissions = await apiCall('GET', '/submissions/my');
    if (!exams) return;

    const submittedExamIds = new Set(mySubmissions?.map(s => s.exam_id) || []);

    const container = document.getElementById('student-exams-container');
    if (!container) return;

    const publishedExams = exams.filter(e => e.status !== 'draft');

    container.innerHTML = publishedExams.map(exam => {
        const alreadySubmitted = submittedExamIds.has(exam.id);
        const statusBadge = alreadySubmitted ? '<span class="status-badge approved">Submitted</span>' : '';
        return `
            <div class="col-md-6 col-lg-4">
                <div class="exam-card">
                    <span class="exam-subject">${escapeHtml(exam.subject)}</span>
                    ${statusBadge}
                    <h5>${escapeHtml(exam.title)}</h5>
                    <div class="exam-meta-info">
                        <span><i class="far fa-clock"></i> ${exam.duration_minutes} min</span>
                        <span><i class="far fa-calendar"></i> ${exam.end_time ? formatDate(exam.end_time) : 'No deadline'}</span>
                    </div>
                    ${!alreadySubmitted && exam.status !== 'completed' ?
                        `<button class="btn-start" onclick="startExam(${exam.id})">Start Exam</button>` :
                        alreadySubmitted ? `<button class="btn-start" style="background: #10B981;" disabled>Submitted</button>` :
                        `<button class="btn-start" disabled style="opacity:0.6">Closed</button>`
                    }
                </div>
            </div>
        `;
    }).join('') || '<p class="col text-muted">No exams available for your class</p>';
}

// ==================== TAKE EXAM ====================
async function startExam(examId) {
    // Check existing submission
    const mySubmissions = await apiCall('GET', `/submissions/my?exam_id=${examId}`);

    let submission;
    if (mySubmissions && mySubmissions.length > 0 && mySubmissions[0].status !== 'submitted') {
        submission = mySubmissions[0];
        showToast('Resuming your exam...', 'info');
    } else {
        // Start new submission
        const params = new URLSearchParams({ exam_id: examId });
        submission = await apiCall('POST', `/submissions/start?${params}`);
    }

    if (!submission) return;

    currentSubmissionId = submission.id;
    currentExamId = examId;

    // Get exam details
    const exam = await apiCall('GET', `/exams/${examId}`);
    if (!exam) return;

    showPage('student-exam', { exam, submission });
}

async function startExamPage(data) {
    const { exam, submission } = data;
    const question = exam.questions?.[0];
    if (!question) return;

    // Populate exam info
    setTextContent('exam-page-title', exam.title);
    setTextContent('exam-page-subject', exam.subject);
    setTextContent('exam-page-class', exam.class_name);
    setTextContent('exam-page-duration', `${exam.duration_minutes} min`);
    setTextContent('exam-page-question', question.question_text);

    // Set up timer
    examTimeLeft = exam.duration_minutes * 60;
    if (submission.started_at) {
        const elapsed = Math.floor((Date.now() - new Date(submission.started_at).getTime()) / 1000);
        examTimeLeft = Math.max(0, examTimeLeft - elapsed);
    }
    startExamTimer();

    // Load existing answer if any
    if (submission.answers?.length > 0) {
        const existingAnswer = submission.answers.find(a => a.question_id === question.id);
        if (existingAnswer?.answer_text) {
            document.getElementById('student-answer-textarea').value = existingAnswer.answer_text;
        }
    }
}

function startExamTimer() {
    if (examTimerInterval) clearInterval(examTimerInterval);
    updateTimerDisplay();
    examTimerInterval = setInterval(() => {
        examTimeLeft--;
        updateTimerDisplay();
        if (examTimeLeft <= 0) {
            clearInterval(examTimerInterval);
            showToast('Time is up! Submitting your exam...', 'warning');
            submitExam();
        }
    }, 1000);
}

function updateTimerDisplay() {
    const mins = Math.floor(examTimeLeft / 60);
    const secs = examTimeLeft % 60;
    const display = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    setTextContent('examTimer', display);

    // Color warning when < 10 minutes
    const timerEl = document.getElementById('examTimer');
    if (timerEl) {
        timerEl.style.color = examTimeLeft < 600 ? '#EF4444' : '';
    }
}

async function saveExamProgress() {
    const answerText = document.getElementById('student-answer-textarea')?.value;
    if (!currentSubmissionId || !currentExamId) return;

    const exam = await apiCall('GET', `/exams/${currentExamId}`);
    if (!exam || !exam.questions?.length) return;

    const formData = new FormData();
    formData.append('question_id', exam.questions[0].id);
    if (answerText) formData.append('answer_text', answerText);

    const result = await apiCall('POST', `/submissions/${currentSubmissionId}/answers`, formData, true);
    if (result) showToast('Progress saved!', 'success');
}

async function submitExam() {
    // Auto-save first
    await saveExamProgress();

    if (!confirm('Are you sure you want to submit your exam? You cannot edit after submission.')) return;

    const result = await apiCall('POST', `/submissions/${currentSubmissionId}/submit`);
    if (result) {
        clearInterval(examTimerInterval);
        showToast('Exam submitted successfully! Waiting for AI grading...', 'success');
        setTimeout(() => showPage('student-dashboard'), 2000);
    }
}

// ==================== STUDENT RESULTS ====================
async function loadStudentResults(submissionId = null) {
    let submission;
    if (submissionId) {
        // Try to get a specific submission
        const mySubmissions = await apiCall('GET', '/submissions/my');
        submission = mySubmissions?.find(s => s.id === submissionId);
    }

    if (!submission) {
        // Show all released results
        const mySubmissions = await apiCall('GET', '/submissions/my');
        const released = mySubmissions?.filter(s => s.status === 'released') || [];

        const container = document.getElementById('all-results-container');
        if (container) {
            container.innerHTML = released.map(s => `
                <div class="col-md-6">
                    <div class="result-summary-card" onclick="viewResult(${s.id})" style="cursor:pointer">
                        <h5>${escapeHtml(s.exam_title || 'Exam')}</h5>
                        <div class="d-flex justify-content-between align-items-center mt-2">
                            <span class="fw-bold fs-4 text-primary">${s.percentage?.toFixed(1)}%</span>
                            <span class="status-badge approved">Graded</span>
                        </div>
                        <div class="mt-2 text-muted small">Score: ${s.total_score?.toFixed(0)}/${s.max_score?.toFixed(0)}</div>
                    </div>
                </div>
            `).join('') || '<p class="col text-muted">No released results yet</p>';
        }
        return;
    }

    viewResult(submission.id);
}

async function viewResult(submissionId) {
    const sub = await apiCall('GET', `/submissions/my/${submissionId}`);
    if (!sub) return;

    // If not released, show waiting message
    if (sub.status !== 'released') {
        showToast('Your result is not yet released by the teacher.', 'info');
        return;
    }

    showPage('student-results');

    // Populate result page
    const answer = sub.answers?.[0];
    const feedback = answer?.ai_feedback;

    setTextContent('result-score-number', Math.round(sub.total_score || 0));
    setTextContent('result-percentage', sub.percentage?.toFixed(1) + '%');
    setTextContent('result-exam-title', sub.exam_title);

    if (feedback) {
        // Correct concepts
        const correctTags = document.getElementById('result-correct-tags');
        if (correctTags) {
            correctTags.innerHTML = (feedback.strengths || []).map(s =>
                `<span class="feedback-tag correct"><i class="fas fa-check"></i>${escapeHtml(s)}</span>`
            ).join('');
        }

        // Missing concepts
        const missingTags = document.getElementById('result-missing-tags');
        if (missingTags) {
            missingTags.innerHTML = (feedback.missing_concepts || []).map(s =>
                `<span class="feedback-tag missing"><i class="fas fa-times"></i>${escapeHtml(s)}</span>`
            ).join('');
        }

        // Suggestions
        const improveTags = document.getElementById('result-improve-tags');
        if (improveTags) {
            improveTags.innerHTML = (feedback.suggestions || []).map(s =>
                `<span class="feedback-tag improve"><i class="fas fa-arrow-up"></i>${escapeHtml(s)}</span>`
            ).join('');
        }

        // AI Comment
        setTextContent('result-ai-comment', feedback.comment || '');

        // Progress bars for criteria
        if (feedback.per_criteria) {
            const breakdownContainer = document.getElementById('result-score-breakdown');
            if (breakdownContainer) {
                breakdownContainer.innerHTML = feedback.per_criteria.map(c => {
                    const pct = ((c.score / c.max_score) * 100).toFixed(0);
                    return `
                        <div class="progress-row">
                            <span class="progress-label">${escapeHtml(c.criteria_name)}</span>
                            <div class="progress-bar-wrapper">
                                <div class="progress-bar-fill" style="width: ${pct}%; background: var(--primary-blue);"></div>
                            </div>
                            <span class="progress-value">${c.score}/${c.max_score}</span>
                        </div>
                    `;
                }).join('');
            }
        }
    }
}

// ==================== PROFILE PAGE ====================
async function loadProfilePage() {
    if (!currentUser) return;

    setTextContent('profile-name', currentUser.full_name);
    setTextContent('profile-email', currentUser.email);
    setTextContent('profile-role', currentUser.role);
    setTextContent('profile-class', currentUser.class_name || currentUser.subject || '-');

    // Set form values
    const nameInput = document.getElementById('profile-name-input');
    if (nameInput) nameInput.value = currentUser.full_name;
}

async function updateProfile(event) {
    event.preventDefault();
    const fullName = document.getElementById('profile-name-input')?.value;

    const result = await apiCall('PUT', `/users/${currentUser.id}`, { full_name: fullName });
    if (result) {
        currentUser.full_name = result.full_name;
        localStorage.setItem('equigrade_user', JSON.stringify(currentUser));
        showToast('Profile updated!', 'success');
        updateUserUI();
    }
}

// ==================== BULK IMPORT ====================
async function importStudentsFile(input) {
    if (!input.files?.length) return;
    const formData = new FormData();
    formData.append('file', input.files[0]);

    const result = await apiCall('POST', '/users/bulk-import', formData, true);
    if (result) {
        showToast(`Imported ${result.created_count} students. Errors: ${result.error_count}`, 'success');
        loadStudentsList();
    }
}

async function importQuestionsFile(input, examId) {
    if (!input.files?.length || !examId) return;
    const formData = new FormData();
    formData.append('file', input.files[0]);

    const result = await apiCall('POST', `/exams/${examId}/questions/import`, formData, true);
    if (result) {
        showToast(`Imported ${result.imported_count} questions`, 'success');
    }
}

function downloadStudentsTemplate() {
    window.open(`${API_BASE}/users/template/students`, '_blank');
}

function downloadQuestionsTemplate() {
    window.open(`${API_BASE}/exams/template/questions`, '_blank');
}

function downloadGradeReport(examId) {
    window.open(`${API_BASE}/submissions/exam/${examId}/report`, '_blank');
}

// ==================== NOTIFICATIONS ====================
function startNotificationPolling() {
    loadNotificationCount();
    notificationInterval = setInterval(loadNotificationCount, 30000); // Every 30 seconds
}

async function loadNotificationCount() {
    const data = await apiCall('GET', '/notifications/unread-count');
    if (data) {
        document.querySelectorAll('.notification-badge').forEach(badge => {
            badge.textContent = data.unread_count || 0;
            badge.style.display = data.unread_count > 0 ? 'flex' : 'none';
        });
    }
}

async function loadNotifications() {
    const notifs = await apiCall('GET', '/notifications/');
    if (!notifs) return;

    const container = document.getElementById('notifications-list');
    if (!container) return;

    container.innerHTML = notifs.map(n => `
        <div class="notification-item ${n.is_read ? '' : 'unread'}" onclick="markNotificationRead(${n.id}, this)">
            <div class="notif-icon ${n.type}"><i class="fas ${getNotifIcon(n.type)}"></i></div>
            <div class="notif-content">
                <div class="notif-title">${escapeHtml(n.title)}</div>
                <div class="notif-message">${escapeHtml(n.message)}</div>
                <div class="notif-time">${formatDate(n.created_at)}</div>
            </div>
        </div>
    `).join('') || '<p class="text-center text-muted p-4">No notifications</p>';
}

async function markNotificationRead(id, element) {
    await apiCall('PUT', `/notifications/${id}/read`);
    element?.classList.remove('unread');
    loadNotificationCount();
}

function getNotifIcon(type) {
    const icons = {
        'exam_published': 'fa-file-alt',
        'submission_received': 'fa-inbox',
        'ai_grading_complete': 'fa-robot',
        'grade_released': 'fa-star',
        'review_needed': 'fa-eye',
        'system': 'fa-bell'
    };
    return icons[type] || 'fa-bell';
}

// ==================== HELPERS ====================
function updateUserUI() {
    if (!currentUser) return;
    document.querySelectorAll('.user-name-display').forEach(el => el.textContent = currentUser.full_name);
    document.querySelectorAll('.user-role-display').forEach(el => el.textContent =
        currentUser.role === 'teacher' ? (currentUser.subject || 'Teacher') : (currentUser.class_name || 'Student'));
    document.querySelectorAll('.user-avatar-img').forEach(img => {
        img.src = `https://ui-avatars.com/api/?name=${encodeURIComponent(currentUser.full_name)}&background=${currentUser.avatar_color || '2563EB'}&color=fff`;
    });
}

function setTextContent(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value ?? '-';
}

function setButtonLoading(btn, isLoading, originalText = null) {
    if (!btn) return;
    if (isLoading) {
        btn.disabled = true;
        btn.dataset.originalHtml = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Loading...';
    } else {
        btn.disabled = false;
        btn.innerHTML = originalText || btn.dataset.originalHtml || 'Submit';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

function formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    const now = new Date();
    const diff = now - d;
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} min ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 172800000) return 'Yesterday';
    return d.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function getStatusClass(status) {
    const classes = {
        'draft': 'pending',
        'submitted': 'pending',
        'ai_grading': 'pending',
        'ai_graded': 'graded',
        'needs_review': 'review',
        'approved': 'approved',
        'released': 'approved',
        'published': 'approved',
        'completed': 'graded',
        'ongoing': 'pending'
    };
    return classes[status] || 'pending';
}

function formatStatus(status) {
    const labels = {
        'draft': 'Draft',
        'submitted': 'Submitted',
        'ai_grading': 'AI Grading...',
        'ai_graded': 'AI Graded',
        'needs_review': 'Needs Review',
        'approved': 'Approved',
        'released': 'Released',
        'published': 'Published',
        'completed': 'Completed',
        'ongoing': 'Ongoing'
    };
    return labels[status] || status;
}

function showToast(message, type = 'info') {
    // Create toast container if not exists
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = 'position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:8px;';
        document.body.appendChild(container);
    }

    const colors = { success: '#10B981', error: '#EF4444', warning: '#F59E0B', info: '#2563EB' };
    const icons = { success: 'check-circle', error: 'times-circle', warning: 'exclamation-triangle', info: 'info-circle' };

    const toast = document.createElement('div');
    toast.style.cssText = `
        background: white; border-left: 4px solid ${colors[type]}; border-radius: 8px;
        padding: 12px 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        display: flex; align-items: center; gap: 10px; min-width: 280px;
        animation: slideIn 0.3s ease; font-size: 14px;
    `;
    toast.innerHTML = `
        <i class="fas fa-${icons[type]}" style="color:${colors[type]}"></i>
        <span style="flex:1">${escapeHtml(message)}</span>
        <button onclick="this.parentElement.remove()" style="border:none;background:none;cursor:pointer;color:#6B7280;font-size:16px;">&times;</button>
    `;
    container.appendChild(toast);

    // Auto remove after 4 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Add toast animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    @keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }
`;
document.head.appendChild(style);
