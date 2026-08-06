import os
import sys
import time
import re
from flask import Flask, request, jsonify, render_template, redirect
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime
from flask_cors import CORS
from flask_socketio import SocketIO, join_room

print("🚀 Iniciando aplicação...")
sys.stdout.flush()

app = Flask(__name__)
CORS(app)
print("✅ Flask e CORS configurados")
sys.stdout.flush()

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
print("✅ SocketIO configurado (async_mode=threading)")
sys.stdout.flush()

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

    print(f"✅ DATABASE_URL configurada")
    sys.stdout.flush()

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
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
CODIGOS_DISPONIVEIS = ["VO", "CQ", "RE", "SO", "EA", "TR", "TN"]
CORES = {
    "DM": "laranja",
    "CM": "laranja_claro",
    "VO": "azul",
    "EA": "amarelo",
    "FR": "verde",
    "FS": "vermelho",
    "FE": "verde_claro",
    "RE": "rosa",
    "SO": "branco",
    "TR": "amarelo_escuro",
    "TN": "azul_claro",
    "CQ": "azul_medio"
}
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
    hours = db.Column(db.Float, nullable=False, default=0.0)
    sugestoes = db.Column(db.JSON, nullable=False, default=dict)
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

def getNomeMes(num):
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    return meses[num-1] if 1 <= num <= 12 else "Julho"

def normalizar_status(status):
    if status is None or status == "" or status == " ":
        return "VO"
    return status

def obtener_escala_dinamica(pilot_obj, month, year):
    return []

def logs_por_piloto(logs):
    result = {}
    for log in logs:
        if log.pilot.name not in result:
            result[log.pilot.name] = {}
        key = f"{log.month},{log.day}"
        result[log.pilot.name][key] = log.hours
    return result

@app.route("/")
def landing():
    return redirect("/planilha")

@app.route("/planilha")
def planilha():
    return render_template("planilha.html")

@app.route("/health")
def health():
    return "OK", 200

def sala_do_mes(month, year):
    return f"{int(month)}-{int(year)}"

@socketio.on("join_month")
def on_join_month(data):
    try:
        month = int(data.get("month"))
        year = int(data.get("year"))
        join_room(sala_do_mes(month, year))
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

        prev_month = month - 1 if month > 1 else 12
        prev_year = year if month > 1 else year - 1
        logs_prev = FlightLog.query.filter_by(month=prev_month, year=prev_year).all()
        next_month = month + 1 if month < 12 else 1
        next_year = year if month < 12 else year + 1
        logs_next = FlightLog.query.filter_by(month=next_month, year=next_year).all()

        logs_current_map = logs_por_piloto(logs_current)
        logs_prev_map = logs_por_piloto(logs_prev)
        logs_next_map = logs_por_piloto(logs_next)

        logs_adjacent = {}
        for pilot_name in set(logs_current_map) | set(logs_prev_map) | set(logs_next_map):
            logs_adjacent[pilot_name] = {}
            for key, horas in logs_prev_map.get(pilot_name, {}).items():
                logs_adjacent[pilot_name][key] = horas
            for key, horas in logs_current_map.get(pilot_name, {}).items():
                logs_adjacent[pilot_name][key] = horas
            for key, horas in logs_next_map.get(pilot_name, {}).items():
                logs_adjacent[pilot_name][key] = horas

        sugestoes_consolidadas = {}
        for log in logs_current:
            if log.sugestoes:
                sugestoes_consolidadas.update(log.sugestoes)

        # Status / cores
        overrides = StatusOverride.query.filter_by(month=month, year=year).all()
        status_map = {}
        for ov in overrides:
            if ov.pilot and ov.pilot.name:
                if ov.pilot.name not in status_map:
                    status_map[ov.pilot.name] = {}
                status_map[ov.pilot.name][ov.day] = ov.status

        result = {
            "pilots": [{"name": p.name, "group": p.group, "full_name": p.full_name or p.name} for p in pilots],
            "logs": {},
            "logs_adjacent": logs_adjacent,
            "escala": {},
            "sugestoes": sugestoes_consolidadas,
            "status": status_map
        }

        for log in logs_current:
            if log.pilot.name not in result["logs"]:
                result["logs"][log.pilot.name] = {}
            result["logs"][log.pilot.name][log.day] = log.hours

        for p in pilots:
            escala_pilot = obtener_escala_dinamica(p, month, year)
            if escala_pilot:
                result["escala"][p.name] = escala_pilot

        print(f"📤 Retornando {len(sugestoes_consolidadas)} sugestões e {len(status_map)} status para {month}/{year}")
        return jsonify(result)
    except Exception as e:
        print(f"❌ Erro em /api/data (GET): {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/data", methods=["POST"])
def save_data():
    print("🚨 POST /api/data CHAMADO!")
    try:
        data = request.get_json()
        if data.get("password") not in [EDIT_PASSWORD, EDIT_PASSWORD_2]:
            return jsonify({"success": False}), 401
        month = data.get("month")
        year = data.get("year")
        if not month or not year:
            return jsonify({"success": False, "erro": "Mês e ano são obrigatórios"}), 400
        month = int(month); year = int(year)
        
        sugestoes_recebidas = data.get("sugestoes", {})
        mes_nome = getNomeMes(month)
        
        print(f"📥 Salvando {len(sugestoes_recebidas)} sugestões e dados para {month}/{year}")
        
        eventos_para_emitir = []
        for pilot_name, days in data.get("logs", {}).items():
            pilot = Pilot.query.filter_by(name=pilot_name).first()
            if not pilot:
                print(f"⚠️ Piloto não encontrado: {pilot_name}")
                continue
            for day_str, hours in days.items():
                day = int(day_str)
                key = f"{mes_nome}_{year}_{pilot_name}_{day}"
                has_sugestao = key in sugestoes_recebidas and sugestoes_recebidas[key]
                
                valor_horas = float(hours) if hours is not None and str(hours).strip() != "" else 0.0
                log = FlightLog.query.filter_by(pilot_id=pilot.id, day=day, month=month, year=year).first()
                
                if hours is None and not has_sugestao:
                    if log:
                        db.session.delete(log)
                    continue
                
                if log:
                    log.hours = valor_horas
                    if log.sugestoes is None:
                        log.sugestoes = {}
                    
                    sug_dict = dict(log.sugestoes)
                    if has_sugestao:
                        sug_dict[key] = True
                    else:
                        sug_dict.pop(key, None)
                    
                    log.sugestoes = sug_dict
                    flag_modified(log, "sugestoes")
                else:
                    sug_dict = {key: True} if has_sugestao else {}
                    log = FlightLog(
                        pilot_id=pilot.id, 
                        day=day, 
                        month=month, 
                        year=year, 
                        hours=valor_horas, 
                        sugestoes=sug_dict
                    )
                    db.session.add(log)
                    
                eventos_para_emitir.append({
                    "pilot": pilot_name, "day": day, "value": valor_horas,
                    "month": month, "year": year
                })
                
        db.session.commit()
        print(f"✅ Commit realizado com sucesso no Supabase para {month}/{year}")
        
        for evento in eventos_para_emitir:
            socketio.emit("logs_atualizados", evento, room=sala_do_mes(month, year))
            
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Erro em /api/data (POST): {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        return jsonify({"success": False, "erro": str(e)}), 500

@app.route("/api/available_commanders/<int:day_index>", methods=["GET"])
def get_available_commanders(day_index):
    try:
        pilotos_com_horas = {"CESSNA 206/210": [], "CARAVAN": [], "COPILOTO": []}
        pilots = Pilot.query.filter(Pilot.name.notin_(PILOTOS_EXCLUIDOS)).all()
        month = request.args.get("month", default=datetime.now().month, type=int)
        year = request.args.get("year", default=datetime.now().year, type=int)
        dia_solicitado = day_index + 1
        for pilot in pilots:
            status = "VO"
            cor = "azul"
            if status in CODIGOS_DISPONIVEIS:
                logs = FlightLog.query.filter_by(pilot_id=pilot.id, month=month, year=year).all()
                horas_acumuladas = sum(log.hours for log in logs if log.day <= dia_solicitado)
                pilotos_com_horas[pilot.group].append({
                    "name": pilot.name,
                    "status": status,
                    "color": cor,
                    "horas_totais": horas_acumuladas
                })
        available = {}
        for grupo, lista_pilotos in pilotos_com_horas.items():
            available[grupo] = sorted(lista_pilotos, key=lambda x: x["horas_totais"], reverse=True)
        return jsonify(available)
    except Exception as e:
        print(f"❌ Erro em /api/available_commanders: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/update_status", methods=["POST"])
def update_status():
    try:
        data = request.get_json()
        pilot_name = data.get("pilot")
        day = data.get("day")
        new_status = data.get("status")
        month = data.get("month")
        year = data.get("year")
        if not month or not year or not pilot_name or day is None or not new_status:
            return jsonify({"success": False, "erro": "Dados incompletos"}), 400
        month = int(month); year = int(year)
        pilot = Pilot.query.filter_by(name=pilot_name).first()
        if not pilot:
            return jsonify({"success": False, "erro": "Piloto não encontrado"}), 404
        override = StatusOverride.query.filter_by(pilot_id=pilot.id, day=day, month=month, year=year).first()
        if override:
            override.status = new_status
        else:
            override = StatusOverride(pilot_id=pilot.id, day=day, month=month, year=year, status=new_status)
            db.session.add(override)
        db.session.commit()
        socketio.emit("status_atualizado", {
            "pilot": pilot_name, "day": day, "status": new_status,
            "month": month, "year": year
        }, room=sala_do_mes(month, year))
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Erro em /api/update_status: {e}")
        return jsonify({"success": False, "erro": str(e)}), 500

@app.route("/api/debug/reset-banco")
def reset_banco():
    try:
        db.drop_all()
        db.create_all()
        povoar_dados_iniciais()
        return "Banco reiniciado e dados da frota atualizados com sucesso!"
    except Exception as e:
        return f"Erro: {e}", 500

@app.route("/api/debug/clear-month/<int:month>/<int:year>")
def clear_month(month, year):
    try:
        apagados = FlightLog.query.filter_by(month=month, year=year).delete()
        db.session.commit()
        return f"✅ {apagados} registro(s) de horas apagados para {month}/{year}. Pilotos e escala não foram alterados."
    except Exception as e:
        db.session.rollback()
        return f"Erro: {e}", 500

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
    nomes_completos = {
        "Adelio": "Adelio Costa Felinto", "Otto": "Albert Otto Azevedo",
        "Andre": "Andre Luis Fernandes", "Cleiton": "Cleiton Taumaturgo",
        "Cleverson": "Cleverson dos Santos", "Edson": "Edson Fonteles Portela",
        "Frank": "Franker Wendell Dias", "Gabriel": "Gabriel de Oliveira",
        "Costa": "Felipe Pereira Costa de Lima", "Hazafe": "Hazafe Pacheco de Alencar",
        "Amarildo": "João Amarildo Reis dos Santos", "Igorh": "Igorh Coutinho Martins",
        "Joao": "Joao Marcus Oliveira", "Dayvid": "Jose Deyvid Monteiro",
        "Leandro": "Leandro Magalhães", "Lindomar": "Lindomar Bras Mota",
        "Lucas": "Lucas Alves Pereira", "Luiz": "Luiz Andrade de Souza",
        "Matias": "Matias Pires de Campos Junior", "Milton": "Milton Braga de Souza",
        "Pascoal": "Pascoal Brito de Araujo", "Paulo": "Paulo Andre Silva",
        "Perisson": "Perisson Parmigiani", "Renan": "Renan da Silva Nascimento",
        "Roberto": "Roberto Adolfo Boesing", "Ronie": "Ronie Welter",
        "Rui": "Rui de Almeida Vasconcelos", "Sergio": "Sergio Carneiro Rodrigues",
        "Victor": "Victor Augusto Fernandes Monteiro da Silva", "Bento": "Vitor da Costa Bento",
        "Wellber": "Wellber Nogueira Barros", "Andrade": "Wilken Andrade de Paulo",
        "Yago": "Yago Bezerra Correia", "Cauê": "Caue Montanari",
        "Daniela": "Daniela Goncalves Fabricio", "Ernesto": "Ernesto da Silva Kaster",
        "Ruben": "Francisco Rubenicio Souza", "Rodrigo": "Rodrigo Silva Melo",
        "Ronalldo": "Ronalldo Rodrigues Parreao Junior", "Thales": "Thales Araujo Penna",
        "Serafim": "Tiago Carvalho Serafim"
    }
    for nome, group in grupos.items():
        piloto = Pilot(name=nome, full_name=nomes_completos.get(nome, nome), group=group)
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
