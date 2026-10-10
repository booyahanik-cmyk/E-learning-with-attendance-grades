/**
 * ChronosClass - Grade Management System
 * Client-side Controller & Data Layer
 */

// Semester Dataset
const ACADEMIC_DATA = {
  1: {
    semester: 1,
    sgpa: "8.42",
    totalSubjects: 5,
    status: "PASS",
    totalCredits: 18,
    stampText: "SEM 1",
    subjects: [
      { code: "CS101", name: "Programming Fundamentals", credits: 4, internal: 18, external: 62, total: 80, grade: "A", gradePoint: "9.0" },
      { code: "CS102", digitalLogic: true, name: "Digital Logic Design", credits: 4, internal: 16, external: 54, total: 70, grade: "B+", gradePoint: "8.0" },
      { code: "CS103", name: "Computer Organization", credits: 4, internal: 20, external: 68, total: 88, grade: "A+", gradePoint: "10.0" },
      { code: "MA101", name: "Engineering Mathematics", credits: 4, internal: 17, external: 58, total: 75, grade: "A", gradePoint: "9.0" },
      { code: "HS101", name: "Communication Skills", credits: 2, internal: 19, external: 66, total: 85, grade: "A+", gradePoint: "10.0" }
    ]
  },
  2: {
    semester: 2,
    sgpa: "8.75",
    totalSubjects: 5,
    status: "PASS",
    totalCredits: 20,
    stampText: "SEM 2",
    subjects: [
      { code: "CS201", name: "Data Structures & Algorithms", credits: 4, internal: 19, external: 65, total: 84, grade: "A+", gradePoint: "10.0" },
      { code: "CS202", name: "Object Oriented Programming", credits: 4, internal: 18, external: 60, total: 78, grade: "A", gradePoint: "9.0" },
      { code: "MA201", name: "Discrete Mathematics", credits: 4, internal: 17, external: 56, total: 73, grade: "B+", gradePoint: "8.0" },
      { code: "EC201", name: "Basic Electronic Circuits", credits: 4, internal: 18, external: 64, total: 82, grade: "A", gradePoint: "9.0" },
      { code: "EV201", name: "Environmental Sciences", credits: 4, internal: 20, external: 67, total: 87, grade: "A+", gradePoint: "10.0" }
    ]
  },
  3: {
    semester: 3,
    sgpa: "8.60",
    totalSubjects: 5,
    status: "PASS",
    totalCredits: 21,
    stampText: "SEM 3",
    subjects: [
      { code: "CS301", name: "Database Management Systems", credits: 4, internal: 19, external: 63, total: 82, grade: "A", gradePoint: "9.0" },
      { code: "CS302", name: "Operating Systems", credits: 4, internal: 18, external: 61, total: 79, grade: "A", gradePoint: "9.0" },
      { code: "CS303", name: "Design & Analysis of Algorithms", credits: 4, internal: 17, external: 59, total: 76, grade: "A", gradePoint: "9.0" },
      { code: "MA301", name: "Probability & Statistics", credits: 4, internal: 16, external: 55, total: 71, grade: "B+", gradePoint: "8.0" },
      { code: "CS304", name: "Software Engineering", credits: 5, internal: 20, external: 70, total: 90, grade: "A+", gradePoint: "10.0" }
    ]
  },
  4: {
    semester: 4,
    sgpa: "8.90",
    totalSubjects: 5,
    status: "PASS",
    totalCredits: 22,
    stampText: "SEM 4",
    subjects: [
      { code: "CS401", name: "Computer Networks", credits: 4, internal: 20, external: 67, total: 87, grade: "A+", gradePoint: "10.0" },
      { code: "CS402", name: "Theory of Computation", credits: 4, internal: 18, external: 62, total: 80, grade: "A", gradePoint: "9.0" },
      { code: "CS403", name: "Web Technologies", credits: 4, internal: 19, external: 68, total: 87, grade: "A+", gradePoint: "10.0" },
      { code: "CS404", name: "Artificial Intelligence", credits: 5, internal: 19, external: 65, total: 84, grade: "A+", gradePoint: "10.0" },
      { code: "HS401", name: "Engineering Economics", credits: 5, internal: 17, external: 58, total: 75, grade: "A", gradePoint: "9.0" }
    ]
  }
};

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const semesterSelect = document.getElementById("semester-select");
  const valSemester = document.getElementById("val-semester");
  const valSgpa = document.getElementById("val-sgpa");
  const valSubjects = document.getElementById("val-subjects");
  const valStatus = document.getElementById("val-status");
  const semStamp = document.getElementById("sem-stamp");
  const summarySgpa = document.getElementById("summary-sgpa");
  const summaryCredits = document.getElementById("summary-credits");
  const gradesTbody = document.getElementById("grades-tbody");
  const pageEyebrow = document.getElementById("page-eyebrow");

  // Modals & Buttons
  const modalBackdrop = document.getElementById("modal-backdrop");
  const modalTitle = document.getElementById("modal-title");
  const modalContentArea = document.getElementById("modal-content-area");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const modalCancelBtn = document.getElementById("modal-cancel-btn");
  const modalPrintBtn = document.getElementById("modal-print-btn");

  const actionReportCard = document.getElementById("action-report-card");
  const actionDownloadPdf = document.getElementById("action-download-pdf");
  const actionGradeAnalysis = document.getElementById("action-grade-analysis");
  const btnSignout = document.getElementById("btn-signout");

  // Render Semester Data
  function renderSemester(semNumber) {
    const data = ACADEMIC_DATA[semNumber];
    if (!data) return;

    // Update Eyebrow & Stamp
    pageEyebrow.innerHTML = `<span class="eyebrow-dash">—</span> SEMESTER ${data.semester} · GRADE MANAGEMENT`;
    semStamp.innerHTML = `<span class="stamp-inner-text">${data.stampText}</span>`;

    // Update Top Stat Cards
    valSemester.textContent = data.semester;
    valSgpa.textContent = data.sgpa;
    valSubjects.textContent = data.totalSubjects;
    valStatus.textContent = data.status;

    // Update Sidebar Summary
    summarySgpa.textContent = data.sgpa;
    summaryCredits.textContent = data.totalCredits;

    // Render Table Rows
    gradesTbody.innerHTML = "";
    data.subjects.forEach(sub => {
      const tr = document.createElement("tr");

      // Badge class
      let pillClass = "grade-pill-a";
      if (sub.grade === "A+") pillClass = "grade-pill-aplus";
      if (sub.grade === "B+") pillClass = "grade-pill-bplus";

      tr.innerHTML = `
        <td class="col-code">${sub.code}</td>
        <td class="col-subject">${sub.name}</td>
        <td class="col-credits">${sub.credits}</td>
        <td class="col-internal">${sub.internal}</td>
        <td class="col-external">${sub.external}</td>
        <td class="col-total">${sub.total}</td>
        <td class="col-grade"><span class="grade-pill ${pillClass}">${sub.grade}</span></td>
        <td class="col-gradepoint">${sub.gradePoint}</td>
      `;
      gradesTbody.appendChild(tr);
    });
  }

  // Toast Notification Helper
  function showToast(message) {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <span>${message}</span>
    `;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(30px)";
      toast.style.transition = "all 0.25s ease";
      setTimeout(() => toast.remove(), 250);
    }, 2800);
  }

  // Modal Display Logic
  function openModal(title, htmlContent) {
    modalTitle.textContent = title;
    modalContentArea.innerHTML = htmlContent;
    modalBackdrop.classList.add("open");
    modalBackdrop.setAttribute("aria-hidden", "false");
  }

  function closeModal() {
    modalBackdrop.classList.remove("open");
    modalBackdrop.setAttribute("aria-hidden", "true");
  }

  // Semester Selector Change Event
  semesterSelect.addEventListener("change", (e) => {
    const sem = parseInt(e.target.value, 10);
    renderSemester(sem);
    showToast(`Loaded grades for Semester ${sem}`);
  });

  // Action 1: View Detailed Report Card
  actionReportCard.addEventListener("click", () => {
    const currentSem = semesterSelect.value;
    const data = ACADEMIC_DATA[currentSem];
    const modalHtml = `
      <div style="font-family: var(--font-sans); color: var(--ink);">
        <div style="display:flex; justify-content:space-between; border-bottom:1px solid #E5DFD2; padding-bottom:12px; margin-bottom:16px;">
          <div>
            <h4 style="font-family:var(--font-serif); font-size:18px; margin:0;">ChronosClass Academic Registry</h4>
            <div style="font-size:12px; color:var(--ink-soft); margin-top:2px;">Student ID: STU001 · Anik Dey</div>
          </div>
          <div style="text-align:right;">
            <span style="font-family:var(--font-mono); font-size:12px; font-weight:600; color:var(--stamp-border); border:1px solid var(--stamp-border); padding:2px 8px; border-radius:3px;">SEM ${currentSem}</span>
          </div>
        </div>
        <table style="width:100%; font-size:12.5px; border-collapse:collapse; margin-bottom:16px;">
          <thead>
            <tr style="background:#25355A; color:#FFF; font-family:var(--font-mono); font-size:11px;">
              <th style="padding:6px 10px; text-align:left;">CODE</th>
              <th style="padding:6px 10px; text-align:left;">SUBJECT</th>
              <th style="padding:6px 10px; text-align:center;">MARKS</th>
              <th style="padding:6px 10px; text-align:center;">GRADE</th>
            </tr>
          </thead>
          <tbody>
            ${data.subjects.map(s => `
              <tr style="border-bottom:1px solid #ECE7D9;">
                <td style="padding:8px 10px; font-family:var(--font-mono);">${s.code}</td>
                <td style="padding:8px 10px;">${s.name}</td>
                <td style="padding:8px 10px; text-align:center; font-family:var(--font-mono);">${s.total}/100</td>
                <td style="padding:8px 10px; text-align:center; font-weight:600; color:var(--grade-badge-ink);">${s.grade}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        <div style="display:flex; justify-content:space-between; background:#F4EFE5; padding:10px 14px; border-radius:4px; font-size:13px;">
          <span><strong>SGPA:</strong> ${data.sgpa} / 10.0</span>
          <span><strong>Total Credits:</strong> ${data.totalCredits}</span>
          <span><strong>Result:</strong> <span style="color:var(--green-pass); font-weight:700;">${data.status}</span></span>
        </div>
      </div>
    `;
    openModal(`Semester ${currentSem} Detailed Report Card`, modalHtml);
  });

  // Action 2: Download Marksheet (PDF)
  actionDownloadPdf.addEventListener("click", () => {
    showToast("Preparing printable marksheet...");
    window.print();
  });

  // Action 3: View Grade Analysis
  actionGradeAnalysis.addEventListener("click", () => {
    const currentSem = semesterSelect.value;
    const data = ACADEMIC_DATA[currentSem];
    const avgScore = (data.subjects.reduce((acc, s) => acc + s.total, 0) / data.subjects.length).toFixed(1);
    const modalHtml = `
      <div style="font-family: var(--font-sans); color: var(--ink);">
        <p style="margin-bottom:14px; font-size:13px; color:var(--ink-soft);">
          Performance breakdown across internal assessments, final examinations, and credit weighting.
        </p>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">
          <div style="background:#FAF8F3; border:1px solid #E5DFD2; padding:12px; border-radius:4px;">
            <span style="font-family:var(--font-mono); font-size:10px; color:var(--ink-muted);">AVERAGE RAW SCORE</span>
            <div style="font-family:var(--font-serif); font-size:24px; font-weight:700; margin-top:4px;">${avgScore}%</div>
          </div>
          <div style="background:#FAF8F3; border:1px solid #E5DFD2; padding:12px; border-radius:4px;">
            <span style="font-family:var(--font-mono); font-size:10px; color:var(--ink-muted);">PERCENTILE ESTIMATE</span>
            <div style="font-family:var(--font-serif); font-size:24px; font-weight:700; color:var(--green-pass); margin-top:4px;">Top 5%</div>
          </div>
        </div>
        <div style="font-size:12.5px; color:var(--ink-soft); line-height:1.6;">
          • Highest subject score: <strong>Computer Organization (${data.subjects.find(s=>s.code==='CS103')?.total || 88}/100)</strong><br>
          • Internal examination average: <strong>18.0 / 20.0 (90%)</strong><br>
          • Academic standing: <strong>Exemplary Honor Roll</strong>
        </div>
      </div>
    `;
    openModal(`Grade Analysis — Semester ${currentSem}`, modalHtml);
  });

  // Modal Close Handlers
  modalCloseBtn.addEventListener("click", closeModal);
  modalCancelBtn.addEventListener("click", closeModal);
  modalBackdrop.addEventListener("click", (e) => {
    if (e.target === modalBackdrop) closeModal();
  });
  modalPrintBtn.addEventListener("click", () => {
    window.print();
  });

  // Sign out Button
  btnSignout.addEventListener("click", () => {
    showToast("Signed out of session STU001.");
  });

  // Initialize
  renderSemester(1);
});
