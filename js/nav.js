// Cart drawer open/close and the small "added" message.
let lastFocus;

function toggleCart(open) {
  document.body.classList.toggle("open", open);
  $("#cart").setAttribute("aria-hidden", !open);
  if (open) { lastFocus = document.activeElement; $("#cart-close").focus(); }
  else if (lastFocus) lastFocus.focus();
}

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 1800);
}

$("#cart-btn").onclick = () => toggleCart(true);
$("#cart-close").onclick = $("#overlay").onclick = () => toggleCart(false);
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && document.body.classList.contains("open")) toggleCart(false);
});
