(() => {
  const STORAGE_KEYS = {
    theme: "bh_theme", // "light" | "dark" | "system"
    compact: "bh_compact", // "1" | "0"
    reduceMotion: "bh_reduce_motion", // "1" | "0"
    cart: "bh_cart",
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
    document.documentElement.setAttribute("data-bh-theme-preference", themePreference);
    document.documentElement.classList.toggle("theme-dark", theme === "dark");
    document.documentElement.style.colorScheme = theme;
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
    syncThemeControls(value);
  }

  function syncThemeControls(themePreference) {
    const effectiveTheme =
      themePreference === "system"
        ? prefersDark()
          ? "dark"
          : "light"
        : themePreference;

    const label = document.querySelector("[data-bh-theme-label]");
    if (label) {
      label.textContent =
        themePreference === "system"
          ? `System (${effectiveTheme[0].toUpperCase() + effectiveTheme.slice(1)})`
          : themePreference[0].toUpperCase() + themePreference.slice(1);
    }

    const toggleButton = document.querySelector("[data-bs-toggle='dropdown']");
    if (toggleButton) {
      toggleButton.setAttribute(
        "aria-label",
        `Theme selector (current: ${label ? label.textContent : themePreference})`
      );
    }

    updateThemeCheckmarks(themePreference);

    document
      .querySelectorAll("[data-bh-setting='theme']")
      .forEach((select) => {
        if (select.value !== themePreference) {
          select.value = themePreference;
        }
      });
  }

  function initNavbarTheme() {
    const menu = document.querySelector("[data-bh-theme-menu]");
    if (!menu) return;

    const current = getThemePreference();

    syncThemeControls(current);

    // Use event delegation on the menu items with capture phase to avoid Bootstrap interference
    menu.addEventListener("click", (event) => {
      const button = event.target.closest("[data-bh-theme]");
      if (!button) return;

      event.preventDefault();
      event.stopImmediatePropagation();

      const theme = button.getAttribute("data-bh-theme");
      setThemePreference(theme);

      const toggle = menu.parentElement?.querySelector("[data-bs-toggle='dropdown']");
      if (toggle && window.bootstrap?.Dropdown) {
        window.bootstrap.Dropdown.getOrCreateInstance(toggle).hide();
      }
    }, true); // Use capture phase

    // Update label and checkmarks when system theme changes
    if (window.matchMedia) {
      const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
      const handleChange = () => {
        if (getThemePreference() === "system") {
          applyTheme("system");
          syncThemeControls("system");
        }
      };
      if (typeof mediaQuery.addEventListener === "function") {
        mediaQuery.addEventListener("change", handleChange);
      } else if (typeof mediaQuery.addListener === "function") {
        mediaQuery.addListener(handleChange);
      }
    }
  }

  function updateThemeCheckmarks(selectedTheme) {
    const themeOptions = document.querySelectorAll(
      "[data-bh-theme-menu] [data-bh-theme]"
    );

    // Hide all checkmarks
    document.querySelectorAll("[data-bh-theme-check]").forEach(check => {
      check.style.opacity = "0";
    });

    themeOptions.forEach((option) => {
      const isSelected = option.getAttribute("data-bh-theme") === selectedTheme;
      option.classList.toggle("is-active", isSelected);
      option.setAttribute("aria-current", isSelected ? "true" : "false");
    });

    // Show checkmark for selected theme
    const selectedCheck = document.querySelector(`[data-bh-theme-check="${selectedTheme}"]`);
    if (selectedCheck) {
      selectedCheck.style.opacity = "1";
    }
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

  function initThemeShortcut() {
    window.addEventListener("keydown", (event) => {
      if (!event.ctrlKey || !event.shiftKey || event.key.toLowerCase() !== "t") return;
      if (event.target && /input|textarea|select/i.test(event.target.tagName)) return;

      event.preventDefault();
      const current = getThemePreference();
      const next = current === "system" ? "light" : current === "light" ? "dark" : "system";
      setThemePreference(next);
      showRoyalToast(`Theme set to ${
        next === "system" ? `System (${prefersDark() ? "Dark" : "Light"})` : next[0].toUpperCase() + next.slice(1)
      }`);
    });
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

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatCurrency(value) {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(value);
  }

  function getCart() {
    try {
      const raw = localStorage.getItem(STORAGE_KEYS.cart);
      const parsed = JSON.parse(raw || "[]");
      if (!Array.isArray(parsed)) return [];

      return parsed
        .filter((item) => item && item.key && item.name)
        .map((item) => ({
          key: String(item.key),
          name: String(item.name),
          price: Number.parseFloat(item.price) || 0,
          seller: String(item.seller || "Marketplace seller"),
          url: String(item.url || ""),
          image: String(item.image || ""),
          quantity: Math.max(1, Number.parseInt(item.quantity, 10) || 1),
        }));
    } catch (error) {
      return [];
    }
  }

  function saveCart(cart) {
    try {
      localStorage.setItem(STORAGE_KEYS.cart, JSON.stringify(cart));
    } catch (error) {
      showRoyalToast("Cart storage is unavailable on this device.");
      return false;
    }
    renderCart();
    return true;
  }

  function renderCart() {
    const cart = getCart();
    const count = cart.reduce((total, item) => total + item.quantity, 0);
    const subtotal = cart.reduce((total, item) => total + item.price * item.quantity, 0);

    document.querySelectorAll("[data-bh-cart-count]").forEach((badge) => {
      badge.textContent = count;
      badge.classList.toggle("d-none", count === 0);
    });

    document.querySelectorAll("[data-bh-cart-items-label]").forEach((label) => {
      label.textContent = `${count} item${count === 1 ? "" : "s"}`;
    });

    document.querySelectorAll("[data-bh-cart-subtotal]").forEach((subtotalNode) => {
      subtotalNode.textContent = formatCurrency(subtotal);
    });

    document.querySelectorAll("[data-bh-cart-note]").forEach((note) => {
      note.textContent =
        count > 0
          ? "Your saved cart is stored on this device, so you can come back and keep browsing."
          : "Save products as you browse and compare sellers before you decide.";
    });

    const itemsRoot = document.querySelector("[data-bh-cart-items]");
    const emptyState = document.querySelector("[data-bh-cart-empty]");
    if (!itemsRoot || !emptyState) return;

    emptyState.classList.toggle("d-none", cart.length > 0);
    itemsRoot.innerHTML = "";
    if (!cart.length) return;

    const placeholder = itemsRoot.getAttribute("data-bh-cart-placeholder") || "";
    itemsRoot.innerHTML = cart
      .map((item) => {
        const image = escapeHtml(item.image || placeholder);
        const name = escapeHtml(item.name);
        const seller = escapeHtml(item.seller);
        const url = item.url ? escapeHtml(item.url) : "";

        return `
          <article class="bh-cart-item">
            <img class="bh-cart-thumb" src="${image}" alt="${name}">
            <div class="bh-cart-copy">
              <div class="fw-semibold">${name}</div>
              <div class="text-muted small">by ${seller}</div>
              <div class="bh-cart-meta">
                <span>${formatCurrency(item.price)} each</span>
                <span>Qty ${item.quantity}</span>
              </div>
            </div>
            <div class="bh-cart-actions">
              <div class="bh-price">${formatCurrency(item.price * item.quantity)}</div>
              ${
                url
                  ? `<a class="btn btn-sm btn-outline-success" href="${url}" data-bs-dismiss="offcanvas">Seller</a>`
                  : ""
              }
              <button type="button" class="btn btn-sm btn-outline-secondary" data-bh-cart-remove="${escapeHtml(item.key)}">Remove</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  function addToCart(button, openCart) {
    const key = button.getAttribute("data-bh-cart-id");
    const name = button.getAttribute("data-bh-cart-name");
    if (!key || !name) return;

    const price = Number.parseFloat(button.getAttribute("data-bh-cart-price") || "0") || 0;
    const seller = button.getAttribute("data-bh-cart-seller") || "Marketplace seller";
    const url = button.getAttribute("data-bh-cart-url") || "";
    const image = button.getAttribute("data-bh-cart-image") || "";

    const cart = getCart();
    const existing = cart.find((item) => item.key === key);
    if (existing) {
      existing.quantity += 1;
    } else {
      cart.unshift({ key, name, price, seller, url, image, quantity: 1 });
    }

    if (!saveCart(cart)) return;
    showRoyalToast(`${name} saved to your cart.`);

    if (!openCart) return;

    const canvas = document.getElementById("bhCartCanvas");
    if (canvas && window.bootstrap?.Offcanvas) {
      window.bootstrap.Offcanvas.getOrCreateInstance(canvas).show();
    }
  }

  function removeFromCart(key) {
    if (!saveCart(getCart().filter((item) => item.key !== key))) return;
    showRoyalToast("Item removed from your cart.");
  }

  function clearCart() {
    if (!saveCart([])) return;
    showRoyalToast("Saved cart cleared.");
  }

  function initCart() {
    renderCart();

    document.addEventListener("click", (event) => {
      const addButton = event.target.closest("[data-bh-add-to-cart]");
      if (addButton) {
        event.preventDefault();
        addToCart(
          addButton,
          addButton.getAttribute("data-bh-open-cart") === "true"
        );
        return;
      }

      const removeButton = event.target.closest("[data-bh-cart-remove]");
      if (removeButton) {
        event.preventDefault();
        removeFromCart(removeButton.getAttribute("data-bh-cart-remove"));
        return;
      }

      const clearButton = event.target.closest("[data-bh-cart-clear]");
      if (clearButton) {
        event.preventDefault();
        clearCart();
      }
    });

    window.addEventListener("storage", (event) => {
      if (event.key === STORAGE_KEYS.cart) renderCart();
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
    initThemeShortcut();
    initNavbarTheme();
    initProfileSettings();
    initBackToTop();
    initCart();
    initEasterEggs();
    initReveals();

    // Ensure theme label is updated after all initialization
    const current = getThemePreference();
    syncThemeControls(current);
  });
})();
