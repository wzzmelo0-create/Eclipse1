from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from functools import wraps
import sqlite3
import urllib.parse


# ============================================================
# Cidade Eclipse
# SISTEMA PRINCIPAL
# ============================================================

app = Flask(__name__)

app.secret_key = "atlas_city_chave_secreta_2026"

DATABASE = "atlas_city.db"

DISCORD_URL = "https://discord.gg/6QYFQjZC9q"

WHATSAPP_URL = "https://wa.me/message/5519971471401"


# ============================================================
# CARGOS
# ============================================================

CARGOS = {
    "Ceo": 5,
    "Fundador": 4,
    "Programador": 3,
    "Administrador": 2,
    "Civil": 1
}


# ============================================================
# BANCO DE DADOS
# ============================================================

def conectar_banco():

    conexao = sqlite3.connect(DATABASE)

    conexao.row_factory = sqlite3.Row

    return conexao


def criar_banco():

    conexao = conectar_banco()

    cursor = conexao.cursor()

    # ========================================================
    # USUÁRIOS
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            cargo TEXT NOT NULL DEFAULT 'Civil',
            banido INTEGER NOT NULL DEFAULT 0,
            ativo INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("PRAGMA table_info(usuarios)")

    colunas = {
        coluna["name"]
        for coluna in cursor.fetchall()
    }

    if "cargo" not in colunas:

        cursor.execute("""
            ALTER TABLE usuarios
            ADD COLUMN cargo TEXT NOT NULL DEFAULT 'Civil'
        """)

    if "banido" not in colunas:

        cursor.execute("""
            ALTER TABLE usuarios
            ADD COLUMN banido INTEGER NOT NULL DEFAULT 0
        """)

    if "ativo" not in colunas:

        cursor.execute("""
            ALTER TABLE usuarios
            ADD COLUMN ativo INTEGER NOT NULL DEFAULT 1
        """)

    if "criado_em" not in colunas:

        cursor.execute("""
            ALTER TABLE usuarios
            ADD COLUMN criado_em TEXT
        """)

        cursor.execute("""
            UPDATE usuarios
            SET criado_em = CURRENT_TIMESTAMP
            WHERE criado_em IS NULL
        """)

    # ========================================================
    # CONFIGURAÇÕES
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    """)

    # ========================================================
    # STATUS INICIAL
    # ========================================================

    cursor.execute("""
        INSERT OR IGNORE INTO configuracoes
        (
            chave,
            valor
        )
        VALUES
        (
            'servidor_status',
            'online'
        )
    """)

    # ========================================================
    # LOG ADMINISTRATIVO
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs_admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            acao TEXT NOT NULL,
            alvo TEXT,
            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(admin_id)
            REFERENCES usuarios(id)
        )
    """)

    # ========================================================
    # BOXES DA CIDADE
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cidade_boxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            titulo TEXT NOT NULL,

            descricao TEXT DEFAULT '',

            imagem TEXT DEFAULT '',

            categoria TEXT DEFAULT 'Cidade',

            botao_texto TEXT DEFAULT '',

            botao_url TEXT DEFAULT '',

            ordem INTEGER NOT NULL DEFAULT 0,

            ativo INTEGER NOT NULL DEFAULT 1,

            criado_por INTEGER,

            criado_em TEXT DEFAULT CURRENT_TIMESTAMP,

            atualizado_em TEXT DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(criado_por)
            REFERENCES usuarios(id)
        )
    """)

    # ========================================================
    # ÍNDICES
    # ========================================================

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_cidade_boxes_ordem
        ON cidade_boxes(ordem)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_cidade_boxes_ativo
        ON cidade_boxes(ativo)
    """)

    conexao.commit()

    conexao.close()


# ============================================================
# STATUS DO SERVIDOR
# ============================================================

def obter_status_servidor():

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT valor
        FROM configuracoes
        WHERE chave = 'servidor_status'
    """)

    resultado = cursor.fetchone()

    conexao.close()

    if resultado:
        return resultado["valor"]

    return "online"


def alterar_status_servidor(status):

    if status not in ["online", "offline"]:
        return False

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        INSERT OR IGNORE INTO configuracoes
        (
            chave,
            valor
        )
        VALUES
        (
            'servidor_status',
            'online'
        )
    """)

    cursor.execute("""
        UPDATE configuracoes
        SET valor = ?
        WHERE chave = 'servidor_status'
    """, (
        status,
    ))

    conexao.commit()

    conexao.close()

    return True


# ============================================================
# STATUS GLOBAL PARA TODOS OS TEMPLATES
# ============================================================

@app.context_processor
def dados_globais():

    status = obter_status_servidor()

    return {
        "status_servidor": status,
        "status_online": status == "online",
        "status_offline": status == "offline",
        "discord_url": DISCORD_URL,
        "whatsapp_url": WHATSAPP_URL
    }


# ============================================================
# USUÁRIO LOGADO
# ============================================================

def usuario_logado():

    if "usuario_id" not in session:
        return None

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM usuarios
        WHERE id = ?
    """, (
        session["usuario_id"],
    ))

    usuario = cursor.fetchone()

    conexao.close()

    return usuario


# ============================================================
# NÍVEL DO CARGO
# ============================================================

def nivel_cargo(cargo):

    return CARGOS.get(cargo, 0)


# ============================================================
# DECORATOR DE LOGIN
# ============================================================

def login_obrigatorio(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if "usuario_id" not in session:

            flash(
                "Você precisa fazer login para continuar.",
                "erro"
            )

            return redirect(
                url_for("login")
            )

        usuario = usuario_logado()

        if not usuario:

            session.clear()

            flash(
                "Sua sessão não é mais válida.",
                "erro"
            )

            return redirect(
                url_for("login")
            )

        if usuario["banido"]:

            session.clear()

            flash(
                "Sua conta está banida.",
                "erro"
            )

            return redirect(
                url_for("login")
            )

        if not usuario["ativo"]:

            session.clear()

            flash(
                "Sua conta está desativada.",
                "erro"
            )

            return redirect(
                url_for("login")
            )

        return func(*args, **kwargs)

    return wrapper


# ============================================================
# DECORATOR DE CARGO
# ============================================================

def cargo_obrigatorio(cargo_minimo):

    def decorator(func):

        @wraps(func)
        def wrapper(*args, **kwargs):

            if "usuario_id" not in session:

                flash(
                    "Faça login para acessar essa área.",
                    "erro"
                )

                return redirect(
                    url_for("login")
                )

            usuario = usuario_logado()

            if not usuario:

                session.clear()

                return redirect(
                    url_for("login")
                )

            if usuario["banido"] or not usuario["ativo"]:

                session.clear()

                flash(
                    "Sua conta não pode acessar essa área.",
                    "erro"
                )

                return redirect(
                    url_for("login")
                )

            if nivel_cargo(usuario["cargo"]) < nivel_cargo(cargo_minimo):

                flash(
                    "Você não possui permissão para acessar essa área.",
                    "erro"
                )

                return redirect(
                    url_for("painel")
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# MONITORAMENTO DO CHAT
# ============================================================

def monitor_chat_obrigatorio(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if "usuario_id" not in session:

            flash(
                "Faça login para acessar essa área.",
                "erro"
            )

            return redirect(
                url_for("login")
            )

        usuario = usuario_logado()

        if not usuario:

            session.clear()

            return redirect(
                url_for("login")
            )

        if usuario["banido"] or not usuario["ativo"]:

            session.clear()

            flash(
                "Sua conta não pode acessar essa área.",
                "erro"
            )

            return redirect(
                url_for("login")
            )

        cargos_permitidos = [
            "Ceo",
            "Fundador",
            "Programador",
            "Administrador"
        ]

        if usuario["cargo"] not in cargos_permitidos:

            flash(
                "Você não possui permissão para monitorar o chat.",
                "erro"
            )

            return redirect(
                url_for("painel")
            )

        return func(*args, **kwargs)

    return wrapper


# ============================================================
# LOG ADMINISTRATIVO
# ============================================================

def registrar_log(acao, alvo=""):

    if "usuario_id" not in session:
        return

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO logs_admin
        (
            admin_id,
            acao,
            alvo
        )
        VALUES (?, ?, ?)
    """, (
        session["usuario_id"],
        acao,
        alvo
    ))

    conexao.commit()

    conexao.close()


# ============================================================
# LINK WHATSAPP
# ============================================================

def gerar_link_whatsapp(produto, preco):

    mensagem = (
        f"Olá! Tenho interesse em comprar o produto "
        f"*{produto}* por *R$ {preco}* na loja da Cidade Eclipse. "
        f"Gostaria de finalizar a compra."
    )

    mensagem_codificada = urllib.parse.quote(
        mensagem
    )

    return (
        "https://wa.me/5519971471401"
        f"?text={mensagem_codificada}"
    )


# ============================================================
# PRODUTOS
# ============================================================

PRODUTOS = [

    # ========================================================
    # UTILITÁRIOS
    # ========================================================

    {
        "nome": "Nick Brilhante",
        "preco": "100,00",
        "icone": "fa-star",
        "categoria": "utilitarios",
        "descricao":
            "Deixe seu nome em destaque dentro da Cidade."
    },

    {
        "nome": "Carro Arco-íris",
        "preco": "70,00",
        "icone": "fa-star",
        "categoria": "utilitarios",
        "descricao":
            "Deixe seu veículo em destaque dentro da Cidade."
    },

    {
        "nome": "Som Automotivo",
        "preco": "60,00",
        "icone": "fa-star",
        "categoria": "utilitarios",
        "descricao":
            "Curta sua música favorita em um veículo."
    },


    # ========================================================
    # VEÍCULOS
    # ========================================================

    {
        "nome": "Sultan",
        "preco": "50,00",
        "icone": "fa-car",
        "categoria": "veiculos",
        "descricao":
            "Adquira um veículo esportivo exclusivo para sua garagem."
    },

    {
        "nome": "Infernus",
        "preco": "40,00",
        "icone": "fa-car-side",
        "categoria": "veiculos",
        "descricao":
            "Tenha um veículo de luxo exclusivo dentro da Cidade Eclipse."
    },

    {
        "nome": "Cheeta",
        "preco": "30,00",
        "icone": "fa-car",
        "categoria": "veiculos",
        "descricao":
            "Um veículo exclusivo para quem busca presença e estilo."
    },

    {
        "nome": "NRG-500",
        "preco": "50,00",
        "icone": "fa-car-side",
        "categoria": "veiculos",
        "descricao":
            "Adquira uma moto clássica e diferenciada para sua garagem."
    },

    {
        "nome": "Sanchez",
        "preco": "30,00",
        "icone": "fa-car",
        "categoria": "veiculos",
        "descricao":
            "Uma moto exclusiva para os jogadores mais exigentes."
    },

    {
        "nome": "FCR-900",
        "preco": "30,00",
        "icone": "fa-car-side",
        "categoria": "veiculos",
        "descricao":
            "Veículo premium dentro da Cidade Eclipse."
    },


    # ========================================================
    # VEÍCULOS ESPECIAIS
    # ========================================================

    {
        "nome": "Vaca",
        "preco": "80,00",
        "icone": "fa-car",
        "categoria": "veiculos-especiais",
        "descricao":
            "Adquira um veículo especial com visual exclusivo e diferenciado."
    },

    {
        "nome": "Veículo Personalizado",
        "preco": "100,00",
        "icone": "fa-car-side",
        "categoria": "veiculos-especiais",
        "descricao":
            "Escolha e personalize seu veículo para deixar sua marca única dentro da Cidade Eclipse."
    }

]


# ============================================================
# INÍCIO
# ============================================================

@app.route("/")
def inicio():

    return render_template(
        "index.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if "usuario_id" in session:

        return redirect(
            url_for("painel")
        )

    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        senha = request.form.get(
            "senha",
            ""
        )

        if not usuario or not senha:

            flash(
                "Preencha o usuário e a senha.",
                "erro"
            )

            return redirect(
                url_for("login")
            )

        conexao = conectar_banco()

        cursor = conexao.cursor()

        cursor.execute("""
            SELECT *
            FROM usuarios
            WHERE usuario = ?
        """, (
            usuario,
        ))

        usuario_db = cursor.fetchone()

        conexao.close()

        if usuario_db is None:

            flash(
                "Usuário ou senha incorretos.",
                "erro"
            )

            return redirect(
                url_for("login")
            )

        if not check_password_hash(
            usuario_db["senha"],
            senha
        ):

            flash(
                "Usuário ou senha incorretos.",
                "erro"
            )

            return redirect(
                url_for("login")
            )

        if usuario_db["banido"]:

            flash(
                "Essa conta está banida.",
                "erro"
            )

            return redirect(
                url_for("login")
            )

        if not usuario_db["ativo"]:

            flash(
                "Essa conta está desativada.",
                "erro"
            )

            return redirect(
                url_for("login")
            )

        session.clear()

        session["usuario_id"] = usuario_db["id"]
        session["usuario"] = usuario_db["usuario"]
        session["cargo"] = usuario_db["cargo"]

        return redirect(
            url_for("painel")
        )

    return render_template(
        "login.html"
    )


# ============================================================
# CADASTRO
# ============================================================

@app.route(
    "/cadastro",
    methods=["GET", "POST"]
)
def cadastro():

    if "usuario_id" in session:

        return redirect(
            url_for("painel")
        )

    if request.method == "POST":

        usuario = request.form.get(
            "usuario",
            ""
        ).strip()

        senha = request.form.get(
            "senha",
            ""
        )

        confirmar_senha = request.form.get(
            "confirmar_senha",
            ""
        )

        if (
            not usuario
            or not senha
            or not confirmar_senha
        ):

            flash(
                "Preencha todos os campos.",
                "erro"
            )

            return redirect(
                url_for("cadastro")
            )

        if len(usuario) < 3:

            flash(
                "O usuário precisa ter pelo menos 3 caracteres.",
                "erro"
            )

            return redirect(
                url_for("cadastro")
            )

        if len(usuario) > 20:

            flash(
                "O usuário pode ter no máximo 20 caracteres.",
                "erro"
            )

            return redirect(
                url_for("cadastro")
            )

        if len(senha) < 6:

            flash(
                "A senha precisa ter pelo menos 6 caracteres.",
                "erro"
            )

            return redirect(
                url_for("cadastro")
            )

        if senha != confirmar_senha:

            flash(
                "As senhas não são iguais.",
                "erro"
            )

            return redirect(
                url_for("cadastro")
            )

        conexao = conectar_banco()

        cursor = conexao.cursor()

        cursor.execute("""
            SELECT id
            FROM usuarios
            WHERE usuario = ?
        """, (
            usuario,
        ))

        usuario_existente = cursor.fetchone()

        if usuario_existente:

            conexao.close()

            flash(
                "Esse usuário já está cadastrado.",
                "erro"
            )

            return redirect(
                url_for("cadastro")
            )

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM usuarios
        """)

        total_usuarios = cursor.fetchone()["total"]

        if total_usuarios == 0:

            cargo_inicial = "Ceo"

        else:

            cargo_inicial = "Civil"

        senha_hash = generate_password_hash(
            senha
        )

        cursor.execute("""
            INSERT INTO usuarios
            (
                usuario,
                senha,
                cargo,
                banido,
                ativo
            )
            VALUES (?, ?, ?, 0, 1)
        """, (
            usuario,
            senha_hash,
            cargo_inicial
        ))

        conexao.commit()

        conexao.close()

        if cargo_inicial == "Ceo":

            flash(
                "Conta criada com sucesso! Você é o CEO do Eclipse RPG.",
                "sucesso"
            )

        else:

            flash(
                "Conta criada com sucesso! Agora faça login.",
                "sucesso"
            )

        return redirect(
            url_for("login")
        )

    return render_template(
        "cadastro.html"
    )


# ============================================================
# PAINEL
# ============================================================

@app.route("/painel")
@login_obrigatorio
def painel():

    usuario = usuario_logado()

    return render_template(
        "painel.html",
        usuario=usuario,
        status_servidor=obter_status_servidor()
    )


# ============================================================
# ADMIN
# ============================================================

@app.route("/admin")
@cargo_obrigatorio("Programador")
def admin():

    usuario = usuario_logado()

    conexao = conectar_banco()

    cursor = conexao.cursor()

    # ========================================================
    # USUÁRIOS
    # ========================================================

    cursor.execute("""
        SELECT
            id,
            usuario,
            cargo,
            banido,
            ativo,
            criado_em
        FROM usuarios
        ORDER BY id DESC
    """)

    usuarios = cursor.fetchall()

    # ========================================================
    # LOGS
    # ========================================================

    cursor.execute("""
        SELECT
            logs_admin.id,
            logs_admin.acao,
            logs_admin.alvo,
            logs_admin.criado_em,
            usuarios.usuario
        FROM logs_admin
        JOIN usuarios
        ON usuarios.id = logs_admin.admin_id
        ORDER BY logs_admin.id DESC
        LIMIT 100
    """)

    logs = cursor.fetchall()

    # ========================================================
    # ESTATÍSTICAS
    # ========================================================

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM usuarios
    """)

    total_usuarios = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM usuarios
        WHERE banido = 1
    """)

    total_banidos = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM usuarios
        WHERE ativo = 1
    """)

    total_ativos = cursor.fetchone()["total"]

    # ========================================================
    # BOXES
    # ========================================================

    cursor.execute("""
        SELECT
            cidade_boxes.*,
            usuarios.usuario AS criador
        FROM cidade_boxes
        LEFT JOIN usuarios
        ON usuarios.id = cidade_boxes.criado_por
        ORDER BY
            cidade_boxes.ordem ASC,
            cidade_boxes.id DESC
    """)

    cidade_boxes = cursor.fetchall()

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM cidade_boxes
    """)

    total_boxes = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM cidade_boxes
        WHERE ativo = 1
    """)

    total_boxes_ativos = cursor.fetchone()["total"]

    conexao.close()

    # ========================================================
    # STATUS ATUAL
    # ========================================================

    status_atual = obter_status_servidor()

    return render_template(
        "admin.html",

        usuario=usuario,

        usuarios=usuarios,

        logs=logs,

        total_usuarios=total_usuarios,

        total_banidos=total_banidos,

        total_ativos=total_ativos,

        cidade_boxes=cidade_boxes,

        total_boxes=total_boxes,

        total_boxes_ativos=total_boxes_ativos,

        status_servidor=status_atual
    )


# ============================================================
# ALTERAR STATUS DO SERVIDOR
# ============================================================

@app.route(
    "/admin/status",
    methods=["POST"]
)
@cargo_obrigatorio("Programador")
def admin_status():

    novo_status = request.form.get(
        "status",
        ""
    ).strip().lower()

    if novo_status not in [
        "online",
        "offline"
    ]:

        flash(
            "Status inválido.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    sucesso = alterar_status_servidor(
        novo_status
    )

    if not sucesso:

        flash(
            "Não foi possível alterar o status.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    registrar_log(
        f"Alterou o status do servidor para {novo_status.upper()}",
        "Servidor"
    )

    flash(
        f"Servidor alterado para {novo_status.upper()}.",
        "sucesso"
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# BANIR USUÁRIO
# ============================================================

@app.route(
    "/admin/usuario/<int:usuario_id>/banir",
    methods=["POST"]
)
@cargo_obrigatorio("Fundador")
def admin_banir(usuario_id):

    admin_usuario = usuario_logado()

    if usuario_id == admin_usuario["id"]:

        flash(
            "Você não pode banir sua própria conta.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM usuarios
        WHERE id = ?
    """, (
        usuario_id,
    ))

    alvo = cursor.fetchone()

    if not alvo:

        conexao.close()

        flash(
            "Usuário não encontrado.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    if nivel_cargo(alvo["cargo"]) >= nivel_cargo(admin_usuario["cargo"]):

        conexao.close()

        flash(
            "Você não pode banir um usuário com cargo igual ou superior ao seu.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    cursor.execute("""
        UPDATE usuarios
        SET
            banido = 1,
            ativo = 0
        WHERE id = ?
    """, (
        usuario_id,
    ))

    conexao.commit()

    conexao.close()

    registrar_log(
        "Baniu usuário",
        alvo["usuario"]
    )

    flash(
        f"O usuário {alvo['usuario']} foi banido.",
        "sucesso"
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# DESBANIR USUÁRIO
# ============================================================

@app.route(
    "/admin/usuario/<int:usuario_id>/desbanir",
    methods=["POST"]
)
@cargo_obrigatorio("Fundador")
def admin_desbanir(usuario_id):

    admin_usuario = usuario_logado()

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM usuarios
        WHERE id = ?
    """, (
        usuario_id,
    ))

    alvo = cursor.fetchone()

    if not alvo:

        conexao.close()

        flash(
            "Usuário não encontrado.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    if nivel_cargo(alvo["cargo"]) >= nivel_cargo(admin_usuario["cargo"]):

        conexao.close()

        flash(
            "Você não pode alterar um usuário com cargo igual ou superior ao seu.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    cursor.execute("""
        UPDATE usuarios
        SET
            banido = 0,
            ativo = 1
        WHERE id = ?
    """, (
        usuario_id,
    ))

    conexao.commit()

    conexao.close()

    registrar_log(
        "Desbaniu usuário",
        alvo["usuario"]
    )

    flash(
        f"O usuário {alvo['usuario']} foi desbanido.",
        "sucesso"
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# DESATIVAR USUÁRIO
# ============================================================

@app.route(
    "/admin/usuario/<int:usuario_id>/desativar",
    methods=["POST"]
)
@cargo_obrigatorio("Fundador")
def admin_desativar(usuario_id):

    admin_usuario = usuario_logado()

    if usuario_id == admin_usuario["id"]:

        flash(
            "Você não pode desativar sua própria conta.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM usuarios
        WHERE id = ?
    """, (
        usuario_id,
    ))

    alvo = cursor.fetchone()

    if not alvo:

        conexao.close()

        flash(
            "Usuário não encontrado.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    if nivel_cargo(alvo["cargo"]) >= nivel_cargo(admin_usuario["cargo"]):

        conexao.close()

        flash(
            "Você não pode alterar um usuário com cargo igual ou superior ao seu.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    cursor.execute("""
        UPDATE usuarios
        SET ativo = 0
        WHERE id = ?
    """, (
        usuario_id,
    ))

    conexao.commit()

    conexao.close()

    registrar_log(
        "Desativou usuário",
        alvo["usuario"]
    )

    flash(
        f"O usuário {alvo['usuario']} foi desativado.",
        "sucesso"
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# ATIVAR USUÁRIO
# ============================================================

@app.route(
    "/admin/usuario/<int:usuario_id>/ativar",
    methods=["POST"]
)
@cargo_obrigatorio("Fundador")
def admin_ativar(usuario_id):

    admin_usuario = usuario_logado()

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM usuarios
        WHERE id = ?
    """, (
        usuario_id,
    ))

    alvo = cursor.fetchone()

    if not alvo:

        conexao.close()

        flash(
            "Usuário não encontrado.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    if nivel_cargo(alvo["cargo"]) >= nivel_cargo(admin_usuario["cargo"]):

        conexao.close()

        flash(
            "Você não pode alterar um usuário com cargo igual ou superior ao seu.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    cursor.execute("""
        UPDATE usuarios
        SET ativo = 1
        WHERE id = ?
    """, (
        usuario_id,
    ))

    conexao.commit()

    conexao.close()

    registrar_log(
        "Ativou usuário",
        alvo["usuario"]
    )

    flash(
        f"O usuário {alvo['usuario']} foi ativado.",
        "sucesso"
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# ALTERAR CARGO
# ============================================================

@app.route(
    "/admin/usuario/<int:usuario_id>/cargo",
    methods=["POST"]
)
@cargo_obrigatorio("Ceo")
def admin_cargo(usuario_id):

    novo_cargo = request.form.get(
        "cargo",
        ""
    ).strip()

    admin_usuario = usuario_logado()

    if novo_cargo not in CARGOS:

        flash(
            "Cargo inválido.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    if usuario_id == admin_usuario["id"]:

        flash(
            "Você não pode alterar o próprio cargo.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM usuarios
        WHERE id = ?
    """, (
        usuario_id,
    ))

    alvo = cursor.fetchone()

    if not alvo:

        conexao.close()

        flash(
            "Usuário não encontrado.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    if alvo["cargo"] == "Ceo":

        conexao.close()

        flash(
            "A conta CEO é protegida e não pode ter o cargo alterado.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    if novo_cargo == "Ceo":

        conexao.close()

        flash(
            "Não é permitido criar outro CEO pelo painel.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    if nivel_cargo(alvo["cargo"]) >= nivel_cargo(admin_usuario["cargo"]):

        conexao.close()

        flash(
            "Você não pode alterar o cargo de um usuário com cargo igual ou superior ao seu.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    if nivel_cargo(novo_cargo) >= nivel_cargo(admin_usuario["cargo"]):

        conexao.close()

        flash(
            "Você não pode atribuir um cargo igual ou superior ao seu.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    cursor.execute("""
        UPDATE usuarios
        SET cargo = ?
        WHERE id = ?
    """, (
        novo_cargo,
        usuario_id
    ))

    conexao.commit()

    conexao.close()

    registrar_log(
        f"Alterou cargo para {novo_cargo}",
        alvo["usuario"]
    )

    flash(
        f"O cargo de {alvo['usuario']} foi alterado para {novo_cargo}.",
        "sucesso"
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# CIDADE
# ============================================================

@app.route("/cidade")
def cidade():

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            id,
            titulo,
            descricao,
            imagem,
            categoria,
            botao_texto,
            botao_url,
            ordem
        FROM cidade_boxes
        WHERE ativo = 1
        ORDER BY
            ordem ASC,
            id DESC
    """)

    cidade_boxes = cursor.fetchall()

    conexao.close()

    return render_template(
        "cidade.html",
        cidade_boxes=cidade_boxes
    )


# ============================================================
# NOVO BOX DA CIDADE
# ============================================================

@app.route(
    "/admin/cidade/novo",
    methods=["GET", "POST"]
)
@cargo_obrigatorio("Programador")
def admin_cidade_novo():

    if request.method == "POST":

        titulo = request.form.get(
            "titulo",
            ""
        ).strip()

        descricao = request.form.get(
            "descricao",
            ""
        ).strip()

        imagem = request.form.get(
            "imagem",
            ""
        ).strip()

        categoria = request.form.get(
            "categoria",
            "Cidade"
        ).strip()

        botao_texto = request.form.get(
            "botao_texto",
            ""
        ).strip()

        botao_url = request.form.get(
            "botao_url",
            ""
        ).strip()

        ordem_texto = request.form.get(
            "ordem",
            "0"
        ).strip()

        ativo = request.form.get(
            "ativo",
            "1"
        )

        if not titulo:

            flash(
                "Digite um título para o box.",
                "erro"
            )

            return redirect(
                url_for("admin_cidade_novo")
            )

        try:

            ordem = int(ordem_texto)

        except ValueError:

            ordem = 0

        if ativo not in ["0", "1"]:

            ativo = "1"

        conexao = conectar_banco()

        cursor = conexao.cursor()

        cursor.execute("""
            INSERT INTO cidade_boxes
            (
                titulo,
                descricao,
                imagem,
                categoria,
                botao_texto,
                botao_url,
                ordem,
                ativo,
                criado_por
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            titulo,
            descricao,
            imagem,
            categoria,
            botao_texto,
            botao_url,
            ordem,
            int(ativo),
            session["usuario_id"]
        ))

        conexao.commit()

        conexao.close()

        registrar_log(
            "Criou box na cidade",
            titulo
        )

        flash(
            "Box criado com sucesso.",
            "sucesso"
        )

        return redirect(
            url_for("admin")
        )

    return render_template(
        "admin_cidade_novo.html"
    )


# ============================================================
# EDITAR BOX
# ============================================================

@app.route(
    "/admin/cidade/<int:box_id>/editar",
    methods=["GET", "POST"]
)
@cargo_obrigatorio("Programador")
def admin_cidade_editar(box_id):

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM cidade_boxes
        WHERE id = ?
    """, (
        box_id,
    ))

    box = cursor.fetchone()

    if not box:

        conexao.close()

        flash(
            "Box não encontrado.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    if request.method == "POST":

        titulo = request.form.get(
            "titulo",
            ""
        ).strip()

        descricao = request.form.get(
            "descricao",
            ""
        ).strip()

        imagem = request.form.get(
            "imagem",
            ""
        ).strip()

        categoria = request.form.get(
            "categoria",
            "Cidade"
        ).strip()

        botao_texto = request.form.get(
            "botao_texto",
            ""
        ).strip()

        botao_url = request.form.get(
            "botao_url",
            ""
        ).strip()

        ordem_texto = request.form.get(
            "ordem",
            "0"
        ).strip()

        ativo = request.form.get(
            "ativo",
            "1"
        )

        if not titulo:

            conexao.close()

            flash(
                "Digite um título para o box.",
                "erro"
            )

            return redirect(
                url_for(
                    "admin_cidade_editar",
                    box_id=box_id
                )
            )

        try:

            ordem = int(ordem_texto)

        except ValueError:

            ordem = 0

        if ativo not in ["0", "1"]:

            ativo = "1"

        cursor.execute("""
            UPDATE cidade_boxes
            SET
                titulo = ?,
                descricao = ?,
                imagem = ?,
                categoria = ?,
                botao_texto = ?,
                botao_url = ?,
                ordem = ?,
                ativo = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (
            titulo,
            descricao,
            imagem,
            categoria,
            botao_texto,
            botao_url,
            ordem,
            int(ativo),
            box_id
        ))

        conexao.commit()

        conexao.close()

        registrar_log(
            "Editou box da cidade",
            titulo
        )

        flash(
            "Box atualizado com sucesso.",
            "sucesso"
        )

        return redirect(
            url_for("admin")
        )

    conexao.close()

    return render_template(
        "admin_cidade_editar.html",
        box=box
    )


# ============================================================
# EXCLUIR BOX
# ============================================================

@app.route(
    "/admin/cidade/<int:box_id>/excluir",
    methods=["POST"]
)
@cargo_obrigatorio("Programador")
def admin_cidade_excluir(box_id):

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM cidade_boxes
        WHERE id = ?
    """, (
        box_id,
    ))

    box = cursor.fetchone()

    if not box:

        conexao.close()

        flash(
            "Box não encontrado.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    cursor.execute("""
        DELETE FROM cidade_boxes
        WHERE id = ?
    """, (
        box_id,
    ))

    conexao.commit()

    conexao.close()

    registrar_log(
        "Excluiu box da cidade",
        box["titulo"]
    )

    flash(
        f"O box '{box['titulo']}' foi excluído.",
        "sucesso"
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# ATIVAR BOX
# ============================================================

@app.route(
    "/admin/cidade/<int:box_id>/ativar",
    methods=["POST"]
)
@cargo_obrigatorio("Programador")
def admin_cidade_ativar(box_id):

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE cidade_boxes
        SET
            ativo = 1,
            atualizado_em = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        box_id,
    ))

    conexao.commit()

    conexao.close()

    registrar_log(
        "Ativou box da cidade",
        str(box_id)
    )

    flash(
        "Box ativado com sucesso.",
        "sucesso"
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# DESATIVAR BOX
# ============================================================

@app.route(
    "/admin/cidade/<int:box_id>/desativar",
    methods=["POST"]
)
@cargo_obrigatorio("Programador")
def admin_cidade_desativar(box_id):

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE cidade_boxes
        SET
            ativo = 0,
            atualizado_em = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (
        box_id,
    ))

    conexao.commit()

    conexao.close()

    registrar_log(
        "Desativou box da cidade",
        str(box_id)
    )

    flash(
        "Box desativado com sucesso.",
        "sucesso"
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# DUPLICAR BOX
# ============================================================

@app.route(
    "/admin/cidade/<int:box_id>/duplicar",
    methods=["POST"]
)
@cargo_obrigatorio("Programador")
def admin_cidade_duplicar(box_id):

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT *
        FROM cidade_boxes
        WHERE id = ?
    """, (
        box_id,
    ))

    box = cursor.fetchone()

    if not box:

        conexao.close()

        flash(
            "Box não encontrado.",
            "erro"
        )

        return redirect(
            url_for("admin")
        )

    novo_titulo = f"{box['titulo']} - Cópia"

    cursor.execute("""
        INSERT INTO cidade_boxes
        (
            titulo,
            descricao,
            imagem,
            categoria,
            botao_texto,
            botao_url,
            ordem,
            ativo,
            criado_por
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        novo_titulo,
        box["descricao"],
        box["imagem"],
        box["categoria"],
        box["botao_texto"],
        box["botao_url"],
        box["ordem"] + 1,
        0,
        session["usuario_id"]
    ))

    conexao.commit()

    conexao.close()

    registrar_log(
        "Duplicou box da cidade",
        box["titulo"]
    )

    flash(
        "Box duplicado. A cópia foi criada desativada.",
        "sucesso"
    )

    return redirect(
        url_for("admin")
    )


# ============================================================
# LOJA
# ============================================================

@app.route("/loja")
def loja():

    produtos = []

    for indice, produto in enumerate(PRODUTOS):

        produto_copia = produto.copy()

        produto_copia["id"] = indice

        produto_copia["whatsapp"] = gerar_link_whatsapp(
            produto["nome"],
            produto["preco"]
        )

        produtos.append(
            produto_copia
        )

    return render_template(
        "loja.html",
        produtos=produtos
    )


# ============================================================
# COMPRAR PRODUTO
# ============================================================

@app.route(
    "/comprar/<int:produto_id>"
)
def comprar(produto_id):

    if (
        produto_id < 0
        or produto_id >= len(PRODUTOS)
    ):

        flash(
            "Produto não encontrado.",
            "erro"
        )

        return redirect(
            url_for("loja")
        )

    produto = PRODUTOS[produto_id]

    whatsapp = gerar_link_whatsapp(
        produto["nome"],
        produto["preco"]
    )

    return render_template(
        "comprar.html",
        produto=produto,
        produto_id=produto_id,
        whatsapp_url=whatsapp
    )


# ============================================================
# CHAT
# ============================================================

@app.route(
    "/chat",
    methods=["GET", "POST"]
)
@login_obrigatorio
def chat():

    if request.method == "POST":

        mensagem = request.form.get(
            "mensagem",
            ""
        ).strip()

        if not mensagem:

            flash(
                "Digite uma mensagem.",
                "erro"
            )

            return redirect(
                url_for("chat")
            )

        if len(mensagem) > 500:

            flash(
                "A mensagem pode ter no máximo 500 caracteres.",
                "erro"
            )

            return redirect(
                url_for("chat")
            )

        conexao = conectar_banco()

        cursor = conexao.cursor()

        cursor.execute("""
            INSERT INTO mensagens
            (
                usuario_id,
                mensagem
            )
            VALUES (?, ?)
        """, (
            session["usuario_id"],
            mensagem
        ))

        conexao.commit()

        conexao.close()

        return redirect(
            url_for("chat")
        )

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            mensagens.id,
            mensagens.usuario_id,
            mensagens.mensagem,
            mensagens.criado_em,
            usuarios.usuario,
            usuarios.cargo
        FROM mensagens
        JOIN usuarios
        ON usuarios.id = mensagens.usuario_id
        WHERE usuarios.banido = 0
        AND usuarios.ativo = 1
        ORDER BY mensagens.id DESC
        LIMIT 100
    """)

    mensagens = cursor.fetchall()

    conexao.close()

    return render_template(
        "chat.html",
        mensagens=mensagens,
        usuario=usuario_logado()
    )


# ============================================================
# APAGAR MENSAGEM
# ============================================================

@app.route(
    "/chat/mensagem/<int:mensagem_id>/apagar",
    methods=["POST"]
)
@login_obrigatorio
def apagar_mensagem(mensagem_id):

    usuario_atual = usuario_logado()

    conexao = conectar_banco()

    cursor = conexao.cursor()

    cursor.execute("""
        SELECT
            mensagens.*,
            usuarios.usuario,
            usuarios.cargo
        FROM mensagens
        JOIN usuarios
        ON usuarios.id = mensagens.usuario_id
        WHERE mensagens.id = ?
    """, (
        mensagem_id,
    ))

    mensagem = cursor.fetchone()

    if not mensagem:

        conexao.close()

        flash(
            "Mensagem não encontrada.",
            "erro"
        )

        return redirect(
            url_for("chat")
        )

    eh_dono = (
        mensagem["usuario_id"]
        == usuario_atual["id"]
    )

    eh_admin_tecnico = (
        usuario_atual["cargo"]
        in [
            "Ceo",
            "Fundador",
            "Programador"
        ]
    )

    if not eh_dono and not eh_admin_tecnico:

        conexao.close()

        flash(
            "Você não possui permissão para apagar essa mensagem.",
            "erro"
        )

        return redirect(
            url_for("chat")
        )

    cursor.execute("""
        DELETE FROM mensagens
        WHERE id = ?
    """, (
        mensagem_id,
    ))

    conexao.commit()

    conexao.close()

    if not eh_dono:

        registrar_log(
            "Apagou mensagem do chat",
            mensagem["usuario"]
        )

    flash(
        "Mensagem apagada com sucesso.",
        "sucesso"
    )

    return redirect(
        url_for("chat")
    )


# ============================================================
# RESENHA ANTIGA
# ============================================================

@app.route("/resenha")
def resenha_antiga():

    return redirect(
        url_for("inicio")
    )


# ============================================================
# DISCORD
# ============================================================

@app.route("/discord")
def discord():

    return redirect(
        DISCORD_URL
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "Você saiu da sua conta.",
        "sucesso"
    )

    return redirect(
        url_for("inicio")
    )


# ============================================================
# GARANTE BANCO
# ============================================================

criar_banco()


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    print("")
    print("==========================================")
    print("             CIDADE ECLIPSE RPG")
    print("==========================================")
    print("")
    print("Servidor iniciado!")
    print("")
    print("Site:")
    print("http://127.0.0.1:5000")
    print("")
    print("Login:")
    print("http://127.0.0.1:5000/login")
    print("")
    print("Cadastro:")
    print("http://127.0.0.1:5000/cadastro")
    print("")
    print("Painel:")
    print("http://127.0.0.1:5000/painel")
    print("")
    print("Admin:")
    print("http://127.0.0.1:5000/admin")
    print("")
    print("Cidade:")
    print("http://127.0.0.1:5000/cidade")
    print("")
    print("Loja:")
    print("http://127.0.0.1:5000/loja")
    print("")
    print("Discord:")
    print(DISCORD_URL)
    print("")
    print("WhatsApp:")
    print(WHATSAPP_URL)
    print("")
    print("Para parar o servidor:")
    print("CTRL + C")
    print("==========================================")
    print("")

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )