#rag dengan vector db
from dotenv import load_dotenv

from typing import Dict, List, Tuple
import os

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_chroma import Chroma
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.runnables import RunnableBranch
from langchain_community.callbacks import get_openai_callback
from langchain_core.output_parsers import JsonOutputParser
from helper import token_usage_calculator, post_query, text_to_json
from rich import print
from langchain_community.callbacks import get_openai_callback
import time
from itertools import islice
from typing import Iterable

from operator import itemgetter
import json

from helper import jakarta_time_greeting

load_dotenv()

PERSIST_DIR = "chroma/realestate"
COLLECTION_NAME = "realestate"
DATA_API_URL = os.getenv("DATA_API_URL")
API_TOKEN = os.getenv("API_TOKEN")
STORE_HISTORY_URL = DATA_API_URL + "/chat_history"

report_param = {}

_session_store: Dict[str, ChatMessageHistory] = {}
def get_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in _session_store:
        _session_store[session_id] = ChatMessageHistory()
    return _session_store[session_id]


def coming_soon(x):
    return "Maaf, fitur ini masih dalam tahap pengembangan. Silahkan hubungi Admin atau kunjungi www.metaproperty.co.id ."

def serialize_history(hist_obj: BaseChatMessageHistory, turns: int = 10) -> str:
    """
    Ambil 10 percakapan terakhir (user+AI = 2 pesan x 10 = 20 messages)
    dan ubah jadi transcript teks sederhana: "Human: ..." / "AI: ..."
    """
    if not hist_obj or not getattr(hist_obj, "messages", None):
        return ""
    msgs = hist_obj.messages[-2*turns:]  # 10 percakapan terakhir
    lines = []
    for m in msgs:
        role = "Human" if m.type in ("human", "user") else "AI"
        try:
            content = m.content if isinstance(m.content, str) else json.dumps(m.content, ensure_ascii=False)
        except Exception:
            content = str(m.content)
        lines.append(f"{role}: {content}")
    return "\n".join(lines)

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

contextualize_q_prompt = ChatPromptTemplate.from_messages([
        (   
            "system",
            "Ubahlah pertanyaan berikut menjadi satu kalimat mandiri."
            "Memanfaatkan HISTORY chat bila ada. Jangan menjawab; keluarkan hanya pertanyaannya."
            "Buatlah kalimat pertanyaan dengan posisi anda adalah user. "
            "Ikuti gaya bicara dan bahasa sesuai HISTORY CHAT."
        ),
        (
            "system",
            "berikut ini adalah HISTORY CHAT : \n "
            "{history_chat} \n"
        ),
        ("human", "{question}")
    ])

def rewrite_chain(x):
    q = x['question']
    hist_chat = x.get("history_chat")  
    history_context = contextualize_q_prompt | llm | StrOutputParser()
    hist_chain = history_context.invoke({"question":q, "history_chat":hist_chat})
    
    print("\n[italic bold green]Membaca histori chat sebelumnya... [/italic bold green]\n")
    print(f"[italic bold green]{hist_chat if hist_chat else 'Tidak ada history chat'}[/italic bold green]\n")
    print("[italic bold green]Membuat pertanyaan baru (history context)... [/italic bold green]\n")
    print(f"[italic bold green]hasil pertanyaan baru (history): {hist_chain} [italic bold green]\n" ) 
    
    return hist_chain

classifier_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        # "Hubungkan konteks pertanyaan user dan HISTORY CHAT nya."
        "Klasifikasikan pertayaan user ke dalam salah satu kategori berikut: \n"
        "1. Minta informasi properti, pencarian properti, rekomendasi properti. \n"
        "2. Mau melakukan perumahan data properti yang sudah ada di website atau aplikasi. ( misal perubahan harga, status, atau detail lainnya) \n"
        "3. Salam, Perkenalan, Sapaan pembuka. \n"
        "4. Lainnya. \n"
    ),
    (
        "system",
        "Jawab hanya dalam bentuk angka saja, misal 1 atau 2 atau 3 sesuai kategori di atas. "
    ),
    # (
    #     "system",
    #     "Berikut adalah HISTORY CHAT yang ada : \n"
    #     "{history_chat}"
    # ),
    ("human", "{rewrite_question}")
])

def classifier(x):
    rewrite_question = x['rewrite_question'] 
    chain = classifier_prompt | llm | StrOutputParser()
    cls = chain.invoke({"rewrite_question":rewrite_question})

    if(cls == "1"):
        classification  = "(1) Minta informasi properti, pencarian properti, rekomendasi properti."
    elif(cls == "2"):
        classification  = "(2) Mau melakukan update data properti yang sudah ada, misal perubahan harga, status, atau detail lainnya."
    elif(cls == "3"):
        classification  = "(3) Sapaan pembuka."
    else:
        classification  = "Lainnya."
    
    print("[italic bold green]Melakukan klasifikasi pertanyaan... [/italic bold green]\n")
    print("[italic bold green]Hasil Klasifikasi : " + classification + " [/italic bold green]\n")
    
    return cls

greeting_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Anda adalah AI Asisten Meta Property, tugas anda adalah menjadi asisten , admin nya agent (broker) meta property."
        "Layanan yang dapat anda beri seperti : mencari property, merubah data properti ke website, tanya jawab pertanyaan tentang properti, memberi inspirasi cara penjualan properti. "
        "Beri jawaban dengan gaya percakapan dan bahasa yang sesuai dengan user, tetapi harus tetap sopan dan profesional. "
        "NAMA USER adalah {user_name}. "
        "Jika NAMA USER bukan guest, sapa nama nya dengan panggilan kk {user_name}."
        "Berikan salam pembuka dengan {time_greeting} HANYA JIKA belum ada salam pada HISTORY CHAT."
        "Perkenalkan singkat tentang dirimu secara singkat. "
        "Tanyakan apa yang bisa dibantu saat ini. "
        "Tambahkan emoji pada akhir kalimat, pelajari HISTORY CHAT supaya jangan setiap balasan menggunakan emoji. \n"
        "Jika sudah ada HISTORY CHAT, sesuaikan kembali konteksnya untuk menjawab. \n"
        "Buat pertanyaan supaya user memberitahu keperluannya. "
    ),
    (
        "system",
        "Jangan menambahkan kalimat yang panjang lebar, cukup salam dan perkenalan singkat 1 kalimat. "
        "Jangan berikan salam {time_greeting} jika sudah ada pada HISTORY CHAT."
        "Hindari tanda seru (!) dalam jawaban. "
    ),
    (
        "system",
        "Berikut adalah HISTORY CHAT yang ada : \n"
        "{history_chat}"
    ),
    ("human", "{question}")
])

greeting_chain = greeting_prompt | llm | StrOutputParser()

vectordb = Chroma(
        persist_directory=PERSIST_DIR,
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
    )

# retriever =vectordb.as_retriever(
#     search_type="similarity_score_threshold",
#     search_kwargs={
#         "k": 200, 
#         "score_threshold": 0.3,
#         # "filter" : {"price": {"$lt": 1000_000_000}}
#     },
# )

retriever =vectordb.as_retriever(
    search_type="similarity",
    search_kwargs={
        "k": 10, 
    },
)

# retriever = vectordb.as_retriever(
#         search_type="mmr",
#         search_kwargs={
#             "k": 10, 
#             "fetch_k": 100, 
#             "lambda_mult": 0.35,
#             # "filter" : {"price": {"$lt": 1000_000_000}}
#         },
# )

def join_page_contents(relevant_docs: Iterable, limit: int = 15 ) -> str:
    """
    Gabungkan field `page_content` dari setiap doc jadi satu string,
    dipisah dengan 2 newline.
    - Abaikan doc yang tidak punya/empty `page_content`.
    - Trim spasi di awal/akhir tiap potongan.
    - Ambil maksimal `limit` dokumen pertama.
    """
    chunks = []
    for doc in islice(relevant_docs, limit):
        # dukung objek mirip LangChain Document (punya .page_content)
        content = getattr(doc, "page_content", None)
        if content:
            text = str(content).strip()
            if text:
                chunks.append(text)
    return "\n\n".join(chunks)

def fetch_relevant_docs(x):
    query = x['rewrite_question']
    question = x['question']

    print("[italic bold green]Mencari document yang sesuai ... [/italic bold green]\n")
    relevant_docs = retriever.invoke(query)
    count = len(relevant_docs)

    print(f"[italic bold green]Menemukan {count} document yang sesuai ... [/italic bold green]\n")
    data_property = join_page_contents(relevant_docs, limit=15)

    report_param["doc"] = data_property

    print(f"[italic bold green]{'Menemukan document properti...' if count > 0 else 'Tidak menemukan document properti'}[/italic bold green]\n")
    print(f"[italic bold green]Document : \n{data_property} [/italic bold green]\n")
    print("[italic bold green]Menyiapkan jawaban kepada user ... [/italic bold green]\n")

    return {"question" : question, "data_property" : data_property}

property_finder_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Anda adalah AI Asisten Meta Property, tugas anda adalah menjadi asisten , admin nya agent (broker) meta property."
        "Layanan yang dapat anda beri seperti : mencari property, merubah data properti ke website (coming soon), tanya jawab pertanyaan tentang properti, memberi inspirasi cara penjualan properti. "
        "Beri jawaban dengan gaya percakapan dan bahasa yang sesuai dengan user, tetapi harus tetap sopan dan profesional. "
        "Tambahkan emoji pada akhir kalimat, pelajari HISTORY CHAT supaya jangan setiap balasan menggunakan emoji. "
    ),
    (   "system",
        "Modifikasi Markdown menjadi aturan berikut: \n"
        "**bold** diganti menjadi *bold*, bullet tetap ada, tanpa `[teks](url)`. "
        "Jika ada link, tulis sebagai URL polos, contoh: Link: https://contoh.com"
    ),
    (
        "human", 
        "Jawablah pertanyaan berikut ini berdasarkan Data Property yang ada. \n"
        "Berikan jawaban yang ringkas, tepat dan padat. Berikan maksimal 5 pilihan property yang paling sesuai. \n"
        "Jangan menampilkan googlemap link jika tidak diminta. \n"
        "Wajib tampilkan link ke website yang diterakan di Data Property. \n"
        "Pertanyaan : {question} \n"
        "Data Property : \n"
        "{data_property} \n"
        "Jika tidak ada data, jawab dengan jujur tidak menemukan data yang dicari. \n"
        "Tanyakan apakah ada kata kunci lain yang ingin dicari atau tawarkan perubahan kriteria pencarian lain. \n"
    )
]) 

fetch_property_chain = RunnableParallel(
    data_property = RunnableLambda(fetch_relevant_docs),
    question = itemgetter("question")
)

fallback_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Anda adalah AI Asisten Meta Property, tugas anda adalah menjadi asisten , admin nya agent (broker) meta property."
        "Layanan yang dapat anda beri seperti : mencari property, merubah data properti ke website, tanya jawab pertanyaan tentang properti, memberi inspirasi cara penjualan properti. "
        "Beri jawaban dengan gaya percakapan dan bahasa yang sesuai dengan user, tetapi harus tetap sopan dan profesional. "
        "Tambahkan emoji pada akhir kalimat, pelajari HISTORY CHAT supaya jangan setiap balasan menggunakan emoji. "
    ),
    (   
        "system",
        "Pelajari HISTORY CHAT untuk membangun komunikasi yang lebih bersahabat."
        "Anda bisa membalas dengan pertanyaan untuk mendapatkan info yang lebih lengkap supaya anda bisa membantu menemukan jawaban."
        "KONTEKS anda hanya pada Asisten Meta Property, perusahaan agensi broker properti."
        "Jika pertanyaan {rewrite_question} diluar KONTEKS atau pengetahuan Property, sampaikan dengan sopan dan halus. lalu arahkan ke tugas yang dapat kamu layani. \n"
        "Hindari tanda seru (!) dalam jawaban. "
    ),
    (   
        "system",
        "Modifikasi Markdown menjadi aturan berikut: \n"
        "**bold** diganti menjadi *bold*, bullet tetap ada, tanpa `[teks](url)`. "
        "Jika ada link, tulis sebagai URL polos, contoh: Link: https://contoh.com"
    ),
    (
        "system",
        "berikut ini adalah HISTORY CHAT : \n "
        "{history_chat} \n"
    ),
    ("human", "{question}")
]) 

classifier_branches = RunnableBranch(
    (
        lambda x: x['cls'] == "3",
        greeting_chain
    ),
    (
        lambda x: x['cls'] == "1",
        fetch_property_chain 
        | property_finder_prompt 
        | llm
        | StrOutputParser()
    ),
    (
        lambda x: x['cls'] == "2",
        RunnableLambda(coming_soon)
    ),
    fallback_prompt | llm | StrOutputParser()  
)

classifier_chain = RunnableParallel(
    cls = RunnableLambda(classifier),
    rewrite_question = itemgetter("rewrite_question"),
    question = itemgetter("question"),
    history_chat = itemgetter("history_chat"),
    time_greeting = itemgetter("time_greeting"),
    user_name = itemgetter("user_name")
)

rewrite_context_chain = RunnableParallel(
    rewrite_question = RunnableLambda(rewrite_chain),
    question = itemgetter("question"),
    history_chat = itemgetter("history_chat"),
    time_greeting = itemgetter("time_greeting"),
    user_name = itemgetter("user_name")
)

chain = rewrite_context_chain | classifier_chain | classifier_branches



def build_chain(data):
    start = time.perf_counter()
    session_id = data['session_id']
    question = data['question']
    history = get_history(session_id)
    last_history = serialize_history(history,10)

    with get_openai_callback() as cb:
        answer = chain.invoke({
            "session_id": session_id,
            "question": question,
            "history_chat": last_history,
            "time_greeting": jakarta_time_greeting(),
            "user_name": data['user_name']
        })

    history.add_user_message(question)
    history.add_ai_message(answer)

    elapsed_ms = (time.perf_counter() - start) * 1000

    store_data = {
        "chat_session_id" : session_id,
        "human" : question,
        "ai" : answer,
        "method" : 'vector-similarity',
        "input_token" : cb.prompt_tokens,
        "output_token" : cb.completion_tokens,
        "total_token" : cb.total_tokens,
        "response_count" : cb.successful_requests,
        "response_time" : elapsed_ms,
        "cost_usd" : cb.total_cost,
        "cost_idr" : cb.total_cost * 17000,
    }
    
    post_query(STORE_HISTORY_URL,store_data,API_TOKEN)

    print("[italic bold blue]\n======== RINCIAN PEMAKAIAN TOKEN =============[/italic bold blue]")
    print(f"[italic bold blue]Total Token : {cb.total_tokens}[/italic bold blue]")
    print(f"[italic bold blue]Input Token : {cb.prompt_tokens}[/italic bold blue]")
    print(f"[italic bold blue]Output Token : {cb.completion_tokens}[/italic bold blue]")
    print(f"[italic bold blue]Request Count : {cb.successful_requests}[/italic bold blue]")
    print(f"[italic bold blue]Cost (USD) : {round(cb.total_cost,4)}[/italic bold blue]")
    print(f"[italic bold blue]Cost (IDR) : {round((cb.total_cost * 17000),2)}[/italic bold blue]")
    print(f"[italic bold blue]Total response time: {elapsed_ms:.1f} ms[/italic bold blue]")
    print("[italic bold blue]===============================================[/italic bold blue]\n")
    

    return answer

def build_chain_test(data):
    start = time.perf_counter()
    session_id = data['session_id']
    question = data['question']
    history = get_history(session_id)
    last_history = serialize_history(history,10)

    with get_openai_callback() as cb:
         answer = chain.invoke({
            "session_id": session_id,
            "question": question,
            "history_chat": last_history,
            "time_greeting": jakarta_time_greeting(),
            "user_name": data['user_name']
        })

    
    history.add_user_message(question)
    history.add_ai_message(answer)

    elapsed_ms = (time.perf_counter() - start) * 1000

    report_param["chat_session_id"] = session_id
    report_param["human"] = question
    report_param["ai"] = answer
    report_param["gold"] = data['gold'] 
    report_param["method"] = 'vector-similarity'
    report_param["input_token"] = cb.prompt_tokens
    report_param["output_token"] = cb.completion_tokens
    report_param["total_token"] = cb.total_tokens
    report_param["response_count"] = cb.successful_requests
    report_param["response_time"] = elapsed_ms
    report_param["cost_usd"] = cb.total_cost
    report_param["cost_idr"] = cb.total_cost * 17000

    print("[italic bold blue]\n======== RINCIAN PEMAKAIAN TOKEN =============[/italic bold blue]")
    print(f"[italic bold blue]Total Token : {cb.total_tokens}[/italic bold blue]")
    print(f"[italic bold blue]Input Token : {cb.prompt_tokens}[/italic bold blue]")
    print(f"[italic bold blue]Output Token : {cb.completion_tokens}[/italic bold blue]")
    print(f"[italic bold blue]Request Count : {cb.successful_requests}[/italic bold blue]")
    print(f"[italic bold blue]Cost (USD) : {round(cb.total_cost,4)}[/italic bold blue]")
    print(f"[italic bold blue]Cost (IDR) : {round((cb.total_cost * 17000),2)}[/italic bold blue]")
    print(f"[italic bold blue]Total response time: {elapsed_ms:.1f} ms[/italic bold blue]")
    print("[italic bold blue]===============================================[/italic bold blue]\n")
    
    # return answer
    return report_param



def query_chain():
    x = {
        "question" : "cari rumah di cemara",
        "rewrite_question" : "cari rumah daerah cemara atau ringroad",
    }
    answer = fetch_relevant_docs(x)
    return answer



if __name__ == "__main__":
    ans = build_chain({
        "session_id": "1234",
        "question": "cari rumah full furnished yang harganya dibawah 1 M dalam komplek dengan fasilitas lapangan basket",
        "user_name": "Tester",
        "gold": '{ "keyword": "medan", "info_lainnya":"cctv" }'
    })
    print(ans)














