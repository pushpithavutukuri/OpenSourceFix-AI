import faiss
import json
import numpy as np
from sentence_transformers import SentenceTransformer

# Load embedding model
model = SentenceTransformer("BAAI/bge-small-en-v1.5")

# Load FAISS index
index = faiss.read_index("code_index.faiss")

# Load stored chunks
with open("chunks.json", "r", encoding="utf-8") as f:
    chunks = json.load(f)


def retrieve_relevant_chunks(query, top_k=5):
    """
    Retrieve the most relevant code chunks
    for a natural language issue description.
    """

    query_embedding = model.encode([query])

    query_embedding = np.array(
        query_embedding,
        dtype="float32"
    )

    distances, indices = index.search(query_embedding, top_k)

    results = []

    for idx in indices[0]:
        if idx < len(chunks):
            results.append(chunks[idx])

    return results


if __name__ == "__main__":

    issue = input("Enter GitHub Issue: ")

    results = retrieve_relevant_chunks(issue)

    print("\nTop Relevant Code Chunks\n")

    for i, chunk in enumerate(results, start=1):

        print("=" * 80)
        print(f"Result {i}")
        print("File:", chunk["path"])
        print("-" * 80)
        print(chunk["text"][:700])
        print("=" * 80)
