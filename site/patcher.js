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
const customColour = document.querySelector("#custom-colour");

let workerReady = false;
let building = false;
let downloadUrl = null;
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

customColour.addEventListener("input", () => {
  document.querySelector('input[name="mario-colour"][value="custom"]').checked = true;
});

function selectedColour() {
  const preset = document.querySelector('input[name="mario-colour"]:checked').value;
  if (preset === "green") return [24, 88, 22];
  if (preset === "red") return [255, 0, 0];
  const value = customColour.value;
  return [1, 3, 5].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16));
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
      { type: "build", sm64, oot, mm, colour: selectedColour() },
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
