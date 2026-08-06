import faiss
import numpy as np
import json


def build_faiss_index(embeddings, chunks):
    """
    Build and save a FAISS index.

    Args:
        embeddings: numpy array or list of embeddings
        chunks: list of chunk dictionaries

    Returns:
        FAISS index
    """

    embeddings = np.array(
        embeddings,
        dtype=np.float32
    )

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)

    index.add(embeddings)

    # Save FAISS index
    faiss.write_index(
        index,
        "code_index.faiss"
    )

    # Save chunk metadata
    with open(
        "chunks.json",
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            chunks,
            f,
            indent=4,
            ensure_ascii=False
        )

    print(
        f"FAISS index created with {index.ntotal} vectors"
    )
    print("Saved: code_index.faiss")
    print("Saved: chunks.json")

    return index
