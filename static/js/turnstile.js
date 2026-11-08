(function () {
  "use strict";
  if (window.hemblaTurnstileStarted) return;
  window.hemblaTurnstileStarted = true;

  const selector = "[data-hembla-turnstile]";
  const pendingMessage = "Please complete the security check before sending your request.";
  const retryMessage = "The security check could not complete. Please retry or reload the page.";

  function showError(container, message) {
    const error = container.querySelector("[data-turnstile-error]");
    error.textContent = message;
    error.hidden = !message;
  }

  window.resetHemblaTurnstile = function (form) {
    if (!window.turnstile) return;
    form.querySelectorAll(selector).forEach((container) => {
      if (container.widgetId !== undefined) window.turnstile.reset(container.widgetId);
    });
  };

  window.hemblaTurnstileReady = function () {
    document.querySelectorAll(selector).forEach((container) => {
      if (container.widgetId !== undefined) return;
      container.widgetId = window.turnstile.render(container.querySelector("[data-turnstile-widget]"), {
        sitekey: container.dataset.sitekey,
        action: container.dataset.action,
        size: "flexible",
        callback: function () { showError(container, ""); },
        "expired-callback": function () {
          showError(container, pendingMessage);
          window.turnstile.reset(container.widgetId);
        },
        "error-callback": function () { showError(container, retryMessage); },
      });
    });
  };

  // Capture runs before existing form and AJAX handlers, preserving their behavior.
  document.addEventListener("submit", function (event) {
    const container = event.target.querySelector(selector);
    if (!container) return;
    if (window.turnstile && container.widgetId !== undefined && window.turnstile.getResponse(container.widgetId)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    showError(container, pendingMessage);
    container.scrollIntoView({ block: "center", behavior: "smooth" });
  }, true);

  document.addEventListener("reset", function (event) {
    if (event.target.querySelector(selector)) {
      window.setTimeout(function () { window.resetHemblaTurnstile(event.target); }, 0);
    }
  }, true);
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) document.querySelectorAll("form").forEach(window.resetHemblaTurnstile);
  });

  const script = document.createElement("script");
  script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=hemblaTurnstileReady&render=explicit";
  script.async = true;
  script.defer = true;
  script.onerror = function () {
    document.querySelectorAll(selector).forEach((container) => showError(container, retryMessage));
  };
  document.head.appendChild(script);
})();
