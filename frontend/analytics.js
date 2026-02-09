const API_BASE = window.location.origin && window.location.origin !== "null" ? window.location.origin : "http://localhost:8000";

const kpiGrid = document.getElementById("kpiGrid");
const highlightGrid = document.getElementById("highlightGrid");
const gradeGrid = document.getElementById("gradeGrid");
const topBooks = document.getElementById("topBooks");
const topStudents = document.getElementById("topStudents");

function createCard(title, value, meta) {
  const card = document.createElement("article");
  card.className = "card";
  card.innerHTML = `
    <h4>${title}</h4>
    <div class="meta">${value}</div>
    ${meta ? `<div class="reason">${meta}</div>` : ""}
  `;
  return card;
}

function countBy(items, keyFn) {
  return items.reduce((acc, item) => {
    const key = keyFn(item);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function topEntries(map, limit = 5) {
  return Object.entries(map)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
}

function safeNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

async function loadData() {
  const [catalogRes, studentRes, loanRes] = await Promise.all([
    fetch(`${API_BASE}/catalog`),
    fetch(`${API_BASE}/students`),
    fetch(`${API_BASE}/loans`),
  ]);

  const catalog = await catalogRes.json();
  const students = await studentRes.json();
  const loans = await loanRes.json();

  return { catalog, students, loans };
}

function renderKpis({ catalog, students, loans }) {
  const availabilityCounts = countBy(catalog, (b) => b.availability || "Unknown");
  const activeLoans = loans.filter((loan) => !loan.return_date).length;

  kpiGrid.appendChild(createCard("Total Books", catalog.length, "Catalog size"));
  kpiGrid.appendChild(
    createCard("Available Now", availabilityCounts["Available"] || 0, "Ready for checkout")
  );
  kpiGrid.appendChild(
    createCard("Checked Out", availabilityCounts["Checked Out"] || 0, "Currently borrowed")
  );
  kpiGrid.appendChild(
    createCard("Active Loans", activeLoans, "Return date not set")
  );
  kpiGrid.appendChild(createCard("Students", students.length, "Profiles on file"));
}

function renderHighlights({ catalog, students, loans }) {
  const genres = countBy(catalog, (b) => b.genre || "Unknown");
  const topGenre = topEntries(genres, 1)[0];

  const statusCounts = countBy(students, (s) => s.account_status || "Unknown");
  const activeStudents = statusCounts["Active"] || 0;
  const avgItems =
    students.reduce((sum, s) => sum + safeNumber(s.items_checkedout), 0) /
    Math.max(students.length, 1);

  const renewalAvg =
    loans.reduce((sum, l) => sum + safeNumber(l.renewals), 0) /
    Math.max(loans.length, 1);

  highlightGrid.appendChild(
    createCard(
      "Top Genre",
      topGenre ? `${topGenre[0]} (${topGenre[1]})` : "N/A",
      "Most common in catalog"
    )
  );
  highlightGrid.appendChild(
    createCard("Active Accounts", activeStudents, `${statusCounts["Inactive"] || 0} inactive`)
  );
  highlightGrid.appendChild(
    createCard("Avg Items Checked Out", avgItems.toFixed(2), "Per student")
  );
  highlightGrid.appendChild(
    createCard("Avg Renewals", renewalAvg.toFixed(2), "Per loan")
  );
}

function renderGradeBorrowing({ students, loans }) {
  const gradeCounts = countBy(loans, (l) => l.grade || "Unknown");
  const gradeEntries = Object.entries(gradeCounts).sort((a, b) => Number(a[0]) - Number(b[0]));

  gradeEntries.forEach(([grade, count]) => {
    const studentCount = students.filter((s) => s.grade === grade).length;
    const perStudent = studentCount ? (count / studentCount).toFixed(2) : "0.00";
    gradeGrid.appendChild(
      createCard(`Grade ${grade}`, `${count} loans`, `${perStudent} loans/student`)
    );
  });
}

function renderTopBooks({ catalog, loans }) {
  const loanCounts = countBy(loans, (l) => l.book_id);
  topEntries(loanCounts, 6).forEach(([bookId, count]) => {
    const book = catalog.find((b) => b.book_id === bookId);
    topBooks.appendChild(
      createCard(
        book ? book.title : bookId,
        `${count} loans`,
        book ? `${book.author} · ${book.genre}` : ""
      )
    );
  });
}

function renderTopStudents({ students, loans }) {
  const loanCounts = countBy(loans, (l) => l.student_id);
  topEntries(loanCounts, 6).forEach(([studentId, count]) => {
    const student = students.find((s) => s.student_id === studentId);
    topStudents.appendChild(
      createCard(
        student ? `${student.student_id} (Grade ${student.grade})` : studentId,
        `${count} loans`,
        student ? student.interests : ""
      )
    );
  });
}

loadData()
  .then((data) => {
    renderKpis(data);
    renderHighlights(data);
    renderGradeBorrowing(data);
    renderTopBooks(data);
    renderTopStudents(data);
  })
  .catch((error) => {
    kpiGrid.innerHTML = `<div class="card">Failed to load analytics: ${error}</div>`;
  });
