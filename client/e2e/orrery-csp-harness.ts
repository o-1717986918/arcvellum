import { NarrativeParallaxRenderer } from "../src/features/orrery/engine/parallaxRenderer";

const host = document.querySelector<HTMLElement>("#stage")!;
const status = document.querySelector<HTMLElement>("#status")!;
if (new URLSearchParams(location.search).get("motion") === "still") {
  document.documentElement.dataset.arcvellumMotion = "still";
}

async function start(): Promise<void> {
  try {
    const renderer = await NarrativeParallaxRenderer.create(host);
    renderer.resize(host.clientWidth, host.clientHeight);
    window.addEventListener("resize", () => renderer.resize(host.clientWidth, host.clientHeight));
    window.addEventListener("pagehide", () => renderer.dispose(), { once: true });
    requestAnimationFrame(() => requestAnimationFrame(() => {
      status.dataset.state = "rendered";
      status.textContent = "WebGL 天幕已启用，桌面 CSP 保持不变。";
    }));
  } catch (error) {
    status.dataset.state = "failed";
    status.textContent = error instanceof Error ? error.message : String(error);
  }
}

void start();
