document.addEventListener("DOMContentLoaded", () => {
  const defaultCenter = [-1.286389, 36.817223];
  const defaultZoom = 12;

  const parseNumber = (value) => {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const createBaseMap = (element, center, zoom) => {
    const map = L.map(element, { scrollWheelZoom: false }).setView(center, zoom);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);
    setTimeout(() => map.invalidateSize(), 120);
    return map;
  };

  const reverseGeocode = async (lat, lng) => {
    const url = new URL("https://nominatim.openstreetmap.org/reverse");
    url.searchParams.set("format", "jsonv2");
    url.searchParams.set("lat", String(lat));
    url.searchParams.set("lon", String(lng));
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
      },
    });
    if (!response.ok) {
      throw new Error("Reverse geocoding failed");
    }
    return response.json();
  };

  document.querySelectorAll("[data-location-picker]").forEach((picker) => {
    const mapElement = picker.querySelector("[data-location-map]");
    const searchInput = picker.querySelector("[data-location-search]");
    const searchButton = picker.querySelector("[data-location-search-button]");
    const statusElement = picker.querySelector("[data-location-status]");
    const latInput = document.getElementById(picker.dataset.latInput);
    const lngInput = document.getElementById(picker.dataset.lngInput);
    const labelInput = document.getElementById(picker.dataset.labelInput);
    const addressInput = picker.dataset.addressInput
      ? document.getElementById(picker.dataset.addressInput)
      : null;

    if (!mapElement || !latInput || !lngInput || !labelInput) {
      return;
    }

    const initialLat = parseNumber(latInput.value);
    const initialLng = parseNumber(lngInput.value);
    const hasSavedPoint = initialLat !== null && initialLng !== null;
    const map = createBaseMap(
      mapElement,
      hasSavedPoint ? [initialLat, initialLng] : defaultCenter,
      hasSavedPoint ? 15 : defaultZoom
    );

    let marker = null;

    const ensureMarker = (lat, lng) => {
      if (marker) {
        marker.setLatLng([lat, lng]);
        return marker;
      }

      marker = L.marker([lat, lng], { draggable: true }).addTo(map);
      marker.on("dragend", async (event) => {
        const { lat: nextLat, lng: nextLng } = event.target.getLatLng();
        await updateLocation(nextLat, nextLng);
      });
      return marker;
    };

    const setStatus = (message, isError = false) => {
      if (!statusElement) {
        return;
      }
      statusElement.textContent = message;
      statusElement.classList.toggle("text-danger", isError);
      statusElement.classList.toggle("text-muted", !isError);
    };

    const maybeAutofillAddress = async (lat, lng) => {
      if (!addressInput) {
        return;
      }
      try {
        const data = await reverseGeocode(lat, lng);
        const displayName = data.display_name || "";
        const currentValue = addressInput.value.trim();
        if (!currentValue || currentValue === addressInput.dataset.lastAutofill) {
          addressInput.value = displayName;
          addressInput.dataset.lastAutofill = displayName;
        }
      } catch (_error) {
        // Ignore reverse-geocode failures; the user can still type an address.
      }
    };

    const updateLocation = async (lat, lng, options = {}) => {
      latInput.value = lat.toFixed(6);
      lngInput.value = lng.toFixed(6);
      ensureMarker(lat, lng);
      map.setView([lat, lng], 15);
      setStatus("Location selected.");
      if (options.autofillAddress !== false) {
        await maybeAutofillAddress(lat, lng);
      }
    };

    map.on("click", async (event) => {
      await updateLocation(event.latlng.lat, event.latlng.lng);
    });

    if (!hasSavedPoint) {
      latInput.value = "";
      lngInput.value = "";
      setStatus("Search for a place or click the map to drop a pin.");
    } else {
      ensureMarker(initialLat, initialLng);
      setStatus("Saved location loaded.");
    }

    const runSearch = async () => {
      const query = (searchInput?.value || "").trim();
      if (!query) {
        setStatus("Enter a place, road, estate, or landmark to search.", true);
        return;
      }

      try {
        setStatus("Searching…");
        const url = new URL("https://nominatim.openstreetmap.org/search");
        url.searchParams.set("format", "jsonv2");
        url.searchParams.set("limit", "1");
        url.searchParams.set("q", query);
        const response = await fetch(url, {
          headers: {
            Accept: "application/json",
          },
        });
        if (!response.ok) {
          throw new Error("Search request failed");
        }
        const results = await response.json();
        if (!results.length) {
          setStatus("No matching place was found. Try a nearby landmark.", true);
          return;
        }

        const result = results[0];
        const lat = parseNumber(result.lat);
        const lng = parseNumber(result.lon);
        if (lat === null || lng === null) {
          throw new Error("Invalid search result");
        }
        if (!labelInput.value.trim()) {
          labelInput.value = query;
        }
        await updateLocation(lat, lng);
      } catch (_error) {
        setStatus("We could not search that place right now. You can still click the map manually.", true);
      }
    };

    searchButton?.addEventListener("click", runSearch);
    searchInput?.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        runSearch();
      }
    });
  });

  document.querySelectorAll("[data-location-view]").forEach((viewer) => {
    const mapElement = viewer.querySelector("[data-location-map]");
    const lat = parseNumber(viewer.dataset.lat);
    const lng = parseNumber(viewer.dataset.lng);
    if (!mapElement || lat === null || lng === null) {
      return;
    }

    const map = createBaseMap(mapElement, [lat, lng], 15);
    L.marker([lat, lng]).addTo(map);
  });
});
