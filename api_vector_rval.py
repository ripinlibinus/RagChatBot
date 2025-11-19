#api_rval.py
#rag dengan mysql
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
from helper import doc_to_json, post_query, text_to_json, jakarta_time_greeting
from rich import print
from itertools import islice
from typing import Iterable
from langchain_community.callbacks import get_openai_callback
import time



from operator import itemgetter
import ast, json

from helper import jakarta_time_greeting

load_dotenv()

DATA_API_URL = os.getenv("DATA_API_URL")
API_TOKEN = os.getenv("API_TOKEN")
FETCH_PROPERTY_URL = DATA_API_URL + "/query_listing"
STORE_HISTORY_URL = DATA_API_URL + "/chat_history"

PERSIST_DIR = "chroma/metaproperty"
COLLECTION_NAME = "metaproperty"


report_param = {}

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

def prev_param(hist_obj: BaseChatMessageHistory):
    """ambil data terakhir dari AIMessage di history query"""
    jumlah = len(hist_obj.messages)
    if jumlah > 0:
        return hist_obj.messages[jumlah-2].content

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
        "2. Mau melakukan perubahan data properti yang sudah ada di website atau aplikasi. ( misal perubahan harga, status, atau detail lainnya) \n"
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

json_convertion_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Anda adalah AI yang memahami konteks kalimat manusia."
        # "Hubungkan konteks dengan HISTORY QUERY jika ada."
        "Tugas anda adalah mengubah kalimat pencarian properti menjadi JSON FORMAT utuh dengan aturan dibawah ini: \n"
        "1. alamat = berisi alamat. \n"
        "2. keyword = berisi maksimal 2 kata yang menandakan lokasi.\n"
        "3. harga_min = harga minimal yang dicari, jika disebut miliar, M, artinya billion atau 10^9. \n"
        "4. harga_max = harga maksimal, minimal 1.2 kali diatas harga min dan tidak boleh sama dengan harga min. \n"
        "5. kamar_tidur = jumlah kamar tidur yang diinginkan. \n"
        "6. lebar_bangunan = lebar bangunan yang diinginkan. \n"
        "7. luas_bangunan = luas bangunan yang diinginkan. \n"
        "8. jumlah_tingkat = jumlah lantai / tingkat bangunan. \n"
        "9. luas_tanah = luas tanah yang diinginkan. \n"
        "10. kondisi = pilih salah satu (baru, kosong, full furnished, non furnished). \n"
        "11. tipe_listing = hanya isi angka 1/2/3 untuk jual/sewa/lelang. \n"
        "12. jenis_properti = hanya isi angka 1/2/3/4/5/6 untuk rumah/ruko/tanah/apartment/gudang/gedung. \n"
        "13. mata_angin = isikan arah mata angin dalam string, misalnya timur, barat, tenggara, dan lainnya. \n"
        "14. is_hard_filter = isi TRUE jika filter berisi salah satu dari harga_min, harga_max, kamar_tidur, luas_bangunan, luas_tanah. jika tidak isi dengan FALSE (wajib ada)\n"        
        "HANYA TAMBAHKAN KEY JIKA ADA NILAI. \n\n"
        "Ikuti aturan dibawah ini untuk memberikan nilai yang tepat pada keyword, harga_max dan harga_min. \n"
        "Cara untuk memberikan hasil pada KEYWORD : \n"
        "1. Ekstrak lokasi dari kalimat. Gunakan pengetahuan umum geografis. \n "
        "2. Cari dari sumber terpercaya bisa memberikan lokasi yang dikenal oleh masyarakat lokal. misalnya : kampung lalang, padang bulan, baloi, dll \n"
        "3. Jangan cantumkan nama negara seperti indonesia, malaysia, dan lainnya. \n"
        "4. Jangan cantumkan nama propinsi, kota, seperti sumatera utara, dki jakarta, medan, batam dan lainnya. \n"
        "5. Jangan cantumkan kata seperti komplek, perumahan, cluster, dan kata lain sejenisnya. \n\n"
        "Ini adalah beberapa cara menentukan nilai harga_max dan harga_min : \n"
        "1. jika kalimat seperti : harga dibawah 1M, harga maksimal 1M, budget maksimal 1M, artinya harga_max = 1000000000 dan harga_min = None \n"
        "2. jika kalimat seperti harga 1M ke 2M, berarti harga_max = 2000000000 dan harga_min = 1000000000. \n"
        "3. Jika ada kata SEKITAR, KISARAN, atau akhiran -an seperti M an, juta an, jt an, maka tentukan rentang harga_min 80%/dan harga_max 120%/dari harga. \n\n"
        "Jika sudah ada HISTORY JSON sebelumnya, maka ikuti aturan ini:"
        "HISTORY JSON sebelumnya adalah {history_query}\n "
        "Beberapa kalimat yang menghasilkan JSON yang sama dengan HISTORY JSON sebelumnya seperti : 'ada yang lain?', 'masih ada pilihan lain?', dan sejenis lainnya. \n"
    ),
    (
        "system",
        "Balas hanya JSON dengan keys yang sudah disebutkan diatas"
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

def fetch_property(x):
    url = FETCH_PROPERTY_URL
    param = x['json_query']
    rewrite_question = x['rewrite_question']

    def normalize(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            if v is None:
                continue
            if isinstance(v, str) and v.strip() == "":
                continue
            out[k] = v
        return out

    prev_param = x['history_query']
    if prev_param and "page" in prev_param: 
        prev_param = ast.literal_eval(prev_param)
        last_page = prev_param["page"]
        del prev_param["page"]
        del prev_param["paginate"]

        prev_param_n = normalize(prev_param)
        param_n = normalize(param)
        if all(param_n.get(k) == v for k, v in prev_param_n.items()):
            param["page"] = last_page + 1

    if len(param) > 0:
        
        print("[italic bold green]Mengubah text menjadi JSON ... [/italic bold green]\n")
        print("[italic bold green]JSON : " + str(param) + " [/italic bold green]\n")

        if param["is_hard_filter"] == "FALSE" or param["is_hard_filter"] == False:
            print("[italic bold green]Melakukan pencairan dokumen vector [/italic bold green]\n")
            vector_doc = fetch_relevant_docs(x)
            documents = vector_doc
            report_param["method"] = 'vector'

        else :
            param["page"] = 1 if "page" not in param else param["page"]
            param["paginate"] = 5

            print("[italic bold green]Mengambil data properti ... [/italic bold green]\n")

            filter_result = post_query(url,param,API_TOKEN)
            documents = filter_result.text
            report_param["method"] = 'mysql'

    def is_hard_constrained(p):
        hard_keys = ["harga_min", "harga_max", "kamar_tidur", "jenis_properti", "luas_tanah", "luas_bangunan"]
        return any(k in p for k in hard_keys)

    if len(param) == 0 or documents == "":
        if is_hard_constrained(param):
            # Pertahankan CPA: akui no-result
            report_param["method"] = 'mysql'
            return ""  # biar LLM jawab "tidak menemukan" (sesuai prompt)
        else:
            # Barulah vector fallback
            print("[italic bold green]Melakukan pencairan dokumen vector [/italic bold green]\n")
            vector_doc = fetch_relevant_docs(x)
            documents = vector_doc
            report_param["method"] = 'vector'
        

    print(f"[italic bold green]{'Menemukan data properti...' if documents != '' else 'Tidak menemukan data properti'}[/italic bold green]\n")
    print("[italic bold green]Menyiapkan jawaban kepada user ... [/italic bold green]\n")

    query_history = get_query_history(session_id=x['session_id'])
    query_history.add_ai_message(str(param))
    query_history.add_user_message(rewrite_question)

    # list = doc_to_json(filter_result.text)
    # print(list)
    report_param["doc"] = documents

    return documents



def fetch_relevant_docs(x):

    vectordb = Chroma(
        persist_directory=PERSIST_DIR,
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
    )

    # retriever =vectordb.as_retriever(
    #     search_type="similarity_score_threshold",
    #     search_kwargs={
    #         "k": 200, 
    #         "score_threshold": 0.35,
    #         # "filter" : {"price": {"$lt": 1000_000_000}}
    #     },
    # )

    retriever =vectordb.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 10, 
        },
    )

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

    return data_property

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
        "**bold** diganti menjadi *bold*, tanpa `[teks](url)`. "
        "Jika ada link, tulis sebagai URL polos, contoh: Link: https://contoh.com"
    ),
    (
        "human", 
        "Jawablah pertanyaan berikut ini berdasarkan Data Property yang ada. \n"
        "Berikan jawaban yang ringkas, tepat dan padat. Berikan pilihan data maksimal 5 property yang paling sesuai. \n"
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
    data_property = json_convertion_chain | RunnableLambda(fetch_property) ,
    question = itemgetter("question"),
    session_id = itemgetter("session_id")
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
        "Analisa pertanyaan {rewrite_question} apakah masih dalam KONTEKS properti atau tidak." 
        "Jika IYA, gunakan pengetahuan anda untuk menjawab pertanyaan tersebut. "
        "Jika TIDAK, sampaikan dengan sopan dan halus. lalu arahkan ke tugas yang dapat kamu layani. \n"
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
    history_query = itemgetter("history_query"),
    time_greeting = itemgetter("time_greeting"),
    user_name = itemgetter("user_name"),
    session_id = itemgetter("session_id"),
)

rewrite_context_chain = RunnableParallel(
    rewrite_question = RunnableLambda(rewrite_chain),
    question = itemgetter("question"),
    history_chat = itemgetter("history_chat"),
    history_query = itemgetter("history_query"),
    time_greeting = itemgetter("time_greeting"),
    user_name = itemgetter("user_name"),
    session_id = itemgetter("session_id"),
)

chain = rewrite_context_chain | classifier_chain | classifier_branches

def build_chain(data):
    start = time.perf_counter()
    session_id = data['session_id']
    question = data['question']
    history = get_history(session_id)
    last_history = serialize_history(history,10)
    history_query = get_query_history(session_id)
    last_history_query = prev_param(history_query)

    with get_openai_callback() as cb:
        answer = chain.invoke({
            "session_id": session_id,
            "question": question,
            "history_chat": last_history,
            "history_query": last_history_query,
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
        "method" : 'mysql',
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
    history_query = get_query_history(session_id)
    last_history_query = prev_param(history_query)

    with get_openai_callback() as cb:
        answer = chain.invoke({
            "session_id": session_id,
            "question": question,
            "history_chat": last_history,
            "history_query": last_history_query,
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
    
    return report_param


test_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "ubah kalimat pertanyaan berikut menjadi SQL statement."
        "tabel yang dituju adalah table properti dengan kolom nama_properti, alamat_properti, harga,mata_angin, keyword_lokasi, luas_bangunan, luas_tanah, jumlah_lantai. \n"
        "jawab hanya dalam SQL statement tanpa text lainnya."
    ),
    ("human", "{question}")
]) 

def query_chain():
    x = {
        "question" : "cari rumah di cemara",
        "rewrite_question" : "cari rumah daerah cemara atau ringroad",
    }
    chain = test_prompt | llm | StrOutputParser()
    answer = chain.invoke({
        "question" : "Carikan rumah di komplek yang punya fasilitas kolam renang"
    })
    return answer



if __name__ == "__main__":
    # Quick sanity test (opsional)
    ans = build_chain({
        "session_id": "1234",
        "question": "cari apartment di podomoro yang bisa harganya dibawah 1.5 M",
        "user_name": "Tester"
    })
    print(ans)







