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
from sqlalchemy import text

print("🚀 Iniciando aplicação...")
sys.stdout.flush()

app = Flask(__name__)
CORS(app)
app.config['TIMEOUT'] = 120

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

database_url = os.environ.get("DATABASE_URL")
if not database_url:
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
            if "?" not in database_url:
                database_url += f"?sslmode=require&options=project%3D{project_id}"
            elif "sslmode" not in database_url:
                database_url += f"&sslmode=require&options=project%3D{project_id}"
            elif "options" not in database_url:
                database_url += f"&options=project%3D{project_id}"
        else:
            if "?" not in database_url:
                database_url += "?sslmode=require"
            elif "sslmode" not in database_url:
                database_url += "&sslmode=require"
    else:
        if "?" not in database_url:
            database_url += "?sslmode=require"
        elif "sslmode" not in database_url:
            database_url += "&sslmode=require"

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

EDIT_PASSWORD = os.environ.get("EDIT_PASSWORD", "Emerson")
EDIT_PASSWORD_2 = os.environ.get("EDIT_PASSWORD_2", "Bispo")
PILOTOS_EXCLUIDOS = []

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
    hours = db.Column(db.Float, nullable=True, default=None)
    sugestoes = db.Column(db.JSON, nullable=False, default={})
    cor = db.Column(db.String(20), nullable=True)
    pilot = db.relationship("Pilot", backref=db.backref("flight_logs", lazy=True))

def getNomeMes(num):
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    return meses[num-1] if 1 <= num <= 12 else "Julho"

def sala_do_mes(month, year):
    return f"{int(month)}-{int(year)}"

def converter_para_float(valor):
    if valor is None or valor == "":
        return None
    valor_str = str(valor).replace('h', '').replace('H', '').replace(',', '.').strip()
    valor_str = re.sub(r'[^0-9.]', '', valor_str)
    try:
        return float(valor_str)
    except ValueError:
        return None

@app.errorhandler(404)
def not_found(error):
    return jsonify({"erro": "Rota não encontrada"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"erro": "Erro interno do servidor"}), 500

@app.errorhandler(Exception)
def handle_exception(error):
    return jsonify({"erro": str(error)}), 500

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
        print(f"❌ Erro join_month: {e}")

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
            "cores": {},
            "sugestoes": sugestoes_consolidadas
        }

        for log in logs_current:
            pilot_name = log.pilot.name
            if pilot_name not in result["logs"]:
                result["logs"][pilot_name] = {}
                result["cores"][pilot_name] = {}
            result["logs"][pilot_name][log.day] = log.hours
            if log.cor:
                result["cores"][pilot_name][log.day] = log.cor

        return jsonify(result)
    except Exception as e:
        print(f"❌ Erro GET /api/data: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/data", methods=["POST"])
def save_data():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "erro": "Dados não enviados"}), 400
        if data.get("password") not in [EDIT_PASSWORD, EDIT_PASSWORD_2]:
            return jsonify({"success": False}), 401

        try:
            month = int(data.get("month"))
            year = int(data.get("year"))
        except (ValueError, TypeError):
            return jsonify({"success": False, "erro": "Mês ou ano inválidos"}), 400

        logs_recebidos = data.get("logs", {})
        sugestoes_recebidas = data.get("sugestoes", {})
        cores_recebidas = data.get("cores", {})

        pilotos_nomes = list(logs_recebidos.keys())
        pilotos = Pilot.query.filter(Pilot.name.in_(pilotos_nomes)).all()
        pilotos_dict = {p.name: p for p in pilotos}

        logs_existentes = FlightLog.query.filter_by(month=month, year=year).all()
        logs_dict = {f"{log.pilot_id}_{log.day}": log for log in logs_existentes}

        logs_para_adicionar = []
        logs_para_atualizar = []
        logs_para_deletar = []

        for pilot_name, days in logs_recebidos.items():
            pilot = pilotos_dict.get(pilot_name)
            if not pilot:
                continue

            for day_str, hours in days.items():
                day = int(day_str)
                key = f"{pilot.id}_{day}"
                log = logs_dict.get(key)
                cor = cores_recebidas.get(f"{pilot_name}_{day}")

                if hours is None or hours == "":
                    if cor:
                        if log:
                            log.hours = None
                            log.cor = cor
                            logs_para_atualizar.append(log)
                        else:
                            logs_para_adicionar.append(FlightLog(
                                pilot_id=pilot.id, day=day, month=month, year=year,
                                hours=None, sugestoes={}, cor=cor
                            ))
                    else:
                        if log:
                            logs_para_deletar.append(log)
                    continue

                valor_horas = converter_para_float(hours)
                if valor_horas is None:
                    continue

                if log:
                    log.hours = valor_horas
                    if cor is not None:
                        log.cor = cor
                    logs_para_atualizar.append(log)
                else:
                    logs_para_adicionar.append(FlightLog(
                        pilot_id=pilot.id, day=day, month=month, year=year,
                        hours=valor_horas, sugestoes={}, cor=cor
                    ))

        if sugestoes_recebidas:
            mes_nome = getNomeMes(month)
            for key, value in sugestoes_recebidas.items():
                if not value:
                    continue
                parts = key.split('_')
                if len(parts) < 4:
                    continue
                if int(parts[1]) != year or parts[0] != mes_nome:
                    continue
                pilot = pilotos_dict.get(parts[2])
                if not pilot:
                    continue
                dia_key = int(parts[3])
                log_key = f"{pilot.id}_{dia_key}"
                log = logs_dict.get(log_key)
                if log:
                    if log.sugestoes is None:
                        log.sugestoes = {}
                    log.sugestoes[key] = True
                else:
                    logs_para_adicionar.append(FlightLog(
                        pilot_id=pilot.id, day=dia_key, month=month, year=year,
                        hours=None, sugestoes={key: True}, cor=None
                    ))

        for log in logs_para_deletar:
            db.session.delete(log)
        if logs_para_adicionar:
            db.session.add_all(logs_para_adicionar)

        db.session.commit()
        socketio.emit("data_updated", {"month": month, "year": year}, to=sala_do_mes(month, year))
        return jsonify({"success": True})

    except Exception as e:
        print(f"❌ Erro POST /api/data: {e}")
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"success": False, "erro": str(e)}), 500

@app.route("/api/debug/clear-month/<int:month>/<int:year>")
def clear_month(month, year):
    try:
        apagados = FlightLog.query.filter_by(month=month, year=year).delete()
        db.session.commit()
        return jsonify({"success": True, "apagados": apagados})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "erro": str(e)}), 500

@app.route("/api/debug/pilots")
def debug_pilots():
    try:
        pilots = Pilot.query.all()
        return jsonify([{"id": p.id, "name": p.name, "group": p.group} for p in pilots])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        db.session.add(Pilot(name=nome, full_name=nome, group=group))
    db.session.commit()

def init_db():
    for attempt in range(5):
        try:
            with app.app_context():
                db.create_all()
                if Pilot.query.count() == 0:
                    povoar_dados_iniciais()
                return
        except Exception as e:
            print(f"⚠️ Tentativa {attempt+1}/5: {e}")
            time.sleep(5)

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
