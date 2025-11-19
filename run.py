# run_min.py
# pip install langchain langchain-openai python-dotenv
from dotenv import load_dotenv
from rich import print
import argparse

from api_rval import build_chain as build_chain_api
from vector_rval import build_chain as build_chain_vector
from api_vector_rval import build_chain as build_chain_hybrid

load_dotenv()

def main():
    # ============== PARSE ARGUMENT ==============
    parser = argparse.ArgumentParser(
        description="Jalankan RAG bot dengan mode berbeda (api/vector/hybrid)."
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--api",
        action="store_const",
        dest="mode",
        const="api",
        help="Gunakan chain API (SQL saja)",
    )
    group.add_argument(
        "--vector",
        action="store_const",
        dest="mode",
        const="vector",
        help="Gunakan chain Vector DB saja",
    )
    group.add_argument(
        "--hybrid",
        action="store_const",
        dest="mode",
        const="hybrid",
        help="Gunakan chain Hybrid (API + Vector)",
    )

    args = parser.parse_args()

    # Pilih fungsi build_chain sesuai argumen
    if args.mode == "api":
        build_chain = build_chain_api
        print("[bold green]Mode:[/bold green] API (SQL)")
    elif args.mode == "vector":
        build_chain = build_chain_vector
        print("[bold green]Mode:[/bold green] VECTOR")
    elif args.mode == "hybrid":
        build_chain = build_chain_hybrid
        print("[bold green]Mode:[/bold green] HYBRID (API + Vector)")
    else:
        # Harusnya tidak pernah terjadi karena kita pakai mutually exclusive group
        raise ValueError(f"Mode tidak dikenal: {args.mode}")

    # ============== LOOP CHAT ==============
    session = {
        "id": "628126577345",
        "name": "Ripin",
    }

    while True:
        try:
            q = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if q.lower() in {"exit", "quit"}:
            break

        reply = build_chain({
            "question": q,
            "session_id": session["id"],
            "user_name": session["name"],
        })
        print("AI :", reply)


if __name__ == "__main__":
    main()


# Mode API (SQL)
# python run.py --api

# Mode Vector DB
# python run.py --vector

# Mode Hybrid API + Vector
# python run.py --hybrid




        




    
    
    

   