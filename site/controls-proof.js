const STORAGE_KEY = "marios-mask-controls-proof-v1";

const defaults = {
  player1: {
    1: [50, 55],
    2: [19.35, 31.22],
    3: [82.6576, 22.9543],
    4: [75, 42],
    5: [68.56, 35.18],
    6: [50, 36],
    7: [50, 83],
    8: [81.09, 12.56],
    10: [82.6576, 34.5159],
  },
  player2: {
    9: [50, 55],
  },
};

const status = document.querySelector("#proof-status");
let positions = loadPositions();

function cloneDefaults() {
  return JSON.parse(JSON.stringify(defaults));
}

function loadPositions() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    if (!saved?.player1 || !saved?.player2) return cloneDefaults();
    return {
      player1: { ...defaults.player1, ...saved.player1 },
      player2: { ...defaults.player2, ...saved.player2 },
    };
  } catch {
    return cloneDefaults();
  }
}

function savePositions() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(positions));
}

function placeLabel(controller, label) {
  const controllerId = controller.dataset.controller;
  const [left, top] = positions[controllerId][label.dataset.label];
  label.style.left = `${left}%`;
  label.style.top = `${top}%`;
}

function placeAllLabels() {
  for (const controller of document.querySelectorAll(".proof-controller")) {
    for (const label of controller.querySelectorAll(".drag-label")) {
      placeLabel(controller, label);
    }
  }
}

for (const controller of document.querySelectorAll(".proof-controller")) {
  for (const label of controller.querySelectorAll(".drag-label")) {
    label.addEventListener("pointerdown", (event) => {
      event.preventDefault();
      label.setPointerCapture(event.pointerId);
    });

    label.addEventListener("pointermove", (event) => {
      if (!label.hasPointerCapture(event.pointerId)) return;
      const bounds = controller.getBoundingClientRect();
      const left = Math.max(0, Math.min(100, ((event.clientX - bounds.left) / bounds.width) * 100));
      const top = Math.max(0, Math.min(100, ((event.clientY - bounds.top) / bounds.height) * 100));
      positions[controller.dataset.controller][label.dataset.label] = [
        Number(left.toFixed(2)),
        Number(top.toFixed(2)),
      ];
      placeLabel(controller, label);
    });

    label.addEventListener("pointerup", (event) => {
      if (!label.hasPointerCapture(event.pointerId)) return;
      label.releasePointerCapture(event.pointerId);
      savePositions();
      status.textContent = `Saved label ${label.dataset.label}.`;
    });
  }
}

document.querySelector("#reset-labels").addEventListener("click", () => {
  positions = cloneDefaults();
  savePositions();
  placeAllLabels();
  status.textContent = "Reset all labels.";
});

document.querySelector("#copy-labels").addEventListener("click", async () => {
  const text = JSON.stringify(positions, null, 2);
  try {
    await navigator.clipboard.writeText(text);
    status.textContent = "Copied label positions.";
  } catch {
    status.textContent = text;
  }
});

placeAllLabels();
