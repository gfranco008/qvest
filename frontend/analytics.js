const API_BASE = window.location.origin && window.location.origin !== "null" ? window.location.origin : "http://localhost:8000";

const kpiGrid = document.getElementById("kpiGrid");
const highlightGrid = document.getElementById("highlightGrid");
const gradeGrid = document.getElementById("gradeGrid");
const topBooks = document.getElementById("topBooks");
const topStudents = document.getElementById("topStudents");
const availabilityChart = document.getElementById("availabilityChart");
const availabilityMeta = document.getElementById("availabilityMeta");
const availabilityLegend = document.getElementById("availabilityLegend");
const loanTrendChart = document.getElementById("loanTrendChart");
const loanTrendMeta = document.getElementById("loanTrendMeta");
const genreChart = document.getElementById("genreChart");
const genreMeta = document.getElementById("genreMeta");

const palette = ["#c17b37", "#3c8a7a", "#c95d63", "#7b8f4a", "#8a5a44"];

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

function renderVisualsSkeleton(message) {
  const fallback = `<div class="meta">${message}</div>`;
  if (availabilityChart) availabilityChart.innerHTML = fallback;
  if (loanTrendChart) loanTrendChart.innerHTML = fallback;
  if (genreChart) genreChart.innerHTML = fallback;
  if (availabilityLegend) availabilityLegend.innerHTML = "";
  if (availabilityMeta) availabilityMeta.textContent = "";
  if (loanTrendMeta) loanTrendMeta.textContent = "";
  if (genreMeta) genreMeta.textContent = "";
}

function createDonutChart(segments, { size = 140, stroke = 16 } = {}) {
  const total = segments.reduce((sum, seg) => sum + seg.value, 0);
  if (!total) {
    return `<div class="meta">No data yet</div>`;
  }
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  const trackColor = "#f0e3d5";

  const circles = segments
    .map((seg) => {
      const length = (seg.value / total) * circumference;
      const dash = `${length} ${circumference - length}`;
      const svg = `
        <circle
          class="donut-seg"
          cx="${size / 2}"
          cy="${size / 2}"
          r="${radius}"
          fill="none"
          stroke="${seg.color}"
          stroke-width="${stroke}"
          stroke-linecap="round"
          stroke-dasharray="${dash}"
          stroke-dashoffset="${-offset}"
        />
      `;
      offset += length;
      return svg;
    })
    .join("");

  return `
    <div class="donut-chart">
      <svg viewBox="0 0 ${size} ${size}">
        <circle
          class="donut-track"
          cx="${size / 2}"
          cy="${size / 2}"
          r="${radius}"
          fill="none"
          stroke="${trackColor}"
          stroke-width="${stroke}"
        />
        ${circles}
        <text x="50%" y="50%" text-anchor="middle" dy="6" class="donut-label" fill="#1f1c1b">${total}</text>
      </svg>
    </div>
  `;
}

function createLineChart(points, { width = 260, height = 140, padding = 16 } = {}) {
  if (!points.length) {
    return `<div class="meta">No trend data yet</div>`;
  }
  const values = points.map((p) => p.value);
  const max = Math.max(...values, 1);
  const usableWidth = width - padding * 2;
  const usableHeight = height - padding * 2;
  const step = points.length > 1 ? usableWidth / (points.length - 1) : 0;

  const coords = points.map((point, index) => {
    const x = padding + step * index;
    const y = height - padding - (point.value / max) * usableHeight;
    return { ...point, x, y };
  });

  const line = coords.map((point) => `${point.x},${point.y}`).join(" ");
  const area = `M ${coords[0].x} ${height - padding} L ${line.replace(/,/g, " ")} L ${
    coords[coords.length - 1].x
  } ${height - padding} Z`;

  const dots = coords
    .map(
      (point) =>
        `<circle class="trend-dot" cx="${point.x}" cy="${point.y}" r="4" fill="#c17b37" />`
    )
    .join("");

  const labels = coords
    .map(
      (point) =>
        `<text x="${point.x}" y="${height - 4}" text-anchor="middle" font-size="10" fill="#5f5a55">${point.label}</text>`
    )
    .join("");

  return `
    <div class="trend-chart">
      <svg viewBox="0 0 ${width} ${height}">
        <path class="trend-area" d="${area}" fill="rgba(193, 123, 55, 0.18)" />
        <polyline
          class="trend-line"
          points="${line}"
          fill="none"
          stroke="#8d5424"
          stroke-width="3"
          stroke-linecap="round"
        />
        ${dots}
        ${labels}
      </svg>
    </div>
  `;
}

function createBarStack(items) {
  if (!items.length) {
    return `<div class="meta">No data yet</div>`;
  }
  const max = Math.max(...items.map((item) => item.value), 1);
  return `
    <div class="bar-stack">
      ${items
        .map((item) => {
          const pct = (item.value / max) * 100;
          return `
            <div class="bar-row">
              <div class="bar-row-header">
                <span>${item.label}</span>
                <span>${item.value}</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" style="width: ${pct}%; background: ${item.color};"></div>
              </div>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
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

function renderVisuals({ catalog, loans }) {
  if (!availabilityChart || !loanTrendChart || !genreChart) {
    return;
  }
  const availabilityCounts = countBy(catalog, (b) => b.availability || "Unknown");
  const available = availabilityCounts["Available"] || 0;
  const checkedOut = availabilityCounts["Checked Out"] || 0;
  const onHold = availabilityCounts["On Hold"] || 0;
  const other = Math.max(
    catalog.length - available - checkedOut - onHold,
    0
  );

  const availabilitySegments = [
    { label: "Available", value: available, color: palette[0] },
    { label: "Checked Out", value: checkedOut, color: palette[1] },
    { label: "On Hold", value: onHold, color: palette[2] },
    { label: "Other", value: other, color: palette[3] },
  ];

  availabilityChart.innerHTML = createDonutChart(availabilitySegments);
  if (availabilityLegend) {
    availabilityLegend.innerHTML = availabilitySegments
      .filter((seg) => seg.value > 0)
      .map(
        (seg) => `
          <span class="legend-item">
            <span class="legend-swatch" style="background: ${seg.color};"></span>
            ${seg.label} (${seg.value})
          </span>
        `
      )
      .join("");
  }
  availabilityMeta.textContent = `${available} available · ${checkedOut} checked out · ${onHold} on hold`;

  const loansByMonth = loans.reduce((acc, loan) => {
    if (!loan.checkout_date) return acc;
    const date = new Date(loan.checkout_date);
    if (Number.isNaN(date.getTime())) return acc;
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});

  const monthKeys = Object.keys(loansByMonth).sort();
  const lastKeys = monthKeys.slice(-8);
  const trendPoints = lastKeys.map((key) => {
    const [, month] = key.split("-");
    const label = new Date(`${key}-01`).toLocaleString("en-US", { month: "short" });
    return { label, value: loansByMonth[key] };
  });

  loanTrendChart.innerHTML = createLineChart(trendPoints);
  const latest = trendPoints[trendPoints.length - 1];
  const previous = trendPoints[trendPoints.length - 2];
  if (latest && previous) {
    const delta = latest.value - previous.value;
    loanTrendMeta.textContent = `${latest.label}: ${latest.value} loans (${delta >= 0 ? "+" : ""}${delta} vs prior)`;
  } else if (latest) {
    loanTrendMeta.textContent = `${latest.label}: ${latest.value} loans`;
  } else {
    loanTrendMeta.textContent = "No recent loans tracked.";
  }

  const genreCounts = countBy(catalog, (b) => b.genre || "Unknown");
  const topGenres = topEntries(genreCounts, 5).map(([genre, count], index) => ({
    label: genre,
    value: count,
    color: palette[index % palette.length],
  }));

  genreChart.innerHTML = createBarStack(topGenres);
  const totalTop = topGenres.reduce((sum, item) => sum + item.value, 0);
  genreMeta.textContent = `${totalTop} titles across top genres`;
}

function initAnalytics() {
  renderVisualsSkeleton("Loading visuals...");
  loadData()
    .then((data) => {
      renderKpis(data);
      renderVisuals(data);
      renderHighlights(data);
      renderGradeBorrowing(data);
      renderTopBooks(data);
      renderTopStudents(data);
    })
    .catch((error) => {
      kpiGrid.innerHTML = `<div class="card">Failed to load analytics: ${error}</div>`;
      renderVisualsSkeleton("Analytics data unavailable.");
    });
}

initAnalytics();
