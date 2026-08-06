import os
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

# ==========================================
# 1. INICIALIZAÇÃO DO FLASK
# ==========================================
app = Flask(__name__)

# ==========================================
# 2. CONFIGURAÇÃO DO BANCO DE DADOS (SUPABASE)
# ==========================================

# Pega a URL do ambiente (Render ou local)
database_url = os.environ.get('DATABASE_URL')

# CORREÇÃO CRÍTICA: Se não tiver a varável, para o app com erro amigável
if not database_url:
    raise ValueError("ERRO CRÍTICO: A variável de ambiente 'DATABASE_URL' não foi encontrada. Verifique as configurações no Render.")

# Substitui 'postgres://' por 'postgresql://' (Obrigatório para SQLAlchemy >= 2.0)
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

# Aplica as configurações no Flask
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuração OBRIGATÓRIA para o Supabase (SSL e timeout)
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {
        "sslmode": "require",
        "connect_timeout": 10
    }
}

# ==========================================
# 3. INICIALIZAÇÃO DO BANCO DE DADOS
# ==========================================
db = SQLAlchemy(app)

# ==========================================
# 4. CRIAÇÃO DOS MODELOS (SUAS TABELAS)
# ==========================================
# ATENÇÃO: Descomente e edite este bloco com suas tabelas reais!
# Exemplo de modelo de usuário:

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email
        }

# ==========================================
# 5. ROTAS DA APLICAÇÃO (SUA API)
# ==========================================

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "message": "Aplicação rodando perfeitamente com Supabase!"
    })

# Exemplo de rota para listar usuários
@app.route('/users', methods=['GET'])
def get_users():
    try:
        users = User.query.all()
        return jsonify([user.to_dict() for user in users])
    except SQLAlchemyError as e:
        return jsonify({"error": str(e)}), 500

# Exemplo de rota para criar usuário
@app.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('email'):
        return jsonify({"error": "Nome e email são obrigatórios"}), 400
    
    try:
        new_user = User(name=data['name'], email=data['email'])
        db.session.add(new_user)
        db.session.commit()
        return jsonify(new_user.to_dict()), 201
    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ==========================================
# 6. CRIAÇÃO AUTOMÁTICA DAS TABELAS (SÓ FUNCIONA SE FOR MODELO)
# ==========================================
# Isso garante que ao subir o app, as tabelas sejam criadas no Supabase se não existirem
with app.app_context():
    try:
        db.create_all()
        print("✅ Tabelas verificadas/criadas com sucesso no Supabase.")
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")

# ==========================================
# 7. EXECUÇÃO DO APP (Gunicorn usa isso como entry point)
# ==========================================
if __name__ == '__main__':
    # Só roda essa linha se você executar python app.py diretamente. No Render, ignora.
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
