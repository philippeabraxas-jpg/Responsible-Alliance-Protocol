import time
import statistics
from core.hsm_signer import HSMSigner, HSMType

def benchmark_signing(iterations=100):
    signer = HSMSigner(hsm_type=HSMType.SOFTWARE)
    payload = b"{\"action\": \"transfer\", \"amount\": 1000, \"agent_id\": \"bot-001\"}"
    
    latencies = []
    
    print(f"🚀 Démarrage du benchmark : {iterations} signatures...")
    
    for i in range(iterations):
        start_time = time.perf_counter()
        signer.sign(payload, agent_id=f"agent-{i}")
        end_time = time.perf_counter()
        latencies.append((end_time - start_time) * 1000) # Convertir en ms

    avg_latency = statistics.mean(latencies)
    p95_latency = statistics.quantiles(latencies, n=20)[18] # 95ème percentile

    print(f"\n--- Résultats du Benchmark ---")
    print(f"Moyenne : {avg_latency:.2f} ms")
    print(f"P95     : {p95_latency:.2f} ms")
    
    if p95_latency <= 5.0:
        print("✅ PERFORMANCE OK : Sous le seuil de 5ms.")
    else:
        print("⚠️ WARNING : Latence supérieure à l'objectif de 5ms.")

    signer.close()

if __name__ == "__main__":
    benchmark_signing()
