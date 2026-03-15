(function () {
  var form = document.getElementById("paymentForm");
  if (!form) return;

  var publishableKey = form.getAttribute("data-stripe-publishable-key") || "";
  var clientSecret = form.getAttribute("data-stripe-client-secret") || "";
  var completeUrl = form.getAttribute("data-stripe-complete-url") || "";
  var returnUrl = form.getAttribute("data-stripe-return-url") || completeUrl;
  var failureUrl = form.getAttribute("data-stripe-failure-url") || "";
  var stripeReady = form.getAttribute("data-stripe-ready") === "1";
  var button = document.getElementById("confirmPayment");
  var errorEl = document.getElementById("card-errors");
  function setError(message) {
    if (errorEl) errorEl.textContent = message || "";
  }
  function formatStripeError(error, fallbackMessage) {
    if (!error) return fallbackMessage || "Payment failed.";
    var parts = [];
    if (error.message) parts.push(error.message);
    if (error.code) parts.push("code: " + error.code);
    if (error.decline_code) parts.push("decline: " + error.decline_code);
    if (error.type) parts.push("type: " + error.type);
    return parts.join(" | ") || fallbackMessage || "Payment failed.";
  }

  if (typeof Stripe === "undefined") {
    if (button) button.disabled = true;
    setError("Payment service failed to load.");
    return;
  }

  if (!stripeReady || !publishableKey || !clientSecret || !completeUrl) {
    if (button) button.disabled = true;
    var missing = [];
    if (!stripeReady) missing.push("stripe not ready");
    if (!publishableKey) missing.push("publishable key");
    if (!clientSecret) missing.push("client secret");
    if (!completeUrl) missing.push("complete url");
    setError("Payment form is not ready: " + missing.join(", ") + ".");
    return;
  }

  var stripe = Stripe(publishableKey);
  var elements;
  var paymentElement;
  try {
    elements = stripe.elements({
      clientSecret: clientSecret,
      appearance: {
        theme: "stripe",
        variables: {
          colorText: "#0f172a",
          colorDanger: "#c0392b",
          fontFamily: "\"Inter\", sans-serif"
        }
      }
    });
    paymentElement = elements.create("payment", {
      layout: "tabs"
    });
    paymentElement.mount("#payment-element");
  } catch (err) {
    console.error("[Stripe] payment element mount failed", err);
    if (button) button.disabled = true;
    setError((err && err.message) || "Payment form failed to initialize.");
    return;
  }

  paymentElement.on("change", function (event) {
    setError(event.error ? event.error.message : "");
  });

  function sendCompletion(paymentIntentId, originalText) {
    var csrfTokenInput = form.querySelector("input[name=csrfmiddlewaretoken]");
    var csrfToken = csrfTokenInput ? csrfTokenInput.value : "";
    var payload = new FormData();
    payload.append("payment_intent_id", paymentIntentId);

    return fetch(completeUrl, {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken },
      body: payload
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data && data.redirect_url) {
          window.location.href = data.redirect_url;
          return;
        }
        setError((data && data.error) || "Payment succeeded, but confirmation failed.");
        button.disabled = false;
        button.textContent = originalText;
      })
      .catch(function () {
        setError("Payment succeeded, but confirmation failed.");
        button.disabled = false;
        button.textContent = originalText;
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    if (!button) return;

    button.disabled = true;
    var originalText = button.textContent;
    button.textContent = "Processing...";

    stripe.confirmPayment({
      elements: elements,
      confirmParams: {
        return_url: returnUrl
      },
      redirect: "if_required"
    }).then(function (result) {
      if (result.error) {
        console.error("[Stripe] confirmPayment error", result.error);
        setError(formatStripeError(result.error, "Payment failed."));
        button.disabled = false;
        button.textContent = originalText;
        return;
      }

      if (!result.paymentIntent) {
        console.error("[Stripe] confirmPayment completed without paymentIntent", result);
        setError("Payment did not complete.");
        button.disabled = false;
        button.textContent = originalText;
        return;
      }

      if (result.paymentIntent.status === "succeeded") {
        sendCompletion(result.paymentIntent.id, originalText);
        return;
      }

      if (result.paymentIntent.status === "processing" || result.paymentIntent.status === "requires_action") {
        window.location.href = returnUrl + "?payment_intent=" + encodeURIComponent(result.paymentIntent.id);
        return;
      }

      if (failureUrl) {
        console.error("[Stripe] Unexpected payment intent status", result.paymentIntent.status, result.paymentIntent);
      }
      setError("Payment did not complete.");
      button.disabled = false;
      button.textContent = originalText;
    });
  });
})();
