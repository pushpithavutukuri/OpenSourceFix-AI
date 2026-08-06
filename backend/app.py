from clone_repo import clone_repository
from file_reader import read_repository
from chunker import create_chunks
from embedder import generate_embeddings
from vector_store import build_faiss_index

repo_path = clone_repository(
    "https://github.com/pallets/flask.git",
    "flask"
)

documents = read_repository(repo_path)

print(f"Documents: {len(documents)}")

chunks = create_chunks(documents)

print(f"Chunks: {len(chunks)}")

embeddings = generate_embeddings(chunks)

build_faiss_index(embeddings)

print("Repository indexed successfully!")
