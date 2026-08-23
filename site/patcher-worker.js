import init, { build_marios_mask } from "./pkg/marios_mask_builder.js";

try {
  await init();
  self.postMessage({ type: "ready" });
} catch (error) {
  self.postMessage({ type: "error", message: `Could not load the patcher: ${error.message}` });
}

self.addEventListener("message", ({ data }) => {
  if (data.type !== "build") return;
  try {
    self.postMessage({ type: "status", message: "Building Mario's Mask locally…" });
    const output = build_marios_mask(
      new Uint8Array(data.sm64),
      new Uint8Array(data.oot),
      new Uint8Array(data.mm),
      ...data.colour,
    );
    const rom = output.buffer.slice(output.byteOffset, output.byteOffset + output.byteLength);
    self.postMessage({ type: "complete", rom }, [rom]);
  } catch (error) {
    self.postMessage({ type: "error", message: error.message || String(error) });
  }
});
