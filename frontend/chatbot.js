const chatWindow = document.getElementById("chatWindow");
const chatInput = document.getElementById("chatInput");
const sendButton = document.getElementById("sendButton");
const resetButton = document.getElementById("resetButton");
const recommendations = document.getElementById("chatRecommendations");
const studentStatus = document.getElementById("chatStudentStatus");
const pageSelect = document.getElementById("pageSelect");

const API_BASE = window.location.origin && window.location.origin !== "null" ? window.location.origin : "http://localhost:8000";
const CHAT_SESSION_KEY = "qvest-chat-session";
const SHARED_STUDENT_KEY = "qvest-student-id";
const LEGACY_CHAT_STUDENT_KEY = "qvest-chat-student-id";
let chatSessionId = localStorage.getItem(CHAT_SESSION_KEY);
let chatStudentId =
  localStorage.getItem(SHARED_STUDENT_KEY) ||
  localStorage.getItem(LEGACY_CHAT_STUDENT_KEY);
if (chatStudentId && !localStorage.getItem(SHARED_STUDENT_KEY)) {
  localStorage.setItem(SHARED_STUDENT_KEY, chatStudentId);
}
let lastRecommendations = [];
const starterTips = [
  "Try: \"Suggest books for a grade 5 student who likes mystery.\"",
  "Try: \"What are good read-alikes for The Brave Map?\"",
  "Try: \"Give me a short pitch for a library mystery book.\"",
];

if (pageSelect) {
  const current = window.location.pathname.split("/").pop() || "chatbot.html";
  pageSelect.value = current;
  pageSelect.addEventListener("change", () => {
    window.location.href = pageSelect.value;
  });
}

function showStarterTips() {
  starterTips.forEach((tip) => addMessage(tip, "bot"));
}

function addMessage(text, sender = "user") {
  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${sender}`;
  bubble.textContent = text;
  chatWindow.appendChild(bubble);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

function setSessionId(value) {
  chatSessionId = value;
  if (chatSessionId) {
    localStorage.setItem(CHAT_SESSION_KEY, chatSessionId);
  }
}

function setStudentId(value) {
  chatStudentId = value;
  if (chatStudentId) {
    localStorage.setItem(SHARED_STUDENT_KEY, chatStudentId);
    localStorage.removeItem(LEGACY_CHAT_STUDENT_KEY);
  }
  updateStudentStatus();
}

function extractStudentId(text) {
  const match = text.match(/\bS\d{4}\b/i);
  return match ? match[0].toUpperCase() : null;
}

function generateSessionId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `CHAT-${crypto.randomUUID().slice(0, 12)}`;
  }
  return `CHAT-${Math.random().toString(16).slice(2, 14)}`;
}

function ensureSessionId() {
  if (!chatSessionId) {
    setSessionId(generateSessionId());
  }
}

function updateStudentStatus() {
  if (!studentStatus) return;
  studentStatus.textContent = chatStudentId
    ? `Using student: ${chatStudentId}`
    : "Using student: none";
}

async function fetchResponse(prompt) {
  ensureSessionId();
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: prompt,
      session_id: chatSessionId,
      student_id: chatStudentId || null,
    }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Chat request failed");
  }

  const data = await response.json();
  if (data.session_id && data.session_id !== chatSessionId) {
    setSessionId(data.session_id);
  }
  if (data.student_id) {
    setStudentId(data.student_id);
  }
  lastRecommendations = data.recommendations || [];
  renderRecommendations(lastRecommendations);
  return data.reply;
}

function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;
  const detected = extractStudentId(text);
  if (detected) {
    setStudentId(detected);
  }
  addMessage(text, "user");
  chatInput.value = "";
  fetchResponse(text)
    .then((reply) => addMessage(reply, "bot"))
    .catch((error) => {
      addMessage(`Error: ${error.message}`, "bot");
    });
}

async function submitFeedback(studentId, bookId, rating) {
  const response = await fetch(`${API_BASE}/agents/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      student_id: studentId,
      book_id: bookId,
      rating,
      comment: "chatbot",
    }),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || "Feedback failed");
  }
  return response.json();
}

function renderRecommendations(items) {
  recommendations.innerHTML = "";
  if (!items || !items.length) return;

  if (!chatStudentId) {
    const promptCard = document.createElement("article");
    promptCard.className = "card";
    promptCard.innerHTML = `
      <h4>Save feedback</h4>
      <div class="meta">Enter a student ID like S0001 to record feedback.</div>
      <div class="feedback-row">
        <input id="chatStudentInput" type="text" placeholder="S0001" />
        <button id="chatStudentSave">Use ID</button>
      </div>
    `;
    recommendations.appendChild(promptCard);
    const saveButton = promptCard.querySelector("#chatStudentSave");
    saveButton.addEventListener("click", () => {
      const input = promptCard.querySelector("#chatStudentInput");
      const value = input.value.trim();
      if (value) {
        setStudentId(value);
        renderRecommendations(lastRecommendations);
      }
    });
  }

  items.forEach((rec) => {
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      <h4>${rec.book.title}</h4>
      <div class="meta">${rec.book.author} · ${rec.book.genre} · Level ${rec.book.reading_level}</div>
      <div class="reason">${rec.reason}</div>
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
      if (!chatStudentId) {
        button.disabled = true;
      }
      button.addEventListener("click", async () => {
        try {
          await submitFeedback(chatStudentId, rec.book.book_id, Number(button.dataset.rating));
          status.textContent = "Feedback saved.";
          buttons.forEach((btn) => (btn.disabled = true));
        } catch (error) {
          status.textContent = `Error: ${error.message}`;
        }
      });
    });
    recommendations.appendChild(card);
  });
}

sendButton.addEventListener("click", sendMessage);
chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") sendMessage();
});
resetButton.addEventListener("click", () => {
  chatSessionId = null;
  localStorage.removeItem(CHAT_SESSION_KEY);
  chatStudentId = null;
  localStorage.removeItem(SHARED_STUDENT_KEY);
  localStorage.removeItem(LEGACY_CHAT_STUDENT_KEY);
  updateStudentStatus();
  lastRecommendations = [];
  chatWindow.innerHTML = "";
  recommendations.innerHTML = "";
  showStarterTips();
  chatInput.focus();
});

showStarterTips();
updateStudentStatus();
