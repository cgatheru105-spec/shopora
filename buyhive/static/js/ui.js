(() => {
  const STORAGE_KEYS = {
    theme: "bh_theme", // "light" | "dark" | "system"
    compact: "bh_compact", // "1" | "0"
    reduceMotion: "bh_reduce_motion", // "1" | "0"
  };

  let revealObserver = null;
  let royalClicks = [];

  function getThemePreference() {
    const value = localStorage.getItem(STORAGE_KEYS.theme);
    if (value === "light" || value === "dark" || value === "system") return value;
    return "system";
  }

  function prefersDark() {
    return (
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
    );
  }

  function applyTheme(themePreference) {
    const useDark =
      themePreference === "dark" ||
      (themePreference === "system" && prefersDark());

    const theme = useDark ? "dark" : "light";
    document.documentElement.setAttribute("data-bs-theme", theme);
    document.documentElement.setAttribute("data-bh-theme", theme);
  }

  function applyCompact(enabled) {
    document.body.classList.toggle("bh-compact", enabled);
  }

  function applyReduceMotion(enabled) {
    document.body.classList.toggle("bh-reduce-motion", enabled);
    if (enabled) {
      if (revealObserver) {
        revealObserver.disconnect();
        revealObserver = null;
      }
      document.querySelectorAll(".bh-reveal").forEach((el) => {
        el.classList.add("is-visible");
      });
    } else {
      initReveals();
    }
  }

  function readBool(key) {
    return localStorage.getItem(key) === "1";
  }

  function writeBool(key, value) {
    localStorage.setItem(key, value ? "1" : "0");
  }

  function applyAll() {
    applyTheme(getThemePreference());
    applyCompact(readBool(STORAGE_KEYS.compact));
    applyReduceMotion(readBool(STORAGE_KEYS.reduceMotion));
  }

  function setThemePreference(value) {
    localStorage.setItem(STORAGE_KEYS.theme, value);
    applyTheme(value);
  }

  function initNavbarTheme() {
    const menu = document.querySelector("[data-bh-theme-menu]");
    if (!menu) return;

    const label = document.querySelector("[data-bh-theme-label]");
    const current = getThemePreference();
    if (label) label.textContent = current[0].toUpperCase() + current.slice(1);

    menu.addEventListener("click", (event) => {
      const button = event.target.closest("[data-bh-theme]");
      if (!button) return;
      event.preventDefault();
      const theme = button.getAttribute("data-bh-theme");
      setThemePreference(theme);
      if (label) label.textContent = theme[0].toUpperCase() + theme.slice(1);
    });
  }

  function initProfileSettings() {
    const root = document.querySelector("[data-bh-settings]");
    if (!root) return;

    const themeSelect = root.querySelector("[data-bh-setting='theme']");
    const compactToggle = root.querySelector("[data-bh-setting='compact']");
    const motionToggle = root.querySelector("[data-bh-setting='reduce-motion']");

    if (themeSelect) themeSelect.value = getThemePreference();
    if (compactToggle) compactToggle.checked = readBool(STORAGE_KEYS.compact);
    if (motionToggle) motionToggle.checked = readBool(STORAGE_KEYS.reduceMotion);

    if (themeSelect) {
      themeSelect.addEventListener("change", () => {
        setThemePreference(themeSelect.value);
      });
    }

    if (compactToggle) {
      compactToggle.addEventListener("change", () => {
        writeBool(STORAGE_KEYS.compact, compactToggle.checked);
        applyCompact(compactToggle.checked);
      });
    }

    if (motionToggle) {
      motionToggle.addEventListener("change", () => {
        writeBool(STORAGE_KEYS.reduceMotion, motionToggle.checked);
        applyReduceMotion(motionToggle.checked);
      });
    }
  }

  function initSystemThemeListener() {
    if (!window.matchMedia) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (getThemePreference() === "system") applyTheme("system");
    };
    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", handler);
    } else if (typeof media.addListener === "function") {
      media.addListener(handler);
    }
  }

  function initBackToTop() {
    const button = document.querySelector("[data-bh-back-to-top]");
    if (!button) return;

    const syncVisibility = () => {
      button.classList.toggle("is-visible", window.scrollY > 380);
    };

    syncVisibility();
    window.addEventListener("scroll", syncVisibility, { passive: true });
    button.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: document.body.classList.contains("bh-reduce-motion") ? "auto" : "smooth" });
    });
  }

  function showRoyalToast(message) {
    const existing = document.querySelector(".bh-royal-toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.className = "bh-royal-toast";
    toast.textContent = message;
    document.body.appendChild(toast);

    window.setTimeout(() => {
      toast.remove();
    }, 2600);
  }

  function initEasterEggs() {
    const mark = document.querySelector(".bh-brand-mark");
    if (!mark) return;

    mark.addEventListener("click", () => {
      const now = Date.now();
      royalClicks = royalClicks.filter((stamp) => now - stamp < 1800);
      royalClicks.push(now);

      if (royalClicks.length >= 5) {
        royalClicks = [];
        const enabled = document.body.classList.toggle("bh-royal-mode");
        showRoyalToast(
          enabled
            ? "Royal mode unlocked. Long live the founders."
            : "Royal mode dismissed. Back to business."
        );
      }
    });
  }

  function initReveals() {
    if (revealObserver) {
      revealObserver.disconnect();
      revealObserver = null;
    }

    if (document.body.classList.contains("bh-reduce-motion")) {
      return;
    }

    const elements = Array.from(
      document.querySelectorAll(
        ".bh-hero, .bh-surface, .bh-product-card, .bh-category-card, .alert"
      )
    );

    elements.forEach((el, index) => {
      if (!el.classList.contains("bh-reveal")) {
        el.classList.add("bh-reveal");
      }
      const delay = Math.min(index * 35, 260);
      el.style.setProperty("--bh-reveal-delay", `${delay}ms`);
    });

    if (!("IntersectionObserver" in window)) {
      elements.forEach((el) => el.classList.add("is-visible"));
      return;
    }

    revealObserver = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        }
      },
      { threshold: 0.12 }
    );

    elements.forEach((el) => revealObserver.observe(el));
  }

  document.addEventListener("DOMContentLoaded", () => {
    applyAll();
    initSystemThemeListener();
    initNavbarTheme();
    initProfileSettings();
    initBackToTop();
    initEasterEggs();
    initReveals();
  });
})();
