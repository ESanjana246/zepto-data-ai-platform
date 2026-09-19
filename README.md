# Zepto Data & AI Platform

A modular Data & AI platform developed as part of the capstone project.

## Project Modules

- **Module 1 — Data Pipeline**
- **Module 2 — Analytics**
- **Module 3 — Support Assistant**

---

# Module 1 — Data Pipeline

## Overview

The Data Pipeline module automatically scrapes book data from
[Books to Scrape](https://books.toscrape.com/), cleans and transforms
the data using Python and Pandas, converts GBP prices to INR using the
required fixed exchange rate, and stores the processed data in a
normalized SQLite database.

The complete pipeline runs without manual copy-paste.

---

## Technologies Used

- Python
- Requests
- BeautifulSoup
- Pandas
- SQLite
- sqlite3

---

## Data Source

Data is collected from:

https://books.toscrape.com/

The pipeline currently scrapes four categories:

1. Travel
2. Mystery
3. Historical Fiction
4. Sequential Art

### Dataset Size

- **Books scraped:** 71
- **Categories:** 4

This satisfies the requirement of at least 60 books and at least
3 categories.

---

# Data Fields

The cleaned dataset contains the following fields:

| Field | Description |
|---|---|
| `title` | Book title |
| `price_gbp` | Book price in GBP |
| `price_inr` | Book price converted to INR |
| `rating` | Star rating from 1 to 5 |
| `in_stock` | Whether the book is currently in stock |
| `category` | Book category |

---

# Data Cleaning

## Price Cleaning

The currency symbol is removed from the scraped price and converted
to a numeric floating-point value.

Example:

```text
£45.17 → 45.17