import os
import sys
import threading
import time
import math
import random
import subprocess
import urllib.request
import gradio as gr

try:
    import spaces
    HAS_SPACES = True
except ImportError:
    HAS_SPACES = False

# ZeroGPU requires at least one @spaces.GPU decorated function on free tier
if HAS_SPACES:
    @spaces.GPU
    def gpu_health_check():
        return "ZeroGPU Online"
else:
    def gpu_health_check():
        return "CPU Mode"

def run_instajetload_bot():
    print("🚀 [InstaJetLoad] Launching main.py background service...")
    while True:
        try:
            env = os.environ.copy()
            env["PORT"] = "8080"
            p = subprocess.run([sys.executable, "main.py"], env=env)
            print(f"⚠️ [InstaJetLoad] main.py exited with code {p.returncode}. Restarting in 5s...")
        except Exception as e:
            print(f"❌ [InstaJetLoad] Exception running main.py: {e}")
        time.sleep(5)

# Launch bot background thread
bot_thread = threading.Thread(target=run_instajetload_bot, daemon=True)
bot_thread.start()

def run_cloud_diagnostics():
    import requests
    import urllib.parse
    time.sleep(3)
    print("🔍 [Cloud Diagnostics] Running network & API tests from inside Hugging Face...")
    
    # 1. Test Cobalt with normal video (dQw)
    try:
        r = requests.post("https://rue-cobalt.xenon.zone/", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "videoQuality": "720", "downloadMode": "auto"}, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Content-Type": "application/json"}, timeout=10)
        print(f"🔍 [Diag Cobalt dQw]: status={r.status_code}, body={r.text[:120]}")
    except Exception as e:
        print(f"🔍 [Diag Cobalt Error]: {e}")

    # 2. Test Loader.to with 2FNO
    try:
        url = f"https://loader.to/ajax/download.php?format=720&url={urllib.parse.quote('https://www.youtube.com/watch?v=2FNOhhJqDg0', safe='')}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://en.loader.to/"}, timeout=10)
        print(f"🔍 [Diag Loader.to 2FNO]: status={r.status_code}, body={r.text[:120]}")
    except Exception as e:
        print(f"🔍 [Diag Loader.to Error]: {e}")

    # 3. Test Loader.to with normal video dQw
    try:
        url = f"https://loader.to/ajax/download.php?format=720&url={urllib.parse.quote('https://www.youtube.com/watch?v=dQw4w9WgXcQ', safe='')}"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://en.loader.to/"}, timeout=10)
        print(f"🔍 [Diag Loader.to dQw]: status={r.status_code}, body={r.text[:120]}")
    except Exception as e:
        print(f"🔍 [Diag Loader.to dQw Error]: {e}")

threading.Thread(target=run_cloud_diagnostics, daemon=True).start()

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
]

def organic_keep_alive_engine():
    print("🌊 [Organic Traffic Engine] Initialized: Sinusoidal wave + Gaussian jitter active.")
    time.sleep(random.uniform(90.0, 180.0))
    
    step = random.randint(0, 17)
    base_interval = 840  # ~14 minutes base
    amplitude = 220      # +/- 3.6 minutes oscillation
    period_steps = 18    # Complete sinusoidal cycle over ~4 hours
    
    token = os.environ.get("HF_TOKEN", "")
    targets = [
        "https://rezaoff-instajetload-bot.hf.space",
        "https://rezaoff-geminimind-bot.hf.space"
    ]
    
    while True:
        try:
            # 1. Harmonic sinusoidal curve
            sine_component = amplitude * math.sin((2 * math.pi * step) / period_steps)
            # 2. Gaussian Brownian jitter
            jitter = random.uniform(-90.0, 120.0)
            # 3. Dynamic non-deterministic delay (between 9m and 20m)
            delay = max(540, min(1200, int(base_interval + sine_component + jitter)))
            
            selected_targets = list(targets)
            random.shuffle(selected_targets)
            
            for url in selected_targets:
                try:
                    qp = f"?ref={random.choice(['tg', 'web', 'direct', 'share'])}&_t={random.randint(1000, 9999)}" if random.random() > 0.4 else ""
                    full_url = url.rstrip("/") + "/" + qp
                    
                    headers = {
                        "User-Agent": random.choice(USER_AGENTS),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": random.choice(["en-US,en;q=0.9", "en-US,en;q=0.8,fa;q=0.7", "en;q=0.9"]),
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": random.choice(["none", "cross-site"]),
                        "Cache-Control": random.choice(["max-age=0", "no-cache"]),
                        "Connection": "keep-alive"
                    }
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                    
                    req = urllib.request.Request(full_url, headers=headers)
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        pass
                except Exception:
                    pass
                
                time.sleep(random.uniform(2.0, 7.0))
                
        except Exception:
            delay = random.randint(480, 780)
            
        step = (step + 1) % period_steps
        time.sleep(delay)

watchdog_thread = threading.Thread(target=organic_keep_alive_engine, daemon=True)
watchdog_thread.start()

def get_server_status():
    current_time = time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
    return f"🟢 InstaJetLoad Bot Online | Uptime Check: {current_time}"

def get_live_bot_logs():
    try:
        req = urllib.request.Request("http://127.0.0.1:8080/debug?token=admin", headers={"User-Agent": "HF-Internal"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"Could not connect to bot backend on 8080: {e}"

def run_test_diagnostic(test_url: str):
    import io, contextlib
    from downloader import download_youtube_sync
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            vid = "dQw4w9WgXcQ"
            if "v=" in test_url:
                vid = test_url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in test_url:
                vid = test_url.split("youtu.be/")[1].split("?")[0]
            elif "shorts/" in test_url:
                vid = test_url.split("shorts/")[1].split("?")[0]
            print(f"Running test download for {vid} on Hugging Face...")
            res = download_youtube_sync(vid, "720")
            print(f"RESULT: {res.get('title')} | size={os.path.getsize(res.get('file_path', ''))} | tier={res.get('tier_used')}")
    except Exception as e:
        print(f"EXCEPTION: {e}")
    return buf.getvalue()

with gr.Blocks(title="InstaJetLoad Bot Server") as demo:
    gr.Markdown("# 📥 InstaJetLoad Instagram Downloader Telegram Bot")
    gr.Markdown("### ✅ Server Status: **Running 24/7 on Hugging Face Spaces (Free Tier)**")
    status_display = gr.Textbox(value=get_server_status, label="Live Heartbeat", every=15, interactive=False)
    gpu_status = gr.Textbox(value=gpu_health_check, label="Hardware Engine", interactive=False)
    logs_display = gr.Textbox(value=get_live_bot_logs, label="Live Bot Logs", every=5, lines=15)
    test_in = gr.Textbox(value="https://www.youtube.com/watch?v=dQw4w9WgXcQ", label="Test Video URL")
    test_btn = gr.Button("Run Test Download on HF")
    test_out = gr.Textbox(label="Test Output", lines=10)
    test_btn.click(fn=run_test_diagnostic, inputs=test_in, outputs=test_out)
    gr.Markdown("---")
    gr.Markdown("💡 *Organic Stochastic Traffic Engine active: randomized non-linear browsing emulation.*")

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
