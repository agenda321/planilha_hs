import os
import sys
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "OK - Servidor rodando"

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ Servidor iniciando na porta {port}")
    sys.stdout.flush()
    app.run(host="0.0.0.0", port=port)
