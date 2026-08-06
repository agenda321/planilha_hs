import os
import sys
import time
import re
import traceback
from flask import Flask, request, jsonify, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_cors import CORS
from flask_socketio import SocketIO, join_room

print("🚀 Iniciando aplicação...")
sys.stdout.flush()

app = Flask(__name__)
CORS(app)
print("✅ Flask e CORS configurados")
sys.stdout.flush()

socketio = SocketIO(app, cors_allowed_origins="*")
print("✅ SocketIO configurado")
sys.stdout.flush()

# === CONFIGURAÇÃO DO BANCO DE DADOS ===
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    print("❌ DATABASE_URL não definida! Usando SQLite para teste.")
    database_url = "sqlite:///test.db"
else:
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    if "supabase" in database_url.lower():
        match = re.search(r'postgres\.([a-zA-Z0-9]+)[:@]', database_url)
        if not match:
            match = re.search(r'://[^@]+@([^.]+)\.supabase\.co', database_url)
        if match:
            project_id = match.group(1)
            print(f"🔑 Projeto Supabase detectado: {project_id}")
            if "?" not in database_url:
                database_url += f"?sslmode=require&options=project%3D{project_id}"
            elif "sslmode" not in database_url:
                database_url += f"&sslmode=require&options=project%3D{project_id}"
            elif "options" not in database_url:
                database_url += f"&options=project%3D{project_id}"
        else:
            print("⚠️ Não foi possível extrair o ID do projeto Supabase. Adicionando fallback.")
            if "?" not in database_url:
                database_url += "?sslmode=require"
            elif "sslmode" not in database_url:
                database_url += "&sslmode=require"
    else:
        if "?" not in database_url:
            database_url += "?sslmode=require"
        elif "sslmode" not in database_url:
            database_url += "&sslmode=require"

    print("✅ DATABASE_URL configurada")
    sys.stdout.flush()

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 280,
    "pool_size": 10,
    "max_overflow": 20,
    "connect_args": {
        "connect_timeout": 30,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3
    }
}
db = SQLAlchemy(app)
print("✅ SQLAlchemy configurado")
sys.stdout.flush()

EDIT_PASSWORD = os.environ.get("EDIT_PASSWORD", "Emerson")
EDIT_PASSWORD_2 = os.environ.get("EDIT_PASSWORD_2", "Bispo")
PILOTOS_EXCLUIDOS = []

# === MODELOS ===
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

print("✅ Modelos definidos")
sys.stdout.flush()

# === FUNÇÕES AUXILIARES ===
def getNomeMes(num):
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    return meses[num-1] if 1 <= num <= 12 else "Julho"

def sala_do_mes(month, year):
    return f"{int(month)}-{int(year)}"

# === ROTAS E SOCKETS ===
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
        room = sala_do_mes(month, year)
        join_room(room)
        print(f"👤 Cliente entrou na sala: {room}")
        sys.stdout.flush()
    except Exception as e:
        print(f"❌ Erro em join_month: {e}")
        sys.stdout.flush()

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        if data.get("password") in [EDIT_PASSWORD, EDIT_PASSWORD_2]:
            return jsonify({"success": True})
        return jsonify({"success": False}), 401
    except Exception as e:
        print(f"❌ Erro em /api/login: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/data", methods=["GET"])
def get_data():
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

        print(f"📤 Retornando dados para {month}/{year}")
        return jsonify(result)
    except Exception as e:
        print(f"❌ Erro em /api/data (GET): {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/data", methods=["POST"])
def save_data():
    print("🚨 POST /api/data CHAMADO!")
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "erro": "Dados não enviados"}), 400
            
        if data.get("password") not in [EDIT_PASSWORD, EDIT_PASSWORD_2]:
            return jsonify({"success": False}), 401

        month = data.get("month")
        year = data.get("year")
        if not month or not year:
            return jsonify({"success": False, "erro": "Mês e ano são obrigatórios"}), 400

        month = int(month)
        year = int(year)

        logs_recebidos = data.get("logs", {})
        sugestoes_recebidas = data.get("sugestoes", {})
        
        print(f"📥 RECEBIDO logs para {month}/{year}")

        # === SALVAR HORAS ===
        for pilot_name, days in logs_recebidos.items():
            pilot = Pilot.query.filter_by(name=pilot_name).first()
            if not pilot:
                print(f"⚠️ Piloto não encontrado: {pilot_name}")
                continue
                
            for day_str, hours in days.items():
                day = int(day_str)
                
                # Se hours for None ou vazio, remove o registro
                if hours is None or hours == "":
                    log = FlightLog.query.filter_by(
                        pilot_id=pilot.id, 
                        day=day, 
                        month=month, 
                        year=year
                    ).first()
                    if log:
                        db.session.delete(log)
                    continue
                
                try:
                    valor_horas = float(hours)
                except (ValueError, TypeError):
                    print(f"⚠️ Valor inválido: {pilot_name} dia {day} = {hours}")
                    continue
                
                log = FlightLog.query.filter_by(
                    pilot_id=pilot.id, 
                    day=day, 
                    month=month, 
                    year=year
                ).first()
                
                if log:
                    log.hours = valor_horas
                else:
                    log = FlightLog(
                        pilot_id=pilot.id,
                        day=day,
                        month=month,
                        year=year,
                        hours=valor_horas
                    )
                    db.session.add(log)

        # === SALVAR SUGESTÕES ===
        if sugestoes_recebidas:
            mes_nome = getNomeMes(month)
            for key, value in sugestoes_recebidas.items():
                if not value:
                    continue
                parts = key.split('_')
                if len(parts) < 4:
                    continue
                mes_nome_key = parts[0]
                ano_key = int(parts[1])
                pilot_name_key = parts[2]
                dia_key = int(parts[3])
                
                if ano_key != year or mes_nome_key != mes_nome:
                    continue
                    
                pilot = Pilot.query.filter_by(name=pilot_name_key).first()
                if not pilot:
                    continue
                    
                log = FlightLog.query.filter_by(
                    pilot_id=pilot.id, 
                    day=dia_key, 
                    month=month, 
                    year=year
                ).first()
                
                if log:
                    if log.sugestoes is None:
                        log.sugestoes = {}
                    log.sugestoes[key] = True
                else:
                    log = FlightLog(
                        pilot_id=pilot.id,
                        day=dia_key,
                        month=month,
                        year=year,
                        hours=0.0,
                        sugestoes={key: True}
                    )
                    db.session.add(log)

        db.session.commit()
        print(f"✅ Commit realizado com sucesso para {month}/{year}")

        # 📢 EMITE O AVISO EM TEMPO REAL PARA TODOS CONECTADOS NO MESMO MÊS/ANO
        socketio.emit(
            "data_updated", 
            {"month": month, "year": year}, 
            to=sala_do_mes(month, year)
        )

        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Erro em /api/data (POST): {e}")
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"success": False, "erro": str(e)}), 500

@app.route("/api/debug/clear-month/<int:month>/<int:year>")
def clear_month(month, year):
    try:
        apagados = FlightLog.query.filter_by(month=month, year=year).delete()
        db.session.commit()
        return f"✅ {apagados} registro(s) de horas apagados para {month}/{year}."
    except Exception as e:
        db.session.rollback()
        return f"Erro: {e}", 500

# === POPULAR BANCO INICIAL ===
def povoar_dados_iniciais():
    grupos = {
        "Andre": "CESSNA 206/210", "Andrade": "CESSNA 206/210", "Luiz": "CESSNA 206/210",
        "Adelio": "CESSNA 206/210", "Amarildo": "CESSNA 206/210", "Cleverson": "CESSNA 206/210",
        "Hazafe": "CESSNA 206/210", "Dayvid": "CESSNA 206/210", "Edson": "CESSNA 206/210",
        "Frank": "CESSNA 206/210", "Gabriel": "CESSNA 206/210", "Igorh": "CESSNA 206/210",
        "Leandro": "CESSNA 206/210", "Milton": "CESSNA 206/210", "Paulo": "CESSNA 206/210",
        "Ronie": "CESSNA 206/210", "Sergio": "CESSNA 206/210", "Otto": "CESSNA 206/210",
        "Dany": "CESSNA 206/210", "Lucas": "CESSNA 206/210", "Roberto": "CESSNA 206/210",
        "Renan": "CESSNA 206/210", "Wellber": "CESSNA 206/210", "Bento": "CESSNA 206/210",
        "Costa": "CESSNA 206/210", "Victor": "CESSNA 206/210", "Matias": "CESSNA 206/210",
        "Cleiton": "CARAVAN", "Joao": "CARAVAN", "Pascoal": "CARAVAN",
        "Lindomar": "CARAVAN", "Perisson": "CARAVAN", "Rui": "CARAVAN", "Yago": "CARAVAN",
        "Cauê": "COPILOTO", "Ruben": "COPILOTO", "Ernesto": "COPILOTO", "Daniela": "COPILOTO",
        "Thales": "COPILOTO", "Serafim": "COPILOTO", "Ronalldo": "COPILOTO", "Rodrigo": "COPILOTO"
    }
    for nome, group in grupos.items():
        piloto = Pilot(name=nome, full_name=nome, group=group)
        db.session.add(piloto)
    db.session.commit()
    print("✅ Pilotos populados")
    sys.stdout.flush()

def init_db():
    print("🔄 Tentando criar tabelas...")
    sys.stdout.flush()
    for attempt in range(5):
        try:
            with app.app_context():
                db.create_all()
                if Pilot.query.count() == 0:
                    povoar_dados_iniciais()
                else:
                    print(f"✅ Banco já possui {Pilot.query.count()} pilotos.")
                print("✅ Banco conectado e inicializado com sucesso.")
                sys.stdout.flush()
                return
        except Exception as e:
            print(f"⚠️ Tentativa {attempt+1}/5 falhou: {e}")
            sys.stdout.flush()
            time.sleep(5)
    print("❌ Falha ao criar tabelas após 5 tentativas")
    sys.stdout.flush()

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ Servidor rodando na porta {port}")
    sys.stdout.flush()
    socketio.run(app, host="0.0.0.0", port=port)
