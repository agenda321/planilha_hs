import os
import sys
import time
import re
from flask import Flask, request, jsonify, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_cors import CORS
from flask_socketio import SocketIO, join_room

print("🚀 Iniciando aplicação...")
sys.stdout.flush()

try:
    from escala import ESCALA_MENSAL
    print("✅ Escala carregada com sucesso")
except Exception as e:
    print(f"❌ Erro ao carregar escala: {e}")
    ESCALA_MENSAL = {}
sys.stdout.flush()

app = Flask(__name__)
CORS(app)
print("✅ Flask e CORS configurados")
sys.stdout.flush()

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
print("✅ SocketIO configurado")
sys.stdout.flush()

# Configuração do banco de dados
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    print("❌ DATABASE_URL não definida! Usando SQLite.")
    database_url = "sqlite:///test.db"
else:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    print(f"✅ DATABASE_URL configurada")
    sys.stdout.flush()

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}
db = SQLAlchemy(app)
print("✅ SQLAlchemy configurado")
sys.stdout.flush()

EDIT_PASSWORD = os.environ.get("EDIT_PASSWORD", "Emerson")
EDIT_PASSWORD_2 = os.environ.get("EDIT_PASSWORD_2", "Bispo")
PILOTOS_EXCLUIDOS = []

# ===== MODELOS =====
class Pilot(db.Model):
    __tablename__ = "pilot"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    group = db.Column(db.String(50), nullable=False)

class FlightLog(db.Model):
    __tablename__ = "flight_log"
    id = db.Column(db.Integer, primary_key=True)
    pilot_id = db.Column(db.Integer, db.ForeignKey("pilot.id"), nullable=False)
    day = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    hours = db.Column(db.Float, nullable=False, default=0.0)
    sugestoes = db.Column(db.JSON, nullable=False, default={})
    pilot = db.relationship("Pilot", backref=db.backref("flight_logs", lazy=True))

class StatusOverride(db.Model):
    __tablename__ = "status_override"
    id = db.Column(db.Integer, primary_key=True)
    pilot_id = db.Column(db.Integer, db.ForeignKey("pilot.id"), nullable=False)
    day = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(10), nullable=False)
    pilot = db.relationship("Pilot", backref=db.backref("status_overrides", lazy=True))

print("✅ Modelos definidos")
sys.stdout.flush()

# ===== FUNÇÕES AUXILIARES =====
def getNomeMes(num):
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    return meses[num-1] if 1 <= num <= 12 else "Julho"

def sala_do_mes(month, year):
    return f"{int(month)}-{int(year)}"

def logs_por_piloto(logs):
    result = {}
    for log in logs:
        if log.pilot.name not in result:
            result[log.pilot.name] = {}
        key = f"{log.month},{log.day}"
        result[log.pilot.name][key] = log.hours
    return result

# ===== ROTAS =====
@app.route("/")
def landing():
    return redirect("/planilha")

@app.route("/planilha")
def planilha():
    return render_template("planilha.html")

@app.route("/health")
def health():
    return "OK", 200

@socketio.on("join_month")
def on_join_month(data):
    try:
        month = int(data.get("month"))
        year = int(data.get("year"))
        join_room(sala_do_mes(month, year))
    except Exception as e:
        print(f"❌ Erro em join_month: {e}")

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        if data.get("password") in [EDIT_PASSWORD, EDIT_PASSWORD_2]:
            return jsonify({"success": True})
        return jsonify({"success": False}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/data", methods=["GET"])
def get_data():
    print("📤 GET /api/data chamado")
    try:
        month = request.args.get("month", default=datetime.now().month, type=int)
        year = request.args.get("year", default=datetime.now().year, type=int)
        pilots = Pilot.query.filter(Pilot.name.notin_(PILOTOS_EXCLUIDOS)).all()
        logs_current = FlightLog.query.filter_by(month=month, year=year).all()

        sugestoes_consolidadas = {}
        for log in logs_current:
            if log.sugestoes:
                sugestoes_consolidadas.update(log.sugestoes)

        result = {
            "pilots": [{"name": p.name, "group": p.group, "full_name": p.full_name or p.name} for p in pilots],
            "logs": {},
            "sugestoes": sugestoes_consolidadas
        }

        for log in logs_current:
            if log.pilot.name not in result["logs"]:
                result["logs"][log.pilot.name] = {}
            result["logs"][log.pilot.name][log.day] = log.hours

        print(f"📤 Retornando {len(sugestoes_consolidadas)} sugestões")
        return jsonify(result)
    except Exception as e:
        print(f"❌ Erro em GET: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/data", methods=["POST"])
def save_data():
    print("🚨 POST /api/data CHAMADO!")
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "erro": "Dados não enviados"}), 400
            
        print(f"📥 Dados recebidos: {list(data.keys())}")
        
        if data.get("password") not in [EDIT_PASSWORD, EDIT_PASSWORD_2]:
            return jsonify({"success": False}), 401
            
        month = data.get("month")
        year = data.get("year")
        if not month or not year:
            return jsonify({"success": False, "erro": "Mês e ano obrigatórios"}), 400
            
        month = int(month)
        year = int(year)
        
        sugestoes_recebidas = data.get("sugestoes", {})
        mes_nome = getNomeMes(month)
        
        print(f"📥 Salvando {len(sugestoes_recebidas)} sugestões")
        
        for pilot_name, days in data.get("logs", {}).items():
            pilot = Pilot.query.filter_by(name=pilot_name).first()
            if not pilot:
                print(f"⚠️ Piloto não encontrado: {pilot_name}")
                continue
                
            for day_str, hours in days.items():
                day = int(day_str)
                if hours is None:
                    log = FlightLog.query.filter_by(pilot_id=pilot.id, day=day, month=month, year=year).first()
                    if log:
                        db.session.delete(log)
                    continue
                    
                valor_horas = float(hours) if hours else 0.0
                log = FlightLog.query.filter_by(pilot_id=pilot.id, day=day, month=month, year=year).first()
                
                if log:
                    log.hours = valor_horas
                else:
                    log = FlightLog(pilot_id=pilot.id, day=day, month=month, year=year, hours=valor_horas)
                    db.session.add(log)
                    
                # Salva sugestões
                key = f"{mes_nome}_{year}_{pilot_name}_{day}"
                if key in sugestoes_recebidas and sugestoes_recebidas[key]:
                    if not log.sugestoes:
                        log.sugestoes = {}
                    log.sugestoes[key] = True
                    print(f"✅ Sugestão salva: {key}")
                    
        db.session.commit()
        print(f"✅ Commit realizado com sucesso")
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Erro em POST: {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"success": False, "erro": str(e)}), 500

# ===== INICIALIZAÇÃO =====
with app.app_context():
    db.create_all()
    print("✅ Tabelas criadas/verificadas")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
