const FALLBACK_RELEASES = "https://github.com/msmfai/marios-mask/releases";

function releaseAssetUrl(stable, asset) {
  return `https://github.com/${stable.repository}/releases/download/${stable.tag}/${asset}`;
}

function preferredPlatform() {
  const platform = navigator.userAgentData?.platform || navigator.platform || "";
  const agent = navigator.userAgent || "";

  if (/Android/i.test(agent)) return "android";
  if (/Win/i.test(platform) || /Windows/i.test(agent)) return "windows";
  if (/Linux/i.test(platform) || /Linux/i.test(agent)) return "linux";
  if (/Mac/i.test(platform) || /Macintosh/i.test(agent)) return "macAppleSilicon";
  return null;
}

async function configureDownloads() {
  const primary = document.querySelector("#primary-download");

  try {
    const response = await fetch("stable.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`stable manifest returned ${response.status}`);
    const stable = await response.json();
    const links = document.querySelectorAll("[data-platform]");

    for (const link of links) {
      const asset = stable.assets[link.dataset.platform];
      link.href = releaseAssetUrl(stable, asset);
    }

    const platform = preferredPlatform();
    if (platform && stable.assets[platform]) {
      primary.href = releaseAssetUrl(stable, stable.assets[platform]);
      primary.textContent = `Download ${stable.version} for ${
        platform === "windows"
          ? "Windows"
          : platform === "linux"
            ? "Linux"
            : platform === "android"
              ? "Android"
              : "Mac"
      }`;
    } else {
      primary.href = `https://github.com/${stable.repository}/releases/tag/${stable.tag}`;
    }

    document.querySelector("#stable-version").textContent = `Version ${stable.version}`;
  } catch (error) {
    primary.href = FALLBACK_RELEASES;
    document.querySelector("#stable-version").textContent = "See available releases on GitHub";
    console.error("Could not load the stable release manifest", error);
  }
}

async function configureTrailer() {
  try {
    const response = await fetch("site-config.json", { cache: "no-cache" });
    if (!response.ok) return;
    const config = await response.json();
    const poster = document.querySelector("#trailer-poster");
    const playButton = document.querySelector("#play-trailer");
    const comingSoon = document.querySelector("#trailer-coming-soon");

    if (config.trailerPoster) poster.src = config.trailerPoster;
    if (!config.trailerYouTubeId) return;

    playButton.hidden = false;
    comingSoon.hidden = true;
    playButton.addEventListener("click", () => {
      const iframe = document.createElement("iframe");
      iframe.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(
        config.trailerYouTubeId,
      )}?autoplay=1&rel=0`;
      iframe.title = "Mario's Mask trailer";
      iframe.allow = "accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture";
      iframe.allowFullscreen = true;
      document.querySelector("#trailer-frame").replaceChildren(iframe);
    });
  } catch (error) {
    console.error("Could not load trailer configuration", error);
  }
}

configureDownloads();
configureTrailer();
