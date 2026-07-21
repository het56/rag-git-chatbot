# import faiss
# import numpy as np


# class VectorStore:

#     def __init__(self):
#         self.index = None
#         self.metadata = []

#     def build(self, vectors, metadata):
#         dim = len(vectors[0])
#         self.index = faiss.IndexFlatL2(dim)
#         self.index.add(np.array(vectors).astype("float32"))
#         self.metadata = metadata

#     def search(self, query_vector, k=5):
#         # Over-fetch so we can filter out summary chunks and still return k code chunks
#         fetch = min(k * 4, len(self.metadata))
#         D, I = self.index.search(
#             np.array([query_vector]).astype("float32"), fetch
#         )

#         results = []
#         for i in I[0]:
#             if i < 0:
#                 continue
#             chunk = self.metadata[i]
#             if chunk["type"] not in ("repo_summary", "file_summary"):
#                 results.append(chunk)
#             if len(results) >= k:
#                 break

#         return results

#     def get_file_summaries_for(self, file_paths):
#         file_paths = set(file_paths)
#         return [
#             m for m in self.metadata
#             if m["type"] == "file_summary" and m["file"] in file_paths
#         ]

#     def get_repo_summary(self):
#         for m in self.metadata:
#             if m["type"] == "repo_summary":
#                 return m
#         return None


import faiss
import numpy as np
import pickle


class VectorStore:

    def __init__(self):
        self.index = None
        self.metadata = []

    def build(self, vectors, metadata):
        dim = len(vectors[0])

        self.index = faiss.IndexFlatL2(dim)

        self.index.add(
            np.array(vectors).astype("float32")
        )

        self.metadata = metadata

    # =====================
    # SAVE
    # =====================

    def save(self, folder):

        faiss.write_index(
            self.index,
            f"{folder}/faiss.index"
        )

        with open(
            f"{folder}/metadata.pkl",
            "wb"
        ) as f:
            pickle.dump(
                self.metadata,
                f
            )

    # =====================
    # LOAD
    # =====================

    def load(self, folder):

        self.index = faiss.read_index(
            f"{folder}/faiss.index"
        )

        with open(
            f"{folder}/metadata.pkl",
            "rb"
        ) as f:
            self.metadata = pickle.load(f)

    # =====================
    # SEARCH
    # =====================

    def search(self, query_vector, k=5):

        fetch = min(
            k * 4,
            len(self.metadata)
        )

        D, I = self.index.search(
            np.array([query_vector]).astype("float32"),
            fetch
        )

        results = []

        for i in I[0]:

            if i < 0:
                continue

            chunk = self.metadata[i]

            if chunk["type"] not in (
                "repo_summary",
                "file_summary"
            ):
                results.append(chunk)

            if len(results) >= k:
                break

        return results

    def get_file_summaries_for(self, file_paths):

        file_paths = set(file_paths)

        return [
            m for m in self.metadata
            if m["type"] == "file_summary"
            and m["file"] in file_paths
        ]

    def get_repo_summary(self):

        for m in self.metadata:
            if m["type"] == "repo_summary":
                return m

        return None