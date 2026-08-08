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
# 🔧 CORREÇÃO DE TIMEOUT: Permite que o servidor demore até 2 minutos para salvar
app.config['TIMEOUT'] = 120 
print("✅ Flask e CORS configurados")
sys.stdout.flush()

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
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
    cor = db.Column(db.String(20), nullable=True)
    pilot = db.relationship("Pilot", backref=db.backref("flight_logs", lazy=True))

print("✅ Modelos definidos")
sys.stdout.flush()

# === FUNÇÕES AUXILIARES ===
def getNomeMes(num):
    meses = ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
    return meses[num-1] if 1 <= num <= 12 else "Julho"

def sala_do_mes(month, year):
    return f"{int(month)}-{int(year)}"

def converter_para_float(valor):
    """Converte string com vírgula para float"""
    if valor is None or valor == "":
        return None
    # Remove "h", "H" e substitui vírgula por ponto
    valor_str = str(valor).replace('h', '').replace('H', '').replace(',', '.').strip()
    # Remove qualquer caractere que não seja número ou ponto
    valor_str = re.sub(r'[^0-9.]', '', valor_str)
    try:
        return float(valor_str)
    except ValueError:
        return None

# === TRATAMENTO DE ERROS GLOBAL ===
@app.errorhandler(404)
def not_found(error):
    return jsonify({"erro": "Rota não encontrada"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"erro": "Erro interno do servidor"}), 500

@app.errorhandler(Exception)
def handle_exception(error):
    return jsonify({"erro": str(error)}), 500

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
            "cores": {},
            "sugestoes": sugestoes_consolidadas
        }

        for log in logs_current:
            pilot_name = log.pilot.name
            if pilot_name not in result["logs"]:
                result["logs"][pilot_name] = {}
                result["cores"][pilot_name] = {}
            
            result["logs"][pilot_name][log.day] = log.hours if log.hours is not None else 0.0
            
            if log.cor:
                result["cores"][pilot_name][log.day] = log.cor

        print(f"📤 Retornando {len(pilots)} pilotos e {len(logs_current)} logs para {month}/{year}")
        return jsonify(result)
    except Exception as e:
        print(f"❌ Erro em /api/data (GET): {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/data", methods=["POST"])
def save_data():
    """Versão CORRIGIDA com tratamento de vírgula e suporte a cores"""
    print("🚨 POST /api/data CHAMADO!")
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
        
        print(f"📥 RECEBIDO logs para {month}/{year}")
        print(f"📥 Pilotos no payload: {list(logs_recebidos.keys())}")

        # Buscar todos os pilotos de uma vez
        pilotos_nomes = list(logs_recebidos.keys())
        pilotos = Pilot.query.filter(Pilot.name.in_(pilotos_nomes)).all()
        pilotos_dict = {p.name: p for p in pilotos}
        
        # Buscar todos os logs existentes de uma vez
        logs_existentes = FlightLog.query.filter_by(month=month, year=year).all()
        logs_dict = {}
        for log in logs_existentes:
            key = f"{log.pilot_id}_{log.day}"
            logs_dict[key] = log

        logs_para_adicionar = []
        logs_para_atualizar = []
        logs_para_deletar = []

        # PROCESSAR LOGS
        for pilot_name, days in logs_recebidos.items():
            pilot = pilotos_dict.get(pilot_name)
            if not pilot:
                print(f"⚠️ Piloto NÃO ENCONTRADO: {pilot_name}")
                continue
                
            for day_str, hours in days.items():
                day = int(day_str)
                key = f"{pilot.id}_{day}"
                log = logs_dict.get(key)
                
                # Busca a cor para este dia/piloto
                cor_key = f"{pilot_name}_{day}"
                cor = cores_recebidas.get(cor_key)
                
                # Se o valor for None ou vazio, deleta (considera folga)
                if hours is None or hours == "":
                    if log:
                        logs_para_deletar.append(log)
                    continue
                
                # Converte o valor (incluindo 0.0)
                valor_horas = converter_para_float(hours)
                if valor_horas is None:
                    print(f"⚠️ Valor inválido: {pilot_name} dia {day} = {hours}")
                    continue
                
                if log:
                    log.hours = valor_horas
                    if cor:
                        log.cor = cor
                    logs_para_atualizar.append(log)
                else:
                    novo_log = FlightLog(
                        pilot_id=pilot.id,
                        day=day,
                        month=month,
                        year=year,
                        hours=valor_horas,
                        sugestoes={},
                        cor=cor if cor else None
                    )
                    logs_para_adicionar.append(novo_log)

        # PROCESSAR SUGESTÕES
        if sugestoes_recebidas:
            mes_nome = getNomeMes(month)
            print(f"📥 Processando {len(sugestoes_recebidas)} sugestões")
            
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
                    
                pilot = pilotos_dict.get(pilot_name_key)
                if not pilot:
                    continue
                
                log_key = f"{pilot.id}_{dia_key}"
                log = logs_dict.get(log_key)
                
                if log:
                    if log.sugestoes is None:
                        log.sugestoes = {}
                    log.sugestoes[key] = True
                else:
                    novo_log = FlightLog(
                        pilot_id=pilot.id,
                        day=dia_key,
                        month=month,
                        year=year,
                        hours=0.0,
                        sugestoes={key: True},
                        cor=None
                    )
                    logs_para_adicionar.append(novo_log)

        # EXECUTAR OPERAÇÕES EM LOTE
        if logs_para_deletar:
            for log in logs_para_deletar:
                db.session.delete(log)
            print(f"🗑️ Deletados: {len(logs_para_deletar)} logs")

        if logs_para_adicionar:
            db.session.add_all(logs_para_adicionar)
            print(f"➕ Adicionados: {len(logs_para_adicionar)} logs")

        db.session.commit()
        total = len(logs_para_adicionar) + len(logs_para_atualizar)
        print(f"✅ Commit realizado! {total} logs salvos para {month}/{year}")

        socketio.emit(
            "data_updated", 
            {"month": month, "year": year}, 
            to=sala_do_mes(month, year)
        )

        return jsonify({"success": True, "logs_salvos": total})
        
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

# ========================
# 🔧 ROTAS DE TESTE
# ========================

@app.route("/test-db")
def test_db():
    try:
        resultado = {
            "status": "OK",
            "conexao": False,
            "tabelas": {},
            "pilotos": 0,
            "logs": 0,
            "ultimos_logs": []
        }
        
        db.session.execute(text("SELECT 1"))
        resultado["conexao"] = True
        resultado["pilotos"] = Pilot.query.count()
        resultado["logs"] = FlightLog.query.count()
        
        ultimos = FlightLog.query.order_by(FlightLog.id.desc()).limit(5).all()
        for log in ultimos:
            resultado["ultimos_logs"].append({
                "id": log.id,
                "piloto": log.pilot.name if log.pilot else "N/A",
                "dia": log.day,
                "mes": log.month,
                "ano": log.year,
                "horas": log.hours,
                "cor": log.cor
            })
        
        tabelas = db.session.execute(text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)).fetchall()
        resultado["tabelas"]["public"] = [t[0] for t in tabelas]
        
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"status": "ERRO", "erro": str(e), "tipo": type(e).__name__}), 500

@app.route("/test-insert")
def test_insert():
    try:
        from datetime import datetime
        
        pilot = Pilot.query.filter_by(name="TESTE_AUTO").first()
        if not pilot:
            pilot = Pilot(name="TESTE_AUTO", full_name="Teste Automático", group="TESTE")
            db.session.add(pilot)
            db.session.commit()
        
        now = datetime.now()
        log = FlightLog(
            pilot_id=pilot.id,
            day=now.day,
            month=now.month,
            year=now.year,
            hours=8.5,
            sugestoes={"teste": True},
            cor="#fff1b5"
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            "status": "SUCESSO",
            "mensagem": "Dados inseridos com sucesso!",
            "piloto": {"id": pilot.id, "nome": pilot.name, "grupo": pilot.group},
            "log": {"id": log.id, "dia": now.day, "mes": now.month, "ano": now.year, "horas": 8.5, "cor": "#fff1b5"}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "ERRO", "erro": str(e)}), 500

@app.route("/test-supabase")
def test_supabase():
    try:
        is_supabase = "supabase" in app.config["SQLALCHEMY_DATABASE_URI"].lower()
        tabelas = db.session.execute(text("""
            SELECT tablename FROM pg_tables WHERE schemaname = 'public'
        """)).fetchall()
        
        return jsonify({
            "supabase_detectado": is_supabase,
            "tabelas_public": [t[0] for t in tabelas],
            "versao_postgres": db.session.execute(text("SELECT version()")).fetchone()[0][:100]
        })
    except Exception as e:
        return jsonify({"status": "ERRO", "erro": str(e)}), 500

# ========================
# FIM DAS ROTAS DE TESTE
# ========================

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

# ==============================
# 🔥 INICIALIZAÇÃO FINAL COM TIMEOUT CORRIGIDO
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"✅ Servidor rodando na porta {port} em modo otimizado para Render")
    sys.stdout.flush()
    
    # Inicialização do SocketIO com parâmetros que evitam timeouts no Render
    socketio.run(
        app, 
        host="0.0.0.0", 
        port=port,
        debug=False,
        use_reloader=False,
        log_output=True,
        allow_unsafe_werkzeug=True
    )
