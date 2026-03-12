import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from datetime import timedelta

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Controle Mounjaro", page_icon="💧", layout="centered")

# --- ESTILOS CUSTOMIZADOS ---
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
    return gspread.authorize(creds).open("Sistema_Mounjaro_DB")

# --- CARREGAR DADOS ---
def carregar_dados():
    try:
        planilha = conectar_planilha()
        df_frascos = pd.DataFrame(planilha.worksheet("Frascos").get_all_records())
        df_aplicacoes = pd.DataFrame(planilha.worksheet("Aplicacoes").get_all_records())
        df_participantes = pd.DataFrame(planilha.worksheet("Participantes").get_all_records())
        df_pagamentos = pd.DataFrame(planilha.worksheet("Pagamentos").get_all_records())
        
        if not df_aplicacoes.empty:
            df_aplicacoes['Data'] = pd.to_datetime(df_aplicacoes['Data'], format="%d/%m/%Y")
            df_aplicacoes['Dose'] = df_aplicacoes['Dose'].astype(str).str.replace(',', '.').astype(float)
            df_aplicacoes['Peso'] = df_aplicacoes['Peso'].astype(str).str.replace(',', '.').astype(float)
            
        if not df_pagamentos.empty:
            df_pagamentos['Valor'] = df_pagamentos['Valor'].astype(str).str.replace(',', '.').astype(float)
        
        return df_frascos, df_aplicacoes, df_participantes, df_pagamentos
    except Exception as e:
        st.error(f"Erro ao carregar dados. Verifique as abas da planilha. Erro: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_frascos, df_aplicacoes, df_participantes, df_pagamentos = carregar_dados()

# --- CABEÇALHO DO APP ---
st.markdown("<h1 style='text-align: center; color: #1f77b4;'>💧 Mounjaro App</h1>", unsafe_allow_html=True)
st.divider()

# --- ABAS DO APLICATIVO ---
tab_dashboard, tab_registro, tab_financas, tab_ajustes = st.tabs(["📊 Resultados", "📝 Nova Dose", "💰 Finanças", "⚙️ Ajustes"])

# ==========================================
# ABA 1: PAINEL DE RESULTADOS
# ==========================================
with tab_dashboard:
    if df_frascos.empty:
        st.info("👋 Vá na aba 'Ajustes' para começar cadastrando um frasco.")
    else:
        df_frascos['Custo_por_MG'] = df_frascos['Valor Pago'] / df_frascos['MG Total']
        frascos_ativos = df_frascos[df_frascos['Status'] == 'Ativo']
        
        if not frascos_ativos.empty:
            frasco_atual = frascos_ativos.iloc[-1]
            mg_consumido = df_aplicacoes[df_aplicacoes['ID Frasco'] == frasco_atual['ID Frasco']]['Dose'].sum() if not df_aplicacoes.empty else 0
            mg_restante = frasco_atual['MG Total'] - mg_consumido
            
            c1, c2, c3 = st.columns(3)
            c1.metric("📦 Frasco Ativo", frasco_atual['ID Frasco'])
            c2.metric("💧 Disponível", f"{mg_restante} mg")
            c3.metric("💸 Custo / MG", f"R$ {frasco_atual['Custo_por_MG']:.2f}")
            if mg_restante <= 10: st.error("⚠️ Atenção: O frasco está no fim!")
            
        st.divider()

        # --- PRÓXIMAS APLICAÇÕES (LEMBRETE) ---
        if not df_aplicacoes.empty:
            st.subheader("🗓️ Previsão de Próximas Doses")
            proximas = []
            for p in df_participantes['Nome'].unique():
                dados_p = df_aplicacoes[df_aplicacoes['Nome'] == p]
                if not dados_p.empty:
                    ultima_data = dados_p['Data'].max()
                    proxima_data = ultima_data + pd.Timedelta(days=7)
                    if proxima_data >= pd.Timestamp.now() - pd.Timedelta(days=2):
                        proximas.append({"Participante": p, "Próxima Aplicação": proxima_data.strftime("%d/%m/%Y")})
            
            if proximas:
                st.dataframe(pd.DataFrame(proximas), use_container_width=True, hide_index=True)
            else:
                st.info("Nenhuma aplicação prevista para os próximos dias.")
            
            st.divider()

        # --- DADOS E GRÁFICOS ---
        if not df_aplicacoes.empty and not df_participantes.empty:
            df_completo = pd.merge(df_aplicacoes, df_participantes, on='Nome', how='left')
            df_completo = pd.merge(df_completo, df_frascos[['ID Frasco', 'Custo_por_MG']], on='ID Frasco', how='left')
            df_completo['Custo_Dose'] = df_completo['Dose'] * df_completo['Custo_por_MG']
            
            st.subheader("📉 Evolução de Peso")
            fig = px.line(df_completo.sort_values(by=['Nome', 'Data']), x='Data', y='Peso', color='Nome', markers=True, template="plotly_white")
            fig.update_xaxes(tickformat="%d/%m/%Y", title_text="")
            fig.update_yaxes(title_text="Peso (kg)")
            fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5), margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("🏆 Desempenho e Metas")
            resumo = []
            for p in df_participantes['Nome'].unique():
                dados_p = df_completo[df_completo['Nome'] == p].sort_values(by='Data')
                if not dados_p.empty:
                    peso_ini = dados_p.iloc[0]['Peso']
                    peso_atu = dados_p.iloc[-1]['Peso']
                    meta = dados_p.iloc[-1]['Meta de Peso']
                    perda = peso_ini - peso_atu
                    
                    progresso = 0
                    if peso_ini > meta:
                        progresso = int(((peso_ini - peso_atu) / (peso_ini - meta)) * 100)
                        progresso = max(0, min(100, progresso))
                    
                    resumo.append({
                        "Nome": p,
                        "Peso Atual": f"{peso_atu} kg",
                        "Perdido": f"⬇️ {perda:.1f} kg",
                        "Progresso Meta": progresso,
                    })
            
            st.dataframe(
                pd.DataFrame(resumo), 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Progresso Meta": st.column_config.ProgressColumn("Avanço p/ Meta", format="%d%%", min_value=0, max_value=100)
                }
            )


# ==========================================
# ABA 2: REGISTRAR DOSE
# ==========================================
with tab_registro:
    st.header("💉 Nova Aplicação")
    
    lista_frascos = df_frascos[df_frascos['Status'] == 'Ativo']['ID Frasco'].tolist() if not df_frascos.empty else []
    lista_participantes = df_participantes['Nome'].tolist() if not df_participantes.empty else []
    
    nome_selecionado = st.selectbox("1. Selecione o Participante", lista_participantes)
    
    peso_padrao = 80.0
    if not df_aplicacoes.empty and nome_selecionado in df_aplicacoes['Nome'].values:
        ultimo_peso_registrado = df_aplicacoes[df_aplicacoes['Nome'] == nome_selecionado].iloc[-1]['Peso']
        peso_padrao = float(ultimo_peso_registrado)
        st.info(f"O último peso de {nome_selecionado} foi {peso_padrao} kg. Atualize se necessário.")

    with st.form("form_nova_dose"):
        st.markdown("**2. Dados da Aplicação**")
        data = st.date_input("Data da Aplicação", format="DD/MM/YYYY")
        frasco_selecionado = st.selectbox("Frasco Utilizado", lista_frascos)
        
        c1, c2 = st.columns(2)
        with c1: dose = st.number_input("Dose (mg)", min_value=2.5, step=2.5)
        with c2: peso = st.number_input("Peso Atual (kg)", min_value=40.0, step=0.1, value=peso_padrao)
            
        senha_dose = st.text_input("Senha de Admin", type="password")
        if st.form_submit_button("Salvar Registro", use_container_width=True):
            if senha_dose == st.secrets["senha_admin"]:
                if frasco_selecionado:
                    conectar_planilha().worksheet("Aplicacoes").append_row([data.strftime("%d/%m/%Y"), nome_selecionado, float(dose), float(peso), frasco_selecionado])
                    st.success(f"✅ Salvo! {nome_selecionado} tomou {dose}mg. Atualize a página.")
                else: st.error("❌ Cadastre um frasco ativo primeiro.")
            else: st.error("❌ Senha incorreta.")


# ==========================================
# ABA 3: FINANÇAS (CÁLCULO DE SALDO)
# ==========================================
with tab_financas:
    st.header("💰 Controle Financeiro")
    
    if not df_aplicacoes.empty and not df_participantes.empty:
        df_gastos = pd.merge(df_aplicacoes, df_frascos[['ID Frasco', 'Custo_por_MG']], on='ID Frasco', how='left')
        df_gastos['Custo_Dose'] = df_gastos['Dose'] * df_gastos['Custo_por_MG']
        
        balanco = []
        for p in df_participantes['Nome'].unique():
            gasto_total = df_gastos[df_gastos['Nome'] == p]['Custo_Dose'].sum() if (not df_gastos.empty and 'Nome' in df_gastos.columns) else 0.0
            pago_total = df_pagamentos[df_pagamentos['Nome'] == p]['Valor'].sum() if (not df_pagamentos.empty and 'Nome' in df_pagamentos.columns) else 0.0
            
            saldo = pago_total - gasto_total
            
            # Formatação do Saldo e Situação
            if saldo > 0.01:
                situacao = "🟢 Tem Crédito"
                valor_saldo = f"+ R$ {saldo:.2f}"
            elif saldo < -0.01:
                situacao = "🔴 Está Devendo"
                valor_saldo = f"- R$ {abs(saldo):.2f}"
            else:
                situacao = "⚪ Quitado"
                valor_saldo = "R$ 0.00"
            
            balanco.append({
                "Participante": p,
                "Total Pago": f"R$ {pago_total:.2f}",
                "Total Consumido": f"R$ {gasto_total:.2f}",
                "Saldo": valor_saldo,
                "Situação": situacao
            })
            
        st.dataframe(pd.DataFrame(balanco), use_container_width=True, hide_index=True)
    else:
        st.info("Sem dados suficientes para o balanço financeiro.")

    st.divider()
    st.subheader("Registrar Pagamento Recebido")
    with st.form("form_pagamento"):
        p_nome = st.selectbox("Quem está pagando?", df_participantes['Nome'].tolist() if not df_participantes.empty else [])
        p_valor = st.number_input("Valor Pago (R$)", min_value=1.0, step=10.0)
        p_data = st.date_input("Data do Pagamento", format="DD/MM/YYYY")
        p_senha = st.text_input("Senha", type="password")
        
        if st.form_submit_button("Salvar Pagamento", use_container_width=True):
            if p_senha == st.secrets["senha_admin"]:
                conectar_planilha().worksheet("Pagamentos").append_row([p_data.strftime("%d/%m/%Y"), p_nome, float(p_valor)])
                st.success(f"✅ Pagamento de R$ {p_valor} recebido de {p_nome}! Atualize a página.")
            else: st.error("❌ Senha incorreta.")

# ==========================================
# ABA 4: AJUSTES E ADMINISTRAÇÃO
# ==========================================
with tab_ajustes:
    st.header("⚙️ Configurações do Sistema")
    
    st.subheader("📦 Gestão de Frascos")
    c_f1, c_f2 = st.columns(2)
    with c_f1:
        with st.form("f_add_frasco"):
            st.markdown("**Cadastrar Novo**")
            n_id = st.text_input("Lote (Ex: Lote_02)")
            n_mg = st.number_input("MG Total", value=90.0)
            n_val = st.number_input("Valor (R$)", value=2750.0)
            s_add = st.text_input("Senha", type="password")
            if st.form_submit_button("Cadastrar"):
                if s_add == st.secrets["senha_admin"]:
                    conectar_planilha().worksheet("Frascos").append_row([n_id, float(n_mg), float(n_val), "Ativo"])
                    st.success("✅ Cadastrado!")
    with c_f2:
        with st.form("f_ina_frasco"):
            st.markdown("**Esgotar Atual**")
            lista_ativos = df_frascos[df_frascos['Status'] == 'Ativo']['ID Frasco'].tolist() if not df_frascos.empty else []
            f_inativar = st.selectbox("Frasco", lista_ativos)
            s_ina = st.text_input("Senha", type="password")
            if st.form_submit_button("Esgotar"):
                if s_ina == st.secrets["senha_admin"]:
                    plan = conectar_planilha().worksheet("Frascos")
                    plan.update_cell(plan.find(f_inativar).row, 4, "Esgotado")
                    st.success("✅ Esgotado!")

    st.divider()
    st.subheader("👥 Gestão de Participantes")
    with st.form("f_add_part"):
        nome_p = st.text_input("Nome")
        meta_p = st.number_input("Meta (kg)", min_value=30.0)
        s_part = st.text_input("Senha", type="password")
        if st.form_submit_button("Cadastrar Participante"):
            if s_part == st.secrets["senha_admin"]:
                conectar_planilha().worksheet("Participantes").append_row([nome_p, float(meta_p)])
                st.success("✅ Cadastrado!")
