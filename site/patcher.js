const inputs = {
  sm64: document.querySelector("#sm64-rom"),
  oot: document.querySelector("#oot-rom"),
  mm: document.querySelector("#mm-rom"),
};
const names = {
  sm64: document.querySelector("#sm64-name"),
  oot: document.querySelector("#oot-name"),
  mm: document.querySelector("#mm-name"),
};
const buildButton = document.querySelector("#build-rom");
const downloadRom = document.querySelector("#download-rom");
const status = document.querySelector("#patcher-status");
const customPalette = [...document.querySelectorAll("[data-mario-part]")];
const paletteRadios = [...document.querySelectorAll('input[name="mario-colour"]')];
const paletteConfirmation = document.querySelector("#palette-confirmation");
const confirmPalette = document.querySelector("#confirm-palette");
const cancelPalette = document.querySelector("#cancel-palette");
const palettes = {
  green: [[133, 56, 37], [30, 105, 27], [255, 255, 236], [71, 51, 42], [248, 191, 153], [222, 164, 69]],
  red: [[0, 0, 255], [255, 0, 0], [255, 255, 255], [114, 28, 14], [254, 193, 121], [115, 6, 0]],
};
const PALETTE_ACKNOWLEDGEMENT_KEY = "marios-mask-noncanonical-palette-understood";

let workerReady = false;
let building = false;
let downloadUrl = null;
let activePalette = "green";
let pendingPalette = null;
let paletteAcknowledged = false;
try {
  paletteAcknowledged = localStorage.getItem(PALETTE_ACKNOWLEDGEMENT_KEY) === "yes";
} catch {
  // Private browsing or locked-down storage still gets a one-time page acknowledgement.
}
const stableVersion = fetch("stable.json")
  .then((response) => response.json())
  .then((stable) => stable.version)
  .catch(() => "latest");
const worker = new Worker(new URL("patcher-worker.js", import.meta.url), { type: "module" });

function setStatus(message, error = false) {
  status.textContent = message;
  status.classList.toggle("error", error);
}

function updateButton() {
  const hasAllRoms = Object.values(inputs).every((input) => input.files.length === 1);
  buildButton.disabled = !workerReady || !hasAllRoms || building;
}

for (const [key, input] of Object.entries(inputs)) {
  input.addEventListener("change", () => {
    names[key].textContent = input.files[0]?.name || "Select local ROM";
    updateButton();
  });
}

function selectPalette(name) {
  document.querySelector(`input[name="mario-colour"][value="${name}"]`).checked = true;
  activePalette = name;
  for (const input of customPalette) input.disabled = name !== "custom";
}

function confirmNonCanonicalPalette(name) {
  if (paletteAcknowledged) {
    selectPalette(name);
    return;
  }
  const label = name === "red" ? "Original" : "Custom";
  pendingPalette = name;
  selectPalette(activePalette);
  confirmPalette.textContent = `I understand — use ${label}`;
  paletteConfirmation.returnValue = "";
  paletteConfirmation.showModal();
}

for (const radio of paletteRadios) {
  radio.addEventListener("change", () => {
    if (!radio.checked) return;
    if (radio.value === "green") {
      pendingPalette = null;
      selectPalette("green");
      return;
    }
    confirmNonCanonicalPalette(radio.value);
  });
}

paletteConfirmation.addEventListener("close", () => {
  selectPalette(activePalette);
  pendingPalette = null;
});

confirmPalette.addEventListener("click", () => {
  if (!pendingPalette) return;
  paletteAcknowledged = true;
  try {
    localStorage.setItem(PALETTE_ACKNOWLEDGEMENT_KEY, "yes");
  } catch {
    // The in-memory acknowledgement remains valid for this page visit.
  }
  selectPalette(pendingPalette);
  pendingPalette = null;
  paletteConfirmation.close("confirm");
});

cancelPalette.addEventListener("click", () => {
  pendingPalette = null;
  paletteConfirmation.close("cancel");
});

selectPalette("green");

function rgbFromHex(value) {
  return [1, 3, 5].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16));
}

function selectedPalette() {
  const preset = document.querySelector('input[name="mario-colour"]:checked').value;
  return palettes[preset] || customPalette.map((input) => rgbFromHex(input.value));
}

worker.addEventListener("message", async ({ data }) => {
  if (data.type === "ready") {
    workerReady = true;
    setStatus("Ready. Select the three ROMs above.");
  } else if (data.type === "status") {
    setStatus(data.message);
  } else if (data.type === "complete") {
    downloadUrl = URL.createObjectURL(new Blob([data.rom], { type: "application/octet-stream" }));
    downloadRom.href = downloadUrl;
    downloadRom.download = `Marios-Mask-v${await stableVersion}.z64`;
    downloadRom.hidden = false;
    downloadRom.click();
    building = false;
    setStatus("Complete. Your patched ROM has been downloaded.");
    updateButton();
  } else if (data.type === "error") {
    building = false;
    setStatus(data.message, true);
    updateButton();
  }
});

worker.addEventListener("error", () => {
  building = false;
  setStatus("The browser patcher could not start. Try the downloadable builder below.", true);
  updateButton();
});

buildButton.addEventListener("click", async () => {
  if (downloadUrl) URL.revokeObjectURL(downloadUrl);
  downloadUrl = null;
  downloadRom.hidden = true;
  building = true;
  updateButton();
  setStatus("Reading local ROMs…");
  try {
    const [sm64, oot, mm] = await Promise.all(
      Object.values(inputs).map((input) => input.files[0].arrayBuffer()),
    );
    worker.postMessage(
      { type: "build", sm64, oot, mm, palette: selectedPalette() },
      [sm64, oot, mm],
    );
  } catch (error) {
    building = false;
    setStatus(`Could not read the selected files: ${error.message}`, true);
    updateButton();
  }
});

window.addEventListener("pagehide", () => {
  if (downloadUrl) URL.revokeObjectURL(downloadUrl);
});
