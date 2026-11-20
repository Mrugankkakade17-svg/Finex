import json
import time
import ctypes
from ctypes import wintypes
import httpx

# Windows Memory API
class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_uint64),
        ("ullAvailPhys", ctypes.c_uint64),
        ("ullTotalPageFile", ctypes.c_uint64),
        ("ullAvailPageFile", ctypes.c_uint64),
        ("ullTotalVirtual", ctypes.c_uint64),
        ("ullAvailVirtual", ctypes.c_uint64),
        ("ullAvailExtendedVirtual", ctypes.c_uint64),
    ]

def get_ram_info():
    stat = MEMORYSTATUSEX()
    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
    total_gb = stat.ullTotalPhys / (1024 ** 3)
    avail_gb = stat.ullAvailPhys / (1024 ** 3)
    used_gb = total_gb - avail_gb
    return {
        "load_pct": stat.dwMemoryLoad,
        "total_gb": round(total_gb, 2),
        "avail_gb": round(avail_gb, 2),
        "used_gb": round(used_gb, 2),
    }

def unload_models(client: httpx.Client):
    print("Checking active models in memory...")
    r = client.get("http://localhost:11434/api/ps")
    if r.status_code == 200:
        models = r.json().get("models", [])
        for m in models:
            m_name = m.get("model") or m.get("name")
            print(f"Unloading model: {m_name} (keep_alive: 0)...")
            client.post("http://localhost:11434/api/generate", json={"model": m_name, "keep_alive": 0})
        time.sleep(1)
        r2 = client.get("http://localhost:11434/api/ps")
        active_after = r2.json().get("models", [])
        print("Active models after eviction:", [x.get("name") for x in active_after])
        return len(active_after) == 0
    return False

def benchmark_model(model_name: str, prompt: str, num_warm_runs: int = 10):
    client = httpx.Client(timeout=180.0)

    print(f"\n========================================================")
    print(f"BENCHMARKING MODEL: {model_name}")
    print(f"Prompt: {prompt}")
    print(f"========================================================")

    # 1. Ensure Model is Evicted from RAM for Genuine Cold Start
    unload_models(client)

    ram_before = get_ram_info()
    print(f"Baseline RAM: {ram_before['used_gb']} GB used / {ram_before['total_gb']} GB total ({ram_before['load_pct']}%)")

    # 2. Genuine Cold Run
    print("\n--- Running Genuine Cold Start (Disk Load + 1st Generation) ---")
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "seed": 42
        }
    }

    t0 = time.perf_counter()
    resp_cold = client.post(url, json=payload)
    t_cold = time.perf_counter() - t0

    if resp_cold.status_code != 200:
        print(f"Cold run failed: {resp_cold.status_code} {resp_cold.text}")
        return None

    data_cold = resp_cold.json()
    ram_during = get_ram_info()

    cold_load_s = data_cold.get("load_duration", 0) / 1e9
    cold_prompt_eval_s = data_cold.get("prompt_eval_duration", 0) / 1e9
    cold_eval_s = data_cold.get("eval_duration", 0) / 1e9
    cold_eval_count = data_cold.get("eval_count", 0)
    cold_tok_s = (cold_eval_count / cold_eval_s) if cold_eval_s > 0 else 0
    cold_resp = data_cold.get("response", "").strip()

    print(f"Cold Wall Clock: {t_cold:.3f} s")
    print(f"Cold Disk-to-RAM Load: {cold_load_s:.3f} s")
    print(f"Cold Prompt Eval: {cold_prompt_eval_s:.3f} s")
    print(f"Cold Generation: {cold_eval_s:.3f} s ({cold_eval_count} tokens, {cold_tok_s:.2f} tok/s)")
    print(f"RAM during inference: {ram_during['used_gb']} GB (Delta: +{round(ram_during['used_gb'] - ram_before['used_gb'], 2)} GB)")
    print(f"Output snippet: {cold_resp[:120]}...")

    # 3. Warm Runs
    print(f"\n--- Running {num_warm_runs} Warm Runs (Resident in Memory) ---")
    warm_runs = []
    for i in range(1, num_warm_runs + 1):
        t_start = time.perf_counter()
        resp = client.post(url, json=payload)
        t_wall = time.perf_counter() - t_start

        d = resp.json()
        l_s = d.get("load_duration", 0) / 1e9
        pe_s = d.get("prompt_eval_duration", 0) / 1e9
        e_s = d.get("eval_duration", 0) / 1e9
        cnt = d.get("eval_count", 0)
        t_rate = (cnt / e_s) if e_s > 0 else 0

        record = {
            "run": i,
            "wall_clock_s": round(t_wall, 3),
            "load_duration_s": round(l_s, 4),
            "prompt_eval_s": round(pe_s, 4),
            "eval_s": round(e_s, 3),
            "tokens": cnt,
            "tok_per_sec": round(t_rate, 2)
        }
        warm_runs.append(record)
        print(f"  Warm Run #{i:02d}: Wall = {t_wall:.3f}s | Load = {l_s:.4f}s | Gen = {e_s:.3f}s ({cnt} tokens, {t_rate:.2f} tok/s)")
        time.sleep(0.5)

    # Statistical analysis on warm runs
    lats = [r["wall_clock_s"] for r in warm_runs]
    sorted_lats = sorted(lats)
    n = len(sorted_lats)

    min_lat = sorted_lats[0]
    max_lat = sorted_lats[-1]
    mean_lat = sum(lats) / n
    median_lat = (sorted_lats[n // 2] if n % 2 != 0 else (sorted_lats[n // 2 - 1] + sorted_lats[n // 2]) / 2.0)

    # Empirical 90th and 95th percentile with explicit rank method
    p90_idx = min(int(0.90 * n), n - 1)
    p95_idx = min(int(0.95 * n), n - 1)
    p90_lat = sorted_lats[p90_idx]
    p95_lat = sorted_lats[p95_idx]

    speeds = [r["tok_per_sec"] for r in warm_runs]
    mean_speed = sum(speeds) / len(speeds)

    summary = {
        "sample_count": n,
        "min_latency_s": round(min_lat, 3),
        "mean_latency_s": round(mean_lat, 3),
        "median_latency_s": round(median_lat, 3),
        "p90_latency_s": round(p90_lat, 3),
        "p95_latency_s": round(p95_lat, 3),
        "max_latency_s": round(max_lat, 3),
        "mean_tok_per_sec": round(mean_speed, 2)
    }

    print("\n--- Summary Statistics (Warm Runs N=10) ---")
    print(f"Min: {min_lat:.3f}s | Mean: {mean_lat:.3f}s | Median: {median_lat:.3f}s | P90: {p90_lat:.3f}s | P95: {p95_lat:.3f}s | Max: {max_lat:.3f}s")
    print(f"Mean Throughput: {mean_speed:.2f} tokens/sec")

    # 4. Clean eviction after test
    unload_models(client)
    ram_after = get_ram_info()
    print(f"RAM after eviction: {ram_after['used_gb']} GB")

    return {
        "model": model_name,
        "prompt": prompt,
        "ram_before_gb": ram_before["used_gb"],
        "ram_during_gb": ram_during["used_gb"],
        "ram_delta_gb": round(ram_during["used_gb"] - ram_before["used_gb"], 2),
        "ram_after_eviction_gb": ram_after["used_gb"],
        "cold_run": {
            "wall_clock_s": round(t_cold, 3),
            "disk_load_time_s": round(cold_load_s, 3),
            "prompt_eval_s": round(cold_prompt_eval_s, 3),
            "eval_time_s": round(cold_eval_s, 3),
            "eval_count": cold_eval_count,
            "tokens_per_sec": round(cold_tok_s, 2),
            "response": cold_resp
        },
        "warm_runs": warm_runs,
        "summary": summary
    }

if __name__ == "__main__":
    prompt = "Explain asset allocation in 2 sentences."
    models = ["llama3.2:latest", "deepseek-r1:1.5b"]

    results = {}
    for m in models:
        try:
            res = benchmark_model(m, prompt, num_warm_runs=10)
            if res:
                results[m] = res
        except Exception as e:
            print(f"Error benchmarking {m}: {e}")

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ollama_benchmark_v2_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved Ollama benchmark v2 results successfully!")
