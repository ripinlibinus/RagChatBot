# ingest.py
import os
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple

from dotenv import load_dotenv
load_dotenv()

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import OpenAIEmbeddings

DEFAULT_EMBED_MODEL_HF = "intfloat/multilingual-e5-base"  # bagus untuk Indo
PERSIST_DIR_DEFAULT = "chroma/metaproperty"
COLLECTION_DEFAULT = "metaproperty"

def parse_args():
    p = argparse.ArgumentParser(description="Ingest listings.json + page_content/*.txt ke Chroma")
    p.add_argument("--embeds-dir", default="data/embeds",
                   help="Folder yang berisi listings.json dan folder page_content/")
    p.add_argument("--persist-dir", default=PERSIST_DIR_DEFAULT,
                   help="Folder penyimpanan Chroma (persist_directory)")
    p.add_argument("--collection", default=COLLECTION_DEFAULT,
                   help="Nama koleksi Chroma")
    p.add_argument("--use-openai", action="store_true",
                   help="Pakai OpenAIEmbeddings (default: HF e5-base)")
    return p.parse_args()

def load_rows(json_path: Path) -> List[Dict]:
    if not json_path.exists():
        raise FileNotFoundError(f"Tidak ditemukan: {json_path}")
    with json_path.open("r", encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        raise ValueError("listings.json harus berupa array of objects.")
    return rows

def resolve_content_path(row: Dict, embeds_dir: Path) -> Path:
    """
    Ambil path file .txt dari metadata.
    - bila ada field 'page_content_path' seperti 'storage://app/embeds/page_content/listing-123.txt'
      → ambil nama filenya dan cari di {embeds_dir}/page_content/
    - fallback: coba 'listing-{id}.txt'
    """
    pc = (row.get("page_content_path") or "").strip()
    txt_dir = embeds_dir / "page_content"
    if pc:
        # gunakan hanya basename agar portable
        name = os.path.basename(pc)
        cand = txt_dir / name
        if cand.exists():
            return cand

    # fallback by id
    lid = str(row.get("listing_id") or row.get("id") or "").strip()
    if lid:
        cand = txt_dir / f"listing-{lid}.txt"
        if cand.exists():
            return cand

    # terakhir, coba title-based (tidak disarankan, tapi sebagai cadangan)
    title = (row.get("title") or "").strip()
    if title:
        slug = "".join(ch if ch.isalnum() else "-" for ch in title).strip("-")
        cand = txt_dir / f"{slug}.txt"
        if cand.exists():
            return cand

    raise FileNotFoundError(f"File page_content .txt tidak ditemukan untuk row dengan id={row.get('listing_id')}")

def build_document(row: Dict, text: str) -> Tuple[Document, str]:
    """
    Bentuk Document dari satu row metadata + teks.
    - Harga & hal volatil tetap di metadata.
    - ID doc distandarkan 'listing:{listing_id}'
    """
    listing_id = str(row.get("listing_id") or row.get("id"))
    if not listing_id:
        raise ValueError("Row tidak memiliki 'listing_id' / 'id'.")

    # rapikan metadata: hindari field yang tidak perlu besar
    meta = dict(row)  # shallow copy
    # pastikan key koordinat pakai 'lon' (bukan 'long')
    if "long" in meta and "lon" not in meta:
        meta["lon"] = meta.pop("long")

    # jangan gandakan page_content di metadata
    meta.pop("page_content", None)
    meta.pop("page_content_path", None)

    doc = Document(page_content=text, metadata=meta)
    doc_id = f"listing:{listing_id}"
    return doc, doc_id

def get_embeddings(use_openai: bool):
    if use_openai:
        # pastikan OPENAI_API_KEY ada di .env
        return OpenAIEmbeddings(model="text-embedding-3-small")
    # default HF e5 multilingual
    return HuggingFaceEmbeddings(
        model_name=DEFAULT_EMBED_MODEL_HF,
        encode_kwargs={"normalize_embeddings": True}
    )

def main():
    args = parse_args()
    embeds_dir = Path(args.embeds_dir)
    json_path = embeds_dir / "listings.json"
    txt_dir = embeds_dir / "page_content"

    print("== Ingest mulai ==")
    print(f"- embeds_dir     : {embeds_dir}")
    print(f"- listings.json  : {json_path}")
    print(f"- page_content   : {txt_dir}")
    print(f"- persist_dir    : {args.persist_dir}")
    print(f"- collection     : {args.collection}")
    print(f"- embeddings     : {'OpenAI text-embedding-3-small' if args.use_openai else DEFAULT_EMBED_MODEL_HF}")

    rows = load_rows(json_path)
    print(f"  → total baris metadata: {len(rows)}")

    docs, ids, missing = [], [], 0
    for r in rows:
        try:
            p = resolve_content_path(r, embeds_dir)
            text = p.read_text(encoding="utf-8").strip()
            if not text:
                raise ValueError("page_content kosong")
            doc, doc_id = build_document(r, text)
            docs.append(doc)
            ids.append(doc_id)
        except Exception as e:
            missing += 1
            print(f"  ! Skip id={r.get('listing_id')}: {e}")

    print(f"  → siap di-embed: {len(docs)} dokumen (skip: {missing})")

    if not docs:
        print("Tidak ada dokumen yang valid. Stop.")
        return

    embeddings = get_embeddings(args.use_openai)

    # Ingest ke Chroma (add/update). Kita gunakan add saja;
    # jika ingin idempotent update, bisa hapus dulu id yang sama atau gunakan ._collection.update untuk metadata-only.
    db = Chroma(
        persist_directory=args.persist_dir,
        collection_name=args.collection,
        embedding_function=embeddings
    )

    # Tambahkan dokumen (Chroma akan meng-embed otomatis)
    print("  → menulis ke Chroma…")
    db.add_documents(docs, ids=ids)
    print(f"Selesai. Tersimpan di: {args.persist_dir} (collection: {args.collection})")

if __name__ == "__main__":
    main()
