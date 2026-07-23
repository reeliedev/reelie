/* Reelie landing — interactions */
(function () {
  "use strict";

  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- signed-in nav: show the creator, not "Sign in" ---------- */
  (function () {
    var tok = null;
    try { tok = localStorage.getItem("reelie.token"); } catch (e) { return; }
    if (!tok) return;
    fetch("/me", { headers: { Authorization: "Bearer " + tok } })
      .then(function (r) {
        if (!r.ok) {                      // stale/expired session — clear + keep "Sign in"
          try { localStorage.removeItem("reelie.token"); localStorage.removeItem("reelie.user"); } catch (e) {}
          return null;
        }
        return r.json();
      })
      .then(function (u) {
        if (!u) return;
        var name = u.handle ? "@" + u.handle : (u.email || "My studio");
        var signin = document.getElementById("nav-signin");
        if (signin) { signin.textContent = name; signin.href = "/studio"; }
        var cta = document.getElementById("nav-cta");
        if (cta) { cta.textContent = "Go to studio →"; cta.href = "/studio"; }
      })
      .catch(function () {});
  })();

  /* ---------- phone story: 4 scenes ---------- */
  var scenes = document.querySelectorAll(".scene");
  var dots = document.querySelectorAll(".scene-dots .sd");
  var flowItems = document.querySelectorAll("#flow-list li");

  // scene durations (ms): notify → analyze → review → published
  var DURATIONS = [4200, 6600, 4800, 5600];
  var current = 0;
  var sceneTimer = null;

  function showScene(i) {
    scenes.forEach(function (s, idx) { s.classList.toggle("active", idx === i); });
    dots.forEach(function (d, idx) { d.classList.toggle("active", idx === i); });
    flowItems.forEach(function (f, idx) { f.classList.toggle("active", idx === i); });
    current = i;

    // restart analysis % ticker on scene 2, earnings counter on scene 4
    if (i === 1) startPct();
    if (i === 3) startEarnings();

    sceneTimer = setTimeout(function () {
      showScene((current + 1) % scenes.length);
    }, DURATIONS[i]);
  }

  /* analysis % synced to analyze scene */
  var pctEl = document.getElementById("rp-pct");
  var pctTimer = null;

  function startPct() {
    if (!pctEl) return;
    clearInterval(pctTimer);
    var pct = 8;
    pctEl.textContent = pct + "%";
    if (reducedMotion) { pctEl.textContent = "100%"; return; }
    var stepMs = 350;
    var steps = Math.floor(DURATIONS[1] / stepMs) - 2;
    var inc = Math.ceil((100 - pct) / steps);
    pctTimer = setInterval(function () {
      pct = Math.min(pct + inc + Math.floor(Math.random() * 3), 100);
      pctEl.textContent = pct + "%";
      if (pct >= 100) clearInterval(pctTimer);
    }, stepMs);
  }

  /* earnings count-up synced to published scene */
  var earnEl = document.getElementById("earn-total");
  var earnTimer = null;

  function startEarnings() {
    if (!earnEl) return;
    clearInterval(earnTimer);
    var TARGET = 38.6;
    if (reducedMotion) { earnEl.textContent = "$" + TARGET.toFixed(2); return; }
    earnEl.textContent = "$0.00";
    var value = 0;
    var startDelay = 3100; // begins as the total card lands
    var stepMs = 60;
    var steps = 28;
    setTimeout(function () {
      var inc = TARGET / steps;
      earnTimer = setInterval(function () {
        value = Math.min(value + inc, TARGET);
        earnEl.textContent = "$" + value.toFixed(2);
        if (value >= TARGET) clearInterval(earnTimer);
      }, stepMs);
    }, startDelay);
  }

  if (scenes.length) showScene(0);

  /* ---------- nav CTA focuses the form ---------- */
  var navCta = document.getElementById("nav-cta");
  if (navCta) {
    navCta.addEventListener("click", function (e) {
      var email = document.getElementById("hero-email");
      if (email) {
        e.preventDefault();
        email.focus();
      }
    });
  }

  /* ---------- sign-up forms ---------- */
  var ENDPOINT = "https://formspree.io/f/mdaqkree";

  function isValidEmail(value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
  }

  function handleForm(form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();

      var emailInput = form.querySelector('input[type="email"]');
      var handleInput = form.querySelector('input[name="handle"]');
      var email = emailInput.value.trim();
      var handle = handleInput ? handleInput.value.trim() : "";

      if (!isValidEmail(email)) {
        emailInput.classList.remove("invalid");
        void emailInput.offsetWidth; // replay shake
        emailInput.classList.add("invalid");
        emailInput.focus();
        return;
      }

      var payload = { email: email, handle: handle, source: form.id };

      var submitBtn = form.querySelector('button[type="submit"]');
      if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Joining…"; }

      fetch(ENDPOINT, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
        },
        body: JSON.stringify(payload),
      })
        .then(function (res) {
          if (res.ok) {
            showSuccess(form);
          } else {
            throw new Error("submit failed");
          }
        })
        .catch(function () {
          if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Join the pilot"; }
          emailInput.classList.add("invalid");
        });
    });

    var emailInput = form.querySelector('input[type="email"]');
    emailInput.addEventListener("input", function () {
      emailInput.classList.remove("invalid");
    });
  }

  function showSuccess(form) {
    var msg = document.createElement("div");
    msg.className = "success-msg";
    msg.setAttribute("role", "status");
    msg.innerHTML =
      '<span class="check">✓</span>' +
      "<p>You're on the list!<small>We'll reach out personally when your pilot spot opens.</small></p>";
    form.replaceWith(msg);
  }

  document.querySelectorAll("form.signup").forEach(handleForm);
})();
