# MH Spices

A minimalist spice shop. Plain HTML, CSS and JavaScript: no install needed.
Customers fill a cart and send the order to you on WhatsApp.

## Run it
Double-click `mhspices.html` (`index.html` just forwards to it).

## Change things
| What | Where |
|---|---|
| WhatsApp number, currency, spice list and prices | `js/products.js` |
| Spice photos | put files in `assets/images/`, add `image: "assets/images/name.jpg"` to the spice |
| Colours | `css/variable.css` |
| Page text | `mhspices.html` |

## Structure
```
mhspices.html      the page (index.html forwards to it)
css/
  style.css         entry file (imports the rest)
  variable.css      colours, spacing
  reset.css         base element styles
  layout.css        header, hero, sections, responsive
  component.css     buttons, product cards, cart, toast
  animations.css    scroll reveal, reduced motion
js/                 (loaded in this order)
  products.js       settings + spice list
  cart.js           cart state
  nav.js            cart drawer, toast
  animations.js     scroll reveal
  main.js           rendering and events
assets/images/      your photos
sendmail.php        PHP version of the order email (not used by server.py)
db.php              optional: MySQL connection, not used yet
```

## Put it online
Drag this folder onto Netlify Drop. The two PHP files only work on PHP hosting
and are not needed for the shop to work.

## Order email (PDF)
After checkout, WhatsApp opens with the order and `sendmail.php` emails the customer a PDF copy
(you get a Bcc). Before going live, edit `OWNER_EMAIL` and `MAIL_FROM` at the top of `sendmail.php`.
It only works on PHP hosting, not on Netlify or when opening the file from your PC.
If the email fails, the WhatsApp order still goes through.

## Test the PDF email on your PC (Gmail)
1. Google account > Security > turn on 2-Step Verification.
2. Search "App passwords", create one called "MH Spices", copy the 16 characters.
3. In the VS Code terminal run `.\start-server.ps1` and paste the password when asked.
4. Place a test order with your own email. The PDF arrives in your inbox (check spam).

## Accounts and admin (needs `python server.py`)
- Customers can create an account and log in. Their details fill in the order form and their past orders are listed.
- Create the admin login once: `python server.py create-admin` (it asks for email and a hidden password).
- Admin page: http://localhost:8000/admin.html. See orders and change their status, see customers,
  change prices and mark spices sold out.
- Data is stored in `shop.db` next to `server.py`. Back this file up. Never share it: it holds customer details.
- Accounts and the admin page only work with `server.py`. Plain file opening and PHP hosting do not have them.
