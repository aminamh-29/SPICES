// Admin dashboard: orders, customers, prices and stock. The server checks the admin login on every request.
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (n) => "₹" + Number(n).toLocaleString("en-IN");

async function api(path, body) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  return res.json();
}

let msgTimer;
function say(text, err) {
  const el = $("#admin-msg");
  el.textContent = text;
  el.classList.toggle("err", !!err);
  clearTimeout(msgTimer);
  msgTimer = setTimeout(() => (el.textContent = ""), 3000);
}

function showGate(user, note) {
  $("#dash").hidden = true;
  $("#gate").hidden = false;
  $("#admin-logout").hidden = !user;
  $("#gate-note").textContent = note || (user ? `You are logged in as ${user.email}, which is not an admin account.` : "Only the shop owner can open this page.");
}

function showDash(user) {
  $("#gate").hidden = true;
  $("#dash").hidden = false;
  $("#admin-logout").hidden = false;
  $("#hello").textContent = `Hello, ${user.firstName}`;
  loadOrders();
}

// ── tabs ──
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
  const tab = b.dataset.tab;
  document.querySelectorAll(".tabs button").forEach((x) => x.setAttribute("aria-selected", x === b));
  ["orders", "customers", "products"].forEach((t) => ($(`#panel-${t}`).hidden = t !== tab));
  ({ orders: loadOrders, customers: loadCustomers, products: loadProducts })[tab]();
}));

// ── orders ──
let allOrders = [], statuses = [];
const waLink = (phone) => {
  let d = String(phone).replace(/\D/g, "");
  if (d.length === 10) d = "91" + d;          // 10-digit Indian numbers
  return `https://wa.me/${d}`;
};

function renderOrders() {
  const f = $("#order-filter").value;
  const list = allOrders.filter((o) => f === "All" || o.status === f);
  $("#order-count").textContent = `${list.length} order${list.length === 1 ? "" : "s"}`;
  $("#orders").innerHTML = list.length ? list.map((o) => {
    const c = o.customer;
    return `
    <article class="o-card">
      <div class="o-head">
        <div><strong class="o-code">${esc(o.code)}</strong><span class="muted"> · ${esc(o.createdAt.replace("T", " ").slice(0, 16))}</span></div>
        <label class="sr" for="st-${o.id}">Status of ${esc(o.code)}</label>
        <select id="st-${o.id}" data-order="${o.id}">${statuses.map((s) => `<option${s === o.status ? " selected" : ""}>${esc(s)}</option>`).join("")}</select>
      </div>
      <div class="o-body">
        <div>
          <p class="o-label">Customer</p>
          <p><strong>${esc(c.name)}</strong></p>
          <p><a href="tel:${esc(c.phone)}">${esc(c.phone)}</a> · <a href="${waLink(c.phone)}" target="_blank" rel="noopener">WhatsApp</a></p>
          <p><a href="mailto:${esc(c.email)}">${esc(c.email)}</a></p>
          <p class="muted">${esc(c.address)}<br>${esc(c.location)}</p>
        </div>
        <div>
          <p class="o-label">Items</p>
          ${o.items.map((i) => `<p class="o-item"><span>${esc(i.name)} (${esc(i.unit)}) × ${i.qty}</span><span>${money(i.price * i.qty)}</span></p>`).join("")}
          <p class="o-item o-total"><span>Total</span><span>${money(o.total)}</span></p>
          <p class="muted small">${o.emailed ? "PDF emailed to customer" : "PDF email not sent"}</p>
        </div>
      </div>
    </article>`;
  }).join("") : `<p class="empty">No orders${f === "All" ? " yet" : " with this status"}.</p>`;
}

async function loadOrders() {
  const data = await api("/api/admin/orders");
  if (!data.orders) return say(data.error || "Couldn't load orders.", true);
  allOrders = data.orders;
  statuses = data.statuses;
  const sel = $("#order-filter"), keep = sel.value || "All";
  sel.innerHTML = ["All", ...statuses].map((s) => `<option${s === keep ? " selected" : ""}>${s}</option>`).join("");
  renderOrders();
}

$("#order-filter").addEventListener("change", renderOrders);
$("#orders").addEventListener("change", async (e) => {
  if (!e.target.dataset.order) return;
  const data = await api("/api/admin/order-status", { id: +e.target.dataset.order, status: e.target.value });
  if (data.ok) {
    allOrders.find((o) => o.id == e.target.dataset.order).status = e.target.value;
    say("Status saved.");
  } else say(data.error || "Couldn't save.", true);
});

// ── customers ──
async function loadCustomers() {
  const data = await api("/api/admin/customers");
  if (!data.customers) return say(data.error || "Couldn't load customers.", true);
  $("#customers").innerHTML = data.customers.length ? `
    <div class="table">
      <div class="tr th"><span>Name</span><span>Email</span><span>Phone</span><span>Orders</span><span>Joined</span></div>
      ${data.customers.map((c) => `
      <div class="tr">
        <span><strong>${esc(c.firstName)} ${esc(c.lastName)}</strong>${c.role === "admin" ? ' <span class="pill">Admin</span>' : ""}</span>
        <span><a href="mailto:${esc(c.email)}">${esc(c.email)}</a></span>
        <span>${c.phone ? `<a href="tel:${esc(c.phone)}">${esc(c.phone)}</a>` : "–"}</span>
        <span>${c.orders}</span>
        <span class="muted">${esc(c.createdAt.slice(0, 10))}</span>
      </div>`).join("")}
    </div>` : `<p class="empty">No customers yet.</p>`;
}

// ── products ──
async function loadProducts() {
  const data = await api("/api/admin/products");
  if (!data.products) return say(data.error || "Couldn't load products.", true);
  $("#products").innerHTML = `
    <div class="table">
      <div class="tr th prod"><span>Spice</span><span>Price (₹)</span><span>In stock</span><span></span></div>
      ${data.products.map((p) => `
      <div class="tr prod" data-id="${p.id}">
        <span><strong>${esc(p.name)}</strong> <span class="muted">${esc(p.unit)}</span></span>
        <span><label class="sr" for="pr-${p.id}">Price of ${esc(p.name)}</label><input id="pr-${p.id}" class="p-price" type="number" min="0" max="100000" step="1" value="${p.price}"></span>
        <span><label class="check"><input class="p-stock" type="checkbox"${p.inStock ? " checked" : ""}> <span>${p.inStock ? "Yes" : "Sold out"}</span></label></span>
        <span><button type="button" class="save-btn">Save</button></span>
      </div>`).join("")}
    </div>`;
}

$("#products").addEventListener("click", async (e) => {
  if (!e.target.classList.contains("save-btn")) return;
  const row = e.target.closest(".tr");
  const price = row.querySelector(".p-price").value;
  if (price === "" || +price < 0) return say("Please enter a valid price.", true);
  e.target.disabled = true;
  const data = await api("/api/admin/product", { id: +row.dataset.id, price: +price, inStock: row.querySelector(".p-stock").checked });
  e.target.disabled = false;
  if (data.ok) { say("Saved. The shop is updated."); loadProducts(); } else say(data.error || "Couldn't save.", true);
});

// ── login / logout ──
$("#admin-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  $("#gate-error").textContent = "";
  try {
    const data = await api("/api/login", Object.fromEntries(new FormData(e.target)));
    if (!data.ok) $("#gate-error").textContent = data.error || "Login failed.";
    else if (data.user.role !== "admin") { showGate(data.user); }
    else { e.target.reset(); showDash(data.user); }
  } catch (err) {
    $("#gate-error").textContent = "Couldn't reach the shop server.";
  } finally {
    btn.disabled = false;
  }
});

$("#admin-logout").onclick = async () => { await api("/api/logout", {}); showGate(null); };

(async () => {
  try {
    const { user } = await api("/api/me");
    if (user && user.role === "admin") showDash(user); else showGate(user);
  } catch (e) {
    showGate(null, "The shop server isn't running. Start it with python server.py, then open this page at http://localhost:8000/admin.html");
  }
})();
