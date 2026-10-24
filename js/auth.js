// Customer accounts: log in, register, saved details, past orders.
// Needs the shop server (python server.py). If it isn't running, the account button stays hidden.
let currentUser = null;

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, body) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

const dlg = $("#auth");

function fillOrderForm(u) {
  const f = $("#order-form").elements;
  ["firstName", "lastName", "phone", "email", "address", "location"].forEach((k) => {
    if (u[k] && f[k] && !f[k].value) f[k].value = u[k];
  });
}

function applyUser(u) {
  currentUser = u;
  const btn = $("#account-btn");
  btn.hidden = false;
  btn.textContent = u ? u.firstName : "Log in";
  $("#admin-link").hidden = !(u && u.role === "admin");
  $("#auth-guest").hidden = !!u;
  $("#auth-user").hidden = !u;
  if (u) {
    $("#user-name").textContent = `${u.firstName} ${u.lastName}`;
    $("#user-email").textContent = u.email;
    $("#user-admin").hidden = u.role !== "admin";
    fillOrderForm(u);
  }
}

async function loadMyOrders() {
  const box = $("#my-orders");
  box.innerHTML = `<p class="empty">Loading…</p>`;
  try {
    const { orders = [] } = await api("/api/my-orders");
    box.innerHTML = orders.length ? orders.map((o) => `
      <div class="my-order">
        <div class="mo-top"><strong>${esc(o.code)}</strong><span class="pill">${esc(o.status)}</span></div>
        <div class="mo-items">${o.items.map((i) => `${esc(i.name)} × ${i.qty}`).join(", ")}</div>
        <div class="mo-bottom"><span>${esc(o.createdAt.slice(0, 10))}</span><strong>${money(o.total)}</strong></div>
      </div>`).join("") : `<p class="empty">No orders yet.</p>`;
  } catch (e) {
    box.innerHTML = `<p class="empty">Couldn't load your orders.</p>`;
  }
}

function showTab(which) {
  const login = which === "login";
  $("#login-form").hidden = !login;
  $("#register-form").hidden = login;
  $("#tab-login").setAttribute("aria-selected", login);
  $("#tab-register").setAttribute("aria-selected", !login);
  $("#auth-error").textContent = "";
}

function openAuth() {
  showTab("login");
  if (currentUser) loadMyOrders();
  dlg.showModal();
}

async function submitAuth(e, path) {
  e.preventDefault();
  const form = e.target;
  const btn = form.querySelector("button[type=submit]");
  btn.disabled = true;
  $("#auth-error").textContent = "";
  try {
    const data = await api(path, Object.fromEntries(new FormData(form)));
    if (!data.ok) { $("#auth-error").textContent = data.error || "Something went wrong."; return; }
    form.reset();
    applyUser(data.user);
    loadMyOrders();
    toast(`Welcome, ${data.user.firstName}`);
  } catch (err) {
    $("#auth-error").textContent = "Couldn't reach the shop. Please try again.";
  } finally {
    btn.disabled = false;
  }
}

$("#account-btn").onclick = openAuth;
$("#auth-close").onclick = () => dlg.close();
dlg.addEventListener("click", (e) => { if (e.target === dlg) dlg.close(); });   // click outside to close
$("#tab-login").onclick = () => showTab("login");
$("#tab-register").onclick = () => showTab("register");
$("#login-form").addEventListener("submit", (e) => submitAuth(e, "/api/login"));
$("#register-form").addEventListener("submit", (e) => submitAuth(e, "/api/register"));
$("#logout-btn").onclick = async () => {
  await api("/api/logout", {});
  applyUser(null);
  dlg.close();
  toast("Logged out");
};

window.refreshAccount = async () => {
  try { applyUser((await api("/api/me")).user); } catch (e) {}
};

// start-up: show the account button only when the shop server answers
(async () => {
  try {
    const { user } = await api("/api/me");
    applyUser(user);
    // prices and stock the admin has changed
    const { products } = await api("/api/products");
    products.forEach((sp) => {
      const p = find(sp.id);
      if (p) { p.price = sp.price; p.inStock = sp.inStock; }
    });
    renderGrid();
    renderCart();
  } catch (e) { /* opened as a plain file: no accounts */ }
})();
