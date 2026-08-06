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
    sys.stdout.flush()
    try:
        month = request.args.get("month", default=datetime.now().month, type=int)
        year = request.args.get("year", default=datetime.now().year, type=int)
        
        print(f"📥 Buscando dados: {month}/{year}")
        sys.stdout.flush()
        
        pilots = Pilot.query.filter(Pilot.name.notin_(PILOTOS_EXCLUIDOS)).all()
        logs_current = FlightLog.query.filter_by(month=month, year=year).all()

        print(f"📊 Encontrados: {len(pilots)} pilotos, {len(logs_current)} registros de voo")
        sys.stdout.flush()

        # 🔧 CONSOLIDA TODAS AS SUGESTÕES SALVAS
        sugestoes_consolidadas = {}
        try:
            for log in logs_current:
                if log.sugestoes and isinstance(log.sugestoes, dict):
                    sugestoes_consolidadas.update(log.sugestoes)
        except Exception as sug_error:
            print(f"⚠️ Erro ao processar sugestões: {sug_error}")
            sys.stdout.flush()

        result = {
            "pilots": [{"name": p.name, "group": p.group, "full_name": p.full_name or p.name} for p in pilots],
            "logs": {},
            "sugestoes": sugestoes_consolidadas
        }

        for log in logs_current:
            if log.pilot.name not in result["logs"]:
                result["logs"][log.pilot.name] = {}
            # Garante que o valor é um número (float ou int)
            result["logs"][log.pilot.name][log.day] = float(log.hours) if log.hours is not None else None

        print(f"📤 Retornando {len(sugestoes_consolidadas)} sugestões")
        sys.stdout.flush()
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Erro em GET: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        return jsonify({"error": str(e), "success": False}), 500

@app.route("/api/data", methods=["POST"])
def save_data():
    print("🚨 POST /api/data CHAMADO!")
    sys.stdout.flush()
    
    try:
        # Valida se recebeu JSON
        data = request.get_json()
        if not data:
            print("❌ Dados vazios recebidos")
            sys.stdout.flush()
            return jsonify({"success": False, "erro": "Dados não enviados"}), 400
            
        print(f"📥 Dados recebidos - Chaves: {list(data.keys())}")
        sys.stdout.flush()
        
        # Valida senha
        password = data.get("password")
        if password not in [EDIT_PASSWORD, EDIT_PASSWORD_2]:
            print(f"❌ Senha inválida: {password}")
            sys.stdout.flush()
            return jsonify({"success": False, "erro": "Senha inválida"}), 401
            
        # Valida mês e ano
        month = data.get("month")
        year = data.get("year")
        if not month or not year:
            print("❌ Mês ou ano não fornecidos")
            sys.stdout.flush()
            return jsonify({"success": False, "erro": "Mês e ano obrigatórios"}), 400
        
        try:
            month = int(month)
            year = int(year)
        except (ValueError, TypeError) as e:
            print(f"❌ Erro ao converter mês/ano: {e}")
            sys.stdout.flush()
            return jsonify({"success": False, "erro": "Mês/ano inválidos"}), 400
        
        sugestoes_recebidas = data.get("sugestoes", {})
        mes_nome = getNomeMes(month)
        
        print(f"📥 Processando: {mes_nome}/{year} com {len(sugestoes_recebidas)} sugestões")
        sys.stdout.flush()
        
        # 🔧 SALVA VALORES E SUGESTÕES
        logs_dict = data.get("logs", {})
        if not isinstance(logs_dict, dict):
            print("❌ Logs não é um dicionário")
            sys.stdout.flush()
            return jsonify({"success": False, "erro": "Formato de logs inválido"}), 400
        
        saved_count = 0
        for pilot_name, days in logs_dict.items():
            try:
                pilot = Pilot.query.filter_by(name=pilot_name).first()
                if not pilot:
                    print(f"⚠️ Piloto não encontrado: {pilot_name}")
                    sys.stdout.flush()
                    continue
                    
                if not isinstance(days, dict):
                    print(f"⚠️ Days não é dict para {pilot_name}")
                    sys.stdout.flush()
                    continue
                
                for day_str, hours in days.items():
                    try:
                        day = int(day_str)
                    except (ValueError, TypeError):
                        print(f"⚠️ Dia inválido: {day_str}")
                        sys.stdout.flush()
                        continue
                    
                    # Se horas é None, deleta o registro
                    if hours is None:
                        log = FlightLog.query.filter_by(
                            pilot_id=pilot.id, day=day, month=month, year=year
                        ).first()
                        if log:
                            db.session.delete(log)
                            print(f"🗑️ Deletado: {pilot_name} dia {day}")
                            sys.stdout.flush()
                        continue
                        
                    # Converte horas para float (pode ser 0)
                    try:
                        valor_horas = float(hours) if hours is not None else 0.0
                    except (ValueError, TypeError):
                        print(f"⚠️ Horas inválidas: {hours}")
                        sys.stdout.flush()
                        continue
                    
                    # Busca ou cria o registro
                    log = FlightLog.query.filter_by(
                        pilot_id=pilot.id, day=day, month=month, year=year
                    ).first()
                    
                    if log:
                        log.hours = valor_horas
                        print(f"✏️ Atualizado: {pilot_name} dia {day} = {valor_horas}h")
                    else:
                        log = FlightLog(
                            pilot_id=pilot.id, day=day, month=month, 
                            year=year, hours=valor_horas
                        )
                        db.session.add(log)
                        print(f"➕ Criado: {pilot_name} dia {day} = {valor_horas}h")
                    
                    sys.stdout.flush()
                    
                    # 🔧 SALVA AS SUGESTÕES (cores verdes)
                    key = f"{mes_nome}_{year}_{pilot_name}_{day}"
                    if key in sugestoes_recebidas and sugestoes_recebidas[key]:
                        if not log.sugestoes:
                            log.sugestoes = {}
                        log.sugestoes[key] = True
                        print(f"🎨 Sugestão: {key}")
                    else:
                        # Remove a sugestão se não estiver mais marcada
                        if log.sugestoes and key in log.sugestoes:
                            del log.sugestoes[key]
                            print(f"🗑️ Sugestão removida: {key}")
                    
                    saved_count += 1
                    sys.stdout.flush()
                    
            except Exception as pilot_error:
                print(f"❌ Erro processando piloto {pilot_name}: {pilot_error}")
                import traceback
                traceback.print_exc()
                sys.stdout.flush()
                continue
                    
        # Commit no banco
        try:
            db.session.commit()
            print(f"✅ Commit OK - {saved_count} registros salvos, {len(sugestoes_recebidas)} sugestões")
            sys.stdout.flush()
            return jsonify({"success": True, "saved": saved_count})
        except Exception as commit_error:
            print(f"❌ Erro no commit: {commit_error}")
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            db.session.rollback()
            return jsonify({"success": False, "erro": f"Erro ao salvar no banco: {str(commit_error)}"}), 500
        
    except Exception as e:
        print(f"❌ ERRO GERAL em POST: {e}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({"success": False, "erro": f"Erro no servidor: {str(e)}"}), 500

# ===== INICIALIZAÇÃO =====
with app.app_context():
    db.create_all()
    print("✅ Tabelas criadas/verificadas")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port)
