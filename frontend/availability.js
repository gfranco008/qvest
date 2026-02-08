const API_BASE = "http://localhost:8000";

const results = document.getElementById("availableResults");
const genreSelect = document.getElementById("genreSelect");
const availabilitySelect = document.getElementById("availabilitySelect");
let catalog = [];

function renderBooks(items) {
  results.innerHTML = "";
  items.forEach((book) => {
    const card = document.createElement("article");
    card.className = "card";
    const unavailable = book.availability !== "Available";
    card.innerHTML = `
      <h4 class="card-title">
        ${book.title}
        ${unavailable ? '<span class="badge-unavailable" title="Not available">x</span>' : ""}
      </h4>
      <div class="meta">${book.author} · ${book.genre} · Level ${book.reading_level}</div>
      <div class="reason">
        ${book.audience} · ${book.format} · ${book.availability}
      </div>
    `;
    results.appendChild(card);
  });
}

function updateFilterOptions(items) {
  const genres = Array.from(new Set(items.map((b) => b.genre))).sort();
  genreSelect.innerHTML = '<option value="">All</option>';
  genres.forEach((genre) => {
    const option = document.createElement("option");
    option.value = genre;
    option.textContent = genre;
    genreSelect.appendChild(option);
  });
}

function applyFilter() {
  const selected = genreSelect.value;
  const availability = availabilitySelect.value;
  let filtered = catalog;
  if (availability) {
    filtered = filtered.filter((b) => b.availability === availability);
  }
  if (selected) {
    filtered = filtered.filter((b) => b.genre === selected);
  }
  renderBooks(filtered);
}

async function loadAvailable() {
  const response = await fetch(`${API_BASE}/catalog`);
  const items = await response.json();
  catalog = items;
  updateFilterOptions(catalog);
  applyFilter();
}

genreSelect.addEventListener("change", applyFilter);
availabilitySelect.addEventListener("change", applyFilter);

loadAvailable().catch((error) => {
  results.innerHTML = `<div class="card">Failed to load catalog: ${error}</div>`;
});
