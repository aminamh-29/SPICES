// ── Shop settings and spice list: edit this file ─────────
const WHATSAPP = "918089957854"; // your number: country code + number, no + or spaces
const CURRENCY = "₹";
const ORDER_EMAIL_ENDPOINT = "sendmail.php"; // emails the customer a PDF copy of their order (needs PHP hosting)

// Add / edit spices here. Optional: image: "assets/images/cardamom.jpg"
const PRODUCTS = [
  { id: 1, name: "Green Cardamom",  category: "Pods & Seeds", unit: "100g", price: 580, color: "#9bb07a", inStock: true },
  { id: 2, name: "Black Pepper",    category: "Pods & Seeds", unit: "100g", price: 280, color: "#3a3a3a", inStock: true },
  { id: 3, name: "Whole Nutmeg",    category: "Whole Spices", unit: "50g",  price: 340, color: "#8a5a3c", inStock: true, image: "assets/images/nutmeg-mace.jpg" },
  { id: 4, name: "Cloves",          category: "Whole Spices", unit: "50g",  price: 260, color: "#5a3426", inStock: true, image: "assets/images/cloves.jpg" },
  { id: 5, name: "Cinnamon Bark",   category: "Bark & Root",  unit: "100g", price: 220, color: "#b9763f", inStock: true },
  { id: 6, name: "Turmeric Powder", category: "Ground",       unit: "200g", price: 160, color: "#e0a526", inStock: true },
  { id: 7, name: "Chilli Powder",   category: "Ground",       unit: "200g", price: 180, color: "#b3261e", inStock: true },
  { id: 8, name: "Dried Ginger",    category: "Bark & Root",  unit: "100g", price: 190, color: "#d8b77a", inStock: false },
];
