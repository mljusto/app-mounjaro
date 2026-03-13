import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Controle Mounjaro", page_icon="💧", layout="centered")

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
            df_aplicacoes['Dose'] = pd.to_numeric(df_aplicacoes['Dose'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
            df_aplicacoes['Peso'] = pd.to_numeric(df_aplicacoes['Peso'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
            
        if not df_pagamentos.empty:
            df_pagamentos['Valor'] = pd.to_numeric(df_pagamentos['Valor'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
        
        return df_frascos, df_aplicacoes, df_participantes, df_pagamentos
    except Exception as e:
        st.error(f"Erro ao carregar dados. Verifique a planilha. Erro: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_frascos, df_aplicacoes, df_participantes, df_pagamentos = carregar_dados()

# --- CABEÇALHO DO APP ---
st.markdown("<h1 style='text-align: center; color: #1f77b4;'>💧 Mounjaro App</h1>", unsafe_allow_html=True)

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
        
        # CARD DO FRASCO ATUAL
        with st.container(border=True):
            st.subheader("📦 Status do Frasco")
            if not frascos_ativos.empty:
                frasco_atual = frascos_ativos.iloc[-1]
                mg_consumido = df_aplicacoes[df_aplicacoes['ID Frasco'] == frasco_atual['ID Frasco']]['Dose'].sum() if not df_aplicacoes.empty else 0
                mg_restante = frasco_atual['MG Total'] - mg_consumido
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Lote Atual", frasco_atual['ID Frasco'])
                c2.metric("Disponível", f"{mg_restante} mg")
                c3.metric("Custo / MG", f"R$ {frasco_atual['Custo_por_MG']:.2f}")
                
                # --- BARRA DE PROGRESSO VISUAL ---
                if frasco_atual['MG Total'] > 0:
                    percentual = max(0, min(100, int((mg_restante / frasco_atual['MG Total']) * 100)))
                    st.progress(percentual, text=f"Volume Restante: {percentual}%")
                
                # Alerta de Compra Dinâmico
                if not df_aplicacoes.empty and not df_participantes.empty:
                    gasto_semanal_estimado = 0
                    for p in df_participantes['Nome'].unique():
                        dados_p = df_aplicacoes[df_aplicacoes['Nome'] == p]
                        if not dados_p.empty:
                            gasto_semanal_estimado += dados_p.iloc[-1]['Dose']
                    
                    if gasto_semanal_estimado > 0:
                        dias_restantes = int((mg_restante / gasto_semanal_estimado) * 7)
                        data_previsao = pd.Timestamp.now() + pd.Timedelta(days=dias_restantes)
                        
                        st.markdown("<br>", unsafe_allow_html=True) # Espaçinho extra
                        if dias_restantes <= 14:
                            st.error(f"🚨 **URGENTE:** Estoque acaba em aprox. **{data_previsao.strftime('%d/%m')}** ({dias_restantes} dias).")
                        elif dias_restantes <= 28:
                            st.warning(f"⚠️ **Atenção:** Remédio garantido até **{data_previsao.strftime('%d/%m')}**.")
                        else:
                            st.success(f"✅ Ritmo tranquilo. Remédio garantido até **{data_previsao.strftime('%d/%m/%Y')}**.")

# --- TABELA ÚNICA DE ACOMPANHAMENTO (OTIMIZADA PARA MOBILE) ---
        if not df_aplicacoes.empty and not df_participantes.empty:
            st.subheader("⚖️ Acompanhamento de Peso")
            
            df_completo = pd.merge(df_aplicacoes, df_participantes, on='Nome', how='left')
            resumo = []
            
            for p in df_participantes['Nome'].unique():
                dados_p = df_completo[df_completo['Nome'] == p].sort_values(by='Data')
                if not dados_p.empty:
                    peso_ini = dados_p.iloc[0]['Peso']
                    peso_atu = dados_p.iloc[-1]['Peso']
                    meta = dados_p.iloc[-1]['Meta de Peso']
                    perda_total = peso_ini - peso_atu
                    progresso = max(0, min(100, int(((peso_ini - peso_atu) / (peso_ini - meta)) * 100))) if peso_ini > meta else 0
                    
                    # Calcula o ganho/perda da última semana (Delta)
                    delta_str = ""
                    if len(dados_p) > 1:
                        peso_anterior = dados_p.iloc[-2]['Peso']
                        delta_semana = peso_atu - peso_anterior
                        if delta_semana > 0:
                            delta_str = f" (+{delta_semana:.1f})"
                        elif delta_semana < 0:
                            delta_str = f" ({delta_semana:.1f})"
                        else:
                            delta_str = " (=)"
                    
                    resumo.append({
                        "Nome": p, 
                        "Peso Atual": f"{peso_atu:.1f} kg{delta_str}",
                        "Perdido Total": f"⬇️ {perda_total:.1f} kg", 
                        "Progresso Meta": progresso
                    })
            
            # Exibe a tabela otimizada
            st.dataframe(
                pd.DataFrame(resumo), 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "Progresso Meta": st.column_config.ProgressColumn("Avanço", format="%d%%", min_value=0, max_value=100)
                }
            )

            # TABELA DE DESEMPENHO E METAS
            df_completo = pd.merge(df_aplicacoes, df_participantes, on='Nome', how='left')
            resumo = []
            for p in df_participantes['Nome'].unique():
                dados_p = df_completo[df_completo['Nome'] == p].sort_values(by='Data')
                if not dados_p.empty:
                    peso_ini = dados_p.iloc[0]['Peso']
                    peso_atu = dados_p.iloc[-1]['Peso']
                    meta = dados_p.iloc[-1]['Meta de Peso']
                    perda = peso_ini - peso_atu
                    progresso = max(0, min(100, int(((peso_ini - peso_atu) / (peso_ini - meta)) * 100))) if peso_ini > meta else 0
                    
                    resumo.append({"Nome": p, "Perdido Total": f"⬇️ {perda:.1f} kg", "Progresso Meta": progresso})
            
            st.dataframe(pd.DataFrame(resumo), use_container_width=True, hide_index=True,
                         column_config={"Progresso Meta": st.column_config.ProgressColumn("Avanço p/ Meta", format="%d%%", min_value=0, max_value=100)})

# ==========================================
# ABA 2: REGISTRAR DOSE E SINTOMAS
# ==========================================
with tab_registro:
    st.header("💉 Nova Aplicação")
    
    lista_frascos = df_frascos[df_frascos['Status'] == 'Ativo']['ID Frasco'].tolist() if not df_frascos.empty else []
    lista_participantes = df_participantes['Nome'].tolist() if not df_participantes.empty else []
    
    nome_selecionado = st.selectbox("Selecione o Participante", lista_participantes)
    
    peso_padrao = 80.0
    if not df_aplicacoes.empty and nome_selecionado in df_aplicacoes['Nome'].values:
        peso_padrao = float(df_aplicacoes[df_aplicacoes['Nome'] == nome_selecionado].iloc[-1]['Peso'])

    with st.container(border=True):
        with st.form("form_nova_dose", clear_on_submit=False):
            data = st.date_input("Data da Aplicação", format="DD/MM/YYYY")
            frasco_selecionado = st.selectbox("Frasco Utilizado", lista_frascos)
            
            c1, c2 = st.columns(2)
            with c1: dose = st.number_input("Dose (mg)", min_value=2.5, step=2.5)
            with c2: peso = st.number_input("Peso Atual (kg)", min_value=40.0, step=0.1, value=peso_padrao)
            
            st.markdown("---")
            opcoes_sintomas = ["Nenhum", "Saciedade alta", "Enjoo", "Fadiga", "Dor de cabeça", "Constipação", "Azia"]
            sintomas = st.multiselect("Sintomas na última semana", opcoes_sintomas)
            observacoes = st.text_input("Observações Extras (Opcional)")
                
            senha_dose = st.text_input("Senha de Admin", type="password")
            
            if st.form_submit_button("Salvar Registro", use_container_width=True):
                if senha_dose == st.secrets["senha_admin"]:
                    if frasco_selecionado:
                        sintomas_str = ", ".join(sintomas) if sintomas else "Não informado"
                        conectar_planilha().worksheet("Aplicacoes").append_row([
                            data.strftime("%d/%m/%Y"), nome_selecionado, float(dose), float(peso), 
                            frasco_selecionado, sintomas_str, observacoes
                        ])
                        st.toast(f"✅ Aplicação de {nome_selecionado} salva com sucesso!")
                    else: st.error("❌ Cadastre um frasco ativo primeiro.")
                else: st.error("❌ Senha incorreta.")

# ==========================================
# ABA 3: FINANÇAS
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
            
            if saldo > 0.01: texto_saldo = f"🟢 Crédito: R$ {saldo:.2f}"
            elif saldo < -0.01: texto_saldo = f"🔴 Deve: R$ {abs(saldo):.2f}"
            else: texto_saldo = "⚪ Quitado"
            
            balanco.append({"Nome": p, "Consumo": f"R$ {gasto_total:.2f}", "Pagos": f"R$ {pago_total:.2f}", "Saldo Atual": texto_saldo})
            
        st.dataframe(pd.DataFrame(balanco), use_container_width=True, hide_index=True)

    # GAVETA DE PAGAMENTO
    with st.expander("💳 Registrar Novo Pagamento"):
        with st.form("form_pagamento", clear_on_submit=True):
            p_nome = st.selectbox("Quem está pagando?", df_participantes['Nome'].tolist() if not df_participantes.empty else [])
            p_valor = st.number_input("Valor Pago (R$)", min_value=1.0, step=10.0)
            p_data = st.date_input("Data", format="DD/MM/YYYY")
            p_senha = st.text_input("Senha", type="password")
            
            if st.form_submit_button("Salvar Pagamento"):
                if p_senha == st.secrets["senha_admin"]:
                    conectar_planilha().worksheet("Pagamentos").append_row([p_data.strftime("%d/%m/%Y"), p_nome, float(p_valor)])
                    st.toast(f"✅ Pagamento de R$ {p_valor} recebido!")
                else: st.error("❌ Senha incorreta.")

# ==========================================
# ABA 4: AJUSTES
# ==========================================
with tab_ajustes:
    st.header("⚙️ Configurações")
    
    # GAVETA: NOVO FRASCO
    with st.expander("📦 Cadastrar Novo Frasco"):
        with st.form("f_add_frasco", clear_on_submit=True):
            n_id = st.text_input("Nome/Lote (Ex: Lote_02)")
            c1, c2 = st.columns(2)
            with c1: n_mg = st.number_input("MG Total", value=90.0)
            with c2: n_val = st.number_input("Valor Pago (R$)", value=2750.0)
            s_add = st.text_input("Senha", type="password")
            if st.form_submit_button("Salvar Frasco"):
                if s_add == st.secrets["senha_admin"]:
                    conectar_planilha().worksheet("Frascos").append_row([n_id, float(n_mg), float(n_val), "Ativo"])
                    st.toast("✅ Frasco cadastrado com sucesso!")

    # GAVETA: ESGOTAR FRASCO
    with st.expander("🗑️ Esgotar Frasco Atual"):
        with st.form("f_ina_frasco", clear_on_submit=True):
            lista_ativos = df_frascos[df_frascos['Status'] == 'Ativo']['ID Frasco'].tolist() if not df_frascos.empty else []
            f_inativar = st.selectbox("Frasco para inativar", lista_ativos)
            s_ina = st.text_input("Senha Admin", type="password")
            if st.form_submit_button("Marcar como Esgotado"):
                if s_ina == st.secrets["senha_admin"]:
                    plan = conectar_planilha().worksheet("Frascos")
                    plan.update_cell(plan.find(f_inativar).row, 4, "Esgotado")
                    st.toast(f"✅ Frasco {f_inativar} esgotado!")

    # GAVETA: NOVO PARTICIPANTE
    with st.expander("👥 Cadastrar Participante"):
        with st.form("f_add_part", clear_on_submit=True):
            nome_p = st.text_input("Nome")
            meta_p = st.number_input("Meta de Peso (kg)", min_value=30.0)
            s_part = st.text_input("Senha Admin", type="password")
            if st.form_submit_button("Salvar Participante"):
                if s_part == st.secrets["senha_admin"]:
                    conectar_planilha().worksheet("Participantes").append_row([nome_p, float(meta_p)])
                    st.toast(f"✅ Participante {nome_p} adicionado!")
