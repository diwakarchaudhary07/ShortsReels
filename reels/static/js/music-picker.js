(() => {
  const picker = document.querySelector("[data-music-picker]");
  if (!picker) return;

  const searchInput = picker.querySelector("[data-music-search]");
  const results = picker.querySelector("[data-music-results]");
  const status = picker.querySelector("[data-music-status]");
  const closeButton = picker.querySelector("[data-music-close]");
  let activeTrigger = null;
  let activeAudio = null;
  let requestNumber = 0;
  let searchTimer = null;
  let activeTab = "trending";

  const setStatus = (text) => {
    status.textContent = text;
  };

  const formatDuration = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    return `${minutes}:${String(remainder).padStart(2, "0")}`;
  };

  const makeSongCard = (song) => {
    const card = document.createElement("article");
    card.className = "music-song-option";

    if (song.cover_url) {
      const cover = document.createElement("img");
      cover.className = "music-song-cover";
      cover.src = song.cover_url;
      cover.alt = "";
      cover.loading = "lazy";
      cover.referrerPolicy = "no-referrer";
      card.append(cover);
    } else {
      const cover = document.createElement("span");
      cover.className = "music-song-cover music-song-cover-empty";
      cover.innerHTML = '<i class="bi bi-music-note-beamed" aria-hidden="true"></i>';
      card.append(cover);
    }

    const copy = document.createElement("div");
    copy.className = "music-song-copy";
    const title = document.createElement("strong");
    title.textContent = song.title;
    const artist = document.createElement("span");
    artist.textContent = song.artist || "Unknown artist";
    copy.append(title, artist);
    if (song.duration) {
      const duration = document.createElement("small");
      duration.textContent = formatDuration(song.duration);
      copy.append(duration);
    }
    if (song.attribution) {
      const attribution = document.createElement("small");
      attribution.className = "music-song-attribution";
      if (song.attribution_url) {
        const link = document.createElement("a");
        link.href = song.attribution_url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = song.attribution;
        attribution.append(link);
      } else {
        attribution.textContent = song.attribution;
      }
      copy.append(attribution);
    }
    card.append(copy);

    if (song.preview_url) {
      const preview = document.createElement("audio");
      preview.controls = true;
      preview.preload = "none";
      preview.src = song.preview_url;
      preview.setAttribute("aria-label", `Preview ${song.title}`);
      preview.addEventListener("play", () => {
        if (activeAudio && activeAudio !== preview) activeAudio.pause();
        activeAudio = preview;
      });
      preview.addEventListener("error", () => {
        const unavailable = document.createElement("small");
        unavailable.className = "music-no-preview";
        unavailable.textContent = "Preview unavailable";
        preview.replaceWith(unavailable);
      });
      card.append(preview);
    } else {
      const noPreview = document.createElement("small");
      noPreview.className = "music-no-preview";
      noPreview.textContent = "No preview";
      card.append(noPreview);
    }

    const add = document.createElement("button");
    add.className = "music-song-add";
    add.type = "button";
    add.textContent = "Add";
    add.setAttribute("aria-label", `Add ${song.title}`);
    add.addEventListener("click", () => {
      const targetSelector = activeTrigger?.dataset.musicTarget;
      const target = targetSelector
        ? document.querySelector(targetSelector)
        : null;
      if (!target) {
        setStatus("Could not attach this song. Close the picker and try again.");
        return;
      }
      target.value = song.id;
      target.dispatchEvent(new Event("change", { bubbles: true }));
      const label = `${song.title}${song.artist ? ` · ${song.artist}` : ""}`;
      document.querySelectorAll("[data-music-selected-label]").forEach((item) => {
        item.textContent = label;
      });
      document.dispatchEvent(
        new CustomEvent("reelo:music-selected", { detail: song }),
      );
      if (activeAudio) activeAudio.pause();
      picker.close();
    });
    card.append(add);
    return card;
  };

  const loadSongs = async (url) => {
    const thisRequest = ++requestNumber;
    results.replaceChildren();
    setStatus("Loading music...");
    try {
      const response = await fetch(url, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error(
          response.status === 429
            ? "Music is busy right now. Try again shortly."
            : "Music could not be loaded. Please try again.",
        );
      }
      const data = await response.json();
      if (thisRequest !== requestNumber) return;
      if (!Array.isArray(data.results)) {
        throw new Error("The music library returned an invalid response.");
      }
      results.replaceChildren(...data.results.map(makeSongCard));
      setStatus(
        data.degraded
          ? data.message
          : data.results.length
            ? ""
            : data.message || "No songs found. Try another search.",
      );
    } catch (error) {
      if (thisRequest !== requestNumber) return;
      setStatus(error.message || "Music could not be loaded. Please try again.");
    }
  };

  const loadActiveTab = () => {
    if (activeTab === "trending") {
      loadSongs(picker.dataset.trendingUrl);
      return;
    }
    const query = searchInput.value.trim();
    if (!query) {
      results.replaceChildren();
      setStatus("Search songs and artists in Reelo's music library.");
      return;
    }
    const url = new URL(picker.dataset.searchUrl, window.location.origin);
    url.searchParams.set("q", query);
    loadSongs(url);
  };

  picker.querySelectorAll("[data-music-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      activeTab = tab.dataset.musicTab;
      picker.querySelectorAll("[data-music-tab]").forEach((item) => {
        item.setAttribute(
          "aria-selected",
          String(item.dataset.musicTab === activeTab),
        );
      });
      loadActiveTab();
      if (activeTab === "search") searchInput.focus();
    });
  });

  searchInput.addEventListener("input", () => {
    activeTab = "search";
    picker.querySelectorAll("[data-music-tab]").forEach((item) => {
      item.setAttribute(
        "aria-selected",
        String(item.dataset.musicTab === activeTab),
      );
    });
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(loadActiveTab, 250);
  });

  document.querySelectorAll("[data-music-picker-open]").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      activeTrigger = trigger;
      activeTab = "trending";
      searchInput.value = "";
      picker.querySelectorAll("[data-music-tab]").forEach((item) => {
        item.setAttribute(
          "aria-selected",
          String(item.dataset.musicTab === activeTab),
        );
      });
      picker.showModal();
      loadActiveTab();
    });
  });

  picker.querySelector("[data-music-clear]").addEventListener("click", () => {
    const targetSelector = activeTrigger?.dataset.musicTarget;
    const target = targetSelector ? document.querySelector(targetSelector) : null;
    if (!target) return;
    target.value = "";
    target.dispatchEvent(new Event("change", { bubbles: true }));
    document.querySelectorAll("[data-music-selected-label]").forEach((item) => {
      item.textContent = "No music selected";
    });
    document.dispatchEvent(
      new CustomEvent("reelo:music-selected", { detail: null }),
    );
    if (activeAudio) activeAudio.pause();
    picker.close();
  });

  closeButton.addEventListener("click", () => picker.close());
  picker.addEventListener("close", () => {
    if (activeAudio) activeAudio.pause();
    activeAudio = null;
  });
  picker.addEventListener("click", (event) => {
    if (event.target === picker) picker.close();
  });
})();
