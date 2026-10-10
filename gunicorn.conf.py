# gunicorn.conf.py - production server ki settings (Docker image yahi use karti hai)
# Chalao:  gunicorn -c gunicorn.conf.py app:app
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

# Asli bhaari kaam (U-Net, video) alag Python process mein chalta hai, Flask sirf intezaar karta hai.
# Isliye kam workers + threads kaafi hain, aur /health lambi request ke dauraan bhi jawab deta hai.
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
worker_class = "gthread"
threads = int(os.environ.get("GUNICORN_THREADS", "4"))

# /report 600 s tak chal sakta hai (agent + Bedrock), /inspect 300 s tak
timeout = 660
graceful_timeout = 30
keepalive = 5

accesslog = "-"          # logs stdout par -> CloudWatch
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
