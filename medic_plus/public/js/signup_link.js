// Injects a "Register your practice" link below the login form so doctors
// can self-onboard without first clicking "Sign up" (the for-signup section
// is hidden by default on the Frappe login page).
(function () {
  function inject() {
    if (document.getElementById("mp-doctor-signup-link")) return;
    // The for-login section is visible by default; for-signup gets revealed
    // only when the user clicks the built-in "Sign up" link. Inject into both
    // so the CTA is always reachable. Also fall back to .page-card for newer
    // Frappe layouts.
    var hosts = document.querySelectorAll(
      "section.for-login .login-content, section.for-signup .login-content, .login-content.page-card"
    );
    if (!hosts.length) return false;

    var html =
      '<p id="mp-doctor-signup-link" style="text-align:center;margin-top:16px;font-size:.875rem;color:#6b7280;">' +
      'Are you a doctor?&nbsp;' +
      '<a href="/signup" style="color:#2563eb;font-weight:600;text-decoration:none;">Register your practice</a>' +
      "</p>";

    hosts.forEach(function (host) {
      // Avoid duplicates if multiple sections share .login-content
      if (host.querySelector("#mp-doctor-signup-link")) return;
      host.insertAdjacentHTML("beforeend", html);
    });
    return true;
  }

  function ready(cb) {
    if (document.readyState !== "loading") cb();
    else document.addEventListener("DOMContentLoaded", cb);
  }

  ready(function () {
    // Initial inject — and re-inject if Frappe wipes .login-content on
    // section toggles (which it does via $(".login-content").empty()).
    inject();
    var observer = new MutationObserver(function () { inject(); });
    var root = document.querySelector(".page-card-container") || document.body;
    if (root) observer.observe(root, { childList: true, subtree: true });
  });
})();
