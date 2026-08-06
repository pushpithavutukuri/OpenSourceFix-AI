from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)


def create_chunks(documents):

    chunks = []

    for doc in documents:

        texts = splitter.split_text(doc["content"])

        for text in texts:

            chunks.append({
                "path": doc["path"],
                "text": text
            })

    return chunks
