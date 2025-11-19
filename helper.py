from datetime import datetime, timezone, timedelta
import re, json, requests

def token_usage_calculator(prev,result):
    """Ambil token usage dengan aman (berbagai versi LCEL/OpenAI)."""
    # v0: LangChain newer
    usage = getattr(result, "usage_metadata", None)
    if usage:
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        total_tokens = usage.get("total_tokens")
        
    # v1: response_metadata style
    meta = getattr(result, "response_metadata", {}) or {}
    tu = meta.get("token_usage") or {}
    input_tokens = tu.get("prompt_tokens")
    output_tokens = tu.get("completion_tokens")
    total_tokens = tu.get("total_tokens")

    if prev:
        input_tokens = input_tokens + prev.get("input_tokens")
        output_tokens = output_tokens + prev.get("output_tokens")
        total_tokens = total_tokens + prev.get("total_tokens")

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost": (input_tokens*0.15/1000000 + output_tokens*0.6/1000000) * 17000,
    }

def jakarta_time_greeting() -> str:
    # coba pakai zona waktu IANA
    tz = None
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            tz = ZoneInfo("Asia/Jakarta")
        except ZoneInfoNotFoundError:
            tz = None
    except Exception:
        tz = None

    # fallback ke offset +7 jika IANA tidak tersedia
    if tz is None:
        tz = timezone(timedelta(hours=7))

    h = datetime.now(tz).hour
    if 5 <= h < 11:
        return "Pagi"
    elif 11 <= h < 15:
        return "Siang"
    elif 15 <= h < 18:
        return "Sore"
    else:
        return "Malam"

def post_query(url,data,token):
    headers = {
        "Authorization": "Bearer "+token,
        "Accept": "application/json"
    }

    try:
        resp = requests.post(
            url,
            json=data,    
            headers=headers,
            timeout=15        
        )
        resp.raise_for_status()         # error kalau status 4xx/5xx
        return resp

    except requests.exceptions.Timeout:
        print("Timeout: server lambat merespons.")
    except requests.exceptions.HTTPError as e:
        print("HTTP error:", e, "| body:", resp.text if 'resp' in locals() else "")
    except requests.exceptions.RequestException as e:
        print("Request error:", e)

def get_query(url,data):
    headers = {
        # "Authorization": "Bearer "+token,
        "Accept": "application/json"
    }

    try:
        resp = requests.get(
            url,
            json=data,    
            headers=headers,
            timeout=15        
        )
        resp.raise_for_status()         # error kalau status 4xx/5xx
        return resp

    except requests.exceptions.Timeout:
        print("Timeout: server lambat merespons.")
    except requests.exceptions.HTTPError as e:
        print("HTTP error:", e, "| body:", resp.text if 'resp' in locals() else "")
    except requests.exceptions.RequestException as e:
        print("Request error:", e)


def text_to_json(text):
    m = re.search(r'\{.*\}', text, flags=re.S)
    if not m:
        raise ValueError("JSON tidak ditemukan di dalam string.")
    payload = json.loads(m.group(0))
    return payload

def doc_to_json(doc):
    list = doc.split("\n\n---------\n\n")
    return list


