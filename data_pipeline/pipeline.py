import requests
from bs4 import BeautifulSoup
import pandas as pd
import sqlite3


# ============================================================
# PROJECT SETTINGS
# ============================================================

BASE_URL = "https://books.toscrape.com/"
GBP_TO_INR = 105.50

RATING_MAP = {
    "One": 1,
    "Two": 2,
    "Three": 3,
    "Four": 4,
    "Five": 5,
}


# ============================================================
# 1. SCRAPE ONE CATEGORY
# ============================================================

def scrape_category(category_url, category_name):

    response = requests.get(category_url, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    books = []

    for book in soup.select("article.product_pod"):

        title = book.h3.a["title"]

        price_text = book.select_one(
            ".price_color"
        ).get_text(strip=True)

        rating_class = book.select_one(
            "p.star-rating"
        )["class"]

        star_rating = rating_class[1]

        availability = book.select_one(
            ".availability"
        ).get_text(" ", strip=True)

        books.append({
            "title": title,
            "price_gbp": price_text,
            "star_rating": star_rating,
            "availability": availability,
            "category": category_name
        })

    return books


# ============================================================
# 2. SCRAPE 4 CATEGORIES
# ============================================================

def scrape_books():

    response = requests.get(BASE_URL, timeout=20)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    category_links = soup.select(
        ".side_categories ul li ul li a"
    )

    all_books = []

    # First 4 categories gives more than 60 books
    for link in category_links[:4]:

        category_name = link.get_text(strip=True)

        category_url = BASE_URL + link["href"]

        print(
            f"Scraping category: {category_name}"
        )

        books = scrape_category(
            category_url,
            category_name
        )

        all_books.extend(books)

    return all_books


# ============================================================
# 3. CLEAN AND TRANSFORM DATA
# ============================================================

def clean_data(books):

    df = pd.DataFrame(books)

    # --------------------------------------------------------
    # Clean GBP price
    # --------------------------------------------------------

    df["price_gbp"] = (
        df["price_gbp"]
        .str.replace("Â£", "", regex=False)
        .str.replace("£", "", regex=False)
        .str.strip()
    )

    df["price_gbp"] = pd.to_numeric(
        df["price_gbp"],
        errors="coerce"
    )

    # --------------------------------------------------------
    # Convert rating text to integer
    # --------------------------------------------------------

    df["rating"] = df["star_rating"].map(
        RATING_MAP
    )

    # --------------------------------------------------------
    # Convert availability to boolean
    # --------------------------------------------------------

    df["in_stock"] = df["availability"].str.contains(
        "In stock",
        case=False,
        na=False
    )

    # --------------------------------------------------------
    # Convert GBP to INR using required fixed rate
    # 1 GBP = 105.50 INR
    # --------------------------------------------------------

    df["price_inr"] = (
        df["price_gbp"] * GBP_TO_INR
    )

    # --------------------------------------------------------
    # Handle parsing failures
    # Numeric fields use median imputation
    # --------------------------------------------------------

    for column in [
        "price_gbp",
        "price_inr",
        "rating"
    ]:

        if df[column].isna().any():

            median_value = df[column].median()

            df[column] = df[column].fillna(
                median_value
            )

    # --------------------------------------------------------
    # Remove rows missing required text fields
    # --------------------------------------------------------

    df = df.dropna(
        subset=["title", "category"]
    )

    # --------------------------------------------------------
    # Keep required columns
    # --------------------------------------------------------

    df = df[
        [
            "title",
            "price_gbp",
            "price_inr",
            "rating",
            "in_stock",
            "category"
        ]
    ]

    return df


# ============================================================
# 4. LOAD DATA INTO SQLITE DATABASE
# ============================================================

def load_to_database(
    df,
    db_name="data_pipeline.db"
):

    connection = sqlite3.connect(db_name)

    cursor = connection.cursor()

    # Enable foreign-key enforcement
    cursor.execute(
        "PRAGMA foreign_keys = ON"
    )

    # --------------------------------------------------------
    # Create categories table
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_name TEXT UNIQUE NOT NULL
        )
    """)

    # --------------------------------------------------------
    # Create books table
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS books (
            book_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            price_gbp REAL,
            price_inr REAL,
            rating INTEGER,
            in_stock INTEGER,
            category_id INTEGER,
            FOREIGN KEY (category_id)
                REFERENCES categories(category_id)
        )
    """)

    # --------------------------------------------------------
    # Clear previous data
    # This makes the pipeline safe to run again
    # --------------------------------------------------------

    cursor.execute(
        "DELETE FROM books"
    )

    cursor.execute(
        "DELETE FROM categories"
    )

    # --------------------------------------------------------
    # Insert categories
    # --------------------------------------------------------

    categories = df["category"].unique()

    for category in categories:

        cursor.execute(
            """
            INSERT INTO categories (category_name)
            VALUES (?)
            """,
            (category,)
        )

    # --------------------------------------------------------
    # Create category -> ID mapping
    # --------------------------------------------------------

    cursor.execute("""
        SELECT category_id, category_name
        FROM categories
    """)

    category_rows = cursor.fetchall()

    category_id_map = {
        category_name: category_id
        for category_id, category_name
        in category_rows
    }

    # --------------------------------------------------------
    # Insert books
    # --------------------------------------------------------

    for _, row in df.iterrows():

        category_id = category_id_map[
            row["category"]
        ]

        cursor.execute(
            """
            INSERT INTO books (
                title,
                price_gbp,
                price_inr,
                rating,
                in_stock,
                category_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                row["title"],
                float(row["price_gbp"]),
                float(row["price_inr"]),
                int(row["rating"]),
                int(row["in_stock"]),
                category_id
            )
        )

    # --------------------------------------------------------
    # Save database
    # --------------------------------------------------------

    connection.commit()

    # --------------------------------------------------------
    # Verify database
    # --------------------------------------------------------

    cursor.execute(
        "SELECT COUNT(*) FROM books"
    )

    book_count = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM categories"
    )

    category_count = cursor.fetchone()[0]

    connection.close()

    print(
        "\nDatabase created successfully:",
        db_name
    )

    print(
        f"Books stored: {book_count}"
    )

    print(
        f"Categories stored: {category_count}"
    )


# ============================================================
# 5. MAIN PIPELINE
# ============================================================

if __name__ == "__main__":

    # --------------------------------------------------------
    # STEP 1: SCRAPING
    # --------------------------------------------------------

    print("=" * 60)
    print("STEP 1: SCRAPING")
    print("=" * 60)

    books = scrape_books()

    print(
        f"\nTotal books scraped: {len(books)}"
    )

    print("\nFirst 5 raw records:")

    for book in books[:5]:
        print(book)

    # --------------------------------------------------------
    # STEP 2: CLEANING
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("STEP 2: CLEANING")
    print("=" * 60)

    cleaned_df = clean_data(books)

    print("\nFirst 5 cleaned records:")

    print(
        cleaned_df.head().to_string(
            index=False
        )
    )

    print("\nData types:")

    print(cleaned_df.dtypes)

    print(
        f"\nTotal cleaned rows: {len(cleaned_df)}"
    )

    print("\nCategory counts:")

    print(
        cleaned_df["category"].value_counts()
    )

    # --------------------------------------------------------
    # Price conversion check
    # --------------------------------------------------------

    print("\nPrice conversion check:")

    print(
        cleaned_df[
            ["price_gbp", "price_inr"]
        ].head()
    )

    # --------------------------------------------------------
    # STEP 3: DATABASE
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("STEP 3: DATABASE")
    print("=" * 60)

    load_to_database(cleaned_df)

    # --------------------------------------------------------
    # FINAL MESSAGE
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("MODULE 1 PIPELINE COMPLETED")
    print("=" * 60)