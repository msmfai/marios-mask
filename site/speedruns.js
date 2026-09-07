const results = document.querySelector("#speedrun-results");
const empty = document.querySelector("#speedrun-empty");
const status = document.querySelector("#speedrun-status");

function addCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.append(cell);
}

function compareVersionsDescending(left, right) {
  const leftParts = left.split(".").map(Number);
  const rightParts = right.split(".").map(Number);
  const length = Math.max(leftParts.length, rightParts.length);
  for (let index = 0; index < length; index += 1) {
    const difference = (rightParts[index] || 0) - (leftParts[index] || 0);
    if (difference !== 0) return difference;
  }
  return 0;
}

function timeInSeconds(time) {
  return time.split(":").reduce((total, part) => total * 60 + Number(part), 0);
}

function compareRuns(left, right) {
  return compareVersionsDescending(left.version, right.version)
    || timeInSeconds(left.time) - timeInSeconds(right.time);
}

try {
  const response = await fetch("speedruns.json");
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const runs = await response.json();
  if (!Array.isArray(runs)) throw new Error("the leaderboard data is not a list");

  for (const run of [...runs].sort(compareRuns)) {
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
