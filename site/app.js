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

configureTrailer();
