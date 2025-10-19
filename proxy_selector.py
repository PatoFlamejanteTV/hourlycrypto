# proxy_selector.py
import requests
from typing import Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

PROXY_SOURCES = [
    "https://www.proxy-list.download/api/v1/get?type=https",
    "https://www.proxyscan.io/download?type=https",
]

TEST_URL = "https://1.1.1.1"  # ou "https://api.telegram.org" se quiser testar direto
TIMEOUT = 5  # segundos
MAX_WORKERS = 20  # número de threads para testar proxies

def fetch_proxy_list() -> List[str]:
    """Raspa listas de proxies HTTPS de fontes públicas"""
    proxies = set()
    for url in PROXY_SOURCES:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            for line in r.text.splitlines():
                line = line.strip()
                if line:
                    proxies.add(line)
        except Exception as e:
            print(f"⚠️ Falha ao buscar proxies de {url}: {e}")
    return list(proxies)

def test_proxy(proxy: str) -> Tuple[str, float]:
    """Testa latência do proxy retornando tempo em segundos. Se falhar, retorna float('inf')"""
    proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    start = time.time()
    try:
        r = requests.get(TEST_URL, proxies=proxies, timeout=TIMEOUT)
        if r.status_code == 200:
            elapsed = time.time() - start
            return proxy, elapsed
        else:
            return proxy, float('inf')
    except:
        return proxy, float('inf')

def get_fastest_proxy() -> Optional[str]:
    """Retorna o proxy mais rápido disponível"""
    proxy_list = fetch_proxy_list()
    if not proxy_list:
        print("❌ Nenhum proxy encontrado!")
        return None

    fastest_proxy = None
    fastest_time = float('inf')

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_proxy = {executor.submit(test_proxy, p): p for p in proxy_list}
        for future in as_completed(future_to_proxy):
            proxy, latency = future.result()
            if latency < fastest_time:
                fastest_time = latency
                fastest_proxy = proxy
            print(f"Tested {proxy}: {latency:.2f}s")

    if fastest_proxy:
        print(f"✅ Proxy mais rápido: {fastest_proxy} ({fastest_time:.2f}s)")
    return fastest_proxy

if __name__ == "__main__":
    fastest = get_fastest_proxy()
    print("Fastest proxy:", fastest)