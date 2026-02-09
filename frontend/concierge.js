const API_BASE = window.location.origin && window.location.origin !== "null" ? window.location.origin : "http://localhost:8000";
const SHARED_STUDENT_KEY = "qvest-student-id";

const studentSelect = document.getElementById("conciergeStudent");
const limitInput = document.getElementById("conciergeLimit");
const availabilityOnly = document.getElementById("conciergeAvailable");
const chatWindow = document.getElementById("conciergeChat");
const chatInput = document.getElementById("conciergeInput");
const sendButton = document.getElementById("conciergeSend");
const results = document.getElementById("conciergeResults");
let lastRecommendations = [];

function addMessage(text, sender = "user") {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${sender}`;
  bubble.textContent = text;
  chatWindow.appendChild(bubble);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function renderCards(recommendations) {
  results.innerHTML = "";
  const studentId = studentSelect.value;
  recommendations.forEach((rec) => {
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      <h4>${rec.book.title}</h4>
      <div class="meta">${rec.book.author} · ${rec.book.genre} · Level ${rec.book.reading_level}</div>
      <div class="reason">${rec.reason} · ${rec.book.availability}</div>
      <div class="feedback-row">
        <span class="meta">Did they like it?</span>
        <button data-rating="5">Loved it</button>
        <button data-rating="1">Not for them</button>
      </div>
      <div class="meta feedback-status"></div>
    `;
    const buttons = card.querySelectorAll("button[data-rating]");
    const status = card.querySelector(".feedback-status");
    buttons.forEach((button) => {
      if (!studentId) {
        button.disabled = true;
      }
      button.addEventListener("click", async () => {
        try {
          await submitFeedback(studentId, rec.book.book_id, Number(button.dataset.rating));
          status.textContent = "Feedback saved.";
          buttons.forEach((btn) => (btn.disabled = true));
        } catch (error) {
          status.textContent = `Error: ${error.message}`;
        }
      });
    });
    results.appendChild(card);
  });
  if (!studentId && recommendations.length) {
    const note = document.createElement("div");
    note.className = "card";
    note.innerHTML = `<div class="meta">Select a student to save feedback.</div>`;
    results.prepend(note);
  }
  lastRecommendations = recommendations;
}

async function submitFeedback(studentId, bookId, rating) {
  const response = await fetch(`${API_BASE}/agents/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      student_id: studentId,
      book_id: bookId,
      rating,
      comment: "concierge",
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Feedback failed");
  }
  return response.json();
}

async function loadStudents() {
  const response = await fetch(`${API_BASE}/students`);
  const students = await response.json();
  studentSelect.innerHTML = `<option value="">No student</option>`;
  students.forEach((student) => {
    const option = document.createElement("option");
    option.value = student.student_id;
    option.textContent = `${student.student_id} (Grade ${student.grade})`;
    studentSelect.appendChild(option);
  });
  const savedId = localStorage.getItem(SHARED_STUDENT_KEY);
  if (savedId) {
    studentSelect.value = savedId;
  }
}

async function sendConcierge() {
  const text = chatInput.value.trim();
  if (!text) return;
  addMessage(text, "user");
  chatInput.value = "";
  const payload = {
    message: text,
    student_id: studentSelect.value || null,
    limit: Number(limitInput.value || 5),
    availability_only: availabilityOnly.checked,
  };

  try {
    const response = await fetch(`${API_BASE}/agents/concierge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Concierge request failed");
    }
    const data = await response.json();
    addMessage(data.reply, "bot");
    renderCards(data.recommendations || []);
  } catch (error) {
    addMessage(`Error: ${error.message}`, "bot");
  }
}

sendButton.addEventListener("click", sendConcierge);
chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") sendConcierge();
});
studentSelect.addEventListener("change", () => {
  const value = studentSelect.value;
  if (value) {
    localStorage.setItem(SHARED_STUDENT_KEY, value);
  } else {
    localStorage.removeItem(SHARED_STUDENT_KEY);
  }
  if (lastRecommendations.length) {
    renderCards(lastRecommendations);
  }
});

addMessage('Try: "Available fantasy for grade 6"', "bot");
addMessage('Try: "Read-alikes for mystery lovers"', "bot");

loadStudents().catch((error) => {
  addMessage(`Failed to load students: ${error.message}`, "bot");
});
