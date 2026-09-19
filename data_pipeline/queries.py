import sqlite3
import pandas as pd


# ============================================================
# DATABASE SETTINGS
# ============================================================

DB_NAME = "data_pipeline.db"
OUTPUT_FILE = "data_pipeline/query_outputs.txt"


# ============================================================
# CONNECT TO DATABASE
# ============================================================

connection = sqlite3.connect(DB_NAME)


# ============================================================
# SQL QUERIES
# ============================================================

queries = {

    # 1. SELECT + WHERE
    "QUERY 1 - SELECT WHERE": """
        SELECT
            title,
            price_gbp,
            rating,
            category_id
        FROM books
        WHERE rating = 5
    """,

    # 2. ORDER BY + LIMIT
    "QUERY 2 - ORDER BY LIMIT": """
        SELECT
            title,
            price_gbp,
            price_inr
        FROM books
        ORDER BY price_gbp DESC
        LIMIT 10
    """,

    # 3. DISTINCT
    "QUERY 3 - DISTINCT": """
        SELECT DISTINCT
            category_name
        FROM categories
        ORDER BY category_name
    """,

    # 4. BETWEEN
    "QUERY 4 - BETWEEN": """
        SELECT
            title,
            price_gbp,
            rating
        FROM books
        WHERE price_gbp BETWEEN 20 AND 40
        ORDER BY price_gbp
    """,

    # 5. IN
    "QUERY 5 - IN": """
        SELECT
            b.title,
            b.price_gbp,
            b.rating,
            c.category_name
        FROM books b
        JOIN categories c
            ON b.category_id = c.category_id
        WHERE c.category_name IN (
            'Travel',
            'Mystery'
        )
        ORDER BY b.price_gbp DESC
    """,

    # 6. JOIN
    "QUERY 6 - JOIN": """
        SELECT
            b.title,
            b.price_gbp,
            b.price_inr,
            b.rating,
            b.in_stock,
            c.category_name
        FROM books b
        JOIN categories c
            ON b.category_id = c.category_id
        ORDER BY b.title
    """
}


# ============================================================
# SAVE SQL QUERIES AND OUTPUTS
# ============================================================

with open(
    OUTPUT_FILE,
    "w",
    encoding="utf-8"
) as file:

    file.write(
        "ZEPTO DATA & AI PLATFORM\n"
    )

    file.write(
        "MODULE 1 - SQL QUERY OUTPUTS\n\n"
    )

    # --------------------------------------------------------
    # Run every SQL query
    # --------------------------------------------------------

    for query_name, sql in queries.items():

        print("\n" + "=" * 80)
        print(query_name)
        print("=" * 80)

        print("\nSQL:")
        print(sql.strip())

        # Run query using pandas
        df = pd.read_sql(
            sql,
            connection
        )

        print("\nOUTPUT:")
        print(
            df.to_string(index=False)
        )

        # Save query and output
        file.write(
            "=" * 80 + "\n"
        )

        file.write(
            query_name + "\n"
        )

        file.write(
            "=" * 80 + "\n\n"
        )

        file.write(
            "SQL:\n"
        )

        file.write(
            sql.strip() + "\n\n"
        )

        file.write(
            "OUTPUT:\n"
        )

        file.write(
            df.to_string(index=False)
        )

        file.write("\n\n")


# ============================================================
# PANDAS read_sql() REQUIREMENT
# ============================================================

print("\n" + "=" * 80)
print("PANDAS read_sql() CHECK")
print("=" * 80)


sql_read_1 = """
    SELECT
        title,
        price_gbp,
        rating
    FROM books
    WHERE rating >= 4
    ORDER BY price_gbp DESC
    LIMIT 5
"""


sql_read_2 = """
    SELECT
        category_id,
        COUNT(*) AS book_count
    FROM books
    GROUP BY category_id
    ORDER BY book_count DESC
"""


df_read_sql_1 = pd.read_sql(
    sql_read_1,
    connection
)

df_read_sql_2 = pd.read_sql(
    sql_read_2,
    connection
)


print("\nFirst pd.read_sql() result:")

print(
    df_read_sql_1.to_string(
        index=False
    )
)


print("\nSecond pd.read_sql() result:")

print(
    df_read_sql_2.to_string(
        index=False
    )
)


# Save read_sql results

with open(
    OUTPUT_FILE,
    "a",
    encoding="utf-8"
) as file:

    file.write(
        "=" * 80 + "\n"
    )

    file.write(
        "PANDAS read_sql() CHECK\n"
    )

    file.write(
        "=" * 80 + "\n\n"
    )

    file.write(
        "First pd.read_sql() result:\n"
    )

    file.write(
        df_read_sql_1.to_string(
            index=False
        )
    )

    file.write(
        "\n\nSecond pd.read_sql() result:\n"
    )

    file.write(
        df_read_sql_2.to_string(
            index=False
        )
    )

    file.write("\n\n")


# ============================================================
# PANDAS MERGE - EQUIVALENT TO SQL JOIN
# ============================================================

print("\n" + "=" * 80)
print("PANDAS MERGE JOIN CHECK")
print("=" * 80)


# Read books table
books_df = pd.read_sql(
    """
        SELECT
            book_id,
            title,
            price_gbp,
            price_inr,
            rating,
            in_stock,
            category_id
        FROM books
    """,
    connection
)


# Read categories table
categories_df = pd.read_sql(
    """
        SELECT
            category_id,
            category_name
        FROM categories
    """,
    connection
)


# Perform JOIN using pandas merge
merged_df = pd.merge(
    books_df,
    categories_df,
    on="category_id",
    how="inner"
)


# Keep same columns as SQL JOIN
merged_df = merged_df[
    [
        "title",
        "price_gbp",
        "price_inr",
        "rating",
        "in_stock",
        "category_name"
    ]
]


# Same ordering as SQL JOIN
merged_df = merged_df.sort_values(
    by="title"
).reset_index(
    drop=True
)


print("\nPandas merge result:")

print(
    merged_df.to_string(
        index=False
    )
)


# Save pandas merge result

with open(
    OUTPUT_FILE,
    "a",
    encoding="utf-8"
) as file:

    file.write(
        "=" * 80 + "\n"
    )

    file.write(
        "PANDAS MERGE JOIN CHECK\n"
    )

    file.write(
        "=" * 80 + "\n\n"
    )

    file.write(
        merged_df.to_string(
            index=False
        )
    )

    file.write("\n\n")


# ============================================================
# CLOSE DATABASE
# ============================================================

connection.close()


# ============================================================
# FINAL MESSAGE
# ============================================================

print("\n" + "=" * 80)
print("SQL QUERIES COMPLETED SUCCESSFULLY")
print("=" * 80)

print(
    f"\nQueries and outputs saved to: {OUTPUT_FILE}"
)