# MH Spices

Minimalist spice shop. Plain HTML/CSS/JS front end, no build step, no Node. Orders go to the owner via WhatsApp. `server.py` (stdlib Python, SQLite) adds customer accounts, an admin dashboard (`admin.html`), order storage and the PDF email.

- Spices, prices, WhatsApp number: `js/products.js` (placeholders until the owner supplies real ones).
- Script order in `mhspices.html` matters; files share globals.
- Design: Minimalism, warm spice palette. Tokens in `css/variable.css`. Keep touch targets >= 44px, visible focus, and respect `prefers-reduced-motion`.
- Do not invent business claims (customer counts, years in business) on the page.
- `sendmail.php` and `db.php` are optional and need PHP hosting.
- Passwords are hashed (scrypt). Never store or print passwords, and never commit `shop.db`. The server, not the browser, decides prices on orders. The admin account is created with `python server.py create-admin`.
