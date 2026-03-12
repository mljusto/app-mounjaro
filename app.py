import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Controle Mounjaro", page_icon="💉", layout="wide")

# --- CONEXÃO COM O GOOGLE SHEETS ---
@st.cache_resource
def conectar_planilha():
    # Pega as credenciais guardadas em segurança no Streamlit
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
    
    # ATENÇÃO: Substitua pelo nome exato da sua planilha
    planilha = cliente.open("Sistema_Mounjaro_DB")
    return planilha

planilha = conectar_planilha()
aba_frascos = planilha.worksheet("Frascos")
aba_aplicacoes = planilha.worksheet("Aplicacoes")

# --- CARREGAR DADOS ---
def carregar_dados():
    df_frascos = pd.DataFrame(aba_frascos.get_all_records())
    df_aplicacoes = pd.DataFrame(aba_aplicacoes.get_all_records())
    return df_frascos, df_aplicacoes

df_frascos, df_aplicacoes = carregar_dados()

# --- TÍTULO ---
st.title("💉 Sistema de Controle - Mounjaro")

# --- ABAS DO APLICATIVO ---
tab_dashboard, tab_registro = st.tabs(["📊 Painel de Controle", "📝 Registrar Aplicação"])

# ==========================================
# ABA 1: PAINEL DE CONTROLE (Visualização)
# ==========================================
with tab_dashboard:
    st.header("Resumo do Tratamento")
    
    if df_frascos.empty:
        st.warning("Nenhum frasco cadastrado ainda na planilha.")
    else:
        # Calcular custo por mg de cada frasco
        df_frascos['Custo_por_MG'] = df_frascos['Valor Pago'] / df_frascos['MG Total']
        
        # FRASCO ATIVO
        frascos_ativos = df_frascos[df_frascos['Status'] == 'Ativo']
        if not frascos_ativos.empty:
            frasco_atual = frascos_ativos.iloc[-1]
            mg_consumido_atual = df_aplicacoes[df_aplicacoes['ID Frasco'] == frasco_atual['ID Frasco']]['Dose'].sum() if not df_aplicacoes.empty else 0
            mg_restante = frasco_atual['MG Total'] - mg_consumido_atual
            
            # Cards de resumo
            col1, col2, col3 = st.columns(3)
            col1.metric("Frasco Ativo", frasco_atual['ID Frasco'])
            col2.metric("MG Restantes no Frasco", f"{mg_restante} mg")
            col3.metric("Custo por MG (Atual)", f"R$ {frasco_atual['Custo_por_MG']:.2f}")
            
            if mg_restante <= 10:
                st.error("⚠️ Atenção: O frasco está no fim! Considere comprar o próximo lote.")
                
        st.divider()

        # DADOS DOS PARTICIPANTES
        if not df_aplicacoes.empty:
            # Juntar aplicações com frascos para calcular custos
            df_completo = pd.merge(df_aplicacoes, df_frascos[['ID Frasco', 'Custo_por_MG']], on='ID Frasco', how='left')
            df_completo['Custo_Dose'] = df_completo['Dose'] * df_completo['Custo_por_MG']
            
            st.subheader("👥 Desempenho por Participante")
            
            resumo = []
            participantes = df_completo['Nome'].unique()
            
            for p in participantes:
                dados_p = df_completo[df_completo['Nome'] == p].sort_values(by='Data')
                peso_inicial = dados_p.iloc[0]['Peso']
                peso_atual = dados_p.iloc[-1]['Peso']
                perda = peso_inicial - peso_atual
                total_gasto = dados_p['Custo_Dose'].sum()
                mg_total = dados_p['Dose'].sum()
                
                resumo.append({
                    "Participante": p,
                    "Peso Inicial (kg)": peso_inicial,
                    "Peso Atual (kg)": peso_atual,
                    "Perda Total (kg)": perda,
                    "Total Consumido (mg)": mg_total,
                    "Gasto Acumulado (R$)": round(total_gasto, 2)
                })
                
            df_resumo = pd.DataFrame(resumo)
            st.dataframe(df_resumo, use_container_width=True)
        else:
            st.info("Nenhuma aplicação registrada ainda.")


# ==========================================
# ABA 2: REGISTRAR APLICAÇÃO (Admin)
# ==========================================
with tab_registro:
    st.header("Registrar Nova Dose")
    
    # Pegar lista de frascos ativos
    lista_frascos = df_frascos[df_frascos['Status'] == 'Ativo']['ID Frasco'].tolist() if not df_frascos.empty else []
    
    with st.form("form_nova_dose"):
        col1, col2 = st.columns(2)
        with col1:
            data = st.date_input("Data da Aplicação")
            nome = st.selectbox("Participante", ["Murilo", "Oscar", "Carol", "Marcilei"])
            frasco_selecionado = st.selectbox("Lote/Frasco Utilizado", lista_frascos)
        with col2:
            dose = st.number_input("Dose Aplicada (mg)", min_value=2.5, step=2.5)
            peso = st.number_input("Peso Atual do Participante (kg)", min_value=40.0, step=0.1)
            senha = st.text_input("Senha de Admin (para salvar)", type="password")
            
        submit = st.form_submit_button("Salvar Registro")
        
        if submit:
            if senha == st.secrets["senha_admin"]: # Proteção simples
                # Converter data para texto
                data_str = data.strftime("%d/%m/%Y")
                
                # Adicionar linha na planilha
                nova_linha = [data_str, nome, float(dose), float(peso), frasco_selecionado]
                aba_aplicacoes.append_row(nova_linha)
                
                st.success(f"✅ Aplicação de {nome} registrada com sucesso! Atualize a página para ver no Painel.")
            else:
                st.error("❌ Senha incorreta. Apenas o administrador pode salvar.")
