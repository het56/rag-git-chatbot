# import os

# from app.ingestion.repo_loader import load_repo_files
# from app.ingestion.ast_chunker import chunk_python_file
# from app.ingestion.repo_structure import build_tree
# from app.ingestion.file_summarizer import should_summarize, create_file_summary
# from app.ingestion.repo_summarizer import create_repo_summary
# from app.embeddings.embedding import get_embedding
# from app.vectordb.faiss_store import VectorStore
# from app.rag.pipeline import run_rag
# from app.llm.groq_client import ask_llm


# REPO_PATH = "data/repo"

# IGNORE_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}



# # CLONE

# def clone_repo(repo_url):
#     print("\nCloning repo...")
#     os.system("rm -rf data/repo")
#     os.system(f"git clone {repo_url} data/repo")
#     print("Repo cloned.\n")



# # UNIVERSAL CODE CHUNKER

# def smart_chunk(file_path, content):
#     ext = os.path.splitext(file_path)[1].lower()

#     if ext == ".py":
#         chunks = chunk_python_file(file_path, content)
#         # Fallback: if AST produced nothing, store the whole file
#         if not chunks:
#             chunks = [{"type": "code", "name": os.path.basename(file_path),
#                        "file": file_path, "text": content,
#                        "calls": [], "line": 0, "parent_class": None}]
#         return chunks

#     chunk_type = (
#         "code" if ext in {".js", ".ts", ".jsx", ".tsx", ".go", ".java",
#                           ".rb", ".rs", ".cpp", ".c", ".h", ".cs", ".php"} else
#         "json" if ext == ".json" else
#         "doc"  if ext in {".md", ".txt", ".rst"} else
#         "file"
#     )

#     # Truncate very large files
#     text = content[:8000] if len(content) > 8000 else content

#     return [{
#         "type": chunk_type,
#         "name": os.path.basename(file_path),
#         "file": file_path,
#         "text": text,
#         "calls": [],
#         "line": 0,
#         "parent_class": None,
#     }]



# # STEP 1: GET REPO

# repo_url = input("Enter GitHub repo URL: ")
# clone_repo(repo_url)



# # STEP 2: LOAD FILES

# print("Loading files...")
# files = load_repo_files(REPO_PATH)
# print(f"  {len(files)} files loaded")



# # STEP 3: CODE CHUNKS

# print("Chunking code...")
# code_chunks = []
# for f in files:
#     code_chunks.extend(smart_chunk(f["file"], f["content"]))
# print(f"  {len(code_chunks)} code chunks created")

# if not code_chunks:
#     raise ValueError("No chunks created — repo may be empty or unreadable.")



# # STEP 4: FILE SUMMARIES  (LLM per file)

# print("\nGenerating file summaries (this calls the LLM once per file)...")
# file_summaries = []
# summarizable = [f for f in files if should_summarize(f["file"], f["content"])]
# print(f"  {len(summarizable)} files will be summarized")

# for i, f in enumerate(summarizable, 1):
#     print(f"  [{i}/{len(summarizable)}] {os.path.basename(f['file'])}", end="", flush=True)
#     summary_chunk = create_file_summary(f["file"], f["content"], ask_llm)
#     file_summaries.append(summary_chunk)
#     print(" ✓")

# print(f"  {len(file_summaries)} file summaries created")



# # STEP 5: REPO SUMMARY  (one LLM call)

# print("\nGenerating repository overview...")
# tree = build_tree(REPO_PATH)
# repo_summary_chunk = create_repo_summary(REPO_PATH, file_summaries, tree, ask_llm)
# print("  Repository overview created ✓")



# # STEP 6: COMBINE ALL CHUNKS

# all_chunks = code_chunks + file_summaries + [repo_summary_chunk]
# print(f"\nTotal chunks in index: {len(all_chunks)}")
# print(f"  code chunks   : {len(code_chunks)}")
# print(f"  file summaries: {len(file_summaries)}")
# print(f"  repo summary  : 1")



# # STEP 7: EMBEDDINGS

# print("\nBuilding embeddings...")
# vectors = []
# metadata = []
# for c in all_chunks:
#     vectors.append(get_embedding(c["text"]))
#     metadata.append(c)
# print(f"  {len(vectors)} embeddings built")



# # STEP 8: VECTOR STORE

# store = VectorStore()
# store.build(vectors, metadata)



# # STEP 9: PRINT STRUCTURE & START CHAT

# print("\nRepo structure:")
# print(tree)

# print("\n\nRAG READY — multi-layer search active")
# print("(repo overview + file summaries + code chunks)")
# print("Type 'exit' to quit.\n")


# while True:
#     q = input("Ask: ").strip()
#     if not q:
#         continue
#     if q.lower() == "exit":
#         break

#     try:
#         result = run_rag(q, store)
#         print("\nANSWER:\n", result, "\n")
#     except Exception as e:
#         print(f"\nError: {e}\n")


import os
import streamlit as st

from app.ingestion.repo_loader import load_repo_files
from app.ingestion.ast_chunker import chunk_python_file
from app.ingestion.repo_structure import build_tree
from app.ingestion.file_summarizer import should_summarize, create_file_summary
from app.ingestion.repo_summarizer import create_repo_summary
from app.embeddings.embedding import get_embedding
from app.vectordb.faiss_store import VectorStore
from app.rag.pipeline import run_rag
from app.llm.groq_client import ask_llm
import json
from datetime import datetime
from app.storage.s3_client import S3Client
from app.github.github_client import get_latest_commit
from app.scheduler.repo_monitor import get_commit_hash


# from app.scheduler.scheduler import start_scheduler


# if "scheduler_started" not in st.session_state:

#     start_scheduler()

#     st.session_state.scheduler_started = True



# REPO_PATH = "data/repo"



IGNORE_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}


# -----------------------------
# CORE FUNCTIONS
# -----------------------------

# def clone_repo(repo_url):
#     os.system("rm -rf data/repo")
#     os.system(f"git clone {repo_url} data/repo")


#new---------------
def clone_repo(repo_url):

    repo_name = repo_url.split("/")[-1].replace(".git", "")

    repo_path = f"data/repos/{repo_name}"

    os.makedirs("data/repos", exist_ok=True)

    if not os.path.exists(repo_path):

        os.system(
            f"git clone {repo_url} {repo_path}"
        )

    return repo_path





def smart_chunk(file_path, content):
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".py":
        chunks = chunk_python_file(file_path, content)
        if not chunks:
            chunks = [{
                "type": "code",
                "name": os.path.basename(file_path),
                "file": file_path,
                "text": content,
                "calls": [],
                "line": 0,
                "parent_class": None
            }]
        return chunks

    chunk_type = (
        "code" if ext in {".js", ".ts", ".jsx", ".tsx", ".go", ".java",
                          ".rb", ".rs", ".cpp", ".c", ".h", ".cs", ".php"} else
        "json" if ext == ".json" else
        "doc" if ext in {".md", ".txt", ".rst"} else
        "file"
    )

    text = content[:8000]

    return [{
        "type": chunk_type,
        "name": os.path.basename(file_path),
        "file": file_path,
        "text": text,
        "calls": [],
        "line": 0,
        "parent_class": None,
    }]


def build_pipeline(repo_url, progress_bar, status_text):
    s3 = S3Client()
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    # STEP 1: CLONE
    status_text.text("Cloning repo...")
    # clone_repo(repo_url)
    
    #----//-----
    repo_path = clone_repo(repo_url)
    
    

    # STEP 2: LOAD FILES
    status_text.text("Loading files...")
    files = load_repo_files(repo_path)
    
    

    #for s3....
    repo_info = {
    "repo_name": repo_name,
    "repo_url": repo_url,
    "last_commit": get_commit_hash(repo_path),
    "files_count": len(files),
    "indexed_at": datetime.utcnow().isoformat()
}

    s3.upload_json(repo_info, f"{repo_name}/repo_info.json")
    
    #....
 



    # STEP 3: CHUNKING
    status_text.text("Chunking code...")
    code_chunks = []
    for f in files:
        code_chunks.extend(smart_chunk(f["file"], f["content"]))

    if not code_chunks:
        raise ValueError("No chunks created")

    # STEP 4: FILE SUMMARIES
    status_text.text("Generating file summaries...")
    file_summaries = []
    
    
    file_summaries_payload = []
    
    
    
#...........///
    for summary in file_summaries:
        file_summaries_payload.append({
        "file": summary["file"],
        "summary": summary["text"]
    })

    s3.upload_json(
    file_summaries_payload,
    f"{repo_name}/file_summaries.json"
)
    
#......  .//...  





    summarizable = [f for f in files if should_summarize(f["file"], f["content"])]

    for i, f in enumerate(summarizable):
        progress_bar.progress((i + 1) / max(len(summarizable), 1))
        summary = create_file_summary(f["file"], f["content"], ask_llm)
        file_summaries.append(summary)

    # STEP 5: REPO SUMMARY
    status_text.text("Building repo overview...")
    tree = build_tree(repo_path)
    
    #/////
    s3.upload_json(
    {"tree": tree},
    f"{repo_name}/repo_tree.json"
)
    
    #//////
    
    
    repo_summary = create_repo_summary(repo_path, file_summaries, tree, ask_llm)
    s3.upload_json(
    repo_summary,
    f"{repo_name}/repo_summary.json"
)

    # STEP 6: COMBINE
    all_chunks = code_chunks + file_summaries + [repo_summary]

    # STEP 7: EMBEDDINGS
    status_text.text("Creating embeddings...")
    vectors = []
    metadata = []

    for c in all_chunks:
        vectors.append(get_embedding(c["text"]))
        metadata.append(c)

    # STEP 8: VECTOR STORE
    store = VectorStore()
    store.build(vectors, metadata)
    
    
    
    
    
    #.....//.....
    os.makedirs("cache", exist_ok=True)

    store.save("cache")
    
    
    s3.upload_file(
    "cache/faiss.index",
    f"{repo_name}/faiss.index"
)

    s3.upload_file(
    "cache/metadata.pkl",
    f"{repo_name}/metadata.pkl"
)
    
    #.....//....






    status_text.text("Pipeline ready ✅")

    return store, tree


# -----------------------------
# STREAMLIT UI
# -----------------------------

st.set_page_config(page_title="RAG Repo Chat", layout="wide")

st.title("📦 GitHub Repo RAG Chatbot")

repo_url = st.text_input("Enter GitHub Repo URL")

col1, col2 = st.columns([1, 2])

if "store" not in st.session_state:
    st.session_state.store = None
    st.session_state.tree = None

if st.button("Build Index"):
    if not repo_url:
        st.error("Please enter a repo URL")
    else:
        progress = st.progress(0)
        status = st.empty()

        try:
            store, tree = build_pipeline(repo_url, progress, status)
            st.session_state.store = store
            st.session_state.tree = tree
            st.success("Index built successfully!")
        except Exception as e:
            st.error(str(e))


# -----------------------------
# SHOW STRUCTURE
# -----------------------------

if st.session_state.tree:
    with st.expander("📁 Repo Structure"):
        st.code(st.session_state.tree)


# -----------------------------
# CHAT UI
# -----------------------------

st.subheader("💬 Ask Questions about Repo")

query = st.text_input("Ask something")

if st.button("Ask"):
    if not st.session_state.store:
        st.warning("Please build index first")
    else:
        if query.strip():
            try:
                answer = run_rag(query, st.session_state.store)
                st.markdown("### Answer")
                st.write(answer)
            except Exception as e:
                st.error(str(e))