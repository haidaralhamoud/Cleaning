(function () {
  const STORAGE_KEY = "cookie_consent";
  const ONE_YEAR_SECONDS = 60 * 60 * 24 * 365;

  const GA_MEASUREMENT_ID = "G-R9XP0MPGV0";
  const FB_PIXEL_ID = "FACEBOOK_PIXEL_ID";

  const state = {
    gaLoaded: false,
    fbLoaded: false,
    functionalLoaded: false
  };

  function readConsent() {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch (err) {
      // ignore and fallback to cookies
    }

    const match = document.cookie.match(new RegExp(STORAGE_KEY + "=([^;]+)"));
    if (!match) {
      return null;
    }
    try {
      return JSON.parse(decodeURIComponent(match[1]));
    } catch (err) {
      return null;
    }
  }

  function writeConsent(consent) {
    const payload = JSON.stringify(consent);
    try {
      window.localStorage.setItem(STORAGE_KEY, payload);
    } catch (err) {
      // ignore and fallback to cookies
    }
    document.cookie = STORAGE_KEY + "=" + encodeURIComponent(payload) + "; path=/; max-age=" + ONE_YEAR_SECONDS;
  }

  function loadScriptOnce(src, id) {
    if (id && document.getElementById(id)) {
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    if (id) {
      script.id = id;
    }
    document.head.appendChild(script);
  }

  function loadGoogleAnalytics() {
    if (state.gaLoaded) {
      return;
    }
    if (!GA_MEASUREMENT_ID || GA_MEASUREMENT_ID.indexOf("XXXX") !== -1) {
      return;
    }
    loadScriptOnce("https://www.googletagmanager.com/gtag/js?id=" + GA_MEASUREMENT_ID, "ga-gtag");

    const inline = document.createElement("script");
    inline.text =
      "window.dataLayer = window.dataLayer || [];" +
      "function gtag(){dataLayer.push(arguments);} " +
      "gtag('js', new Date());" +
      "gtag('config', '" + GA_MEASUREMENT_ID + "');";
    document.head.appendChild(inline);
    state.gaLoaded = true;
  }

  function loadFacebookPixel() {
    if (state.fbLoaded) {
      return;
    }
    if (!FB_PIXEL_ID || FB_PIXEL_ID.indexOf("PIXEL") !== -1) {
      return;
    }
    const inline = document.createElement("script");
    inline.text =
      "!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?" +
      "n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;" +
      "n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;" +
      "t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}" +
      "(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js');" +
      "fbq('init', '" + FB_PIXEL_ID + "');" +
      "fbq('track', 'PageView');";
    document.head.appendChild(inline);
    state.fbLoaded = true;
  }

  function loadFunctionalScripts() {
    if (state.functionalLoaded) {
      return;
    }
    // Add functional scripts here when available.
    state.functionalLoaded = true;
  }

  function loadScriptsByConsent() {
    const consent = readConsent();
    if (!consent) {
      return;
    }
    if (consent.analytics) {
      loadGoogleAnalytics();
    }
    if (consent.marketing) {
      loadFacebookPixel();
    }
    if (consent.functional) {
      loadFunctionalScripts();
    }
  }

  window.loadScriptsByConsent = loadScriptsByConsent;

  function setupBanner() {
    const consentEl = document.getElementById("cookie-consent");
    if (!consentEl) {
      return;
    }

    const settingsEl = consentEl.querySelector(".cookie-settings");
    const actionButtons = consentEl.querySelectorAll("[data-consent]");
    const categoryInputs = consentEl.querySelectorAll("[data-category]");

    const existing = readConsent();
    if (!existing) {
      consentEl.removeAttribute("hidden");
    } else {
      loadScriptsByConsent();
      return;
    }

    actionButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const action = button.getAttribute("data-consent");
        if (action === "manage") {
          settingsEl.classList.toggle("is-open");
          settingsEl.setAttribute("aria-hidden", settingsEl.classList.contains("is-open") ? "false" : "true");
          return;
        }

        if (action === "save") {
          const prefs = {
            essential: true,
            functional: false,
            analytics: false,
            marketing: false
          };
          categoryInputs.forEach((input) => {
            const category = input.getAttribute("data-category");
            prefs[category] = input.checked;
          });
          writeConsent(prefs);
          consentEl.setAttribute("hidden", "hidden");
          loadScriptsByConsent();
          return;
        }

        if (action === "all") {
          writeConsent({
            essential: true,
            functional: true,
            analytics: true,
            marketing: true
          });
          consentEl.setAttribute("hidden", "hidden");
          loadScriptsByConsent();
          return;
        }

        if (action === "reject") {
          writeConsent({
            essential: true,
            functional: false,
            analytics: false,
            marketing: false
          });
          consentEl.setAttribute("hidden", "hidden");
        }
      });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupBanner);
  } else {
    setupBanner();
  }
})();
