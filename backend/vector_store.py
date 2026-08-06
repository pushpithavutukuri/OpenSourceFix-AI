import faiss
import numpy as np


def build_faiss_index(embeddings):

    embeddings = np.array(
        embeddings,
        dtype="float32"
    )

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatL2(dimension)

    index.add(embeddings)

    faiss.write_index(index, "code_index.faiss")

    print("FAISS index saved.")

    return index
