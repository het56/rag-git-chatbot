# from app.embeddings.embedding import get_embedding
# from app.llm.groq_client import ask_llm


# def _format_code_chunk(chunk):
#     label = f"{chunk['file']} ({chunk['type']}: {chunk['name']})"
#     if chunk.get("parent_class"):
#         label += f" [class {chunk['parent_class']}]"
#     if chunk.get("calls"):
#         label += f" [calls: {', '.join(chunk['calls'][:5])}]"
#     return f"--- {label} ---\n{chunk['text']}"


# def build_prompt(repo_summary, file_summaries, code_chunks, question):
#     sections = []

#     if repo_summary:
#         sections.append(
#             "=== REPOSITORY OVERVIEW ===\n" + repo_summary["text"]
#         )

#     if file_summaries:
#         file_ctx = "=== RELEVANT FILE SUMMARIES ===\n"
#         file_ctx += "\n\n".join(fs["text"] for fs in file_summaries)
#         sections.append(file_ctx)

#     if code_chunks:
#         code_ctx = "=== CODE CHUNKS ===\n"
#         code_ctx += "\n\n".join(_format_code_chunk(c) for c in code_chunks)
#         sections.append(code_ctx)

#     context = "\n\n".join(sections)
    
#     return f"""
# You are a senior software engineer analyzing a Git repository.

# Your task is to answer questions ONLY using the provided context.

# CONTEXT HIERARCHY (MOST IMPORTANT):

# 1. CODE CHUNKS
#    - These are extracted directly from source files.
#    - Treat them as ground truth.
#    - If code contradicts documentation, trust the code.

# 2. FILE SUMMARIES
#    - These describe the contents of individual files.
#    - Use them when the exact implementation is not present.
#    - They are less reliable than code chunks.

# 3. REPOSITORY OVERVIEW
#    - This is generated from README, structure, and summaries.
#    - Treat it as descriptive documentation.
#    - Do NOT assume something exists solely because it is mentioned here.

# ANSWERING RULES:

# - Never invent files, functions, APIs, classes, or features.
# - Distinguish between:
#   * "implemented in code"
#   * "mentioned in documentation"
#   * "cannot be verified"

# - If a feature is mentioned in README or summaries but no supporting code is found, say:

#   "The feature is mentioned in the repository documentation, but the retrieved code does not provide evidence that it is implemented."

# - If code clearly implements something, say:

#   "The feature appears to be implemented."

# - If the context is insufficient, say:

#   "The provided context does not contain enough information to verify this."

# - For architecture questions:
#   Prefer repository overview + file summaries.

# - For implementation questions:
#   Prefer code chunks.

# - Always cite evidence:
#   Include filenames and function/class names when available.

# CONTEXT:

# {context}

# QUESTION:
# {question}

# ANSWER:
# """

# #     return f"""You are a senior software engineer analyzing a code repository.

# # Answer ONLY based on the provided context. Be specific — reference exact file names, \
# # function names, and line logic when relevant. If information is missing from context, say so.

# # {context}

# # QUESTION: {question}

# # ANSWER:"""






# def run_rag(question, store, k=5):
#     query_vec = get_embedding(question)

#     # Layer 1: semantic search over code chunks
#     code_chunks = store.search(query_vec, k=k)

#     # Layer 2: file summaries for matched files
#     matched_files = {c["file"] for c in code_chunks}
#     file_summaries = store.get_file_summaries_for(matched_files)

#     # Layer 3: repo-level overview
#     repo_summary = store.get_repo_summary()

#     prompt = build_prompt(repo_summary, file_summaries, code_chunks, question)
#     return ask_llm(prompt)
























from langchain_core.prompts import PromptTemplate
from langchain_core.documents import Document

from app.embeddings.embedding import get_embedding
from app.llm.groq_client import ask_llm


# ==========================================================
# LANGCHAIN PROMPT TEMPLATE
# ==========================================================

PROMPT_TEMPLATE = PromptTemplate(
    template="""
You are a senior software engineer analyzing a Git repository.

Your task is to answer questions ONLY using the provided context.

==================================================
CONTEXT HIERARCHY (MOST IMPORTANT)
==================================================

1. CODE CHUNKS
   - Extracted directly from source files
   - Ground truth
   - If code contradicts summaries, trust code

2. FILE SUMMARIES
   - Describe file responsibilities
   - Use when implementation is not directly retrieved

3. REPOSITORY OVERVIEW
   - Generated from README, structure, and summaries
   - High-level understanding only

==================================================
ANSWERING RULES
==================================================

- Never invent files, functions, APIs, routes, classes, or features.
- Always reference filenames when possible.
- Prefer implementation evidence from code chunks.
- Distinguish between:
  * implemented in code
  * mentioned in documentation
  * cannot be verified

- If code clearly implements something:
  "The feature appears to be implemented."

- If README mentions something but code evidence is missing:
  "The feature is mentioned in repository documentation, but the retrieved code does not provide evidence that it is implemented."

- If information is missing:
  "The provided context does not contain enough information to verify this."

==================================================
OUTPUT STYLE
==================================================

- Be concise.
- Use bullet points when listing.
- Cite filenames and functions/classes.
- Do not generate code unless asked.

==================================================
CONTEXT
==================================================

{context}

==================================================
QUESTION
==================================================

{question}

==================================================
ANSWER
==================================================
""",
    input_variables=["context", "question"],
)


# ==========================================================
# CONVERT CHUNK -> LANGCHAIN DOCUMENT
# ==========================================================

def chunk_to_document(chunk):

    label = f"{chunk['file']} ({chunk['type']}: {chunk['name']})"

    if chunk.get("parent_class"):
        label += f" [class {chunk['parent_class']}]"

    if chunk.get("calls"):
        label += f" [calls: {', '.join(chunk['calls'][:5])}]"

    return Document(
        page_content=chunk["text"],
        metadata={
            "label": label,
            "file": chunk["file"],
            "type": chunk.get("type"),
            "name": chunk.get("name"),
            "parent_class": chunk.get("parent_class"),
            "calls": chunk.get("calls", [])
        }
    )


# ==========================================================
# BUILD CONTEXT
# ==========================================================

def build_context(
    repo_summary,
    file_summaries,
    code_chunks
):

    sections = []

    # -----------------------------
    # REPO OVERVIEW
    # -----------------------------
    if repo_summary:

        sections.append(
            "=== REPOSITORY OVERVIEW ===\n"
            + repo_summary["text"]
        )

    # -----------------------------
    # FILE SUMMARIES
    # -----------------------------
    if file_summaries:

        file_context = (
            "=== RELEVANT FILE SUMMARIES ===\n"
        )

        file_context += "\n\n".join(
            fs["text"]
            for fs in file_summaries
        )

        sections.append(file_context)

    # -----------------------------
    # CODE CHUNKS
    # -----------------------------
    if code_chunks:

        docs = [
            chunk_to_document(chunk)
            for chunk in code_chunks
        ]

        code_section = []

        for doc in docs:

            chunk_text = f"""
FILE: {doc.metadata['file']}
TYPE: {doc.metadata['type']}
NAME: {doc.metadata['name']}
"""

            if doc.metadata.get("parent_class"):
                chunk_text += (
                    f"\nCLASS: {doc.metadata['parent_class']}"
                )

            if doc.metadata.get("calls"):
                chunk_text += (
                    f"\nCALLS: {', '.join(doc.metadata['calls'][:10])}"
                )

            chunk_text += f"\n\n{doc.page_content}"

            code_section.append(chunk_text)

        sections.append(
            "=== CODE CHUNKS ===\n"
            + "\n\n".join(code_section)
        )

    return "\n\n".join(sections)


# ==========================================================
# BUILD PROMPT
# ==========================================================

def build_prompt(
    repo_summary,
    file_summaries,
    code_chunks,
    question
):

    context = build_context(
        repo_summary,
        file_summaries,
        code_chunks
    )

    return PROMPT_TEMPLATE.format(
        context=context,
        question=question
    )


# ==========================================================
# MAIN RAG PIPELINE
# ==========================================================

def run_rag(question, store, k=5):

    # --------------------------------
    # QUERY EMBEDDING
    # --------------------------------
    query_vec = get_embedding(question)

    # --------------------------------
    # SEMANTIC SEARCH
    # --------------------------------
    code_chunks = store.search(
        query_vec,
        k=k
    )

    # --------------------------------
    # FILE SUMMARIES
    # --------------------------------
    matched_files = {
        c["file"]
        for c in code_chunks
    }

    file_summaries = (
        store.get_file_summaries_for(
            matched_files
        )
    )

    # --------------------------------
    # REPOSITORY SUMMARY
    # --------------------------------
    repo_summary = (
        store.get_repo_summary()
    )

    # --------------------------------
    # PROMPT
    # --------------------------------
    prompt = build_prompt(
        repo_summary,
        file_summaries,
        code_chunks,
        question
    )

    # Uncomment for debugging
    # print(prompt)

    # --------------------------------
    # LLM
    # --------------------------------
    return ask_llm(prompt)