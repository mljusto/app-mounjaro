import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Controle Mounjaro", page_icon="💧", layout="centered")

# --- ESTILOS CUSTOMIZADOS (CSS) ---
st.markdown("""
    <style>
    .stMetric { background-color: rgba(128, 128, 128, 0.15); padding: 10px; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- CONEXÃO COM O GOOGLE SHEETS ---
@st.cache_resource
def conectar_planilha():
    credenciais = {
        "type": st.secrets["gcp_service_account"]["type"],
        "project_id": st.secrets["gcp_service_account"]["project_id"],
        "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
        "private_key": st.secrets["gcp_service_account"]["private_key"],
        "client_email": st.secrets["gcp_service_account"]["client_email"],
        "client_id": st.secrets["gcp_service_account"]["client_id"],
        "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
        "token_uri": st.secrets["gcp_service_account"]["token_uri"],
        "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
        "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"]
    }
    
    escopos = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(credenciais, scopes=escopos)
    cliente = gspread.authorize(creds)
    return cliente.open("Sistema_Mounjaro_DB")

# --- CARREGAR DADOS ---
def carregar_dados():
    try:
        planilha = conectar_planilha()
        aba_frascos = planilha.worksheet("Frascos")
        aba_aplicacoes = planilha.worksheet("Aplicacoes")
        aba_participantes = planilha.worksheet("Participantes")
        
        df_frascos = pd.DataFrame(aba_frascos.get_all_records())
        df_aplicacoes = pd.DataFrame(aba_aplicacoes.get_all_records())
        df_participantes = pd.DataFrame(aba_participantes.get_all_records())
        
        if not df_aplicacoes.empty:
            df_aplicacoes['Data'] = pd.to_datetime(df_aplicacoes['Data'], format="%d/%m/%Y")
            df_aplicacoes['Dose'] = df_aplicacoes['Dose'].astype(str).str.replace(',', '.').astype(float)
            df_aplicacoes['Peso'] = df_aplicacoes['Peso'].astype(str).str.replace(',', '.').astype(float)
        
        return df_frascos, df_aplicacoes, df_participantes
    except Exception as e:
        st.error(f"Erro ao carregar dados. Erro: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_frascos, df_aplicacoes, df_participantes = carregar_dados()

# --- CABEÇALHO DO APP ---
st.markdown("<h1 style='text-align: center; color: #1f77b4;'>💧 Mounjaro App</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666;'>Controle de Doses e Evolução</p>", unsafe_allow_html=True)
st.divider()

# --- ABAS DO APLICATIVO ---
tab_dashboard, tab_registro, tab_participantes = st.tabs(["📊 Resultados", "📝 Nova Dose", "⚙️ Ajustes"])

# ==========================================
# ABA 1: PAINEL DE RESULTADOS
# ==========================================
with tab_dashboard:
    if df_frascos.empty:
        st.info("👋 Bem-vindo! Vá na aba 'Ajustes' para começar.")
    else:
        df_frascos['Custo_por_MG'] = df_frascos['Valor Pago'] / df_frascos['MG Total']
        frascos_ativos = df_frascos[df_frascos['Status'] == 'Ativo']
        frascos_esgotados = df_frascos[df_frascos['Status'] == 'Esgotado']
        
        if not frascos_ativos.empty:
            frasco_atual = frascos_ativos.iloc[-1]
            mg_consumido = df_aplicacoes[df_aplicacoes['ID Frasco'] == frasco_atual['ID Frasco']]['Dose'].sum() if not df_aplicacoes.empty else 0
            mg_restante = frasco_atual['MG Total'] - mg_consumido
            
            st.subheader("📦 Status do Frasco")
            c1, c2, c3 = st.columns(3)
            c1.metric("Frasco Ativo", frasco_atual['ID Frasco'])
            c2.metric("Disponível", f"{mg_restante} mg")
            c3.metric("Custo / MG", f"R$ {frasco_atual['Custo_por_MG']:.2f}")
            
            if mg_restante <= 10:
                st.error("⚠️ Atenção: O frasco está no fim!")
        else:
            st.warning("Nenhum frasco ativo no momento. Cadastre um novo na aba Ajustes.")
            
        # --- HISTÓRICO DE FRASCOS ESGOTADOS ---
        if not frascos_esgotados.empty:
            with st.expander("📦 Ver histórico de frascos esgotados"):
                df_show = frascos_esgotados[['ID Frasco', 'MG Total', 'Valor Pago', 'Custo_por_MG']].copy()
                df_show['Valor Pago'] = df_show['Valor Pago'].apply(lambda x: f"R$ {x:.2f}")
                df_show['Custo_por_MG'] = df_show['Custo_por_MG'].apply(lambda x: f"R$ {x:.2f}")
                st.dataframe(df_show, use_container_width=True, hide_index=True)
        
        st.divider()

        if not df_aplicacoes.empty and not df_participantes.empty:
            df_completo = pd.merge(df_aplicacoes, df_participantes, on='Nome', how='left')
            df_completo = pd.merge(df_completo, df_frascos[['ID Frasco', 'Custo_por_MG']], on='ID Frasco', how='left')
            df_completo['Custo_Dose'] = df_completo['Dose'] * df_completo['Custo_por_MG']
            
            st.subheader("📉 Evolução de Peso")
            
            fig = px.line(df_completo.sort_values(by=['Nome', 'Data']), 
                          x='Data', y='Peso', color='Nome', markers=True,
                          template="plotly_white")
            
            fig.update_xaxes(tickformat="%d/%m/%Y", title_text="")
            fig.update_yaxes(title_text="Peso (kg)")
            fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                              margin=dict(l=0, r=0, t=20, b=0))
            
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("🏆 Desempenho")
            
            resumo = []
            for p in df_participantes['Nome'].unique():
                dados_p = df_completo[df_completo['Nome'] == p].sort_values(by='Data')
                
                if not dados_p.empty:
                    peso_inicial = dados_p.iloc[0]['Peso']
                    peso_atual = dados_p.iloc[-1]['Peso']
                    perda = peso_inicial - peso_atual
                    meta = dados_p.iloc[-1]['Meta de Peso']
                    gasto = dados_p['Custo_Dose'].sum()
                    
                    resumo.append({
                        "Nome": p,
                        "Peso Atual": f"{peso_atual} kg",
                        "Perdido": f"⬇️ {perda:.1f} kg",
                        "Falta p/ Meta": f"🎯 {round(peso_atual - meta, 1)} kg",
                        "Investimento": f"R$ {gasto:.2f}"
                    })
            
            df_resumo = pd.DataFrame(resumo)
            st.dataframe(df_resumo, use_container_width=True, hide_index=True)

# ==========================================
# ABA 2: REGISTRAR DOSE
# ==========================================
with tab_registro:
    st.header("💉 Nova Aplicação")
    
    lista_frascos_ativos = df_frascos[df_frascos['Status'] == 'Ativo']['ID Frasco'].tolist() if not df_frascos.empty else []
    lista_participantes = df_participantes['Nome'].tolist() if not df_participantes.empty else []
    
    with st.form("form_nova_dose"):
        data = st.date_input("Data da Aplicação", format="DD/MM/YYYY")
        nome = st.selectbox("Participante", lista_participantes)
        frasco_selecionado = st.selectbox("Frasco Utilizado", lista_frascos_ativos)
        
        c1, c2 = st.columns(2)
        with c1:
            dose = st.number_input("Dose (mg)", min_value=2.5, step=2.5)
        with c2:
            peso = st.number_input("Peso Atual (kg)", min_value=40.0, step=0.1)
            
        senha_dose = st.text_input("Senha de Admin", type="password", key="senha_dose")
        submit = st.form_submit_button("Salvar Registro", use_container_width=True)
        
        if submit:
            if senha_dose == st.secrets["senha_admin"]:
                if frasco_selecionado:
                    data_str = data.strftime("%d/%m/%Y")
                    aba_aplicacoes = conectar_planilha().worksheet("Aplicacoes")
                    aba_aplicacoes.append_row([data_str, nome, float(dose), float(peso), frasco_selecionado])
                    st.success(f"✅ Salvo! {nome} tomou {dose}mg. Atualize a página.")
                else:
                    st.error("❌ Não há frascos ativos para registrar a dose.")
            else:
                st.error("❌ Senha incorreta.")

# ==========================================
# ABA 3: CONFIGURAÇÕES E ADMINISTRAÇÃO
# ==========================================
with tab_participantes:
    st.header("⚙️ Ajustes do Sistema")
    
    # --- GESTÃO DE FRASCOS ---
    st.subheader("📦 Gestão de Frascos")
    
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        with st.form("form_novo_frasco"):
            st.markdown("**1. Cadastrar Lote Novo**")
            novo_id = st.text_input("Nome do Lote (Ex: Lote_02)")
            novo_mg = st.number_input("MG Total", min_value=10.0, step=10.0, value=90.0)
            novo_valor = st.number_input("Valor Pago (R$)", min_value=0.0, step=10.0, value=2750.0)
            senha_add_f = st.text_input("Senha", type="password", key="s_add_f")
            submit_add_f = st.form_submit_button("Cadastrar Frasco", use_container_width=True)
            
            if submit_add_f:
                if senha_add_f == st.secrets["senha_admin"]:
                    if novo_id:
                        aba_frascos = conectar_planilha().worksheet("Frascos")
                        aba_frascos.append_row([novo_id, float(novo_mg), float(novo_valor), "Ativo"])
                        st.success(f"✅ {novo_id} cadastrado como Ativo! Atualize a página.")
                    else:
                        st.error("Preencha o nome do lote.")
                else:
                    st.error("Senha incorreta.")

    with col_f2:
        with st.form("form_inativar_frasco"):
            st.markdown("**2. Esgotar Lote Atual**")
            lista_ativos = df_frascos[df_frascos['Status'] == 'Ativo']['ID Frasco'].tolist() if not df_frascos.empty else []
            frasco_inativar = st.selectbox("Selecione o Frasco", lista_ativos)
            senha_ina_f = st.text_input("Senha", type="password", key="s_ina_f")
            submit_ina_f = st.form_submit_button("Marcar como Esgotado", use_container_width=True)
            
            if submit_ina_f:
                if senha_ina_f == st.secrets["senha_admin"]:
                    if frasco_inativar:
                        try:
                            aba_frascos = conectar_planilha().worksheet("Frascos")
                            celula = aba_frascos.find(frasco_inativar)
                            aba_frascos.update_cell(celula.row, 4, "Esgotado")
                            st.success(f"✅ {frasco_inativar} esgotado! Atualize a página.")
                        except Exception as e:
                            st.error("Erro ao tentar inativar. Verifique a planilha.")
                    else:
                        st.error("Nenhum frasco selecionado.")
                else:
                    st.error("Senha incorreta.")

    st.divider()

    # --- CADASTRO DE PARTICIPANTES ---
    st.subheader("👥 Gestão de Participantes")
    with st.form("form_novo_participante"):
        nome_novo = st.text_input("Nome do Participante")
        meta_peso_novo = st.number_input("Meta de Peso (kg)", min_value=30.0, step=0.1)
        senha_cad = st.text_input("Senha de Admin", type="password", key="s_cad_p")
        submit_cad = st.form_submit_button("Cadastrar Participante", use_container_width=True)
        
        if submit_cad:
            if senha_cad == st.secrets["senha_admin"]:
                if nome_novo:
                    aba_participantes = conectar_planilha().worksheet("Participantes")
                    nomes_existentes = pd.DataFrame(aba_participantes.get_all_records())['Nome'].tolist() if not pd.DataFrame(aba_participantes.get_all_records()).empty else []
                    
                    if nome_novo not in nomes_existentes:
                        aba_participantes.append_row([nome_novo, float(meta_peso_novo)])
                        st.success(f"✅ '{nome_novo}' cadastrado! Atualize a página.")
                    else:
                        st.error("❌ Participante já existe.")
                else:
                    st.error("❌ Preencha o nome.")
            else:
                st.error("❌ Senha incorreta.")

    if not df_participantes.empty:
        with st.expander("Ver lista de participantes cadastrados"):
            st.dataframe(df_participantes, use_container_width=True, hide_index=True)
            
    st.divider()
    
    st.markdown("<small>Acesso direto ao Banco de Dados (Google Sheets)</small>", unsafe_allow_html=True)
    st.link_button("📊 Abrir Planilha Base", "https://docs.google.com/spreadsheets/d/1OVKS6W9BKXlyQtCrLblPid-87WyBw3lRQPsGWG5-Ka8/edit?usp=sharing", use_container_width=True)
