<?php
// Emails the customer a PDF copy of their order (and a copy to you).
// Needs PHP hosting where mail() works. Called by js/main.js after checkout.

const OWNER_EMAIL = "aminamh2920@gmail.com";      // you get a copy of every order
const MAIL_FROM   = "orders@yourdomain.com";      // change: an address on your own domain, or mail may land in spam
const SHOP_NAME   = "MH Spices";
const PDF_CURRENCY = "Rs.";                       // PDF's built-in font has no rupee sign

header("Content-Type: application/json");

function fail(int $code): void {
    http_response_code($code);
    echo json_encode(["ok" => false]);
    exit;
}

// strip control characters and line breaks (blocks email-header injection)
function clean($v, int $max): string {
    $v = preg_replace('/[\x00-\x1F\x7F]+/u', ' ', (string)$v);
    return trim(mb_substr($v, 0, $max));
}

// ── PDF (plain text document, Helvetica, no libraries needed) ──
function pdf_text(string $s): string {
    $s = str_replace(["•", "–", "—", "’", "‘", "“", "”"], ["-", "-", "-", "'", "'", '"', '"'], $s);
    $s = @iconv("UTF-8", "windows-1252//TRANSLIT//IGNORE", $s) ?: preg_replace('/[^\x20-\x7E]/', '?', $s);
    return str_replace(["\\", "(", ")"], ["\\\\", "\\(", "\\)"], $s);
}

function pdf_build(array $pages): string {
    $objs = [];
    $objs[1] = "<< /Type /Catalog /Pages 2 0 R >>";
    $kids = [];
    $n = count($pages);
    for ($i = 0; $i < $n; $i++) $kids[] = (5 + $i * 2) . " 0 R";
    $objs[2] = "<< /Type /Pages /Kids [" . implode(" ", $kids) . "] /Count $n >>";
    $objs[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>";
    $objs[4] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>";
    foreach ($pages as $i => $content) {
        $pg = 5 + $i * 2;
        $objs[$pg] = "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents " . ($pg + 1) . " 0 R >>";
        $objs[$pg + 1] = "<< /Length " . strlen($content) . " >>\nstream\n$content\nendstream";
    }
    $out = "%PDF-1.4\n";
    $offsets = [];
    foreach ($objs as $num => $body) {
        $offsets[$num] = strlen($out);
        $out .= "$num 0 obj\n$body\nendobj\n";
    }
    $xref = strlen($out);
    $out .= "xref\n0 " . (count($objs) + 1) . "\n0000000000 65535 f \n";
    foreach ($offsets as $off) $out .= sprintf("%010d 00000 n \n", $off);
    $out .= "trailer\n<< /Size " . (count($objs) + 1) . " /Root 1 0 R >>\nstartxref\n$xref\n%%EOF";
    return $out;
}

function order_pdf(string $orderId, array $c, array $items, float $total): string {
    $pages = [];
    $cur = "";
    $y = 790;
    $put = function (int $x, string $text, int $size = 11, bool $bold = false) use (&$cur, &$y) {
        $cur .= sprintf("BT /%s %d Tf %d %d Td (%s) Tj ET\n", $bold ? "F2" : "F1", $size, $x, $y, pdf_text($text));
    };
    $newPage = function () use (&$pages, &$cur, &$y) { $pages[] = $cur; $cur = ""; $y = 790; };

    $put(50, SHOP_NAME, 22, true); $y -= 22;
    $put(50, "Order confirmation", 13); $y -= 34;
    $put(50, "Order no: $orderId", 11, true); $y -= 16;
    $put(50, "Date: " . date("d M Y, H:i"), 11); $y -= 28;

    $put(50, "Customer", 11, true); $y -= 16;
    foreach ([$c["name"], $c["phone"], $c["email"]] as $line) { $put(50, $line, 11); $y -= 15; }
    foreach (explode("\n", wordwrap($c["address"] . ", " . $c["location"], 80, "\n", true)) as $line) { $put(50, $line, 11); $y -= 15; }
    $y -= 18;

    $put(50, "Item", 11, true); $put(320, "Qty", 11, true); $put(380, "Price", 11, true); $put(470, "Amount", 11, true);
    $y -= 8; $cur .= "50 $y m 545 $y l S\n"; $y -= 16;

    foreach ($items as $it) {
        if ($y < 90) $newPage();
        $put(50, $it["name"] . " (" . $it["unit"] . ")", 11);
        $put(320, (string)$it["qty"], 11);
        $put(380, PDF_CURRENCY . " " . number_format($it["price"], 0), 11);
        $put(470, PDF_CURRENCY . " " . number_format($it["price"] * $it["qty"], 0), 11);
        $y -= 18;
    }
    if ($y < 120) $newPage();
    $cur .= "50 $y m 545 $y l S\n"; $y -= 22;
    $put(380, "Total", 12, true); $put(470, PDF_CURRENCY . " " . number_format($total, 0), 12, true); $y -= 40;
    $put(50, "Thank you for your order. We will confirm the final price and delivery with you on WhatsApp.", 10);
    $pages[] = $cur;
    return pdf_build($pages);
}

// ── Request ──
if ($_SERVER["REQUEST_METHOD"] !== "POST") fail(405);
$d = json_decode(file_get_contents("php://input"), true);
if (!is_array($d)) fail(400);
if (!empty($d["website"])) { echo json_encode(["ok" => true]); exit; } // honeypot: bots fill this in

$orderId = preg_replace('/[^A-Z0-9]/', '', strtoupper((string)($d["orderId"] ?? "")));
$cust = $d["customer"] ?? [];
$c = [
    "first"   => clean($cust["firstName"] ?? "", 40),
    "last"    => clean($cust["lastName"] ?? "", 40),
    "email"   => clean($cust["email"] ?? "", 120),
    "phone"   => clean($cust["phone"] ?? "", 25),
    "address" => clean($cust["address"] ?? "", 300),
    "location" => clean($cust["location"] ?? "", 160),
];
$c["name"] = trim($c["first"] . " " . $c["last"]);
if ($orderId === "" || strlen($orderId) > 20 || $c["first"] === "" || $c["last"] === "" || $c["address"] === "" || $c["location"] === "" || $c["phone"] === "" || !filter_var($c["email"], FILTER_VALIDATE_EMAIL)) fail(400);

$items = [];
$total = 0.0;
foreach (array_slice((array)($d["items"] ?? []), 0, 40) as $it) {
    $qty = (int)($it["qty"] ?? 0);
    $price = (float)($it["price"] ?? 0);
    if ($qty < 1 || $qty > 100 || $price < 0 || $price > 100000) continue;
    $items[] = ["name" => clean($it["name"] ?? "", 60), "unit" => clean($it["unit"] ?? "", 20), "qty" => $qty, "price" => $price];
    $total += $qty * $price;
}
if (!$items) fail(400);

// ── Email with PDF attached ──
$pdf = order_pdf($orderId, $c, $items, $total);
$boundary = "mh" . bin2hex(random_bytes(8));
$text = "Hello " . $c["name"] . ",\n\nThank you for your order $orderId with " . SHOP_NAME . ".\nYour order summary is attached as a PDF.\n\nWe will confirm the final price and delivery with you on WhatsApp.\n\n" . SHOP_NAME;

$headers = "From: " . SHOP_NAME . " <" . MAIL_FROM . ">\r\n"
         . "Bcc: " . OWNER_EMAIL . "\r\n"
         . "MIME-Version: 1.0\r\n"
         . "Content-Type: multipart/mixed; boundary=\"$boundary\"";

$body = "--$boundary\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n"
      . chunk_split(base64_encode($text))
      . "--$boundary\r\nContent-Type: application/pdf; name=\"order-$orderId.pdf\"\r\nContent-Transfer-Encoding: base64\r\nContent-Disposition: attachment; filename=\"order-$orderId.pdf\"\r\n\r\n"
      . chunk_split(base64_encode($pdf))
      . "--$boundary--";

$subject = "=?UTF-8?B?" . base64_encode("Your " . SHOP_NAME . " order $orderId") . "?=";
$sent = mail($c["email"], $subject, $body, $headers);

echo json_encode(["ok" => $sent]);
