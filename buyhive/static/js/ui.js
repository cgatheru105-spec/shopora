(() => {
  const STORAGE_KEYS = {
    theme: "bh_theme", // "light" | "dark" | "system"
    compact: "bh_compact", // "1" | "0"
    reduceMotion: "bh_reduce_motion", // "1" | "0"
    cart: "bh_cart",
  };

  let revealObserver = null;
  let royalClicks = [];
  let lastCartCount = null;

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

  function replayClassAnimation(nodes, className, duration = 700) {
    nodes.forEach((node) => {
      if (!node) return;
      node.classList.remove(className);
      void node.offsetWidth;
      node.classList.add(className);
      window.setTimeout(() => {
        node.classList.remove(className);
      }, duration);
    });
  }

  function normalizeCartId(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    const normalized = raw.startsWith("item-") ? raw.slice(5) : raw;
    return /^\d+$/.test(normalized) ? normalized : "";
  }

  function normalizeCartItem(item) {
    if (!item || typeof item !== "object") return null;

    const id = normalizeCartId(item.id || item.key);
    const name = String(item.name || "").trim();
    if (!id || !name) return null;

    return {
      id,
      name,
      price: Number.parseFloat(item.price) || 0,
      seller: String(item.seller || "Marketplace seller"),
      url: String(item.url || item.sellerUrl || ""),
      image: String(item.image || ""),
      quantity: Math.max(1, Number.parseInt(item.quantity, 10) || 1),
    };
  }

  function normalizeCartItems(items) {
    if (!Array.isArray(items)) return [];
    return items
      .map((item) => normalizeCartItem(item))
      .filter(Boolean);
  }

  function getCart() {
    try {
      const raw = localStorage.getItem(STORAGE_KEYS.cart);
      const parsed = JSON.parse(raw || "[]");
      const normalized = normalizeCartItems(parsed);

      if (JSON.stringify(normalized) !== JSON.stringify(parsed)) {
        localStorage.setItem(STORAGE_KEYS.cart, JSON.stringify(normalized));
      }

      return normalized;
    } catch (error) {
      return [];
    }
  }

  function saveCart(cart) {
    const normalizedCart = normalizeCartItems(cart);

    try {
      localStorage.setItem(STORAGE_KEYS.cart, JSON.stringify(normalizedCart));
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
    const shouldAnimateCartUpdate = lastCartCount !== null && lastCartCount !== count;

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
      .map((item, index) => {
        const image = escapeHtml(item.image || placeholder);
        const name = escapeHtml(item.name);
        const seller = escapeHtml(item.seller);
        const url = item.url ? escapeHtml(item.url) : "";

        return `
          <article class="bh-cart-item" style="--bh-cart-item-delay: ${Math.min(index * 55, 220)}ms;">
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
              <button type="button" class="btn btn-sm btn-outline-secondary" data-bh-cart-remove="${escapeHtml(item.id)}">Remove</button>
            </div>
          </article>
        `;
      })
      .join("");

    if (shouldAnimateCartUpdate) {
      replayClassAnimation(
        [
          ...document.querySelectorAll(".bh-cart-toggle"),
          ...document.querySelectorAll("[data-bh-cart-count]"),
          ...document.querySelectorAll("[data-bh-cart-items-label]"),
          ...document.querySelectorAll("[data-bh-cart-subtotal]"),
        ],
        "is-bump"
      );
    }

    lastCartCount = count;
  }

  function appendCheckoutInputs(form, cart) {
    form.querySelectorAll('[data-bh-generated-cart-input="true"]').forEach((field) => {
      field.remove();
    });

    cart.forEach((item) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = `cart_${item.id}`;
      input.value = item.quantity;
      input.setAttribute("data-bh-generated-cart-input", "true");
      form.appendChild(input);
    });
  }

  function addToCart(button, openCart) {
    const id = normalizeCartId(button.getAttribute("data-bh-cart-id"));
    const name = button.getAttribute("data-bh-cart-name");
    if (!id || !name) return;

    const price = Number.parseFloat(button.getAttribute("data-bh-cart-price") || "0") || 0;
    const seller = button.getAttribute("data-bh-cart-seller") || "Marketplace seller";
    const url = button.getAttribute("data-bh-cart-url") || "";
    const image = button.getAttribute("data-bh-cart-image") || "";

    const cart = getCart();
    const existing = cart.find((item) => item.id === id);
    if (existing) {
      existing.quantity += 1;
    } else {
      cart.unshift({ id, name, price, seller, url, image, quantity: 1 });
    }

    if (!saveCart(cart)) return;
    showRoyalToast(`${name} saved to your cart.`);

    if (!openCart) return;

    const canvas = document.getElementById("bhCartCanvas");
    if (canvas && window.bootstrap?.Offcanvas) {
      window.bootstrap.Offcanvas.getOrCreateInstance(canvas).show();
    }
  }

  function removeFromCart(id) {
    if (!saveCart(getCart().filter((item) => item.id !== id))) return;
    showRoyalToast("Item removed from your cart.");
  }

  function clearCart(silent = false) {
    if (!saveCart([])) return;
    if (!silent) {
      showRoyalToast("Saved cart cleared.");
    }
  }

  function initCart() {
    if (document.body.dataset.bhClearCartOnLoad === "true") {
      clearCart(true);
    }

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

    document.querySelectorAll("[data-bh-checkout-form]").forEach((form) => {
      form.addEventListener("submit", (event) => {
        const cart = getCart();
        if (!cart.length) {
          event.preventDefault();
          showRoyalToast("Your cart is empty.");
          return;
        }

        appendCheckoutInputs(form, cart);
      });
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

    window.requestAnimationFrame(() => {
      toast.classList.add("is-entering");
    });

    window.setTimeout(() => {
      toast.classList.add("is-hiding");
    }, 2200);

    window.setTimeout(() => {
      toast.remove();
    }, 2800);
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
        [
          ".bh-hero",
          ".bh-surface",
          ".bh-results-toolbar",
          ".bh-product-card",
          ".bh-category-card",
          ".bh-stat-card",
          ".bh-spotlight-card",
          ".bh-inline-item",
          ".bh-quick-filter",
          ".alert",
          ".bh-footer-grid > *",
        ].join(", ")
      )
    ).filter((element, index, collection) => collection.indexOf(element) === index);

    let previousParent = null;
    let groupIndex = 0;

    elements.forEach((el) => {
      if (!el.classList.contains("bh-reveal")) {
        el.classList.add("bh-reveal");
      }
      groupIndex = el.parentElement === previousParent ? groupIndex + 1 : 0;
      previousParent = el.parentElement;

      const delay = Math.min(groupIndex * 55, 280);
      const distance = el.matches(".bh-hero")
        ? "26px"
        : el.matches(".bh-product-card, .bh-category-card, .bh-spotlight-card, .bh-inline-item, .bh-stat-card")
          ? "22px"
          : "16px";
      const duration = el.matches(".bh-hero") ? "760ms" : "620ms";

      el.style.setProperty("--bh-reveal-delay", `${delay}ms`);
      el.style.setProperty("--bh-reveal-distance", distance);
      el.style.setProperty("--bh-reveal-duration", duration);
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
