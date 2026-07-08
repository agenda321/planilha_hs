import os
import sys
import time
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

print("🚀 1. Iniciando...")
sys.stdout.flush()

app = Flask(__name__)

# Tenta carregar a escala
try:
    from escala import ESCALA_MENSAL
    print("✅ Escala carregada")
except Exception as e:
    print(f"❌ Erro na escala: {e}")
    ESCALA_MENSAL = {}
sys.stdout.flush()

# ===== CONFIGURAÇÃO DO BANCO (COM TIMEOUT) =====
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    print("❌ DATABASE_URL não definida")
    sys.stdout.flush()
    database_url = "sqlite:///test.db"
else:
    # Garante sslmode e timeout
    if "?" not in database_url:
        database_url += "?sslmode=require&connect_timeout=10"
    elif "sslmode" not in database_url:
        database_url += "&sslmode=require&connect_timeout=10"
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    print(f"✅ DATABASE_URL: {database_url[:40]}...")
    sys.stdout.flush()

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "connect_args": {"connect_timeout": 10}
}
db = SQLAlchemy(app)

print("✅ SQLAlchemy configurado")
sys.stdout.flush()

# ===== MODELO MÍNIMO =====
class Pilot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))

print("✅ Modelo definido")
sys.stdout.flush()

# ===== CRIAÇÃO DAS TABELAS COM RETRY =====
def init_db():
    print("🔄 Tentando criar tabelas...")
    sys.stdout.flush()
    for attempt in range(5):
        try:
            with app.app_context():
                db.create_all()
                print("✅ Tabelas criadas com sucesso")
                sys.stdout.flush()
                return
        except Exception as e:
            print(f"⚠️ Tentativa {attempt+1}/5 falhou: {e}")
            sys.stdout.flush()
            time.sleep(3)
    print("❌ Falha ao criar tabelas após 5 tentativas")
    sys.stdout.flush()

init_db()

# ===== ROTAS =====
@app.route("/")
def home():
    return "OK"

@app.route("/health")
def health():
    return "OK", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ Servidor rodando na porta {port}")
    sys.stdout.flush()
    app.run(host="0.0.0.0", port=port)
