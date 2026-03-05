const API_BASE = window.location.origin && window.location.origin !== "null" ? window.location.origin : "http://localhost:8000";

const studentSelect = document.getElementById("feedbackStudent");
const bookSelect = document.getElementById("feedbackBook");
const ratingSelect = document.getElementById("feedbackRating");
const commentInput = document.getElementById("feedbackComment");
const submitButton = document.getElementById("submitFeedback");
const refreshButton = document.getElementById("refreshInsights");
const boostButton = document.getElementById("boostRecommendations");
const insights = document.getElementById("feedbackInsights");
const recommendations = document.getElementById("feedbackRecommendations");

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

async function loadBooks() {
  const response = await fetch(`${API_BASE}/catalog`);
  const books = await response.json();
  bookSelect.innerHTML = "";
  books.forEach((book) => {
    const option = document.createElement("option");
    option.value = book.book_id;
    option.textContent = `${book.title} (${book.book_id})`;
    bookSelect.appendChild(option);
  });
}

function renderCardList(title, items, formatter) {
  const card = document.createElement("article");
  card.className = "card";
  card.innerHTML = `<h4>${title}</h4>`;
  if (!items.length) {
    card.innerHTML += `<div class="meta">No data yet.</div>`;
    return card;
  }
  items.forEach((item) => {
    const line = document.createElement("div");
    line.className = "meta";
    line.textContent = formatter(item);
    card.appendChild(line);
  });
  return card;
}

async function submitFeedback() {
  const payload = {
    student_id: studentSelect.value,
    book_id: bookSelect.value,
    rating: Number(ratingSelect.value),
    comment: commentInput.value.trim() || null,
  };
  try {
    const response = await fetch(`${API_BASE}/agents/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Feedback failed");
    }
    commentInput.value = "";
    await refreshInsights();
  } catch (error) {
    insights.innerHTML = `<div class="card">Error: ${error.message}</div>`;
  }
}

async function refreshInsights() {
  insights.innerHTML = "";
  const response = await fetch(`${API_BASE}/agents/feedback/insights`);
  const data = await response.json();
  insights.appendChild(
    renderCardList("Top rated titles", data.top_rated || [], (item) => {
      return `${item.title} · avg ${item.avg_rating} (${item.count} ratings)`;
    })
  );
  insights.appendChild(
    renderCardList("Genre sentiment", data.genre_sentiment || [], (item) => {
      return `${item.genre} · avg ${item.avg_rating} (${item.count} ratings)`;
    })
  );
  insights.appendChild(
    renderCardList("Recent feedback", data.recent_feedback || [], (item) => {
      return `${item.book?.title || item.book_id} · ${item.rating}/5`;
    })
  );
}

async function loadBoostedRecommendations() {
  recommendations.innerHTML = "";
  const studentId = studentSelect.value;
  if (!studentId) return;
  const response = await fetch(
    `${API_BASE}/agents/feedback/recommendations?student_id=${studentId}&k=5`
  );
  if (!response.ok) {
    recommendations.innerHTML = `<div class="card">Failed to load recommendations.</div>`;
    return;
  }
  const data = await response.json();
  const card = document.createElement("article");
  card.className = "card";
  card.innerHTML = `<h4>Boosted recommendations for ${studentId}</h4>`;
  data.recommendations.forEach((rec) => {
    const line = document.createElement("div");
    line.className = "meta";
    const ratingNote = rec.avg_rating ? `avg ${rec.avg_rating}` : "no ratings yet";
    line.textContent = `${rec.book.title} · score ${rec.score} · ${ratingNote}`;
    card.appendChild(line);
  });
  recommendations.appendChild(card);
}

submitButton.addEventListener("click", submitFeedback);
refreshButton.addEventListener("click", refreshInsights);
boostButton.addEventListener("click", loadBoostedRecommendations);

Promise.all([loadStudents(), loadBooks()])
  .then(refreshInsights)
  .catch((error) => {
    insights.innerHTML = `<div class="card">Failed to load data: ${error.message}</div>`;
  });
