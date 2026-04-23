// Injects a "Register your practice" link into Frappe's sign-up section.
document.addEventListener("DOMContentLoaded", function () {
  var signup = document.querySelector("section.for-signup .login-content");
  if (!signup) { return; }

  var el = document.createElement("p");
  el.style.cssText = "text-align:center;margin-top:16px;font-size:.875rem;color:#6b7280;";
  el.innerHTML =
    'Are you a doctor?&nbsp;' +
    '<a href="/signup" style="color:#2563eb;font-weight:600;text-decoration:none;">Register your practice</a>';

  signup.appendChild(el);
});
