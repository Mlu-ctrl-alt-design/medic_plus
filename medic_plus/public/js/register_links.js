// Inject "Register as Doctor / Patient" links into Frappe's sign-up section.
// Runs on every website page but only modifies the login page sign-up panel.
document.addEventListener("DOMContentLoaded", function () {
  var signup = document.querySelector("section.for-signup .login-content");
  if (!signup) {
    console.warn("[medic_plus] signup panel not found — register links not injected");
    return;
  }

  var el = document.createElement("p");
  el.style.cssText = "text-align:center;margin-top:16px;font-size:.875rem;color:#6b7280;";
  el.innerHTML =
    'Register as a&nbsp;' +
    '<a href="/register/doctor" style="color:#2563eb;font-weight:600;text-decoration:none;">Doctor</a>' +
    '&nbsp;or&nbsp;' +
    '<a href="/register/patient" style="color:#2563eb;font-weight:600;text-decoration:none;">Patient</a>';

  signup.appendChild(el);
});
