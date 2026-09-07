const results = document.querySelector("#speedrun-results");
const empty = document.querySelector("#speedrun-empty");
const status = document.querySelector("#speedrun-status");

function addCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.append(cell);
}

try {
  const response = await fetch("speedruns.json");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const runs = await response.json();
  if (!Array.isArray(runs)) throw new Error("the leaderboard data is not a list");

  for (const run of runs) {
    const row = document.createElement("tr");
    addCell(row, run.username);
    addCell(row, run.time);
    addCell(row, run.version);
    results.append(row);
  }
  empty.hidden = runs.length !== 0;
} catch (error) {
  status.textContent = `The leaderboard could not be loaded: ${error.message}`;
}
