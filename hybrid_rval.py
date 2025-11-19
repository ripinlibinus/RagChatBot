# chain5.py — Hybrid Retrieval (SQL + Vector) + SQL-First Top-5 (tanpa rerank)
from dotenv import load_dotenv

from typing import Dict, List, Iterable
import os, re, ast, time, json
import numpy as np

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_chroma import Chroma
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnableBranch
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.callbacks import get_openai_callback

from helper import post_query, jakarta_time_greeting
from rich import print
from operator import itemgetter
from itertools import islice

load_dotenv()

# ====== ENV & CONST ======
PERSIST_DIR      = os.getenv("CHROMA_DIR", "chroma/metaproperty")
COLLECTION_NAME  = os.getenv("CHROMA_COLLECTION", "metaproperty")
DATA_API_URL     = os.getenv("DATA_API_URL", "").rstrip("/")
API_TOKEN        = os.getenv("API_TOKEN", "")
FETCH_PROPERTY_URL = DATA_API_URL + "/query_listing"
STORE_HISTORY_URL  = DATA_API_URL + "/chat_history"

# ====== GLOBALS ======
report_param: Dict = {}

# ====== HISTORY STORES ======
_session_store: Dict[str, ChatMessageHistory] = {}
def get_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in _session_store:
        _session_store[session_id] = ChatMessageHistory()
    return _session_store[session_id]

_query_session_store: Dict[str, ChatMessageHistory] = {}
def get_query_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in _query_session_store:
        _query_session_store[session_id] = ChatMessageHistory()
    return _query_session_store[session_id]

def serialize_history(hist_obj: BaseChatMessageHistory, turns: int = 10) -> str:
    if not hist_obj or not getattr(hist_obj, "messages", None):
        return ""
    msgs = hist_obj.messages[-2*turns:]
    lines = []
    for m in msgs:
        role = "Human" if m.type in ("human", "user") else "AI"
        try:
            content = m.content if isinstance(m.content, str) else json.dumps(m.content, ensure_ascii=False)
        except Exception:
            content = str(m.content)
        lines.append(f"{role}: {content}")
    return "\n".join(lines)

def prev_param(hist_obj: BaseChatMessageHistory):
    jumlah = len(hist_obj.messages)
    if jumlah > 0:
        return hist_obj.messages[jumlah-2].content

# ====== MODELS ======
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
emb = OpenAIEmbeddings(model="text-embedding-3-small")

# ====== CHROMA / RETRIEVER ======
vectordb = Chroma(
    persist_directory=PERSIST_DIR,
    collection_name=COLLECTION_NAME,
    embedding_function=emb
)

retriever = vectordb.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={
        "k": 1500,
        "score_threshold": 0.35
    },
)

# ====== PROMPTS ======
contextualize_q_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Ubahlah pertanyaan berikut menjadi satu kalimat mandiri. "
     "Manfaatkan HISTORY chat bila ada. Jangan menjawab; keluarkan hanya pertanyaannya. "
     "Buat kalimat pertanyaan sebagai user dan ikut gaya bahasa HISTORY CHAT."
    ),
    ("system", "HISTORY CHAT:\n{history_chat}\n"),
    ("human", "{question}")
])

def rewrite_chain(x):
    q = x["question"]
    hist_chat = x.get("history_chat")
    chain = contextualize_q_prompt | llm | StrOutputParser()
    rq = chain.invoke({"question": q, "history_chat": hist_chat})
    print("\n[bold green]Membuat pertanyaan versi mandiri (rewrite) ...[/bold green]")
    print(f"[bold green]Rewrite: {rq}[/bold green]\n")
    return rq

classifier_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Klasifikasikan pertanyaan ke salah satu kategori: \n"
     "1. Pencarian/rekomendasi properti \n"
     "2. Update data properti (ubah harga/status/dll) \n"
     "3. Salam/sapaan \n"
     "4. Lainnya\n"
     "Jawab hanya angka kategori."
    ),
    ("human", "{rewrite_question}")
])

def classifier(x):
    rq = x["rewrite_question"]
    chain = classifier_prompt | llm | StrOutputParser()
    cls = chain.invoke({"rewrite_question": rq})
    mapping = {"1":"Pencarian", "2":"Update data", "3":"Salam", "4":"Lainnya"}
    print(f"[bold green]Klasifikasi: {mapping.get(cls,'Lainnya')}[/bold green]\n")
    return cls

greeting_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Anda adalah AI Asisten Meta Property. Sapa singkat sesuai {time_greeting}. "
     "Kenalkan diri singkat dan tanya kebutuhan. Hindari tanda seru (!). "
     "Nama user {user_name}. Jika bukan 'guest', panggil 'kk {user_name}'. "
     "Jangan ulang salam jika sudah ada di HISTORY CHAT."
    ),
    ("system", "HISTORY CHAT:\n{history_chat}"),
    ("human", "{question}")
])
greeting_chain = greeting_prompt | llm | StrOutputParser()

# JSON conversion untuk SQL filter (adapt dari chain4, paginate=20)
json_convertion_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Ubah kalimat pencarian properti menjadi JSON dengan kunci berikut (isi hanya jika ada nilainya): "
     "alamat, keyword (maks 2 token lokasi), harga_min, harga_max, kamar_tidur, lebar_bangunan, "
     "luas_bangunan, jumlah_tingkat, luas_tanah, kondisi, tipe_listing(1/2/3), jenis_properti(1..6), mata_angin. "
     "Aturan harga: 'dibawah X' => harga_max=X; 'X–Y' => range min/max; 'sekitar' => ±20%. "
     "Gunakan pengetahuan umum lokasi (tanpa negara/provinsi/kota/suffix 'komplek/cluster'). "
     "Balas HANYA JSON valid. "
     "HISTORY JSON sebelumnya: {history_query}"
    ),
    ("human", "{rewrite_question}")
])

json_convertion_chain = RunnableParallel(
    json_query = json_convertion_prompt | llm | JsonOutputParser(),
    rewrite_question = itemgetter("rewrite_question"),
    question = itemgetter("question"),
    session_id = itemgetter("session_id"),
    history_query = itemgetter("history_query")
)

def normalize_dict(d: dict) -> dict:
    out = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        out[k] = v
    return out

def fetch_sql(x):
    """Panggil API SQL dengan paginate=20 + dukung pagination lanjutan bila param sama."""
    url = FETCH_PROPERTY_URL
    param = x["json_query"] or {}
    rq = x["rewrite_question"]

    # pagination logic (lanjut page jika filter sama dg sebelumnya)
    query_hist = get_query_history(x["session_id"])
    prev = prev_param(query_hist)

    # Set default paginate=20
    param["paginate"] = 20
    if "page" not in param:
        param["page"] = 1

    if prev:
        try:
            prev_obj = ast.literal_eval(prev)
            last_page = prev_obj.get("page", 1)
            # Hilangkan page/paginate dari prev utk banding nilai filter
            pprev = {k:v for k,v in prev_obj.items() if k not in ("page", "paginate")}
            if normalize_dict(pprev) == normalize_dict({k:v for k,v in param.items() if k not in ("page","paginate")}):
                param["page"] = last_page + 1
        except Exception:
            pass

    print("[bold green]JSON Filter SQL:[/bold green]", param, "\n")
    result = post_query(url, param, API_TOKEN)

    # simpan history query
    query_hist.add_ai_message(str(param))
    query_hist.add_user_message(rq)

    txt = result.text or ""
    if txt.strip():
        print("[bold green]SQL: ditemukan data[/bold green]\n")
    else:
        print("[bold green]SQL: tidak ditemukan data[/bold green]\n")
    return txt

def split_sql_blocks(sql_text: str) -> List[str]:
    """Pisahkan listing berdasarkan delimiter '---------' dan newline."""
    if not sql_text:
        return []
    parts = [p.strip() for p in re.split(r"-{5,}\s*", sql_text) if p.strip()]
    return parts

def fetch_vector(x):
    query = x["rewrite_question"]
    print("[bold green]Vector: mencari dokumen relevan ...[/bold green]\n")
    docs = retriever.invoke(query)
    print(f"[bold green]Vector: ditemukan {len(docs)} dokumen[/bold green]\n")
    # ambil konten (batasi 100 biar efisien)
    out = []
    for d in islice(docs, 100):
        pc = getattr(d, "page_content", None)
        if pc:
            s = str(pc).strip()
            if s:
                out.append(s)
    return out

def extract_link(text: str) -> str:
    m = re.search(r"https?://\S+", text)
    return m.group(0).rstrip(".,)") if m else ""

def _head_key(s: str) -> str:
    return s.splitlines()[0][:120].strip().lower() if s else ""

def _make_key(s: str) -> str:
    return extract_link(s) or _head_key(s)

def dedupe_by_link_or_head(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        key = _make_key(it)
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out

# (Masih disimpan bila suatu saat mau dipakai lagi, tapi TIDAK dipanggil)
def embed_batch(texts: List[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 1536), dtype=np.float32)
    vecs = emb.embed_documents(texts)
    return np.array(vecs, dtype=np.float32)

def cosine_sim(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    # a: (n,d), b: (d,)
    if a.size == 0:
        return np.array([])
    an = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    bn = b / (np.linalg.norm(b) + 1e-9)
    return an @ bn

# ====== NEW: SQL-first selector (tanpa rerank) ======
def fetch_hybrid_sql_first_top5(x):
    """
    Ambil kandidat dari SQL lebih dulu (pertahankan urutan SQL).
    Jika total < 5, isi dari hasil Vector (urutan asli retriever) sampai genap 5.
    Tanpa semantic rerank. Dedup lintas sumber berdasar link/head.
    """
    rq = x["rewrite_question"]
    sql_text = x["sql_text"]
    vec_items = x["vec_items"]

    sql_blocks = split_sql_blocks(sql_text)
    sql_blocks = dedupe_by_link_or_head(sql_blocks)
    vec_items = dedupe_by_link_or_head(vec_items)

    print(f"[bold green]Kandidat SQL: {len(sql_blocks)} | Kandidat Vector: {len(vec_items)}[/bold green]")

    # Kumpulkan Top-5: SQL dulu, sisanya dari Vector
    selected = []
    seen_keys = set()

    def try_add(item):
        key = _make_key(item)
        if not key:
            # tetap dedupe berdasarkan head meski tanpa link
            key = _head_key(item)
        if key in seen_keys:
            return False
        seen_keys.add(key)
        selected.append(item)
        return True

    # 1) Ambil dari SQL, sesuai urutan SQL
    for it in sql_blocks:
        if len(selected) >= 5:
            break
        try_add(it)

    # 2) Jika masih kurang dari 5, isi dari Vector
    if len(selected) < 5:
        for it in vec_items:
            if len(selected) >= 5:
                break
            try_add(it)

    print(f"[bold green]Top-5 (SQL-first, no rerank): {len(selected)} item[/bold green]\n")

    fused_text = "\n\n".join(selected)
    report_param["doc"] = fused_text
    report_param["sql_count"] = len(sql_blocks)
    report_param["vector_count"] = len(vec_items)
    report_param["selected_count"] = len(selected)
    return fused_text

property_finder_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Anda adalah AI Asisten Meta Property. Jawab ringkas, padat, sopan. "
     "Modifikasi markdown: *bold* gunakan tanda bintang satu (bukan dua), tanpa [teks](url). "
     "Jika ada link, tulis URL polos. Jangan tampilkan Google Maps kecuali diminta."
    ),
    ("human",
     "Jawab pertanyaan berikut berdasarkan Data Property. "
     "Pertanyaan: {question}\n\n"
     "Data Property (Top-5 SQL-first hybrid):\n"
     "{data_property}\n\n"
     "Jika tidak ada data relevan, jawab jujur belum menemukan dan tawarkan ubah kriteria."
    )
])

# ====== BRANCHES ======
def coming_soon(_):
    return "Maaf, fitur ini masih pengembangan. Hubungi Admin atau kunjungi https://www.metaproperty.co.id"

fetch_sql_chain = json_convertion_chain | RunnableLambda(fetch_sql)
fetch_vector_chain = RunnableParallel(rewrite_question=itemgetter("rewrite_question")) | RunnableLambda(fetch_vector)

hybrid_chain = RunnableParallel(
    rewrite_question = itemgetter("rewrite_question"),
    question        = itemgetter("question"),
    session_id      = itemgetter("session_id"),
    sql_text        = fetch_sql_chain,
    vec_items       = fetch_vector_chain,
) | RunnableParallel(
    question        = itemgetter("question"),
    data_property   = RunnableLambda(fetch_hybrid_sql_first_top5)   # << pakai selector baru (tanpa rerank)
) | property_finder_prompt | llm | StrOutputParser()

fallback_prompt = ChatPromptTemplate.from_messages([
    ("system",
     "Anda adalah AI Asisten Meta Property. Jawab sopan, relevan dengan konteks properti. "
     "Jika di luar konteks, sampaikan halus dan arahkan kembali. Hindari tanda seru (!). "
     "Modifikasi markdown: *bold* pakai bintang satu, bullet tetap, tanpa [teks](url), link tulis polos."
    ),
    ("system", "HISTORY CHAT:\n{history_chat}"),
    ("human", "{question}")
])
fallback_chain = fallback_prompt | llm | StrOutputParser()

classifier_branches = RunnableBranch(
    (lambda x: x["cls"] == "3", greeting_chain),
    (lambda x: x["cls"] == "1", hybrid_chain),          # << hybrid SQL-first + no rerank
    (lambda x: x["cls"] == "2", RunnableLambda(coming_soon)),
    fallback_chain
)

classifier_chain = RunnableParallel(
    cls              = RunnableLambda(classifier),
    rewrite_question = itemgetter("rewrite_question"),
    question         = itemgetter("question"),
    history_chat     = itemgetter("history_chat"),
    history_query    = itemgetter("history_query"),
    time_greeting    = itemgetter("time_greeting"),
    user_name        = itemgetter("user_name"),
    session_id       = itemgetter("session_id"),
)

rewrite_context_chain = RunnableParallel(
    rewrite_question = RunnableLambda(rewrite_chain),
    question         = itemgetter("question"),
    history_chat     = itemgetter("history_chat"),
    history_query    = itemgetter("history_query"),
    time_greeting    = itemgetter("time_greeting"),
    user_name        = itemgetter("user_name"),
    session_id       = itemgetter("session_id"),
)

chain = rewrite_context_chain | classifier_chain | classifier_branches

# ====== PUBLIC FUNCS ======
def build_chain(data):
    start = time.perf_counter()
    session_id = data["session_id"]
    question = data["question"]

    hist = get_history(session_id)
    last_history = serialize_history(hist, 10)
    qhist = get_query_history(session_id)
    last_q = prev_param(qhist)

    with get_openai_callback() as cb:
        answer = chain.invoke({
            "session_id": session_id,
            "question": question,
            "history_chat": last_history,
            "history_query": last_q,
            "time_greeting": jakarta_time_greeting(),
            "user_name": data.get("user_name","guest")
        })

    hist.add_user_message(question)
    hist.add_ai_message(answer)

    elapsed_ms = (time.perf_counter() - start) * 1000
    store_data = {
        "chat_session_id": session_id,
        "human": question,
        "ai": answer,
        "method": "hybrid",
        "input_token": cb.prompt_tokens,
        "output_token": cb.completion_tokens,
        "total_token": cb.total_tokens,
        "response_count": cb.successful_requests,
        "response_time": elapsed_ms,
        "cost_usd": cb.total_cost,
        "cost_idr": cb.total_cost * 17000,
    }
    post_query(STORE_HISTORY_URL, store_data, API_TOKEN)

    print("[bold blue]\n======== RINCIAN TOKEN ========")
    print(f"[bold blue]Total    : {cb.total_tokens}[/bold blue]")
    print(f"[bold blue]Input    : {cb.prompt_tokens}[/bold blue]")
    print(f"[bold blue]Output   : {cb.completion_tokens}[/bold blue]")
    print(f"[bold blue]Requests : {cb.successful_requests}[/bold blue]")
    print(f"[bold blue]Cost USD : {round(cb.total_cost,4)}[/bold blue]")
    print(f"[bold blue]Cost IDR : {round(cb.total_cost*17000,2)}[/bold blue]")
    print(f"[bold blue]Latency  : {elapsed_ms:.1f} ms[/bold blue]")
    print("[bold blue]==============================\n")
    return answer

def build_chain_test(data):
    start = time.perf_counter()
    session_id = data["session_id"]
    question = data["question"]

    hist = get_history(session_id)
    last_history = serialize_history(hist, 10)
    qhist = get_query_history(session_id)
    last_q = prev_param(qhist)

    with get_openai_callback() as cb:
        answer = chain.invoke({
            "session_id": session_id,
            "question": question,
            "history_chat": last_history,
            "history_query": last_q,
            "time_greeting": jakarta_time_greeting(),
            "user_name": data.get("user_name","guest")
        })

    hist.add_user_message(question)
    hist.add_ai_message(answer)

    elapsed_ms = (time.perf_counter() - start) * 1000

    report_param["chat_session_id"] = session_id
    report_param["human"] = question
    report_param["ai"] = answer
    report_param["gold"] = data.get("gold")
    report_param["method"] = "hybrid"
    report_param["input_token"] = cb.prompt_tokens
    report_param["output_token"] = cb.completion_tokens
    report_param["total_token"] = cb.total_tokens
    report_param["response_count"] = cb.successful_requests
    report_param["response_time"] = elapsed_ms
    report_param["cost_usd"] = cb.total_cost
    report_param["cost_idr"] = cb.total_cost * 17000

    print("[bold blue]\n======== RINCIAN TOKEN (TEST) ========")
    print(f"[bold blue]Total    : {cb.total_tokens}[/bold blue]")
    print(f"[bold blue]Input    : {cb.prompt_tokens}[/bold blue]")
    print(f"[bold blue]Output   : {cb.completion_tokens}[/bold blue]")
    print(f"[bold blue]Requests : {cb.successful_requests}[/bold blue]")
    print(f"[bold blue]Cost USD : {round(cb.total_cost,4)}[/bold blue]")
    print(f"[bold blue]Cost IDR : {round(cb.total_cost*17000,2)}[/bold blue]")
    print(f"[bold blue]Latency  : {elapsed_ms:.1f} ms[/bold blue]")
    print("[bold blue]=====================================\n")

    return report_param

if __name__ == "__main__":
    # Quick sanity test (opsional)
    ans = build_chain({
        "session_id": "111",
        "question": "Listing yang ada video tur (virtual tour) di Johor, 3 kamar, 900 jt – 1,3 M",
        "user_name": "Tester"
    })
    print(ans)
