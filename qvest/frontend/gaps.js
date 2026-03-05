const API_BASE = window.location.origin && window.location.origin !== "null" ? window.location.origin : "http://localhost:8000";

const runButton = document.getElementById("runGapAnalysis");
const summary = document.getElementById("gapSummary");

function renderList(title, items, formatter) {
  const card = document.createElement("article");
  card.className = "card";
  card.innerHTML = `<h4>${title}</h4>`;
  if (!items.length) {
    card.innerHTML += `<div class="meta">No data available.</div>`;
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

async function runAnalysis() {
  summary.innerHTML = "";
  try {
    const response = await fetch(`${API_BASE}/agents/collection-gaps`);
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || "Analysis failed");
    }
    const data = await response.json();
    summary.appendChild(
      renderList("Genre demand vs supply", data.genre_pressure || [], (item) => {
        return `${item.genre}: loans ${item.loans} / catalog ${item.catalog} (ratio ${item.demand_ratio})`;
      })
    );
    summary.appendChild(
      renderList("Reading level pressure", data.reading_level_pressure || [], (item) => {
        return `Level ${item.reading_level}: students ${item.students} / catalog ${item.catalog} (ratio ${item.student_ratio})`;
      })
    );
    summary.appendChild(
      renderList("Availability hotspots", data.availability_hotspots || [], (item) => {
        return `${item.genre}: ${Math.round(item.unavailable_rate * 100)}% unavailable`;
      })
    );
    summary.appendChild(
      renderList(
        "High-demand unavailable titles",
        data.high_demand_unavailable || [],
        (item) => `${item.title} (${item.genre}) · loans ${item.loans}`
      )
    );
    summary.appendChild(
      renderList("Recommended actions", data.recommendations || [], (item) => item)
    );
  } catch (error) {
    summary.innerHTML = `<div class="card">Error: ${error.message}</div>`;
  }
}

runButton.addEventListener("click", runAnalysis);
