import streamlit as st
import pandas as pd
import json
import os
from datetime import date, timedelta

# ============================================================
# CONFIGURAÇÕES E CONSTANTES (Equivalente aos #define e arrays)
# ============================================================
st.set_page_config(page_title="FinFlow - Gestão de Despesas", page_icon="💸", layout="wide")

ARQ_USUARIOS = "usuarios.json"
ARQ_SOLIC = "solicitacoes.json"

PERFIS = {1: "Funcionário", 2: "Gestor", 3: "Financeiro"}
DEPTOS = {0: "Financeiro", 1: "Administrativo", 2: "Comercial"}
CATEGORIAS = {0: "Combustível", 1: "Alimentação", 2: "Material", 3: "Outros"}
STATUS = {0: "PENDENTE", 1: "APROVADO", 2: "REJEITADO"}
ORCAMENTO_MENSAL = {0: 5000.0, 1: 3000.0, 2: 8000.0}

# ============================================================
# UTILITÁRIOS E VALIDAÇÕES
# ============================================================
def hash_senha(s: str) -> int:
    """Replica exatamente a função djb2 hash_senha do código em C."""
    h = 5381
    for c in s.encode("utf-8"):
        h = (((h << 5) + h) + c) & 0xFFFFFFFFFFFFFFFF
    return h

def validar_cnpj(c: str) -> bool:
    """Valida os 14 dígitos e os dígitos verificadores do CNPJ."""
    c = "".join(filter(str.isdigit, c))
    if len(c) != 14 or len(set(c)) == 1:
        return False
    
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    
    soma1 = sum(int(c[i]) * p1[i] for i in range(12))
    dv1 = 0 if (soma1 % 11 < 2) else (11 - soma1 % 11)
    
    soma2 = sum(int(c[i]) * p2[i] for i in range(12)) + dv1 * p2[12]
    dv2 = 0 if (soma2 % 11 < 2) else (11 - soma2 % 11)
    
    return dv1 == int(c[12]) and dv2 == int(c[13])

# ============================================================
# PERSISTÊNCIA DE DADOS (JSON)
# ============================================================
def carregar_dados():
    if not os.path.exists(ARQ_USUARIOS):
        usuarios_iniciais = [
            {"id": 1, "nome": "Christian Adriano", "email": "christian@finflow.com", "senha_hash": hash_senha("1234"), "perfil": 1, "depto": 2},
            {"id": 2, "nome": "Kayke Augusto", "email": "kayke@finflow.com", "senha_hash": hash_senha("1234"), "perfil": 2, "depto": 2},
            {"id": 3, "nome": "Lucas Balbino", "email": "lucas@finflow.com", "senha_hash": hash_senha("1234"), "perfil": 3, "depto": 0},
            {"id": 4, "nome": "Matheus Vinicius", "email": "matheus@finflow.com", "senha_hash": hash_senha("1234"), "perfil": 1, "depto": 1},
            {"id": 5, "nome": "Victor Akira", "email": "akira@finflow.com", "senha_hash": hash_senha("1234"), "perfil": 2, "depto": 1},
        ]
        salvar_usuarios(usuarios_iniciais)
    else:
        with open(ARQ_USUARIOS, "r", encoding="utf-8") as f:
            usuarios_iniciais = json.load(f)

    if not os.path.exists(ARQ_SOLIC):
        solicitacoes = []
        salvar_solicitacoes(solicitacoes)
    else:
        with open(ARQ_SOLIC, "r", encoding="utf-8") as f:
            solicitacoes = json.load(f)

    return usuarios_iniciais, solicitacoes

def salvar_usuarios(usuarios):
    with open(ARQ_USUARIOS, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, indent=4, ensure_ascii=False)

def salvar_solicitacoes(solicitacoes):
    with open(ARQ_SOLIC, "w", encoding="utf-8") as f:
        json.dump(solicitacoes, f, indent=4, ensure_ascii=False)

def get_nome_usuario(id_usuario, usuarios):
    for u in usuarios:
        if u["id"] == id_usuario:
            return u["nome"]
    return "(desconhecido)"

# ============================================================
# REGRAS DE NEGÓCIO
# ============================================================
def existe_duplicidade(solicitacoes, cnpj, data_str, valor):
    for s in solicitacoes:
        if (s["cnpj"] == cnpj and s["data"] == data_str and abs(s["valor"] - valor) < 0.005):
            return True
    return False

def gasto_aprovado_mes(solicitacoes, depto, mes, ano):
    total = 0.0
    for s in solicitacoes:
        dt = date.fromisoformat(s["data"])
        if s["status"] == 1 and s["depto"] == depto and dt.month == mes and dt.year == ano:
            total += s["valor"]
    return total

def pode_analisar(usuario_logado, solic):
    if solic["status"] != 0:  # Apenas PENDENTE
        return False
    if solic["id_usuario"] == usuario_logado["id"]:  # Não aprova a própria despesa
        return False
    return usuario_logado["perfil"] == 3 or solic["depto"] == usuario_logado["depto"]

def visivel_relatorio(usuario_logado, solic):
    if usuario_logado["perfil"] == 3:  # Financeiro vê tudo
        return True
    if usuario_logado["perfil"] == 2:  # Gestor vê seu departamento
        return solic["depto"] == usuario_logado["depto"]
    return solic["id_usuario"] == usuario_logado["id"]  # Funcionário vê apenas as suas

# ============================================================
# INICIALIZAÇÃO DO ESTADO DA SESSÃO
# ============================================================
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = None
if "tentativas_login" not in st.session_state:
    st.session_state.tentativas_login = 0

usuarios, solicitacoes = carregar_dados()

# ============================================================
# TELA DE LOGIN
# ============================================================
if st.session_state.usuario_logado is None:
    st.title("💸 FINFLOW - Gestão de Despesas Corporativas")
    st.subheader("Acesso ao Sistema")

    if st.session_state.tentativas_login >= 3:
        st.error("Acesso bloqueado após 3 tentativas inválidas. Recarregue a página para tentar novamente.")
        st.stop()

    with st.form("form_login"):
        email = st.text_input("E-mail")
        senha = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar")

        if submit:
            h_senha = hash_senha(senha)
            user_encontrado = next((u for u in usuarios if u["email"] == email and u["senha_hash"] == h_senha), None)
            
            if user_encontrado:
                st.session_state.usuario_logado = user_encontrado
                st.session_state.tentativas_login = 0
                st.rerun()
            else:
                st.session_state.tentativas_login += 1
                st.error(f"Credenciais inválidas ({st.session_state.tentativas_login}/3).")

    with st.expander("Usuários pré-cadastrados para teste (Senha padrão: 1234)"):
        st.table([{"Nome": u["nome"], "E-mail": u["email"], "Perfil": PERFIS[u["perfil"]], "Depto": DEPTOS[u["depto"]]} for u in usuarios])
    st.stop()

# ============================================================
# SISTEMA LOGADO (SIDEBAR E NAVEGAÇÃO)
# ============================================================
user = st.session_state.usuario_logado

with st.sidebar:
    st.title("💸 FINFLOW")
    st.markdown(f"**Usuário:** {user['nome']}")
    st.markdown(f"**Perfil:** {PERFIS[user['perfil']]}")
    st.markdown(f"**Depto:** {DEPTOS[user['depto']]}")
    st.divider()

    opcoes_menu = ["Registrar Despesa", "Minhas Solicitações", "Relatório de Despesas"]
    if user["perfil"] >= 2:  # Gestor ou Financeiro
        opcoes_menu.insert(2, "Analisar Pendentes")
    if user["perfil"] == 3:  # Apenas Financeiro
        opcoes_menu.extend(["Cadastrar Usuário", "Exportar CSV"])

    pagina = st.radio("Navegação", opcoes_menu)
    st.divider()
    if st.button("Sair", use_container_width=True):
        st.session_state.usuario_logado = None
        st.rerun()

# ============================================================
# PÁGINA 1: REGISTRAR DESPESA (RF02)
# ============================================================
if pagina == "Registrar Despesa":
    st.header("📝 Registrar Nova Despesa")
    st.info("💡 **OCR Simulado:** No sistema em produção, os dados do cupom fiscal são extraídos automaticamente via Amazon Textract.")

    with st.form("form_despesa", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            cnpj_input = st.text_input("CNPJ do Fornecedor (14 dígitos)", max_chars=18, placeholder="Ex: 11222333000181")
            data_desp = st.date_input("Data do Comprovante", value=date.today(), min_value=date(2000, 1, 1), max_value=date(2100, 12, 31))
        with col2:
            valor = st.number_input("Valor Total (R$)", min_value=0.01, max_value=100000.00, step=10.0, format="%.2f")
            categoria = st.selectbox("Categoria", options=list(CATEGORIAS.keys()), format_func=lambda x: CATEGORIAS[x])

        submitted = st.form_submit_button("Enviar para Aprovação")

        if submitted:
            cnpj_limpo = "".join(filter(str.isdigit, cnpj_input))
            data_str = data_desp.isoformat()

            if not validar_cnpj(cnpj_limpo):
                st.error("CNPJ inválido! Verifique os dígitos informados.")
            elif existe_duplicidade(solicitacoes, cnpj_limpo, data_str, valor):
                st.error("🚨 ALERTA ANTIFRAUDE: Comprovante duplicado detectado (mesmo CNPJ, data e valor). Solicitação bloqueada.")
            else:
                novo_id = max([s["id"] for s in solicitacoes], default=0) + 1
                nova_solic = {
                    "id": novo_id,
                    "id_usuario": user["id"],
                    "depto": user["depto"],
                    "categoria": categoria,
                    "cnpj": cnpj_limpo,
                    "data": data_str,
                    "valor": float(valor),
                    "status": 0,  # PENDENTE
                    "justificativa": ""
                }
                solicitacoes.append(nova_solic)
                salvar_solicitacoes(solicitacoes)
                st.success(f"Solicitação #{novo_id} registrada com sucesso e enviada para aprovação!")

# ============================================================
# PÁGINA 2: MINHAS SOLICITAÇÕES
# ============================================================
elif pagina == "Minhas Solicitações":
    st.header("📋 Minhas Solicitações")
    minhas = [s for s in solicitacoes if s["id_usuario"] == user["id"]]

    if not minhas:
        st.info("Nenhuma solicitação encontrada.")
    else:
        dados_tabela = []
        for s in minhas:
            dt_br = date.fromisoformat(s["data"]).strftime("%d/%m/%Y")
            dados_tabela.append({
                "ID": f"#{s['id']}",
                "Data": dt_br,
                "CNPJ": s["cnpj"],
                "Categoria": CATEGORIAS[s["categoria"]],
                "Valor (R$)": f"{s['valor']:.2f}",
                "Status": STATUS[s["status"]],
                "Motivo Rejeição": s["justificativa"] if s["status"] == 2 else "-"
            })
        st.dataframe(pd.DataFrame(dados_tabela), use_container_width=True, hide_index=True)

# ============================================================
# PÁGINA 3: ANALISAR PENDENTES (RF03)
# ============================================================
elif pagina == "Analisar Pendentes":
    st.header("⚖️ Analisar Solicitações Pendentes")
    pendentes = [s for s in solicitacoes if pode_analisar(user, s)]

    if not pendentes:
        st.success("Nenhuma solicitação pendente para sua análise no momento.")
    else:
        for s in pendentes:
            dt_obj = date.fromisoformat(s["data"])
            dt_br = dt_obj.strftime("%d/%m/%Y")
            nome_solicitante = get_nome_usuario(s["id_usuario"], usuarios)

            with st.expander(f"Solicitação #{s['id']} | {nome_solicitante} ({DEPTOS[s['depto']]}) - R$ {s['valor']:.2f}", expanded=True):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Data:** {dt_br}")
                c2.write(f"**Categoria:** {CATEGORIAS[s['categoria']]}")
                c3.write(f"**CNPJ:** {s['cnpj']}")

                # Verificação de orçamento mensal
                gasto_atual = gasto_aprovado_mes(solicitacoes, s["depto"], dt_obj.month, dt_obj.year)
                projetado = gasto_atual + s["valor"]
                orcamento = ORCAMENTO_MENSAL[s["depto"]]

                if projetado > orcamento:
                    st.warning(f"⚠️ **ATENÇÃO:** Aprovar esta despesa estourará o orçamento mensal de **{DEPTOS[s['depto']]}** (Projetado: R$ {projetado:.2f} / Limite: R$ {orcamento:.2f}).")

                col_ap, col_rej = st.columns([1, 2])
                with col_ap:
                    if st.button("✅ Aprovar", key=f"apr_{s['id']}", use_container_width=True):
                        s["status"] = 1
                        salvar_solicitacoes(solicitacoes)
                        st.toast(f"Solicitação #{s['id']} APROVADA!")
                        st.rerun()

                with col_rej:
                    with st.form(key=f"form_rej_{s['id']}"):
                        justificativa = st.text_input("Justificativa para rejeição", key=f"just_{s['id']}")
                        if st.form_submit_button("❌ Rejeitar"):
                            if not justificativa.strip():
                                st.error("Informe uma justificativa obrigatória para rejeitar.")
                            else:
                                s["status"] = 2
                                s["justificativa"] = justificativa.strip()
                                salvar_solicitacoes(solicitacoes)
                                st.toast(f"Solicitação #{s['id']} REJEITADA.")
                                st.rerun()

# ============================================================
# PÁGINA 4: RELATÓRIO DE DESPESAS (RF04)
# ============================================================
elif pagina == "Relatório de Despesas":
    st.header("📊 Relatório de Despesas Aprovadas")

    col1, col2 = st.columns(2)
    with col1:
        tipo_rel = st.selectbox("Período do Relatório", ["Diário", "Semanal (7 dias)", "Mensal"])
    with col2:
        data_ref = st.date_input("Data de Referência (Data Final ou Mês/Ano)", value=date.today())

    if tipo_rel == "Diário":
        ini = fim = data_ref
    elif tipo_rel == "Semanal (7 dias)":
        fim = data_ref
        ini = fim - timedelta(days=6)
    else:  # Mensal
        ini = data_ref.replace(day=1)
        prox_mes = (ini.replace(day=28) + timedelta(days=4)).replace(day=1)
        fim = prox_mes - timedelta(days=1)

    st.caption(f"Exibindo despesas aprovadas entre **{ini.strftime('%d/%m/%Y')}** e **{fim.strftime('%d/%m/%Y')}**")

    # Construção da matriz Departamento x Categoria
    matriz = {depto: {cat: 0.0 for cat in CATEGORIAS.values()} for depto in DEPTOS.values()}

    for s in solicitacoes:
        dt_s = date.fromisoformat(s["data"])
        if s["status"] == 1 and ini <= dt_s <= fim and visivel_relatorio(user, s):
            matriz[DEPTOS[s["depto"]]][CATEGORIAS[s["categoria"]]] += s["valor"]

    df_matriz = pd.DataFrame.from_dict(matriz, orient="index")
    df_matriz["TOTAL"] = df_matriz.sum(axis=1)
    df_matriz.loc["TOTAL GERAL"] = df_matriz.sum()

    st.dataframe(df_matriz.style.format("R$ {:.2f}"), use_container_width=True)

    # Consumo de orçamento no relatório mensal
    if tipo_rel == "Mensal":
        st.subheader("Consumo do Orçamento Mensal")
        cols_orc = st.columns(len(DEPTOS))
        for idx, (cod_depto, nome_depto) in enumerate(DEPTOS.items()):
            gasto = df_matriz.loc[nome_depto, "TOTAL"]
            limite = ORCAMENTO_MENSAL[cod_depto]
            pct = (gasto / limite) * 100
            with cols_orc[idx]:
                st.metric(label=nome_depto, value=f"R$ {gasto:.2f}", delta=f"{pct:.1f}% de R$ {limite:.2f}", delta_color="inverse")
                st.progress(min(gasto / limite, 1.0))

# ============================================================
# PÁGINA 5: CADASTRAR USUÁRIO (Apenas Financeiro)
# ============================================================
elif pagina == "Cadastrar Usuário":
    st.header("👤 Cadastrar Novo Usuário")

    with st.form("form_usuario", clear_on_submit=True):
        nome = st.text_input("Nome Completo", max_chars=39)
        email = st.text_input("E-mail Corporativo", max_chars=39)
        senha = st.text_input("Senha (mínimo 4 caracteres)", type="password")
        perfil = st.selectbox("Perfil de Acesso", options=list(PERFIS.keys()), format_func=lambda x: PERFIS[x])
        depto = st.selectbox("Departamento", options=list(DEPTOS.keys()), format_func=lambda x: DEPTOS[x])

        if st.form_submit_button("Cadastrar Usuário"):
            if not nome.strip() or "@" not in email:
                st.error("Preencha um nome e um e-mail válidos.")
            elif len(senha) < 4:
                st.error("A senha deve ter no mínimo 4 caracteres.")
            elif any(u["email"] == email.strip() for u in usuarios):
                st.error("Este e-mail já está cadastrado.")
            else:
                novo_id = max([u["id"] for u in usuarios], default=0) + 1
                usuarios.append({
                    "id": novo_id,
                    "nome": nome.strip(),
                    "email": email.strip(),
                    "senha_hash": hash_senha(senha),
                    "perfil": perfil,
                    "depto": depto
                })
                salvar_usuarios(usuarios)
                st.success(f"Usuário **{nome}** cadastrado com sucesso (ID #{novo_id})!")

# ============================================================
# PÁGINA 6: EXPORTAR CSV (Apenas Financeiro)
# ============================================================
elif pagina == "Exportar CSV":
    st.header("📥 Exportar Dados para CSV")

    if not solicitacoes:
        st.warning("Não há solicitações registradas para exportar.")
    else:
        linhas = []
        for s in solicitacoes:
            dt_br = date.fromisoformat(s["data"]).strftime("%d/%m/%Y")
            linhas.append({
                "id": s["id"],
                "usuario": get_nome_usuario(s["id_usuario"], usuarios),
                "departamento": DEPTOS[s["depto"]],
                "categoria": CATEGORIAS[s["categoria"]],
                "cnpj": s["cnpj"],
                "data": dt_br,
                "valor": f"{s['valor']:.2f}",
                "status": STATUS[s["status"]]
            })
        df_export = pd.DataFrame(linhas)
        st.dataframe(df_export, use_container_width=True, hide_index=True)

        csv_bytes = df_export.to_csv(sep=";", index=False).encode("utf-8-sig")
        st.download_button(
            label=f"⬇️ Baixar despesas.csv ({len(solicitacoes)} registros)",
            data=csv_bytes,
            file_name="despesas.csv",
            mime="text/csv"
        )