import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px  # Nova biblioteca para o gráfico

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="💉 Controle Mounjaro", page_icon="💉", layout="wide")

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

# --- CARREGAR DADOS ---
def carregar_dados():
    try:
        planilha = conectar_planilha()
        aba_frascos = planilha.worksheet("Frascos")
        aba_aplicacoes = planilha.worksheet("Aplicacoes")
        aba_participantes = planilha.worksheet("Participantes") # Nova aba
        
        df_frascos = pd.DataFrame(aba_frascos.get_all_records())
        df_aplicacoes = pd.DataFrame(aba_aplicacoes.get_all_records())
        df_participantes = pd.DataFrame(aba_participantes.get_all_records()) # Novos dados
        
        # Formatar a coluna Data do df_aplicacoes paradatetime
        if not df_aplicacoes.empty:
            df_aplicacoes['Data'] = pd.to_datetime(df_aplicacoes['Data'], format="%d/%m/%Y")
        
        return df_frascos, df_aplicacoes, df_participantes
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha. Verifique as abas e os cabeçalhos. Erro: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# Carregar os dados inicialmentes
df_frascos, df_aplicacoes, df_participantes = carregar_dados()

# --- TÍTULO ---
st.title("💉 Sistema de Controle - Mounjaro")

# --- ABAS DO APLICATIVO ---
tab_dashboard, tab_participantes, tab_registro = st.tabs(["📊 Painel de Resultados", "⚙️ Configurações", "📝 Registrar Dose"])

# ==========================================
# ABA 1: PAINEL DE RESULTADOS (Dashboard)
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
            
            # Cards de resumo otimizados para mobile
            with st.container():
                c1, c2, c3 = st.columns([2, 1.5, 1])
                c1.metric("📦 Frasco Ativo", frasco_atual['ID Frasco'])
                c2.metric("💧 MG Restantes", f"{mg_restante} mg")
                c3.metric("💰 Custo MG", f"R$ {frasco_atual['Custo_por_MG']:.2f}")
            
            if mg_restante <= 10:
                st.error("⚠️ Atenção: O frasco está no fim! Considere comprar o próximo lote.")
                
        st.divider()

        # DADOS DOS PARTICIPANTES E GRÁFICO
        if not df_aplicacoes.empty and not df_participantes.empty:
            # Juntar aplicações com participantes para ter a meta
            df_completo = pd.merge(df_aplicacoes, df_participantes, on='Nome', how='left')
            
            # Juntar com frascos para calcular custos
            df_completo = pd.merge(df_completo, df_frascos[['ID Frasco', 'Custo_por_MG']], on='ID Frasco', how='left')
            df_completo['Custo_Dose'] = df_completo['Dose'] * df_completo['Custo_por_MG']
            
            # --- SEÇÃO 1: GRÁFICO DE EVOLUÇÃO ---
            st.subheader("📈 Evolução de Peso")
            
            # Criar o gráfico interativo com Plotly Express
            fig = px.line(df_completo.sort_values(by=['Nome', 'Data']), 
                          x='Data', 
                          y='Peso', 
                          color='Nome',
                          labels={"Peso": "Peso Atual (kg)", "Data": "Data da Aplicação"},
                          title="Perda de Peso ao Longo do Tempo")
            
            # Ajustar o layout para mobile (legendas embaixo, margens menores)
            fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                              margin=dict(l=10, r=10, t=40, b=10))
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.divider()

            # --- SEÇÃO 2: TABELA RESUMO ---
            st.subheader("👥 Desempenho por Participante")
            
            resumo = []
            
            for p in df_participantes['Nome'].unique():
                dados_p = df_completo[df_completo['Nome'] == p].sort_values(by='Data')
                
                if not dados_p.empty:
                    peso_inicial = dados_p.iloc[0]['Peso']
                    peso_atual = dados_p.iloc[-1]['Peso']
                    perda = peso_inicial - peso_atual
                    meta_peso = dados_p.iloc[-1]['Meta de Peso']
                    total_gasto = dados_p['Custo_Dose'].sum()
                    mg_total = dados_p['Dose'].sum()
                    
                    # Cálculo simples do saldo de mg que a pessoa "tem direito"
                    # Isso assume que o custo total foi rateado igualmente por mg.
                    # saldo_mg_teorico = total_investido / custo_por_mg_atual - mg_consumido
                    # Como não temos o "investimento" de cada um, vamos apenas mostrar o total consumido.
                    
                    resumo.append({
                        "Participante": p,
                        "Peso Inicial (kg)": peso_inicial,
                        "Peso Atual (kg)": peso_atual,
                        "Perda Total (kg)": perda,
                        "Meta (kg)": meta_peso,
                        "Faltam p/ Meta (kg)": round(peso_atual - meta_peso, 1) if not pd.isna(meta_peso) else "S/ Meta",
                        "Consumo (mg)": mg_total,
                        "Gasto (R$)": round(total_gasto, 2)
                    })
                else:
                    resumo.append({
                        "Participante": p,
                        "Peso Inicial (kg)": "S/ Dados",
                        "Peso Atual (kg)": "S/ Dados",
                        "Perda Total (kg)": 0.0,
                        "Meta (kg)": df_participantes[df_participantes['Nome'] == p].iloc[0]['Meta de Peso'],
                        "Faltam p/ Meta (kg)": "S/ Dados",
                        "Consumo (mg)": 0.0,
                        "Gasto (R$)": 0.0
                    })
                
            df_resumo = pd.DataFrame(resumo)
            # Formatar tabela para mobile: menos colunas ou usar scroll horizontal
            st.dataframe(df_resumo, use_container_width=True)
        else:
            st.info("Nenhuma aplicação registrada ou nenhum participante cadastrado ainda.")


# ==========================================
# ABA 2: CONFIGURAÇÕES (Admin)
# ==========================================
with tab_participantes:
    st.header("⚙️ Cadastro de Participantes")
    
    with st.form("form_novo_participante"):
        col1, col2 = st.columns([2, 1])
        with col1:
            nome_novo = st.text_input("Nome do Participante (como aparecerá no sistema)")
        with col2:
            meta_peso_novo = st.number_input("Meta de Peso (kg)", min_value=30.0, step=0.1, help="Deixe em branco se não houver meta.")
            
        col3, col4 = st.columns([2, 1])
        with col3:
            senha_cad = st.text_input("Senha de Admin (para cadastrar)", type="password")
        with col4:
            submit_cad = st.form_submit_button("Cadastrar Novo Participante")
        
        if submit_cad:
            if senha_cad == st.secrets["senha_admin"]:
                if nome_novo:
                    planilha = conectar_planilha()
                    aba_participantes = planilha.worksheet("Participantes")
                    
                    # Verificar se o nome já existe
                    participantes_existentes = pd.DataFrame(aba_participantes.get_all_records())['Nome'].tolist()
                    if nome_novo not in participantes_existentes:
                        # Adicionar linha na planilha
                        nova_linha = [nome_novo, float(meta_peso_novo)]
                        aba_participantes.append_row(nova_linha)
                        st.success(f"✅ Participante '{nome_novo}' cadastrado com sucesso! Atualize a página.")
                    else:
                        st.error(f"❌ O participante '{nome_novo}' já existe.")
                else:
                    st.error("❌ O nome do participante é obrigatório.")
            else:
                st.error("❌ Senha de administrador incorreta.")

    st.divider()
    
    # Lista simples dos participantes cadastrados
    st.subheader("Lista de Participantes Atuais")
    if not df_participantes.empty:
        st.dataframe(df_participantes[['Nome', 'Meta de Peso']], use_container_width=True)
    else:
        st.info("Nenhum participante cadastrado ainda.")


# ==========================================
# ABA 3: REGISTRAR DOSE (Admin)
# ==========================================
with tab_registro:
    st.header("Registrar Nova Dose")
    
    # Pegar lista de frascos ativos
    lista_frascos = df_frascos[df_frascos['Status'] == 'Ativo']['ID Frasco'].tolist() if not df_frascos.empty else []
    
    # Pegar lista de participantes cadastrados na aba Participantes
    lista_participantes = df_participantes['Nome'].tolist() if not df_participantes.empty else []
    
    with st.form("form_nova_dose"):
        col1, col2 = st.columns([2, 1])
        with col1:
            data = st.date_input("Data da Aplicação")
            # Agora a lista de nomes vem da planilha, não é mais fixa
            nome = st.selectbox("Selecione o Participante", lista_participantes)
            frasco_selecionado = st.selectbox("Lote/Frasco Utilizado", lista_frascos)
        with col2:
            dose = st.number_input("Dose Aplicada (mg)", min_value=2.5, step=2.5)
            peso = st.number_input("Peso Atual (kg)", min_value=40.0, step=0.1)
            senha = st.text_input("Senha de Admin (para salvar)", type="password")
            
        submit = st.form_submit_button("Salvar Registro de Dose")
        
        if submit:
            if senha == st.secrets["senha_admin"]: # Proteção simples
                # Converter data para texto no formato brasileiro
                data_str = data.strftime("%d/%m/%Y")
                
                planilha = conectar_planilha()
                aba_aplicacoes = planilha.worksheet("Aplicacoes")
                
                # Adicionar linha na planilha
                nova_linha = [data_str, nome, float(dose), float(peso), frasco_selecionado]
                aba_aplicacoes.append_row(nova_linha)
                
                st.success(f"✅ Aplicação de {nome} registrada com sucesso! Atualize a página para ver no Painel.")
            else:
                st.error("❌ Senha incorreta. Apenas o administrador pode salvar.")
