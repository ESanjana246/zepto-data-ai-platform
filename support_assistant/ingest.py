from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


# Paths
BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "docs"
CHROMA_DIR = BASE_DIR / "chroma_db"


# Load embedding model
print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")


# Create ChromaDB client
client = chromadb.PersistentClient(path=str(CHROMA_DIR))

# Create or get collection
collection = client.get_or_create_collection(
    name="zepto_policies",
    metadata={"hnsw:space": "cosine"},
)


# Load documents
documents = []
ids = []

for file_path in sorted(DOCS_DIR.glob("doc_*.txt")):
    text = file_path.read_text(encoding="utf-8").strip()

    if not text:
        continue

    # One document = one chunk
    documents.append(text)
    ids.append(file_path.stem)


# Generate embeddings
print(f"Embedding {len(documents)} documents...")

embeddings = model.encode(
    documents,
    normalize_embeddings=True,
).tolist()


# Store in ChromaDB
if documents:
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
    )


print("\nIngestion complete!")
print(f"Documents indexed: {len(documents)}")
print(f"Collection: {collection.name}")
print(f"ChromaDB location: {CHROMA_DIR}")