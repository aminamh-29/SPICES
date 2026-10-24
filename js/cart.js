// Cart state. Saved in the browser so it survives a refresh.
const $ = (s) => document.querySelector(s);
const money = (n) => CURRENCY + n.toLocaleString("en-IN");
const find = (id) => PRODUCTS.find((p) => p.id == id);

let cart = {};
try { cart = JSON.parse(localStorage.getItem("mh-cart")) || {}; } catch (e) {}

const saveCart = () => { try { localStorage.setItem("mh-cart", JSON.stringify(cart)); } catch (e) {} };

function cartItems() {
  return Object.entries(cart).map(([id, qty]) => ({ p: find(id), qty })).filter((i) => i.p);
}
const cartCount = () => cartItems().reduce((s, i) => s + i.qty, 0);
const cartTotal = () => cartItems().reduce((s, i) => s + i.qty * i.p.price, 0);

function changeQty(id, d) {
  cart[id] = (cart[id] || 0) + d;
  if (cart[id] <= 0) delete cart[id];
  saveCart();
}

const newOrderId = () => "MH" + Date.now().toString(36).toUpperCase();

function orderPayload(orderId, customer) {
  return {
    orderId,
    customer,
    items: cartItems().map(({ p, qty }) => ({ id: p.id, name: p.name, unit: p.unit, price: p.price, qty })),
    total: cartTotal(),
  };
}

function orderMessage(orderId, c) {
  const lines = cartItems().map(({ p, qty }) => `• ${p.name} (${p.unit}) x${qty} = ${money(p.price * qty)}`);
  return [
    `Hello MH Spices, I'd like to place order ${orderId}:`,
    ...lines,
    `Total: ${money(cartTotal())}`,
    "",
    `Name: ${c.firstName} ${c.lastName}`,
    `Phone: ${c.phone}`,
    `Email: ${c.email}`,
    `Address: ${c.address}`,
    `Location: ${c.location}`,
  ].join("\n");
}
