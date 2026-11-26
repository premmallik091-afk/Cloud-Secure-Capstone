"use strict";
const $ = (id) => document.getElementById(id);
const API = "/api";
let token = sessionStorage.getItem("token"); // cleared when the tab closes

function say(text, kind) { $("msg").textContent = text; $("msg").className = kind || ""; }

async function api(path, method = "GET", body) {
  const res = await fetch(API + path, {
    method,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: "Bearer " + token } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && token) { logout(); }
  if (!res.ok) throw new Error(data.error || "Request failed (" + res.status + ")");
  return data;
}

function showTab(which) {
  const login = which === "login";
  $("form-login").hidden = !login; $("form-register").hidden = login;
  $("tab-login").classList.toggle("active", login); $("tab-register").classList.toggle("active", !login);
  say("");
}

function render(loggedIn, user) {
  $("auth").hidden = loggedIn; $("app").hidden = !loggedIn; $("userbox").hidden = !loggedIn;
  if (loggedIn) { $("whoami").textContent = user ? user.name : ""; loadNotes(); }
}

function logout() { token = null; sessionStorage.removeItem("token"); render(false); }

async function loadNotes() {
  const list = $("notes"); list.replaceChildren();
  try {
    const notes = await api("/notes");
    $("empty").hidden = notes.length > 0;
    for (const n of notes) {
      const li = document.createElement("li");
      const span = document.createElement("span"); span.textContent = n.content; // textContent => no XSS
      const del = document.createElement("button"); del.textContent = "✕"; del.title = "Delete"; del.ariaLabel = "Delete note";
      del.onclick = async () => { await api("/notes/" + n.id, "DELETE"); loadNotes(); };
      li.append(span, del); list.append(li);
    }
  } catch (e) { say(e.message, "err"); }
}

async function checkHealth() {
  try {
    const h = await api("/health");
    $("dot").className = "dot up"; $("health").textContent = "API online · database " + h.database;
  } catch { $("dot").className = "dot down"; $("health").textContent = "API or database unavailable"; }
}

$("tab-login").onclick = () => showTab("login");
$("tab-register").onclick = () => showTab("register");
$("logout").onclick = logout;

$("form-login").onsubmit = async (e) => {
  e.preventDefault();
  try {
    const d = await api("/login", "POST", { email: $("l-email").value, password: $("l-pass").value });
    token = d.token; sessionStorage.setItem("token", token); $("l-pass").value = ""; say(""); render(true, d.user);
  } catch (err) { say(err.message, "err"); }
};

$("form-register").onsubmit = async (e) => {
  e.preventDefault();
  try {
    await api("/register", "POST", { name: $("r-name").value, email: $("r-email").value, password: $("r-pass").value });
    $("l-email").value = $("r-email").value; $("r-pass").value = "";
    showTab("login"); say("Account created. Please log in.", "ok");
  } catch (err) { say(err.message, "err"); }
};

$("form-note").onsubmit = async (e) => {
  e.preventDefault();
  try { await api("/notes", "POST", { content: $("note").value }); $("note").value = ""; loadNotes(); }
  catch (err) { say(err.message, "err"); }
};

(async () => {
  checkHealth();
  if (token) { try { render(true, await api("/me")); } catch { render(false); } } else { render(false); }
})();
