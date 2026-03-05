const API_BASE = window.location.origin && window.location.origin !== "null" ? window.location.origin : "http://localhost:8000";

const studentSelect = document.getElementById("onboardingStudent");
const interestsInput = document.getElementById("onboardingInterests");
const genresInput = document.getElementById("onboardingGenres");
const levelInput = document.getElementById("onboardingLevel");
const goalsInput = document.getElementById("onboardingGoals");
const avoidInput = document.getElementById("onboardingAvoid");
const notesInput = document.getElementById("onboardingNotes");
const saveButton = document.getElementById("onboardingSave");
const summary = document.getElementById("onboardingSummary");

function renderSummary(data) {
  summary.innerHTML = "";
  const card = document.createElement("article");
  card.className = "card";
  if (!data) {
    card.textContent = "Select a student to view onboarding details.";
    summary.appendChild(card);
    return;
  }
  const student = data.student;
  const profile = data.profile || {};
  card.innerHTML = `
    <h4>${student.student_id} · Grade ${student.grade}</h4>
    <div class="meta">Reading level: ${profile.reading_level || student.reading_level || "n/a"}</div>
    <div class="reason">
      Interests: ${profile.interests || student.interests || "n/a"}<br />
      Preferred genres: ${profile.preferred_genres || student.preferred_genres || "n/a"}<br />
      Goals: ${profile.goals || "n/a"}<br />
      Avoid: ${profile.avoid_topics || "n/a"}<br />
      Notes: ${profile.notes || student.notes || "n/a"}
    </div>
  `;
  summary.appendChild(card);
}

function fillForm(profile) {
  interestsInput.value = profile?.interests || "";
  genresInput.value = profile?.preferred_genres || "";
  levelInput.value = profile?.reading_level || "";
  goalsInput.value = profile?.goals || "";
  avoidInput.value = profile?.avoid_topics || "";
  notesInput.value = profile?.notes || "";
}

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

async function fetchProfile(studentId) {
  const response = await fetch(`${API_BASE}/agents/onboarding/${studentId}`);
  if (!response.ok) {
    throw new Error("Unable to load onboarding profile");
  }
  return response.json();
}

async function refreshProfile() {
  const studentId = studentSelect.value;
  if (!studentId) return;
  try {
    const data = await fetchProfile(studentId);
    fillForm(data.profile);
    renderSummary(data);
  } catch (error) {
    renderSummary(null);
  }
}

async function saveProfile() {
  const payload = {
    student_id: studentSelect.value,
    interests: interestsInput.value.trim() || null,
    preferred_genres: genresInput.value.trim() || null,
    reading_level: levelInput.value.trim() || null,
    goals: goalsInput.value.trim() || null,
    avoid_topics: avoidInput.value.trim() || null,
    notes: notesInput.value.trim() || null,
  };
  try {
    const response = await fetch(`${API_BASE}/agents/onboarding`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Failed to save profile");
    }
    const data = await response.json();
    fillForm(data.profile);
    renderSummary(data);
  } catch (error) {
    summary.innerHTML = `<div class="card">Error: ${error.message}</div>`;
  }
}

studentSelect.addEventListener("change", refreshProfile);
saveButton.addEventListener("click", saveProfile);

loadStudents()
  .then(refreshProfile)
  .catch((error) => {
    summary.innerHTML = `<div class="card">Failed to load students: ${error.message}</div>`;
  });
