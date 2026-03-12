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
    .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; }
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
    
    lista_frascos = df_frascos[df_frascos['Status'] == 'Ativo']['ID Frasco'].tolist() if not df_frascos.empty else []
    lista_participantes = df_participantes['Nome'].tolist() if not df_participantes.empty else []
    
    with st.form("form_nova_dose"):
        data = st.date_input("Data da Aplicação", format="DD/MM/YYYY")
        nome = st.selectbox("Participante", lista_participantes)
        frasco_selecionado = st.selectbox("Frasco Utilizado", lista_frascos)
        
        c1, c2 = st.columns(2)
        with c1:
            dose = st.number_input("Dose (mg)", min_value=2.5, step=2.5)
        with c2:
            peso = st.number_input("Peso Atual (kg)", min_value=40.0, step=0.1)
            
        senha = st.text_input("Senha de Admin", type="password")
        submit = st.form_submit_button("Salvar Registro", use_container_width=True)
        
        if submit:
            if senha == st.secrets["senha_admin"]:
                data_str = data.strftime("%d/%m/%Y")
                aba_aplicacoes = conectar_planilha().worksheet("Aplicacoes")
                aba_aplicacoes.append_row([data_str, nome, float(dose), float(peso), frasco_selecionado])
                st.success(f"✅ Salvo! {nome} tomou {dose}mg.")
            else:
                st.error("❌ Senha incorreta.")

# ==========================================
# ABA 3: CONFIGURAÇÕES
# ==========================================
with tab_participantes:
    st.header("⚙️ Participantes")
    
    with st.form("form_novo_participante"):
        nome_novo = st.text_input("Nome do Participante")
        meta_peso_novo = st.number_input("Meta de Peso (kg)", min_value=30.0, step=0.1)
        senha_cad = st.text_input("Senha de Admin", type="password")
        submit_cad = st.form_submit_button("Cadastrar", use_container_width=True)
        
        if submit_cad:
            if senha_cad == st.secrets["senha_admin"]:
                if nome_novo:
                    aba_participantes = conectar_planilha().worksheet("Participantes")
                    nomes_existentes = pd.DataFrame(aba_participantes.get_all_records())['Nome'].tolist() if not pd.DataFrame(aba_participantes.get_all_records()).empty else []
                    
                    if nome_novo not in nomes_existentes:
                        aba_participantes.append_row([nome_novo, float(meta_peso_novo)])
                        st.success(f"✅ '{nome_novo}' cadastrado!")
                    else:
                        st.error("❌ Participante já existe.")
                else:
                    st.error("❌ Preencha o nome.")
            else:
                st.error("❌ Senha incorreta.")

    st.divider()
    st.subheader("Cadastrados")
    if not df_participantes.empty:
        st.dataframe(df_participantes, use_container_width=True, hide_index=True)
