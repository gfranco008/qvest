const API_BASE = window.location.origin && window.location.origin !== "null" ? window.location.origin : "http://localhost:8000";

const studentSelect = document.getElementById("holdStudent");
const genreSelect = document.getElementById("holdGenre");
const availabilitySelect = document.getElementById("holdAvailability");
const searchButton = document.getElementById("holdSearch");
const results = document.getElementById("holdResults");
const queue = document.getElementById("holdQueue");

let catalog = [];

function renderBooks(items) {
  results.innerHTML = "";
  items.forEach((book) => {
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      <h4>${book.title}</h4>
      <div class="meta">${book.author} · ${book.genre} · Level ${book.reading_level}</div>
      <div class="reason">${book.audience} · ${book.format} · ${book.availability}</div>
      <button data-book="${book.book_id}">Place hold</button>
    `;
    const button = card.querySelector("button");
    button.addEventListener("click", () => placeHold(book.book_id));
    results.appendChild(card);
  });
}

function renderHolds(items) {
  queue.innerHTML = "";
  if (!items.length) {
    queue.innerHTML = `<div class="card">No holds yet for this student.</div>`;
    return;
  }
  items.forEach((hold) => {
    const card = document.createElement("article");
    card.className = "card";
    const book = hold.book || {};
    card.innerHTML = `
      <h4>${book.title || hold.book_id}</h4>
      <div class="meta">${book.author || "Unknown"} · ${book.genre || "n/a"}</div>
      <div class="reason">Status: ${hold.status} · Expires ${hold.expires_at || "n/a"}</div>
      <button data-hold="${hold.hold_id}">Cancel hold</button>
    `;
    const button = card.querySelector("button");
    button.addEventListener("click", () => cancelHold(hold.hold_id));
    queue.appendChild(card);
  });
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

async function loadCatalog() {
  const response = await fetch(`${API_BASE}/catalog`);
  catalog = await response.json();
  const genres = Array.from(new Set(catalog.map((book) => book.genre))).sort();
  genreSelect.innerHTML = `<option value="">All</option>`;
  genres.forEach((genre) => {
    const option = document.createElement("option");
    option.value = genre;
    option.textContent = genre;
    genreSelect.appendChild(option);
  });
}

async function searchCatalog() {
  const params = new URLSearchParams();
  if (genreSelect.value) params.set("genre", genreSelect.value);
  if (availabilitySelect.value) params.set("availability", availabilitySelect.value);
  const response = await fetch(`${API_BASE}/agents/availability?${params.toString()}`);
  const data = await response.json();
  renderBooks(data.results || []);
}

async function loadHolds() {
  const studentId = studentSelect.value;
  if (!studentId) return;
  const response = await fetch(`${API_BASE}/agents/holds?student_id=${studentId}`);
  const data = await response.json();
  renderHolds(data.holds || []);
}

async function placeHold(bookId) {
  const payload = {
    student_id: studentSelect.value,
    book_id: bookId,
  };
  try {
    const response = await fetch(`${API_BASE}/agents/holds`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Hold request failed");
    }
    await response.json();
    await loadHolds();
  } catch (error) {
    queue.innerHTML = `<div class="card">Error: ${error.message}</div>`;
  }
}

async function cancelHold(holdId) {
  try {
    const response = await fetch(`${API_BASE}/agents/holds/${holdId}/cancel`, {
      method: "POST",
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Cancel failed");
    }
    await response.json();
    await loadHolds();
  } catch (error) {
    queue.innerHTML = `<div class="card">Error: ${error.message}</div>`;
  }
}

studentSelect.addEventListener("change", () => {
  loadHolds();
});
searchButton.addEventListener("click", searchCatalog);

Promise.all([loadStudents(), loadCatalog()])
  .then(() => {
    searchCatalog();
    loadHolds();
  })
  .catch((error) => {
    results.innerHTML = `<div class="card">Failed to load catalog: ${error.message}</div>`;
  });
