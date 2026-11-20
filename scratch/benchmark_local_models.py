import json
import time
import ctypes
from ctypes import wintypes

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

def benchmark_minilm():
    print("\n============================================================")
    print("PHASE 3: BENCHMARKING all-MiniLM-L6-v2 (LOCAL PYTORCH CPU)")
    print("============================================================")
    import torch
    from transformers import AutoTokenizer, AutoModel

    torch.set_num_threads(8)
    model_id = "sentence-transformers/all-MiniLM-L6-v2"

    ram_before = get_ram_info()
    print(f"RAM before loading MiniLM: {ram_before['used_gb']} GB")

    # 1. Measure Model Load Time
    t0 = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModel.from_pretrained(model_id)
    model.eval()
    load_time_s = time.perf_counter() - t0

    ram_loaded = get_ram_info()
    ram_delta_load = round(ram_loaded["used_gb"] - ram_before["used_gb"], 2)
    print(f"MiniLM Model Load Time: {load_time_s:.3f} s (RAM delta: +{ram_delta_load} GB)")

    # 2. Representative Inputs
    single_query = "What is the management fee and expense ratio for this fund?"
    batch_5 = [
        "The fund seeks long-term capital appreciation by investing in large-cap equities.",
        "Fixed income securities carry credit risk and interest rate duration risk.",
        "Portfolio turnover was 24% for the trailing twelve-month period.",
        "Cash and cash equivalents represent 4.5% of total net assets.",
        "The benchmark index returned 14.2% annualized over five years."
    ]
    batch_10 = batch_5 + [
        "Expense ratios are deducted directly from fund net asset value on a daily basis.",
        "Emerging markets exposure introduces additional currency volatility.",
        "Redemption requests received before market close are settled at next calculated NAV.",
        "The fund maintains a strict ESG exclusion policy for fossil fuel exploration.",
        "Historical tracking error against the benchmark remains below 35 basis points."
    ]

    def mean_pooling(model_output, attention_mask):
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    def embed_texts(texts):
        encoded = tokenizer(texts, padding=True, truncation=True, return_tensors='pt', max_length=128)
        with torch.no_grad():
            output = model(**encoded)
        embeddings = mean_pooling(output, encoded['attention_mask'])
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
        return embeddings

    # 3. Single Query Benchmark
    print("\n--- Single Query Embedding Benchmark ---")
    t_cold_start = time.perf_counter()
    emb_cold = embed_texts([single_query])
    single_cold_s = time.perf_counter() - t_cold_start
    dim = emb_cold.shape[1]
    print(f"Cold Single Query Latency: {single_cold_s * 1000:.2f} ms (Dimension: {dim})")

    single_warm_runs = []
    for i in range(10):
        t_w = time.perf_counter()
        _ = embed_texts([single_query])
        dur_ms = (time.perf_counter() - t_w) * 1000.0
        single_warm_runs.append(dur_ms)

    s_sorted = sorted(single_warm_runs)
    single_min = s_sorted[0]
    single_max = s_sorted[-1]
    single_mean = sum(single_warm_runs) / len(single_warm_runs)
    single_median = s_sorted[len(s_sorted) // 2]
    print(f"Warm Single (N=10): Min = {single_min:.2f}ms | Mean = {single_mean:.2f}ms | Median = {single_median:.2f}ms | Max = {single_max:.2f}ms")

    # 4. Batch 5 Benchmark
    print("\n--- Batch 5 Embedding Benchmark ---")
    batch5_warm_runs = []
    for i in range(10):
        t_w = time.perf_counter()
        _ = embed_texts(batch_5)
        dur_ms = (time.perf_counter() - t_w) * 1000.0
        batch5_warm_runs.append(dur_ms)
    b5_sorted = sorted(batch5_warm_runs)
    b5_min = b5_sorted[0]
    b5_max = b5_sorted[-1]
    b5_mean = sum(batch5_warm_runs) / len(batch5_warm_runs)
    b5_median = b5_sorted[len(b5_sorted) // 2]
    print(f"Warm Batch 5 (N=10): Min = {b5_min:.2f}ms | Mean = {b5_mean:.2f}ms | Median = {b5_median:.2f}ms | Max = {b5_max:.2f}ms ({b5_mean/5:.2f} ms/chunk)")

    # 5. Batch 10 Benchmark
    print("\n--- Batch 10 Embedding Benchmark ---")
    batch10_warm_runs = []
    for i in range(10):
        t_w = time.perf_counter()
        _ = embed_texts(batch_10)
        dur_ms = (time.perf_counter() - t_w) * 1000.0
        batch10_warm_runs.append(dur_ms)
    b10_sorted = sorted(batch10_warm_runs)
    b10_min = b10_sorted[0]
    b10_max = b10_sorted[-1]
    b10_mean = sum(batch10_warm_runs) / len(batch10_warm_runs)
    b10_median = b10_sorted[len(b10_sorted) // 2]
    print(f"Warm Batch 10 (N=10): Min = {b10_min:.2f}ms | Mean = {b10_mean:.2f}ms | Median = {b10_median:.2f}ms | Max = {b10_max:.2f}ms ({b10_mean/10:.2f} ms/chunk)")

    ram_during = get_ram_info()

    return {
        "model_id": model_id,
        "parameters_million": 22.7,
        "embedding_dimension": dim,
        "ram_before_load_gb": ram_before["used_gb"],
        "ram_after_load_gb": ram_loaded["used_gb"],
        "ram_during_inference_gb": ram_during["used_gb"],
        "model_load_time_s": round(load_time_s, 3),
        "single_query_cold_ms": round(single_cold_s * 1000, 2),
        "single_query_warm": {
            "min_ms": round(single_min, 2),
            "mean_ms": round(single_mean, 2),
            "median_ms": round(single_median, 2),
            "max_ms": round(single_max, 2),
            "samples": [round(x, 2) for x in single_warm_runs]
        },
        "batch_5_warm": {
            "min_ms": round(b5_min, 2),
            "mean_ms": round(b5_mean, 2),
            "median_ms": round(b5_median, 2),
            "max_ms": round(b5_max, 2),
            "per_chunk_mean_ms": round(b5_mean / 5.0, 2),
            "samples": [round(x, 2) for x in batch5_warm_runs]
        },
        "batch_10_warm": {
            "min_ms": round(b10_min, 2),
            "mean_ms": round(b10_mean, 2),
            "median_ms": round(b10_median, 2),
            "max_ms": round(b10_max, 2),
            "per_chunk_mean_ms": round(b10_mean / 10.0, 2),
            "samples": [round(x, 2) for x in batch10_warm_runs]
        }
    }

def benchmark_finbert():
    print("\n============================================================")
    print("PHASE 4: BENCHMARKING ProsusAI/finbert (LOCAL PYTORCH CPU)")
    print("============================================================")
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    torch.set_num_threads(8)
    model_id = "ProsusAI/finbert"

    ram_before = get_ram_info()
    print(f"RAM before loading FinBERT: {ram_before['used_gb']} GB")

    # 1. Model Load Time
    t0 = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForSequenceClassification.from_pretrained(model_id)
    model.eval()
    load_time_s = time.perf_counter() - t0

    ram_loaded = get_ram_info()
    ram_delta_load = round(ram_loaded["used_gb"] - ram_before["used_gb"], 2)
    print(f"FinBERT Model Load Time: {load_time_s:.3f} s (RAM delta: +{ram_delta_load} GB)")

    # 2. Representative Headlines
    headline_pos = "HDFC Bank reports 35% surge in quarterly net profit, beating analyst estimates across all operational segments."
    headline_neg = "Tech giant warns of severe revenue slump and cuts full-year forecast amid worsening global macro headwinds."
    headline_neu = "Reserve Bank of India maintains policy repo rate unchanged at 6.50% following monetary policy committee meeting."

    batch_10_headlines = [
        headline_pos,
        headline_neg,
        headline_neu,
        "Reliance Industries announces major green hydrogen investment with strategic European partners.",
        "Automaker recalls 45,000 electric vehicles following battery overheating and fire safety concerns.",
        "Foreign institutional investors infuse net 4,200 crore rupees into domestic equity markets.",
        "Pharma firm receives US FDA warning letter for manufacturing compliance lapses at Goa plant.",
        "Consumer inflation cools to four-month low of 4.85% in line with central bank projections.",
        "Airline operator grounds eight aircraft following global engine supply chain disruptions.",
        "State Bank of India raises deposit interest rates by 25 basis points across select tenors."
    ]

    labels_map = model.config.id2label

    def classify(texts):
        encoded = tokenizer(texts, padding=True, truncation=True, return_tensors='pt', max_length=128)
        with torch.no_grad():
            outputs = model(**encoded)
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        results = []
        for i, text in enumerate(texts):
            pred_idx = torch.argmax(probs[i]).item()
            label = labels_map[pred_idx]
            conf = probs[i][pred_idx].item()
            results.append({
                "text": text,
                "label": label,
                "confidence": round(conf, 4),
                "probabilities": {labels_map[k]: round(probs[i][k].item(), 4) for k in range(len(labels_map))}
            })
        return results

    # 3. Output Validation Check
    print("\n--- Functional Sentiment Output Verification ---")
    test_outputs = classify([headline_pos, headline_neg, headline_neu])
    for item in test_outputs:
        print(f"Headline: {item['text'][:70]}...")
        print(f"  -> Predicted: {item['label'].upper()} (Confidence: {item['confidence'] * 100:.1f}%) | Probs: {item['probabilities']}")

    # 4. Latency Benchmark: Single Headline
    print("\n--- Single Headline Latency Benchmark ---")
    t_cold = time.perf_counter()
    _ = classify([headline_pos])
    single_cold_ms = (time.perf_counter() - t_cold) * 1000.0
    print(f"Cold Single Headline Latency: {single_cold_ms:.2f} ms")

    single_warm_runs = []
    for i in range(10):
        t_w = time.perf_counter()
        _ = classify([headline_pos])
        dur_ms = (time.perf_counter() - t_w) * 1000.0
        single_warm_runs.append(dur_ms)

    s_sorted = sorted(single_warm_runs)
    s_min = s_sorted[0]
    s_max = s_sorted[-1]
    s_mean = sum(single_warm_runs) / len(single_warm_runs)
    s_median = s_sorted[len(s_sorted) // 2]
    print(f"Warm Single Headline (N=10): Min = {s_min:.2f}ms | Mean = {s_mean:.2f}ms | Median = {s_median:.2f}ms | Max = {s_max:.2f}ms")

    # 5. Latency Benchmark: Batch of 10 Headlines
    print("\n--- Batch 10 Headlines Latency Benchmark ---")
    batch_warm_runs = []
    for i in range(10):
        t_w = time.perf_counter()
        _ = classify(batch_10_headlines)
        dur_ms = (time.perf_counter() - t_w) * 1000.0
        batch_warm_runs.append(dur_ms)

    b_sorted = sorted(batch_warm_runs)
    b_min = b_sorted[0]
    b_max = b_sorted[-1]
    b_mean = sum(batch_warm_runs) / len(batch_warm_runs)
    b_median = b_sorted[len(b_sorted) // 2]
    print(f"Warm Batch 10 Headlines (N=10): Min = {b_min:.2f}ms | Mean = {b_mean:.2f}ms | Median = {b_median:.2f}ms | Max = {b_max:.2f}ms ({b_mean/10:.2f} ms/headline)")

    ram_during = get_ram_info()

    return {
        "model_id": model_id,
        "parameters_million": 109.5,
        "ram_before_load_gb": ram_before["used_gb"],
        "ram_after_load_gb": ram_loaded["used_gb"],
        "ram_during_inference_gb": ram_during["used_gb"],
        "model_load_time_s": round(load_time_s, 3),
        "validation_outputs": test_outputs,
        "single_headline_cold_ms": round(single_cold_ms, 2),
        "single_headline_warm": {
            "min_ms": round(s_min, 2),
            "mean_ms": round(s_mean, 2),
            "median_ms": round(s_median, 2),
            "max_ms": round(s_max, 2),
            "samples": [round(x, 2) for x in single_warm_runs]
        },
        "batch_10_warm": {
            "min_ms": round(b_min, 2),
            "mean_ms": round(b_mean, 2),
            "median_ms": round(b_median, 2),
            "max_ms": round(b_max, 2),
            "per_headline_mean_ms": round(b_mean / 10.0, 2),
            "samples": [round(x, 2) for x in batch_warm_runs]
        }
    }

if __name__ == "__main__":
    results = {}
    try:
        results["minilm"] = benchmark_minilm()
    except Exception as e:
        print("Error in MiniLM benchmark:", e)
        results["minilm_error"] = str(e)

    try:
        results["finbert"] = benchmark_finbert()
    except Exception as e:
        print("Error in FinBERT benchmark:", e)
        results["finbert_error"] = str(e)

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_models_benchmark_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nSaved local models benchmark results to scratch successfully!")
