import os
import sys
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

# Configura o banco
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    print("❌ DATABASE_URL não definida")
    sys.stdout.flush()
    # Fallback apenas para teste
    database_url = "sqlite:///test.db"

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

print("✅ SQLAlchemy configurado")
sys.stdout.flush()

# Define um modelo mínimo
class Pilot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))

print("✅ Modelo definido")
sys.stdout.flush()

# Cria as tabelas
with app.app_context():
    db.create_all()
    print("✅ Tabelas criadas")
    sys.stdout.flush()

@app.route("/")
def home():
    return "OK"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ Servidor rodando na porta {port}")
    sys.stdout.flush()
    app.run(host="0.0.0.0", port=port)
