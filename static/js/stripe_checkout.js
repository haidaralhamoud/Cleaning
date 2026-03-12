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

  if (typeof Stripe === "undefined") {
    if (button) button.disabled = true;
    if (errorEl) errorEl.textContent = "Payment service failed to load.";
    return;
  }

  if (!stripeReady || !publishableKey || !clientSecret || !completeUrl) {
    if (button) button.disabled = true;
    return;
  }

  var stripe = Stripe(publishableKey);
  var elements = stripe.elements({
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
  var paymentElement = elements.create("payment", {
    layout: "tabs"
  });
  paymentElement.mount("#payment-element");

  paymentElement.on("change", function (event) {
    if (!errorEl) return;
    errorEl.textContent = event.error ? event.error.message : "";
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
        if (errorEl) errorEl.textContent = (data && data.error) || "Payment succeeded, but confirmation failed.";
        button.disabled = false;
        button.textContent = originalText;
      })
      .catch(function () {
        if (errorEl) errorEl.textContent = "Payment succeeded, but confirmation failed.";
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
        if (failureUrl) {
          window.location.href = failureUrl;
          return;
        }
        if (errorEl) errorEl.textContent = result.error.message || "Payment failed.";
        button.disabled = false;
        button.textContent = originalText;
        return;
      }

      if (!result.paymentIntent) {
        if (failureUrl) {
          window.location.href = failureUrl;
          return;
        }
        if (errorEl) errorEl.textContent = "Payment did not complete.";
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
        window.location.href = failureUrl;
        return;
      }
      if (errorEl) errorEl.textContent = "Payment did not complete.";
      button.disabled = false;
      button.textContent = originalText;
    });
  });
})();
