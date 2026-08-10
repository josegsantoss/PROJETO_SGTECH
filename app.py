from flask import Flask, render_template, url_for, request, session, redirect, jsonify, make_response, flash, send_file
from functools import wraps
import random
import database
from database.connection import get_connection
from flask_apscheduler import APScheduler
import smtplib
from email.message import EmailMessage
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'uma_chave_super_secreta_e_dificil'

scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# ===================== FUNÇÕES DE E-MAIL =====================

@scheduler.task('cron', id='enviar_relatorios', day_of_week='mon', hour=8, minute=0)
def job_enviar_relatorios():
    print("Iniciando verificação de envio de relatórios semanais...")
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT email FROM usuario WHERE relatorios_ativos = 1")
        usuarios = cursor.fetchall()
        for usuario in usuarios:
            enviar_email_relatorio(usuario['email'])
    except Exception as e:
        print(f"Erro no agendamento: {e}")
    finally:
        cursor.close()
        conn.close()


def enviar_email_relatorio(destinatario):
    EMAIL_ADDRESS = 'tdsatcc@gmail.com'
    EMAIL_PASSWORD = 'fdvvxizyfqyersvg'

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        try:
            cursor.execute("""
                SELECT COUNT(*) as total_vendas, 
                       COALESCE(SUM(valor_total), 0) as faturamento
                FROM vendas 
                WHERE data_venda >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            """)
            vendas = cursor.fetchone() or {'total_vendas': 0, 'faturamento': 0}
        except:
            vendas = {'total_vendas': 0, 'faturamento': 0}

        try:
            cursor.execute("SELECT COUNT(*) as total_produtos FROM produtos")
            produtos = cursor.fetchone() or {'total_produtos': 0}
        except:
            produtos = {'total_produtos': 0}

        try:
            cursor.execute("""
                SELECT COUNT(*) as total_consertos 
                FROM conserto 
                WHERE data_fim >= DATE_SUB(CURDATE(), INTERVAL 7 DAY) AND status = 'Finalizado'
            """)
            consertos = cursor.fetchone() or {'total_consertos': 0}
        except:
            consertos = {'total_consertos': 0}

        top_produtos_html = "<li>Nenhuma venda registrada esta semana.</li>"
        try:
            cursor.execute("""
                SELECT p.nome, SUM(iv.quantidade) as quantidade
                FROM item_venda iv
                JOIN produtos p ON iv.produto_id = p.id
                WHERE iv.data_venda >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                GROUP BY p.nome
                ORDER BY quantidade DESC
                LIMIT 5
            """)
            top_produtos = cursor.fetchall()
            if top_produtos:
                top_produtos_html = "".join([f"<li>{p['nome']} — {p['quantidade']} unidades</li>" for p in top_produtos])
        except:
            pass

        html_content = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333; max-width: 600px; margin: 0 auto;">
            <h2 style="color: #2563eb; text-align: center;">📊 Relatório Semanal - TechManager</h2>
            <p style="text-align: center;">Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
            
            <div style="background-color: #f8fafc; padding: 20px; border-radius: 12px; border-left: 6px solid #2563eb;">
                <h3>Resumo Geral</h3>
                <ul style="list-style: none; padding: 0;">
                    <li>📈 <strong>Vendas Realizadas:</strong> {vendas['total_vendas']}</li>
                    <li>💰 <strong>Faturamento Total:</strong> R$ {float(vendas['faturamento']):.2f}</li>
                    <li>📦 <strong>Produtos Cadastrados:</strong> {produtos['total_produtos']}</li>
                    <li>🛠️ <strong>Consertos Finalizados:</strong> {consertos['total_consertos']}</li>
                </ul>
            </div>

            <div style="margin-top: 20px; background-color: #f8fafc; padding: 20px; border-radius: 12px;">
                <h3>🔥 Top 5 Produtos Mais Vendidos</h3>
                <ol style="padding-left: 20px;">
                    {top_produtos_html}
                </ol>
            </div>

            <p style="text-align: center; margin-top: 30px; color: #64748b; font-size: 14px;">
                Este é um relatório de teste.
            </p>
          </body>
        </html>
        """

        msg = EmailMessage()
        msg['Subject'] = '📊 Relatório Semanal - TechManager (Teste)'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = destinatario
        msg.add_alternative(html_content, subtype='html')

        print(f"Tentando enviar email para {destinatario}...")

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        print(f"✅ Email enviado com sucesso para: {destinatario}")

    except Exception as e:
        print(f"❌ ERRO AO ENVIAR EMAIL: {e}")
    finally:
        cursor.close()
        conn.close()


def enviar_email_codigo(destinatario, codigo):
    EMAIL_ADDRESS = 'tdsatcc@gmail.com'
    EMAIL_PASSWORD = 'fdvvxizyfqyersvg'

    try:
        msg = EmailMessage()
        msg['Subject'] = 'Código de Verificação de Novo Dispositivo - SGE'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = destinatario
        msg.set_content(f"Olá!\n\nDetectamos um acesso ao SGE a partir de um novo dispositivo.\n\nSeu código de segurança é: {codigo}\n\nSe não foi você, altere sua senha imediatamente.")

        print(f"Tentando enviar código 2FA para {destinatario}...")

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)

        print(f"✅ Código 2FA enviado com sucesso para: {destinatario}")

    except Exception as e:
        print(f"❌ Erro ao enviar código 2FA: {e}")


# ===================== DECORADORES =====================

def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_logado' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Bloqueia se não estiver logado OU se o nível não for 1
        if 'usuario_logado' not in session or session.get('nivel') != 1:
            flash("Acesso restrito! Apenas administradores.", "error")
            return redirect(url_for('menu'))
        return f(*args, **kwargs)
    return decorated_function


# ===================== ROTAS =====================

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        
        # 1. Abre a ligação e verifica o utilizador diretamente AQUI!
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM usuario WHERE email = %s AND senha = %s", (email, senha))
            usuario = cursor.fetchone()
        except Exception as e:
            print(f"Erro no login: {e}")
            usuario = None
        finally:
            cursor.close()
            conn.close()

        # 2. Se não encontrou o utilizador, recusa a entrada
        if usuario is None:
            return render_template('login.html', erro="E-mail ou senha incorretos!")
        
        # 3. Lógica do 2FA (Dupla Autenticação)
        # Se o utilizador tiver o 2FA LIGADO (1)
        if usuario.get('two_factor_ativo') == 1:
            dispositivo_salvo = request.cookies.get('dispositivo_confiavel')
            
            # Se for num computador já confiável, entra direto
            if dispositivo_salvo == usuario['email']:
                session['usuario_logado'] = usuario['email']
                session['cargo'] = usuario['cargo']
                session['nivel'] = usuario['nivel_de_permissao']
                session['foto_perfil'] = usuario.get('foto_perfil') or 'default_avatar.png'
                return redirect(url_for('menu'))
            else:
                # Se for um computador novo, envia o código para o e-mail
                codigo_2fa = str(random.randint(100000, 999999))
                session['2fa_codigo'] = codigo_2fa
                session['temp_usuario'] = usuario 
                enviar_email_codigo(email, codigo_2fa)
                return redirect(url_for('verificar_2fa'))
                
        # Se o utilizador tiver o 2FA DESLIGADO (0 ou vazio), ENTRA DIRETO sem pedir código
        else:
            session['usuario_logado'] = usuario['email']
            session['cargo'] = usuario['cargo']
            session['nivel'] = usuario['nivel_de_permissao']
            session['foto_perfil'] = usuario.get('foto_perfil') or 'default_avatar.png'
            return redirect(url_for('menu'))
    
    return render_template('login.html')


@app.route('/verificar_2fa', methods=['GET', 'POST'])
def verificar_2fa():
    if 'temp_usuario' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        if request.form.get('codigo') == session.get('2fa_codigo'):
            usuario = session['temp_usuario']
            session['usuario_logado'] = usuario['email']
            session['cargo'] = usuario['cargo']
            session['nivel'] = usuario['nivel_de_permissao']
            session['foto_perfil'] = usuario.get('foto_perfil') or 'default_avatar.png'
            session.pop('2fa_codigo', None)
            session.pop('temp_usuario', None)
            
            resposta = make_response(redirect(url_for('menu')))
            resposta.set_cookie('dispositivo_confiavel', usuario['email'], max_age=60*60*24*30)
            return resposta
        else:
            return render_template('verificar_2fa.html', erro="Código inválido.")
            
    return render_template('verificar_2fa.html')

# ===================== LIMPAR NOTIFICAÇÕES =====================
@app.route('/limpar_notificacoes', methods=['POST'])
@login_requerido
def limpar_notificacoes():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Muda o status de "lida" para 1 (escondendo-as da tela principal)
        cursor.execute("UPDATE notificacoes SET lida = 1 WHERE lida = 0")
        conn.commit()
    except Exception as e:
        print(f"Erro ao limpar notificações: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('menu'))

@app.route('/menu')
@login_requerido
def menu():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    notificacoes = []
    try:
        # Garante que a tabela existe para não quebrar a busca
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notificacoes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                mensagem VARCHAR(255) NOT NULL,
                data_criacao DATETIME NOT NULL,
                lida TINYINT(1) DEFAULT 0
            )
        """)
        
        try:
            cursor.execute("SELECT notificacoes_ativas FROM usuario WHERE email = %s", (session.get('usuario_logado'),))
            pref = cursor.fetchone()
        except:
            pref = {'notificacoes_ativas': 1}
        
        # Só procura as notificações se a preferência for 1 (Ativa)
        if not pref or pref.get('notificacoes_ativas', 1) == 1:
            cursor.execute("SELECT * FROM notificacoes WHERE lida = 0 ORDER BY data_criacao DESC LIMIT 10")
            notificacoes = cursor.fetchall()
            
            # Formata a data para ficar bonita no HTML (Ex: Hoje às 14:30)
            for n in notificacoes:
                if isinstance(n['data_criacao'], datetime):
                    hoje = datetime.now().date()
                    data_notif = n['data_criacao'].date()
                    hora_str = n['data_criacao'].strftime('%H:%M')
                    if hoje == data_notif:
                        n['data_criacao'] = f"Hoje às {hora_str}"
                    else:
                        n['data_criacao'] = n['data_criacao'].strftime('%d/%m/%Y às %H:%M')

    except Exception as e:
        print(f"Erro com a tabela de notificações: {e}")

    try:
        from datetime import datetime
        dia_atual = datetime.now().day

        # 1. SALDO TOTAL = Vendas + Orçamentos (APROVADOS OU FINALIZADOS)
        cursor.execute("SELECT COALESCE(SUM(total), 0) as saldo_vendas FROM vendas")
        saldo_vendas = float((cursor.fetchone() or {})['saldo_vendas'] or 0.0)
        
        cursor.execute("SELECT COALESCE(SUM(total_geral), 0) as saldo_orcamentos FROM orcamentos WHERE status IN ('Aprovado', 'Finalizado')")
        saldo_orcamentos = float((cursor.fetchone() or {})['saldo_orcamentos'] or 0.0)
        
        saldo_atual = saldo_vendas + saldo_orcamentos

        # 2. RECEITA E VENDAS DE HOJE
        cursor.execute("SELECT COUNT(id_venda) as qtd_hoje, COALESCE(SUM(total), 0) as receita_hoje FROM vendas WHERE DATE(data_venda) = CURDATE()")
        res_vendas = cursor.fetchone() or {'qtd_hoje': 0, 'receita_hoje': 0}
        
        cursor.execute("SELECT COUNT(id) as qtd_hoje, COALESCE(SUM(total_geral), 0) as receita_hoje FROM orcamentos WHERE status IN ('Aprovado', 'Finalizado') AND DATE(data_criacao) = CURDATE()")
        res_orcamentos = cursor.fetchone() or {'qtd_hoje': 0, 'receita_hoje': 0}
        
        receita_hoje = float(res_vendas['receita_hoje']) + float(res_orcamentos['receita_hoje'])
        vendas_hoje = int(res_vendas['qtd_hoje']) + int(res_orcamentos['qtd_hoje'])

        # 3. SERVIÇOS DE HOJE
        try:
            cursor.execute("SELECT COUNT(id) as qtd_servicos FROM conserto WHERE DATE(data_fim) = CURDATE() OR DATE(data_inicio) = CURDATE()")
            servicos_hoje = int((cursor.fetchone() or {})['qtd_servicos'] or 0)
        except:
            servicos_hoje = 0
            
        # 4. DESPESA DE HOJE
        try:
            cursor.execute("SELECT COALESCE(SUM(valor), 0) as despesa_hoje FROM despesas WHERE DATE(data_despesa) = CURDATE()")
            despesa_hoje = float((cursor.fetchone() or {})['despesa_hoje'] or 0.0)
        except:
            despesa_hoje = 0.0

        # 5. RECEITA DO MÊS
        cursor.execute("SELECT COALESCE(SUM(total), 0) as receita_mes FROM vendas WHERE MONTH(data_venda) = MONTH(CURDATE()) AND YEAR(data_venda) = YEAR(CURDATE())")
        rec_mes_vendas = float((cursor.fetchone() or {})['receita_mes'] or 0.0)
        
        cursor.execute("SELECT COALESCE(SUM(total_geral), 0) as receita_mes FROM orcamentos WHERE status IN ('Aprovado', 'Finalizado') AND MONTH(data_criacao) = MONTH(CURDATE()) AND YEAR(data_criacao) = YEAR(CURDATE())")
        rec_mes_orcamentos = float((cursor.fetchone() or {})['receita_mes'] or 0.0)
        
        receita_mes = rec_mes_vendas + rec_mes_orcamentos

        # 6. DESPESA DO MÊS
        try:
            cursor.execute("SELECT COALESCE(SUM(valor), 0) as despesa_mes FROM despesas WHERE MONTH(data_despesa) = MONTH(CURDATE()) AND YEAR(data_despesa) = YEAR(CURDATE())")
            despesa_mes = float((cursor.fetchone() or {})['despesa_mes'] or 0.0)
        except:
            despesa_mes = 0.0

        # 7. META MENSAL
        try:
            cursor.execute("SELECT meta_mensal FROM configuracoes WHERE id = 1")
            meta = cursor.fetchone()
            meta_mensal = float(meta['meta_mensal']) if meta and meta.get('meta_mensal') else 30000.0
        except:
            meta_mensal = 30000.0

        # ======= GRÁFICO DOS ÚLTIMOS 7 DIAS =======
        labels_dias = []
        valores_dias = []
        try:
            cursor.execute("""
                SELECT DATE_FORMAT(data_transacao, '%d/%m') AS dia, SUM(valor) AS total_dia
                FROM (
                    SELECT data_venda AS data_transacao, total AS valor FROM vendas WHERE data_venda >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
                    UNION ALL
                    SELECT data_entrada AS data_transacao, valor_estimado AS valor FROM conserto WHERE data_entrada >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
                    UNION ALL
                    SELECT data_criacao AS data_transacao, total_geral AS valor FROM orcamentos WHERE status IN ('Aprovado', 'Finalizado') AND data_criacao >= DATE_SUB(CURDATE(), INTERVAL 6 DAY)
                ) AS resumo
                GROUP BY DATE(data_transacao), dia
                ORDER BY DATE(data_transacao) ASC
            """)
            evolucao = cursor.fetchall()
            for item in evolucao:
                labels_dias.append(item['dia'])
                valores_dias.append(float(item['total_dia']) if item['total_dia'] else 0.0)
        except Exception as e:
            print(f"Erro ao buscar evolução diária: {e}")

        # ======= CÁLCULOS DOS INDICADORES =======
        clientes_atendidos = vendas_hoje + servicos_hoje
        ticket_medio = (receita_hoje / vendas_hoje) if vendas_hoje > 0 else 0.0
        margem_lucro = ((receita_mes - despesa_mes) / receita_mes * 100) if receita_mes > 0 else 0.0
        projecao_mes = (receita_mes / dia_atual) * 30 if dia_atual > 0 else 0.0
        conversao = 100 if vendas_hoje > 0 else 0 
        
        def formata_br(valor):
            return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    except Exception as e:
        print(f"Erro ao buscar dados financeiros: {e}")
        saldo_atual = receita_hoje = despesa_hoje = vendas_hoje = servicos_hoje = clientes_atendidos = 0
        ticket_medio = margem_lucro = projecao_mes = conversao = meta_mensal = 0.0
        labels_dias = []
        valores_dias = []
        def formata_br(valor): return "0,00"
    finally:
        cursor.close()
        conn.close()

    # ENVIA TODAS AS VARIÁVEIS (INCLUINDO NOTIFICAÇÕES) PARA O HTML
    return render_template('menu.html', 
                           saldo_numerico=saldo_atual,
                           meta_mensal=meta_mensal,
                           saldo_atual_fmt=formata_br(saldo_atual), 
                           receita_hoje_fmt=formata_br(receita_hoje),
                           despesa_hoje_fmt=formata_br(despesa_hoje),
                           vendas_hoje=vendas_hoje,
                           servicos_hoje=servicos_hoje,
                           clientes_atendidos=clientes_atendidos,
                           ticket_medio_fmt=formata_br(ticket_medio),
                           margem_lucro=int(margem_lucro),
                           projecao_mes_fmt=formata_br(projecao_mes),
                           conversao=conversao,
                           labels_dias=labels_dias,
                           valores_dias=valores_dias,
                           notificacoes=notificacoes)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ===================== CONFIGURAÇÕES =====================

# ===================== CONFIGURAÇÕES E SEGURANÇA =====================

@app.route('/configuracao')
@login_requerido
def configuracao():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    config = {}
    try:
        # Busca configurações da empresa
        cursor.execute("SELECT * FROM configuracoes WHERE id = 1")
        config_global = cursor.fetchone() or {}

        # Busca configurações do usuário logado
        cursor.execute("""
            SELECT notificacoes_ativas, relatorios_ativos, two_factor_ativo 
            FROM usuario WHERE email = %s
        """, (session['usuario_logado'],))
        user_prefs = cursor.fetchone() or {}
        
        # Junta tudo numa variável só para enviar para o HTML
        config = {**config_global, **user_prefs}
    except Exception as e:
        print(f"Erro ao carregar configurações: {e}")
    finally:
        cursor.close()
        conn.close()

    return render_template('configuracao.html', config=config)


@app.route('/salvar_config', methods=['POST'])
@login_requerido
def salvar_config():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Pega os dados da Empresa do formulário
        empresa_nome = request.form.get('empresaNome', '')
        empresa_cnpj = request.form.get('empresaCnpj', '')
        empresa_telefone = request.form.get('empresaTelefone', '')
        empresa_email = request.form.get('empresaEmail', '')
        empresa_endereco = request.form.get('empresaEndereco', '')
        backup_freq = request.form.get('backupFrequencia', 'semanal')

        # 2. Pega os dados das Preferências (Checkboxes)
        notificacoes = 1 if request.form.get('notificacoesToggle') else 0
        relatorios = 1 if request.form.get('relatoriosToggle') else 0
        two_factor = 1 if request.form.get('twoFactorToggle') else 0

        # Salva a Empresa e Backup
        cursor.execute('''
            UPDATE configuracoes 
            SET empresa_nome=%s, empresa_cnpj=%s, empresa_telefone=%s,
                empresa_email=%s, empresa_endereco=%s, backup_frequencia=%s
            WHERE id = 1
        ''', (empresa_nome, empresa_cnpj, empresa_telefone, empresa_email, empresa_endereco, backup_freq))

        # Salva as Preferências
        cursor.execute('''
            UPDATE usuario 
            SET notificacoes_ativas=%s, relatorios_ativos=%s, two_factor_ativo=%s
            WHERE email = %s
        ''', (notificacoes, relatorios, two_factor, session['usuario_logado']))

        # Atualiza o nome da empresa na sessão para uso imediato no sistema
        session['empresa_nome'] = empresa_nome

        # 3. VERIFICAÇÃO DE SEGURANÇA PARA MUDAR A SENHA
        senha_atual = request.form.get('senhaAtual', '').strip()
        nova_senha = request.form.get('novaSenha', '').strip()
        confirmar_senha = request.form.get('confirmarSenha', '').strip()

        # Se preencheu algum campo da nova senha
        if nova_senha or confirmar_senha or senha_atual:
            if not senha_atual:
                flash("Digite a sua senha atual para autorizar a alteração!", "error")
                return redirect(url_for('configuracao'))
            
            if nova_senha != confirmar_senha:
                flash("A nova senha e a confirmação não coincidem!", "error")
                return redirect(url_for('configuracao'))
                
            # Procura a senha atual salva no banco de dados
            cursor.execute("SELECT senha FROM usuario WHERE email = %s", (session['usuario_logado'],))
            usuario_db = cursor.fetchone()
            
            # Compara se a senha atual digitada bate com a do banco de dados
            if not usuario_db or str(usuario_db['senha']).strip() != senha_atual:
                flash("Senha atual incorreta! Acesso negado.", "error")
                return redirect(url_for('configuracao'))
                
            # Se a senha atual estiver correta, atualiza para a nova senha!
            cursor.execute("UPDATE usuario SET senha = %s WHERE email = %s", (nova_senha, session['usuario_logado']))
            flash("Senha alterada com sucesso!", "success")

        # Confirma e salva tudo no banco
        conn.commit()
        flash("Configurações salvas com sucesso!", "success")
        
    except Exception as e:
        conn.rollback()
        flash(f"Erro ao salvar: {e}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('configuracao'))

import os
from werkzeug.utils import secure_filename

@app.route('/download_backup')
@login_requerido
def download_backup():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    backup_data = {}
    
    # Lista de todas as tabelas importantes do seu sistema
    tabelas = [
        'cliente', 'produto', 'vendas', 'itens_venda', 
        'conserto', 'orcamentos', 'itens_orcamento', 
        'usuario', 'configuracoes', 'notificacoes'
    ]
    
    try:
        # Extrai os dados de cada tabela
        for tabela in tabelas:
            try:
                cursor.execute(f"SELECT * FROM {tabela}")
                backup_data[tabela] = cursor.fetchall()
            except:
                backup_data[tabela] = [] # Se a tabela não existir, fica vazia
                
        # Converte os dados para um ficheiro JSON
        import json
        from io import BytesIO
        
        # O default=str serve para converter datas e valores monetários (Decimal) em texto
        json_data = json.dumps(backup_data, indent=4, default=str)
        
        # Cria um "ficheiro virtual" na memória para enviar ao utilizador
        buffer = BytesIO()
        buffer.write(json_data.encode('utf-8'))
        buffer.seek(0)
        
        # Gera o nome do ficheiro com a data e hora atual
        data_atual = datetime.now().strftime("%d-%m-%Y_%H-%M")
        nome_ficheiro = f"backup_SGE_{data_atual}.json"
        
        return send_file(
            buffer, 
            as_attachment=True, 
            download_name=nome_ficheiro, 
            mimetype="application/json"
        )
        
    except Exception as e:
        flash(f"Erro ao gerar backup: {e}", "error")
        return redirect(url_for('configuracao'))
    finally:
        cursor.close()
        conn.close()

# Configuração da pasta de uploads (caso tenha apagado também)
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
if 'UPLOAD_FOLDER' not in app.config:
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

import os
from werkzeug.utils import secure_filename

# ===================== ROTA UPLOAD DE FOTO =====================
import os # Garanta que "import os" esteja lá no topo do seu app.py

@app.route('/upload_foto', methods=['POST'])
@login_requerido
def upload_foto():
    if 'foto' not in request.files:
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('configuracao'))
    
    file = request.files['foto']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('configuracao'))
    
    if file:
        # Pega a foto atual antes de salvar a nova
        foto_antiga = session.get('foto_perfil')
        
        # Gera o nome da nova foto e salva
        filename = f"user_{session['usuario_logado']}_{file.filename}"
        upload_path = os.path.join(app.root_path, 'static', 'uploads', filename)
        file.save(upload_path)
        
        # Apaga a foto antiga do servidor (se não for a padrão)
        if foto_antiga and foto_antiga != 'default_avatar.png':
            caminho_antigo = os.path.join(app.root_path, 'static', 'uploads', foto_antiga)
            if os.path.exists(caminho_antigo):
                try:
                    os.remove(caminho_antigo)
                except Exception as e:
                    print(f"Erro ao excluir foto antiga: {e}")

        # Atualiza a sessão e a base de dados
        session['foto_perfil'] = filename
        
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE usuario SET foto_perfil = %s WHERE email = %s", (filename, session['usuario_logado']))
            conn.commit()
            flash('Foto atualizada com sucesso!', 'success')
        except Exception as e:
            flash('Erro ao salvar no banco de dados.', 'error')
        finally:
            cursor.close()
            conn.close()
            
    return redirect(url_for('configuracao'))
# ===================== API DE NOTIFICAÇÕES =====================

@app.route('/vendas', methods=['GET', 'POST'])
@login_requerido
def vendas():
    sucesso = None
    erro = None
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # 0. BUSCAR CONFIGURAÇÕES DA EMPRESA (Nome, CNPJ, Telefone)
    config_empresa = {}
    try:
        cursor.execute("SELECT * FROM configuracoes WHERE id = 1")
        config_empresa = cursor.fetchone() or {}
    except Exception as e:
        print("Erro ao buscar configurações:", e)

    # 1. PROCESSAR A VENDA (Quando o formulário é enviado)
    if request.method == 'POST':
        cliente_nome = request.form.get('cliente_nome', 'Cliente Não Identificado')
        cliente_documento = request.form.get('cliente_documento')
        cliente_telefone = request.form.get('cliente_telefone')
        cliente_email = request.form.get('cliente_email')
        cliente_endereco = request.form.get('cliente_endereco')
        forma_pagamento = request.form.get('forma_pagamento')

        # Conversão segura de valores
        desconto_str = request.form.get('desconto_reais')
        desconto = float(desconto_str) if desconto_str and desconto_str.strip() != '' else 0.0

        subtotal_str = request.form.get('subtotal_oculto')
        subtotal = float(subtotal_str) if subtotal_str and subtotal_str.strip() != '' else 0.0

        total_str = request.form.get('total_oculto')
        total = float(total_str) if total_str and total_str.strip() != '' else 0.0

        # Pegar os arrays de produtos gerados pelo JavaScript oculto
        produtos_ids = request.form.getlist('produto_id')
        quantidades = request.form.getlist('quantidade')
        precos = request.form.getlist('preco_produto')

        if not produtos_ids:
            erro = "O carrinho está vazio! Adicione produtos."
        else:
            try:
                id_usuario = session.get('usuario_id')

                # Salva os dados gerais na tabela VENDAS
                query_venda = """
                    INSERT INTO vendas 
                    (id_usuario, cliente_nome, cliente_documento, cliente_telefone, cliente_email, 
                     cliente_endereco, forma_pagamento, subtotal, desconto, total, data_venda) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """
                cursor.execute(query_venda, (
                    id_usuario, cliente_nome, cliente_documento, cliente_telefone, cliente_email, 
                    cliente_endereco, forma_pagamento, subtotal, desconto, total
                ))
                id_venda = cursor.lastrowid

                # Salva cada produto na tabela ITENS_VENDA e atualiza o ESTOQUE
                query_item = """
                    INSERT INTO itens_venda (id_venda, id_produto, quantidade, preco_unitario, total_item) 
                    VALUES (%s, %s, %s, %s, %s)
                """
                query_estoque = "UPDATE produto SET estoque_atual = estoque_atual - %s WHERE id_produto = %s"

                for i in range(len(produtos_ids)):
                    p_id = produtos_ids[i]
                    qtd = int(quantidades[i])
                    preco_unit = float(precos[i])
                    total_item = preco_unit * qtd

                    cursor.execute(query_item, (id_venda, p_id, qtd, preco_unit, total_item))
                    cursor.execute(query_estoque, (qtd, p_id))

                conn.commit()
                registrar_notificacao(f"💰 Nova venda realizada! Valor: R$ {total:.2f} ({forma_pagamento}) - Cliente: {cliente_nome}")
                sucesso = f"Venda #{id_venda} finalizada com sucesso!"
            except Exception as e:
                conn.rollback()
                erro = f"Erro ao finalizar venda: {e}"

    # 2. BUSCAR PRODUTOS (Para desenhar a vitrine de vendas)
    produtos_db = []
    try:
        cursor.execute("""
            SELECT 
                id_produto AS id, 
                id_produto AS codigo, 
                nome_produto AS nome, 
                categoria_produto AS categoria, 
                preço_vrj AS preco, 
                estoque_atual AS estoque 
            FROM produto
            WHERE estoque_atual > 0
        """)
        produtos_db = cursor.fetchall()
        for p in produtos_db:
            p['preco'] = float(p['preco'])
            p['icone'] = 'fa-box'
    except Exception as e:
        print("Erro ao buscar produtos:", e)

    # 3. BUSCAR HISTÓRICO COM OS ITENS DA VENDA (Para preencher a tabela e o recibo)
    historico = []
    try:
        cursor.execute("""
            SELECT v.id_venda, v.data_venda, v.cliente_nome, v.cliente_documento, v.forma_pagamento, 
                   v.subtotal, v.total as valor_final,
                   (SELECT COALESCE(SUM(quantidade), 0) FROM itens_venda WHERE id_venda = v.id_venda) as total_itens
            FROM vendas v
            ORDER BY v.id_venda DESC
        """)
        vendas_brutas = cursor.fetchall()

        for v in vendas_brutas:
            # Busca os itens individuais de cada venda para o recibo funcionar perfeitamente
            cursor.execute("""
                SELECT iv.quantidade, iv.preco_unitario, iv.total_item, p.nome_produto AS nome
                FROM itens_venda iv
                JOIN produto p ON iv.id_produto = p.id_produto
                WHERE iv.id_venda = %s
            """, (v['id_venda'],))
            v['itens'] = cursor.fetchall()
            historico.append(v)

    except Exception as e:
        print("Erro ao buscar histórico:", e)

    cursor.close()
    conn.close()

    return render_template('vendas.html', produtos=produtos_db, historico=historico, config=config_empresa, sucesso=sucesso, erro=erro)


@app.route('/cadastro', methods=['GET', 'POST'])
@login_requerido
def cadastro():
    # Se o usuário enviou o formulário via POST
    if request.method == 'POST':
        nome = request.form.get('nome')
        cpf_cnpj = request.form.get('cpf')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        celular = request.form.get('celular')
        endereco = request.form.get('endereco')
        cidade = request.form.get('cidade')
        estado = request.form.get('estado')
        cep = request.form.get('cep')
        tipo = request.form.get('tipo')

        if not nome or not cpf_cnpj:
            flash("Nome e CPF/CNPJ são obrigatórios!", "erro")
        else:
            cpf = cpf_cnpj if tipo == 'Física' else None
            cnpj = cpf_cnpj if tipo == 'Jurídica' else None

            conn = get_connection()
            cursor = conn.cursor()
            try:
                query = """
                    INSERT INTO cliente 
                    (nome_cliente, cpf, cnpj, email, telefone, celular, endereco, cidade, estado, cep, tipo) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                valores = (nome, cpf, cnpj, email, telefone, celular, endereco, cidade, estado, cep, tipo)
                cursor.execute(query, valores)
                conn.commit()
                registrar_notificacao(f"👤 Novo cliente cadastrado: {nome}")
                flash("Cliente cadastrado com sucesso!", "sucesso")
            except Exception as e:
                conn.rollback()
                flash(f"Erro ao cadastrar cliente no banco de dados: {e}", "erro")
            finally:
                cursor.close()
                conn.close()

        # O REDIRECIONAMENTO É A CHAVE: Impede que o F5 duplique o cadastro
        return redirect(url_for('cadastro'))

    # Se for GET, busca os clientes normalmente para exibir na tabela
    clientes = []
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT 
                id_cliente AS id, 
                nome_cliente AS nome, 
                COALESCE(cpf, cnpj) AS cpf, 
                email, 
                telefone, 
                celular, 
                endereco, 
                cidade, 
                estado, 
                cep, 
                tipo,
                data_cadastro
            FROM cliente 
            ORDER BY id_cliente DESC
        """)
        clientes = cursor.fetchall()

        for cliente in clientes:
            if cliente.get('data_cadastro'):
                if hasattr(cliente['data_cadastro'], 'strftime'):
                    cliente['data_cadastro'] = cliente['data_cadastro'].strftime('%d/%m/%Y %H:%M')

    except Exception as e:
        print(f"Erro ao buscar clientes: {e}")
    finally:
        cursor.close()
        conn.close()

    return render_template('cadastrocliente.html', clientes=clientes)

       #RECIBO DA VENDA
@app.route('/recibo/<int:id_venda>')
@login_requerido
def recibo(id_venda):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Busca os dados gerais da venda
        cursor.execute("SELECT * FROM vendas WHERE id_venda = %s", (id_venda,))
        venda = cursor.fetchone()

        if not venda:
            return "Venda não encontrada!", 404

        # 2. Busca os itens detalhados dessa venda, juntando com o nome do produto
        cursor.execute("""
            SELECT i.*, p.nome_produto 
            FROM itens_venda i
            JOIN produto p ON i.id_produto = p.id_produto
            WHERE i.id_venda = %s
        """, (id_venda,))
        itens = cursor.fetchall()

        return render_template('recibo.html', venda=venda, itens=itens)
    except Exception as e:
        return f"Erro ao gerar recibo: {e}"
    finally:
        cursor.close()
        conn.close()

@app.route('/extrato')
@login_requerido
def extrato():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    transacoes = []
    total_vendas = 0.0
    total_servicos = 0.0

    # 1. Busca as Vendas reais
    try:
        cursor.execute(
            "SELECT 'Vendas' AS categoria, CONCAT('Venda #', id_venda) AS descricao, total AS valor, DATE_FORMAT(data_venda, '%H:%i') AS hora, 'Concluído' AS status, data_venda AS data_ordenacao FROM vendas"
        )
        vendas = cursor.fetchall()
        for v in vendas:
            v['valor'] = float(v['valor']) if v['valor'] else 0.0
            total_vendas += v['valor']
            transacoes.append(v)
    except Exception as e:
        print(f"Erro ao buscar vendas: {e}")

    # 2. Busca os Consertos reais
    try:
        cursor.execute(
            "SELECT 'Serviços' AS categoria, CONCAT('Conserto: ', COALESCE(equipamento, 'Geral')) AS descricao, valor_estimado AS valor, DATE_FORMAT(data_entrada, '%H:%i') AS hora, COALESCE(status_servico, 'Pendente') AS status, data_entrada AS data_ordenacao FROM conserto"
        )
        consertos = cursor.fetchall()
        for c in consertos:
            c['valor'] = float(c['valor']) if c['valor'] else 0.0
            total_servicos += c['valor']
            transacoes.append(c)
    except Exception as e:
        print(f"Erro ao buscar consertos: {e}")

    # 3. Busca os ORÇAMENTOS reais
    total_orcamentos = 0.0
    try:
        # Puxa o status. Se for Aprovado OU Finalizado, vira Vendas!
        cursor.execute("""
            SELECT 
                IF(status IN ('Aprovado', 'Finalizado'), 'Vendas', 'Orçamento') AS categoria, 
                CONCAT(IF(status IN ('Aprovado', 'Finalizado'), '✅ Venda (Orçamento): ', '📝 Orçamento: '), cliente_nome) AS descricao, 
                total_geral AS valor, 
                DATE_FORMAT(data_criacao, '%H:%i') AS hora, 
                status, 
                data_criacao AS data_ordenacao 
            FROM orcamentos
        """)
        orcamentos = cursor.fetchall()
        for o in orcamentos:
            o['valor'] = float(o['valor']) if o['valor'] else 0.0
            
            # Se foi aprovado/finalizado, soma no lucro do dia (total_vendas)
            if o['status'] in ('Aprovado', 'Finalizado'):
                total_vendas += o['valor']
            else:
                total_orcamentos += o['valor']
                
            transacoes.append(o)
    except Exception as e:
        print(f"Erro ao buscar orçamentos para o extrato: {e}")

    # 4. Busca o histórico dos últimos 7 dias para o gráfico
    labels_dias = []
    valores_dias = []
    try:
        cursor.execute("""
            SELECT DATE_FORMAT(data_transacao, '%d/%m') AS dia, SUM(valor) AS total_dia
            FROM (
                SELECT data_venda AS data_transacao, total AS valor FROM vendas WHERE data_venda >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                UNION ALL
                SELECT data_entrada AS data_transacao, valor_estimado AS valor FROM conserto WHERE data_entrada >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            ) AS resumo
            GROUP BY DATE(data_transacao), dia
            ORDER BY DATE(data_transacao) ASC
        """)
        evolucao = cursor.fetchall()
        for item in evolucao:
            labels_dias.append(item['dia'])
            valores_dias.append(float(item['total_dia']) if item['total_dia'] else 0.0)
    except Exception as e:
        print(f"Erro ao buscar evolução diária: {e}")

    # Ordena as transações da tabela da mais recente para a mais antiga
    transacoes.sort(key=lambda x: str(x.get('data_ordenacao') or ''), reverse=True)

    cursor.close()
    conn.close()

    total_geral = total_vendas + total_servicos
    qtd_transacoes = len(transacoes)

    return render_template(
        'extrato.html', 
        transacoes=transacoes,
        total_vendas=total_vendas,
        total_servicos=total_servicos,
        total_geral=total_geral,
        qtd_transacoes=qtd_transacoes,
        labels_dias=labels_dias,
        valores_dias=valores_dias
    )

# ===================== CADASTRO E EDIÇÃO DE PRODUTOS =====================
@app.route('/cadastro_produtos', methods=['GET', 'POST'])
@login_requerido
def cadastro_produtos():
    sucesso = None
    erro = None

    if request.method == 'POST':
        id_produto = request.form.get('id_produto') # Recebe o ID (se for edição)
        nome_produto = request.form.get('nome_produto')
        categoria_produto = request.form.get('categoria_produto')
        marca = request.form.get('marca')
        
        # Conversão segura para números logo no início
        preco_custo = float(request.form.get('preco_custo') or 0.0)
        preco_at = float(request.form.get('preco_at') or 0.0)
        preco_vrj = float(request.form.get('preco_vrj') or 0.0)
        estoque_atual = int(request.form.get('estoque_atual') or 0)

        if not nome_produto or not preco_vrj:
            erro = "Nome do produto e Preço de Varejo são obrigatórios!"
        else:
            conn = get_connection()
            cursor = conn.cursor()
            try:
                # 1. CRIANDO A TABELA DE DESPESAS (Caso ela ainda não exista)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS despesas (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        descricao VARCHAR(255) NOT NULL,
                        valor DECIMAL(10,2) NOT NULL,
                        data_despesa DATETIME NOT NULL
                    )
                """)

                if id_produto:
                    # ===== SE TEM ID: MODO EDIÇÃO (UPDATE) =====
                    query = """
                        UPDATE produto 
                        SET nome_produto=%s, categoria_produto=%s, marca=%s, preço_custo=%s, preço_at=%s, preço_vrj=%s, estoque_atual=%s 
                        WHERE id_produto=%s
                    """
                    valores = (nome_produto, categoria_produto, marca, preco_custo, preco_at, preco_vrj, estoque_atual, id_produto)
                    cursor.execute(query, valores)
                    sucesso = "Produto atualizado com sucesso!"
                    registrar_notificacao(f"📦 Produto atualizado: {nome_produto}")
                else:
                    # ===== SE NÃO TEM ID: NOVO CADASTRO (INSERT) =====
                    query = """
                        INSERT INTO produto 
                        (nome_produto, categoria_produto, marca, preço_custo, preço_at, preço_vrj, estoque_atual) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    valores = (nome_produto, categoria_produto, marca, preco_custo, preco_at, preco_vrj, estoque_atual)
                    cursor.execute(query, valores)
                    
                    # 2. LANÇAMENTO AUTOMÁTICO DE DESPESA
                    # Se tiver preço de custo E tiver quantidade no estoque, lança o valor gasto!
                    if preco_custo > 0 and estoque_atual > 0:
                        valor_total_gasto = preco_custo * estoque_atual
                        descricao_despesa = f"Compra de Estoque: {nome_produto} ({estoque_atual} un)"
                        
                        cursor.execute("""
                            INSERT INTO despesas (descricao, valor, data_despesa) 
                            VALUES (%s, %s, NOW())
                        """, (descricao_despesa, valor_total_gasto))

                    sucesso = "Produto cadastrado com sucesso!"
                    registrar_notificacao(f"📦 Novo produto cadastrado: {nome_produto}")
                    
                conn.commit()
            except Exception as e:
                conn.rollback()
                erro = f"Erro ao salvar o produto: {e}"
            finally:
                cursor.close()
                conn.close()
    # Buscas para exibir na tela
    produtos = []
    categorias = []
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Busca as categorias dinâmicas
        cursor.execute("SELECT * FROM categoria ORDER BY nome ASC")
        categorias = cursor.fetchall()

        # Busca todos os dados do produto (incluindo preços ocultos para poder editar)
        cursor.execute("""
            SELECT 
                id_produto AS id, 
                id_produto AS codigo, 
                nome_produto AS nome, 
                categoria_produto AS categoria, 
                marca AS marca,
                preço_custo AS preco_custo,
                preço_at AS preco_at,
                preço_vrj AS preco, 
                estoque_atual AS estoque 
            FROM produto 
            ORDER BY id_produto DESC
        """)
        produtos = cursor.fetchall()
        
        # Converte decimais para JSON seguro
        for prod in produtos:
            prod['preco'] = float(prod['preco'] or 0.0)
            prod['preco_custo'] = float(prod['preco_custo'] or 0.0)
            prod['preco_at'] = float(prod['preco_at'] or 0.0)
            
    except Exception as e:
        print(f"Erro ao buscar produtos: {e}")
    finally:
        cursor.close()
        conn.close()

    return render_template('cadastroproduto.html', produtos=produtos, categorias=categorias, sucesso=sucesso, erro=erro)
# ===================== PAINEL UNIFICADO (CONSERTOS E ORÇAMENTOS) =====================
@app.route('/conserto', methods=['GET', 'POST'])
@login_requerido
def conserto():
    return logica_painel_unificado('consertos')

@app.route('/orcamento', methods=['GET'])
@login_requerido
def orcamento():
    return logica_painel_unificado('orcamentos')

def logica_painel_unificado(aba_ativa):
    erro = None
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST' and aba_ativa == 'consertos':
        id_conserto = request.form.get('id_conserto') 
        cliente = request.form.get('cliente')
        equipamento = request.form.get('equipamento')
        tipo = request.form.get('tipo')
        numero_serie = request.form.get('numero_serie')
        prioridade = request.form.get('prioridade')

        if not cliente or not equipamento or not numero_serie:
            erro = "Cliente, Equipamento e Número de Série são obrigatórios!"
        else:
            try:
                if id_conserto: 
                    query = """
                        UPDATE conserto 
                        SET nome_cliente=%s, equipamento=%s, tipo=%s, numero_serie=%s, prioridade=%s
                        WHERE id_conserto=%s
                    """
                    cursor.execute(query, (cliente, equipamento, tipo, numero_serie, prioridade, id_conserto))
                    flash("Dados do equipamento atualizados com sucesso!", "success")
                else: 
                    query = """
                        INSERT INTO conserto 
                        (nome_cliente, equipamento, tipo, numero_serie, prioridade, status_servico, valor_estimado) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(query, (cliente, equipamento, tipo, numero_serie, prioridade, 'recebido', 0.0))
                    flash("Equipamento cadastrado com sucesso!", "success")
                
                conn.commit()
                registrar_notificacao(f"📱 Novo equipamento recebido: {equipamento} ({numero_serie}) - Cliente: {cliente}")
                return redirect(url_for('conserto'))
            except Exception as e:
                conn.rollback()
                erro = f"Erro ao salvar equipamento: {e}"

    servicos = []
    orcamentos_lista = []
    config_empresa = {}
    categorias = [] 
    
    try:
        cursor.execute("SELECT * FROM categoria ORDER BY nome ASC")
        categorias = cursor.fetchall()

        # Busca Serviços (OS)
        cursor.execute("""
            SELECT id_conserto AS id, nome_cliente AS cliente, equipamento, tipo, 
                   numero_serie, prioridade, status_servico AS status, valor_estimado AS valor, observacoes AS laudo_tecnico 
            FROM conserto ORDER BY id_conserto DESC
        """)
        servicos = cursor.fetchall()
        for s in servicos: s['valor'] = float(s['valor'] or 0)

        cursor.execute("""
            SELECT o.id, o.numero_orcamento, o.cliente_nome, o.equipamento, o.numero_serie,
                   o.status AS status_orcamento, o.subtotal, o.desconto_reais, o.total_geral, o.observacoes,
                   DATE_FORMAT(o.data_criacao, '%d/%m/%Y') as data_fmt,
                   c.status_servico AS status_os
            FROM orcamentos o
            LEFT JOIN conserto c ON o.numero_serie = c.numero_serie AND o.numero_serie != '' AND o.numero_serie IS NOT NULL
            ORDER BY o.id DESC
        """)
        orcamentos_lista = cursor.fetchall()
        for o in orcamentos_lista: o['total_geral'] = float(o['total_geral'] or 0)

        cursor.execute("SELECT * FROM configuracoes WHERE id = 1")
        config_empresa = cursor.fetchone() or {}
    except Exception as e:
        print(f"Erro no painel unificado: {e}")
    finally:
        cursor.close()
        conn.close()
    return render_template('painel_servicos.html', servicos=servicos, orcamentos=orcamentos_lista, config=config_empresa, categorias=categorias, erro=erro, aba_ativa=aba_ativa)

@app.route('/salvar_orcamento', methods=['POST'])
@login_requerido
def salvar_orcamento():
    conn = None
    cursor = None
    try:
        status = request.form.get('status', 'Pendente')
        data_orcamento = request.form.get('data')
        cliente_nome = request.form.get('cliente')
        equipamento = request.form.get('equipamento')
        numero_serie = request.form.get('numero_serie')
        subtotal = request.form.get('subtotal', 0)
        desconto_reais = request.form.get('descontoReais', 0)
        total_geral = request.form.get('totalGeral', 0) # Recebe do input hidden
        
        conn = get_connection()
        cursor = conn.cursor()
        
        # Descobre o próximo ID sequencial na tabela de orçamentos para ordenar
        cursor.execute("SELECT MAX(id) FROM orcamentos")
        resultado = cursor.fetchone()
        proximo_id = (resultado[0] or 0) + 1
        
        # Gera o número do orçamento sequencial automaticamente (Ex: ORC-0001, ORC-0002...)
        numero_orcamento = f"ORC-{proximo_id:04d}"

        validade = datetime.now().strftime('%Y-%m-%d')
        cliente_doc = "Não informado"
        cliente_contato = "Não informado"
        vendedor = session.get('usuario_logado', 'Sistema')
        desconto_percent = 0.00
        frete = 0.00
        imposto_percent = 0.00
        metodo_pagamento = "PIX (À Vista)"
        condicao_pagamento = "À vista"
        garantia = "90 Dias"
        observacoes = "Gerado via Painel de Serviços"
        
        # Insere na tabela 'orcamentos'
        cursor.execute("""
            INSERT INTO orcamentos (
                numero_orcamento, data_orcamento, validade, cliente_nome, 
                cliente_doc, cliente_contato, vendedor, subtotal, 
                desconto_percent, desconto_reais, frete, imposto_percent, 
                total_geral, metodo_pagamento, condicao_pagamento, garantia, 
                observacoes, status, equipamento, numero_serie
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            numero_orcamento, data_orcamento, validade, cliente_nome,
            cliente_doc, cliente_contato, vendedor, subtotal,
            desconto_percent, desconto_reais, frete, imposto_percent,
            total_geral, metodo_pagamento, condicao_pagamento, garantia,
            observacoes, status, equipamento, numero_serie
        ))
        
        conn.commit()
        registrar_notificacao(f"📝 Novo orçamento gerado: #{numero_orcamento} (R$ {total_geral}) - Cliente: {cliente_nome}")
        flash(f"Orçamento {numero_orcamento} guardado com sucesso!", "success")
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Erro ao salvar orçamento: {e}")
        flash(f"Erro ao salvar orçamento.", "error")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()
        
    # Redireciona mantendo o usuário na aba de orçamentos
    return redirect(url_for('orcamento'))


@app.route('/status-agendamento')
def status_agendamento():
    jobs = scheduler.get_jobs()
    return jsonify({
        "status": "ok",
        "jobs": [
            {
                "id": job.id,
                "next_run_time": str(job.next_run_time),
                "trigger": str(job.trigger)
            } for job in jobs
        ]
    })

@app.context_processor
def injetar_configuracoes_globais():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    config = {}
    try:
        cursor.execute("SELECT * FROM configuracoes WHERE id = 1")
        config = cursor.fetchone() or {}
    except Exception as e:
        print("Erro ao carregar configurações globais:", e)
    finally:
        cursor.close()
        conn.close()
    return dict(config_global=config)

# ===================== ROTA CADASTRO DE FUNCIONÁRIOS =====================
# ===================== ROTA CADASTRO/EDIÇÃO DE FUNCIONÁRIOS =====================
@app.route('/cadastro_funcionario', methods=['GET', 'POST'])
@login_requerido
def cadastro_funcionario():
    # Bloqueio de segurança
    if session.get('nivel') not in [1, '1']:
        flash("Acesso restrito! Apenas administradores.", "error")
        return redirect(url_for('menu'))

    sucesso = None
    erro = None
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')
        cargo = request.form.get('cargo')
        telefone = request.form.get('telefone')
        departamento = request.form.get('departamento')
        salario = request.form.get('salario')
        two_factor_ativo = request.form.get('two_factor_ativo', 0) # Captura o novo campo (Padrão: 0)
        
        nivel_permissao = 1 if cargo == 'Administrador' else 2

        try:
            # Verifica se o utilizador já existe
            cursor.execute("SELECT id_usuario FROM usuario WHERE email = %s", (email,))
            existe = cursor.fetchone()

            if existe:
                # SE EXISTE: ATUALIZAÇÃO (EDIÇÃO)
                cursor.execute("""
                    UPDATE usuario 
                    SET senha = %s, cargo = %s, telefone = %s, departamento = %s, salario = %s, nivel_de_permissao = %s, two_factor_ativo = %s
                    WHERE email = %s
                """, (senha, cargo, telefone, departamento, float(salario) if salario else 0.0, nivel_permissao, int(two_factor_ativo), email))
                sucesso = f"Dados do funcionário {email} atualizados com sucesso!"
                registrar_notificacao(f"👥 Funcionário atualizado: {email}")
            else:
                # SE NÃO EXISTE: CADASTRO NOVO
                cursor.execute("""
                    INSERT INTO usuario (email, senha, cargo, telefone, departamento, salario, nivel_de_permissao, two_factor_ativo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (email, senha, cargo, telefone, departamento, float(salario) if salario else 0.0, nivel_permissao, int(two_factor_ativo)))
                sucesso = "Novo funcionário registado com sucesso!"
                registrar_notificacao(f"👥 Novo funcionário registado: {email}")
                
            conn.commit()
        except Exception as e:
            conn.rollback()
            erro = f"Erro na operação: {e}"

    # Busca a lista de funcionários (AGORA PUXANDO O CAMPO two_factor_ativo)
    funcionarios = []
    try:
        cursor.execute("SELECT id_usuario, email, cargo, departamento, telefone, two_factor_ativo FROM usuario ORDER BY id_usuario DESC")
        funcionarios = cursor.fetchall()
    except Exception as e:
        print("Erro ao buscar funcionários:", e)
    finally:
        cursor.close()
        conn.close()

    return render_template('cadastro_funcionario.html', funcionarios=funcionarios, sucesso=sucesso, erro=erro)

# ===================== ROTA EXCLUSÃO DE FUNCIONÁRIOS =====================
@app.route('/excluir_funcionario/<email>', methods=['POST'])
@login_requerido
def excluir_funcionario(email):
    # Proteção para garantir que só os admins (nível 1) podem excluir
    if session.get('nivel') not in [1, '1']:
        return redirect(url_for('menu'))

    # Proteção extra: não deixar apagar a si próprio
    if email == session.get('usuario_logado'):
        flash("Por medidas de segurança, não pode excluir a sua própria conta.", "error")
        return redirect(url_for('cadastro_funcionario'))

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM usuario WHERE email = %s", (email,))
        conn.commit()
        flash(f"Funcionário {email} excluído com sucesso.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Erro ao excluir funcionário: {e}", "error")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('cadastro_funcionario'))

# ===================== GERENCIAMENTO DE CATEGORIAS (ADMIN) =====================
@app.route('/adicionar_categoria', methods=['POST'])
@login_requerido
def adicionar_categoria():
    if session.get('nivel') not in [1, '1']: # Apenas Admin
        return redirect(url_for('conserto'))
    
    nome = request.form.get('nome_categoria')
    if nome:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO categoria (nome) VALUES (%s)", (nome.strip(),))
            conn.commit()
            flash(f"Categoria '{nome}' adicionada com sucesso!", "success")
        except Exception as e:
            flash("Erro ao adicionar. A categoria pode já existir.", "error")
        finally:
            cursor.close()
            conn.close()
    return redirect(url_for('conserto'))

@app.route('/excluir_categoria/<int:id_cat>', methods=['POST'])
@login_requerido
def excluir_categoria(id_cat):
    if session.get('nivel') not in [1, '1']: # Apenas Admin
        return redirect(url_for('conserto'))
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM categoria WHERE id_categoria = %s", (id_cat,))
        conn.commit()
        flash("Categoria removida com sucesso!", "success")
    except Exception as e:
        flash("Erro ao remover categoria.", "error")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('conserto'))


@app.route('/atualizar_andamento', methods=['POST'])
@login_requerido
def atualizar_andamento():
    id_orcamento = request.form.get('id_orcamento')
    numero_serie = request.form.get('numero_serie')
    status_os = request.form.get('status_os', 'recebido')
    status_orcamento = request.form.get('status_orcamento', 'Pendente')
    
    # Conversão segura dos valores financeiros
    try: valor = float(request.form.get('valor') or 0.0)
    except: valor = 0.0
        
    try: desconto = float(request.form.get('desconto') or 0.0)
    except: desconto = 0.0
        
    try: total = float(request.form.get('total') or 0.0)
    except: total = 0.0
        
    laudo = request.form.get('laudo_tecnico', '')
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Puxa os dados antigos para saber se o status mudou
        status_anterior = ''
        cliente_nome = 'Cliente'
        if id_orcamento:
            cursor.execute("SELECT status, cliente_nome FROM orcamentos WHERE id = %s", (id_orcamento,))
            orc_db = cursor.fetchone()
            if orc_db:
                status_anterior = orc_db['status']
                cliente_nome = orc_db['cliente_nome']

        # 2. Atualiza o Status Financeiro e Valores
        if id_orcamento:
            cursor.execute("""
                UPDATE orcamentos 
                SET status = %s, subtotal = %s, desconto_reais = %s, total_geral = %s, observacoes = %s
                WHERE id = %s
            """, (status_orcamento, valor, desconto, total, laudo, id_orcamento))
        
        # 3. Atualiza o Status Físico (Apenas se a série existir)
        if numero_serie and str(numero_serie).strip() not in ['', 'N/I']:
            cursor.execute("""
                UPDATE conserto 
                SET status_servico = %s, observacoes = %s 
                WHERE numero_serie = %s
            """, (status_os, laudo, numero_serie))

        conn.commit()

        # 4. GATILHOS DE NOTIFICAÇÃO INTELIGENTES
        if status_orcamento != status_anterior:
            if status_orcamento == 'Aprovado':
                registrar_notificacao(f"✅ Orçamento APROVADO! R$ {total:.2f} do cliente {cliente_nome} adicionados à projeção.")
            elif status_orcamento == 'Finalizado':
                registrar_notificacao(f"🎉 Serviço FINALIZADO e PAGO! R$ {total:.2f} faturados (Cliente: {cliente_nome}).")
            elif status_orcamento == 'Reprovado':
                registrar_notificacao(f"❌ Orçamento Reprovado pelo cliente: {cliente_nome}.")

        flash("Status e valores guardados com sucesso!", "success")
    except Exception as e:
        conn.rollback()
        print(f"Erro fatal ao atualizar andamento: {e}")
        flash(f"Erro ao salvar no banco de dados.", "error")
    finally:
        cursor.close()
        conn.close()
        
    return redirect(url_for('orcamento', aba='andamento'))
def registrar_notificacao(mensagem):
    """Grava notificação apenas se o utilizador logado tiver as notificações ativas"""
    if 'usuario_logado' not in session:
        return

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Garante que a tabela existe (Prevenção de falhas críticas)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notificacoes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                mensagem VARCHAR(255) NOT NULL,
                data_criacao DATETIME NOT NULL,
                lida TINYINT(1) DEFAULT 0
            )
        """)
        conn.commit()

        # Verifica se o utilizador tem as notificações ativas (1)
        try:
            cursor.execute("SELECT notificacoes_ativas FROM usuario WHERE email = %s", (session['usuario_logado'],))
            user_pref = cursor.fetchone()
        except:
            # Se a coluna não existir, adiciona
            cursor.execute("ALTER TABLE usuario ADD COLUMN notificacoes_ativas TINYINT(1) DEFAULT 1")
            conn.commit()
            user_pref = {'notificacoes_ativas': 1}
        
        # Se as notificações estiverem ligadas (ou se não houver registo, por defeito ativa)
        if not user_pref or user_pref.get('notificacoes_ativas', 1) == 1:
            data_hoje = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
                INSERT INTO notificacoes (mensagem, data_criacao, lida) 
                VALUES (%s, %s, 0)
            """, (mensagem, data_hoje))
            conn.commit()
            print(f"✅ Notificação salva na Base de Dados: {mensagem}")
        else:
            print("⚠️ Notificação ignorada (Usuário desligou nas configurações).")
    except Exception as e:
        print(f"❌ Erro ao registrar notificação: {e}")
    finally:
        cursor.close()
        conn.close()

# ===================== ROTA PARA EXCLUIR VENDA E RESTAURAR ESTOQUE =====================
@app.route('/excluir_venda/<int:id_venda>', methods=['POST'])
@login_requerido
def excluir_venda(id_venda):
    # Opcional: Bloqueia para que apenas Administradores possam excluir vendas
    if session.get('nivel') not in [1, '1'] and session.get('cargo') != 'Administrador':
        flash("Acesso restrito! Apenas administradores podem excluir vendas.", "error")
        return redirect(url_for('vendas'))

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Busca os itens dessa venda para devolver ao estoque
        cursor.execute("SELECT id_produto, quantidade FROM itens_venda WHERE id_venda = %s", (id_venda,))
        itens = cursor.fetchall()

        # 2. Para cada item vendido, soma a quantidade de volta no estoque
        for item in itens:
            cursor.execute("""
                UPDATE produto 
                SET estoque_atual = estoque_atual + %s 
                WHERE id_produto = %s
            """, (item['quantidade'], item['id_produto']))

        # 3. Deleta os itens da venda
        cursor.execute("DELETE FROM itens_venda WHERE id_venda = %s", (id_venda,))
        
        # 4. Por fim, deleta a venda principal
        cursor.execute("DELETE FROM vendas WHERE id_venda = %s", (id_venda,))

        conn.commit()
        registrar_notificacao(f"🗑️ Venda #{id_venda} foi cancelada e os itens retornaram ao estoque.")
        
    except Exception as e:
        conn.rollback()
        print(f"Erro ao excluir venda: {e}")
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for('vendas'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)