from dotenv import load_dotenv
from vector_rval import build_chain, build_chain_test
from helper import test_question
from rich import print
from save_chat_to_excel import append_record_to_excel

load_dotenv()

QUESTIONS = test_question()

for i, ques in enumerate(QUESTIONS):
    print(f"Question {i + 1}: {ques['q']}")

    try :
        answer =build_chain_test({
            "question" : ques['q'],
            "gold" : ques['gold'], 
            "session_id" : '111',
            "user_name" : 'LLM-JSON-SQL',
        })   
        append_record_to_excel(answer,"test/test_vector_rval1.xlsx")
        print(f"done question {i + 1}")
    except KeyboardInterrupt:
            print("\nDihentikan oleh user.")
            break