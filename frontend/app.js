const API_BASE = "http://localhost:8000";

const studentSelect = document.getElementById("studentSelect");
const countInput = document.getElementById("countInput");
const runButton = document.getElementById("runButton");
const results = document.getElementById("results");

async function loadStudents() {
  const response = await fetch(`${API_BASE}/students`);
  const students = await response.json();
  studentSelect.innerHTML = "";
  students.forEach((student) => {
    const option = document.createElement("option");
    option.value = student.student_id;
    option.textContent = `${student.student_id} (Grade ${student.grade})`;
    studentSelect.appendChild(option);
  });
}

function renderCards(recommendations) {
  results.innerHTML = "";
  recommendations.forEach((rec) => {
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      <h4>${rec.book.title}</h4>
      <div class="meta">${rec.book.author} · ${rec.book.genre} · Level ${rec.book.reading_level}</div>
      <div class="reason">${rec.reason}</div>
    `;
    results.appendChild(card);
  });
}

async function runRecommendation() {
  const studentId = studentSelect.value;
  const count = Number(countInput.value || 5);
  const response = await fetch(
    `${API_BASE}/recommendations?student_id=${studentId}&k=${count}`
  );
  const data = await response.json();
  renderCards(data.recommendations);
}

runButton.addEventListener("click", () => {
  runRecommendation();
});

loadStudents().catch((error) => {
  results.innerHTML = `<div class="card">Failed to load students: ${error}</div>`;
});
