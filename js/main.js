// Page rendering and events.
let filter = "All";

function renderFilters() {
  const cats = ["All", ...new Set(PRODUCTS.map((p) => p.category))];
  $("#filters").innerHTML = cats
    .map((c) => `<button class="${c === filter ? "on" : ""}" aria-pressed="${c === filter}" data-c="${c}">${c}</button>`)
    .join("");
}

function renderGrid() {
  const list = PRODUCTS.filter((p) => filter === "All" || p.category === filter);
  $("#grid").innerHTML = list.map((p, i) => `
    <article class="card reveal" style="--d:${i * 60}ms">
      <div class="img" style="background:${p.color}22">
        ${p.image ? `<img src="${p.image}" alt="${p.name}" loading="lazy">` : `<div class="swatch" style="background:${p.color}"></div>`}
      </div>
      <h3>${p.name}</h3>
      <div class="meta">${p.unit} · ${p.category}</div>
      <div class="row"><span class="price">${money(p.price)}</span>
        <button class="add" data-id="${p.id}" aria-label="Add ${p.name} to cart" ${p.inStock ? "" : "disabled"}>${p.inStock ? "Add" : "Sold out"}</button></div>
    </article>`).join("");
  observeReveals($("#grid"));
}

function renderCart() {
  const items = cartItems();
  $("#cart-count").textContent = cartCount();
  $("#cart-total").textContent = $("#co-total").textContent = money(cartTotal());
  $("#to-checkout").disabled = !items.length;
  $("#order-summary").innerHTML = items.length
    ? items.map(({ p, qty }) => `<div class="sum-line"><span>${p.name} (${p.unit}) × ${qty}</span><span>${money(p.price * qty)}</span></div>`).join("")
    : `<p class="empty">Your cart is empty. Add spices from the shop above.</p>`;
  const rows = items.length ? items.map(({ p, qty }) => `
    <div class="line">
      <div><strong>${p.name}</strong><small>${p.unit} · ${money(p.price)}</small>
        <div class="qty"><button data-d="-1" data-id="${p.id}" aria-label="Remove one ${p.name}">−</button><span>${qty}</span><button data-d="1" data-id="${p.id}" aria-label="Add one ${p.name}">+</button></div></div>
      <strong>${money(p.price * qty)}</strong>
    </div>`).join("") : `<p class="empty">Your cart is empty. <a href="#shop">Browse the shop</a>.</p>`;
  $("#cart-items").innerHTML = rows;
  $("#cart-section-items").innerHTML = rows;
  $("#cs-total").textContent = money(cartTotal());
  $("#cs-checkout").disabled = !items.length;
}

$("#filters").addEventListener("click", (e) => {
  if (e.target.dataset.c) { filter = e.target.dataset.c; renderFilters(); renderGrid(); }
});

$("#grid").addEventListener("click", (e) => {
  const b = e.target.closest(".add");
  if (b && !b.disabled) { changeQty(b.dataset.id, 1); renderCart(); toast(`${find(b.dataset.id).name} added`); }
});

["#cart-items", "#cart-section-items"].forEach((sel) => $(sel).addEventListener("click", (e) => {
  if (e.target.dataset.d) { changeQty(e.target.dataset.id, +e.target.dataset.d); renderCart(); }
}));

const goToOrder = () => {
  toggleCart(false);
  $("#contact").scrollIntoView({ behavior: "smooth" });
  setTimeout(() => $("#f-first").focus({ preventScroll: true }), 500);
};
$("#to-checkout").onclick = $("#cs-checkout").onclick = goToOrder;

$("#use-location").onclick = () => {
  if (!navigator.geolocation) return setStatus("Your browser can't share location. Please type it in.", true);
  setStatus("Finding your location…");
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const link = `https://maps.google.com/?q=${pos.coords.latitude.toFixed(5)},${pos.coords.longitude.toFixed(5)}`;
      const f = form.elements.location;
      f.value = f.value ? `${f.value} (${link})` : link;
      setStatus("Location added.");
    },
    () => setStatus("Couldn't get your location. Please type it in.", true),
    { timeout: 10000 }
  );
};

const form = $("#order-form");
const setStatus = (msg, err) => { const el = $("#order-status"); el.textContent = msg; el.classList.toggle("err", !!err); };

// remember the customer's details for next time
try { Object.entries(JSON.parse(localStorage.getItem("mh-customer")) || {}).forEach(([k, v]) => { if (form.elements[k]) form.elements[k].value = v; }); } catch (e) {}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!cartCount()) return setStatus("Your cart is empty. Add spices from the shop first.", true);
  const customer = Object.fromEntries(["firstName", "lastName", "phone", "email", "address", "location"].map((k) => [k, form.elements[k].value.trim()]));
  try { localStorage.setItem("mh-customer", JSON.stringify(customer)); } catch (err) {}

  const orderId = newOrderId();
  const payload = { ...orderPayload(orderId, customer), website: form.elements.website.value };
  const waUrl = `https://wa.me/${WHATSAPP}?text=${encodeURIComponent(orderMessage(orderId, customer))}`;

  // open WhatsApp right away (browsers block pop-ups opened after a wait)
  window.open(waUrl, "_blank");

  if (!ORDER_EMAIL_ENDPOINT) return;
  $("#checkout").disabled = true;
  setStatus("Sending your order PDF by email…");
  try {
    const res = await fetch(ORDER_EMAIL_ENDPOINT, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const data = await res.json();
    if (data.error) return setStatus(data.error, true);   // the shop refused the order: nothing was saved
    cart = {}; saveCart(); renderCart();
    setStatus(data.ok
      ? `Order ${orderId} sent. A PDF copy is on its way to ${customer.email}.`
      : `Order ${orderId} saved and sent to WhatsApp. We couldn't email the PDF, but we'll confirm on WhatsApp.`);
    if (window.refreshAccount) refreshAccount();
  } catch (err) {
    setStatus("Your WhatsApp order is placed, but we couldn't email the PDF. We'll confirm on WhatsApp.", true);
  } finally {
    $("#checkout").disabled = false;
  }
});

$("#wa-link").href = `https://wa.me/${WHATSAPP}`;
$("#year").textContent = new Date().getFullYear();
renderFilters();
renderGrid();
renderCart();
observeReveals();
