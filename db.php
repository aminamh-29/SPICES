<?php
// Optional database connection. The shop does not use it yet: products live in js/products.js.
// Use this later if you move products or orders into MySQL.

const DB_HOST = "localhost";
const DB_NAME = "mh_spices";
const DB_USER = "root";
const DB_PASS = "";

function getDb(): PDO {
    return new PDO(
        "mysql:host=" . DB_HOST . ";dbname=" . DB_NAME . ";charset=utf8mb4",
        DB_USER,
        DB_PASS,
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION, PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]
    );
}
