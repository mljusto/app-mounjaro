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
            c3.metric("Custo / MG", f"R$ {fr
