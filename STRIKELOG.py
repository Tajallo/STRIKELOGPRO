import streamlit as st
import pandas as pd
import os
import shutil
from datetime import date, datetime, timedelta
from uuid import uuid4
import plotly.express as px
import plotly.graph_objects as go

# ----------------------------
# Configuración
# ----------------------------
APP_TITLE = "🚀 STRIKELOG Pro"
FILE_NAME = "bitacora_opciones.csv"
BACKUP_DIR = "backups_journal"

if not os.path.exists(BACKUP_DIR):
    os.makedirs(BACKUP_DIR)

# Columnas actualizadas
COLUMNS = [
    "ID", "ChainID", "ParentID", "Ticker", "FechaApertura", "Expiry", 
    "Estrategia", "Side", "OptionType", "Strike", "Delta", "PrimaRecibida", "CostoCierre", "Contratos", 
    "BuyingPower", "MaxLoss", "BreakEven", "POP",
    "Estado", "Notas", "UpdatedAt", "FechaCierre", "MaxProfitUSD", "ProfitPct", "PnL_Capital_Pct",
    "PrecioAccionCierre", "PnL_USD_Realizado"
]

ESTADOS = ["Abierta", "Cerrada", "Rolada", "Asignada"]
ESTRATEGIAS = [
    "CSP (Cash Secured Put)", "CC (Covered Call)", "Put Credit Spread", 
    "Call Credit Spread", "Put Debit Spread", "Call Debit Spread",
    "Long Call", "Long Put", "Iron Condor", "Iron Fly",
    "Strangle", "Straddle", "Calendar", "Diagonal", "Butterfly", "Custom"
]
SIDES = ["Sell", "Buy"]
OPTION_TYPES = ["Put", "Call"]

# ----------------------------
# Gestión de Datos
# ----------------------------
class JournalManager:
    @staticmethod
    def save_with_backup(df: pd.DataFrame):
        try:
            if os.path.exists(FILE_NAME):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy(FILE_NAME, f"{BACKUP_DIR}/journal_{timestamp}.csv.bak")
            df = JournalManager.normalize_df(df)
            df.to_csv(FILE_NAME, index=False)
        except PermissionError:
            st.error(f"❌ Error al guardar: El archivo '{FILE_NAME}' está bloqueado. Ciérralo si lo tienes abierto en Excel.")
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")

    @staticmethod
    def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
        for c in COLUMNS:
            if c not in df.columns:
                if c == "Side": df[c] = "Sell"
                elif c == "OptionType": df[c] = "Put"
                elif c in ["BuyingPower", "MaxLoss", "BreakEven", "POP", "Delta", "PnL_Capital_Pct", "PrecioAccionCierre", "PnL_USD_Realizado"]: df[c] = 0.0
                else: df[c] = pd.NA
        
        df = df[COLUMNS].copy()
        df["FechaApertura"] = pd.to_datetime(df["FechaApertura"], errors='coerce').dt.date
        df["Expiry"] = pd.to_datetime(df["Expiry"], errors='coerce').dt.date
        df["FechaApertura"] = df["FechaApertura"].fillna(date.today())
        df["Expiry"] = df["Expiry"].fillna(date.today())
        
        numeric_cols = ["PrimaRecibida", "CostoCierre", "BuyingPower", "MaxLoss", "BreakEven", "POP", "Delta", "MaxProfitUSD", "ProfitPct", "PnL_Capital_Pct", "PrecioAccionCierre", "PnL_USD_Realizado"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        df["Contratos"] = pd.to_numeric(df["Contratos"], errors='coerce').fillna(1).astype(int)
        df["UpdatedAt"] = datetime.now().isoformat(timespec="seconds")
        return df

    @staticmethod
    def load_data() -> pd.DataFrame:
        if os.path.exists(FILE_NAME):
            try:
                df = pd.read_csv(FILE_NAME, encoding='utf-8')
                return JournalManager.normalize_df(df)
            except Exception as e:
                st.error(f"❌ Error cargando datos: {e}")
                return pd.DataFrame(columns=COLUMNS)
        return pd.DataFrame(columns=COLUMNS)

# ----------------------------
# Lógica de Negocio
# ----------------------------
def calculate_pnl_metrics(row):
    entry = row["PrimaRecibida"]
    exit_price = row["CostoCierre"]
    contracts = row["Contratos"]
    side = row["Side"]
    bp = row["BuyingPower"]
    
    if side == "Sell":
        pnl_usd = (entry - exit_price) * contracts * 100
        profit_pct = ((entry - exit_price) / entry * 100) if entry > 0 else 0.0
    else:
        pnl_usd = (exit_price - entry) * contracts * 100
        profit_pct = ((exit_price - entry) / entry * 100) if entry > 0 else 0.0
        
    pnl_capital_pct = (pnl_usd / bp * 100) if bp > 0 else 0.0
    return pnl_usd, profit_pct, pnl_capital_pct

# ----------------------------
# UI Components
# ----------------------------
def render_dashboard(df):
    st.header("📊 Dashboard Ejecutivo")
    c_f1, c_f2, c_f3 = st.columns([1, 1, 1])
    periodo = c_f1.selectbox("Periodo", ["Todos", "Este Mes", "Este Año", "Personalizado"])
    custom_range = None
    if periodo == "Personalizado":
        custom_range = c_f2.date_input("Rango", [date.today() - timedelta(days=30), date.today()])
    all_tickers = ["Todos"] + sorted(df["Ticker"].unique().tolist())
    ticker_filter = c_f3.selectbox("Filtrar por Ticker", all_tickers)
    
    df_view = df.copy()
    if ticker_filter != "Todos":
        df_view = df_view[df_view["Ticker"] == ticker_filter]
    
    closed_trades = df_view[df_view["Estado"].isin(["Cerrada", "Rolada", "Asignada"])].copy()
    open_trades = df_view[df_view["Estado"] == "Abierta"].copy()
    
    pnl_total = closed_trades["PnL_USD_Realizado"].sum()
    wins = len(closed_trades[closed_trades["PnL_USD_Realizado"] > 0])
    losses = len(closed_trades[closed_trades["PnL_USD_Realizado"] < 0])
    
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("PnL Realizado Total", f"${pnl_total:,.2f}")
    k2.metric("Win Rate", f"{(wins/(wins+losses)*100 if (wins+losses)>0 else 0):.1f}%")
    k3.metric("BP en Uso", f"${open_trades['BuyingPower'].sum():,.2f}")
    k4.metric("Trades Abiertos", len(open_trades))
    
    # Desglose de Estados
    c_closed = len(df_view[df_view["Estado"] == "Cerrada"])
    c_rolled = len(df_view[df_view["Estado"] == "Rolada"])
    c_assigned = len(df_view[df_view["Estado"] == "Asignada"])
    
    k5, k6, k7 = st.columns(3)
    k5.metric("Trades Cerrados", c_closed)
    k6.metric("Trades Rolados", c_rolled)
    k7.metric("Trades Asignados", c_assigned)
    
    st.divider()
    
    col_graph1, col_graph2 = st.columns(2)
    
    with col_graph1:
        if not closed_trades.empty:
            fig_equity = px.line(closed_trades.sort_values("FechaCierre"), x="FechaCierre", y=closed_trades["PnL_USD_Realizado"].cumsum(), title="Curva de Equidad")
            st.plotly_chart(fig_equity, use_container_width=True)
        else:
            st.info("No hay datos suficientes para la curva de equidad.")
            
    with col_graph2:
        st.subheader("Distribución por Estrategia")
        if not df_view.empty:
            strat_counts = df_view["Estrategia"].value_counts().reset_index()
            strat_counts.columns = ["Estrategia", "Cantidad"]
            fig_strat = px.bar(strat_counts, x="Cantidad", y="Estrategia", orientation='h', text="Cantidad", title="Trades por Estrategia")
            st.plotly_chart(fig_strat, use_container_width=True)

def render_active_portfolio(df):
    st.header("📂 Cartera Activa")
    active_df = df[df["Estado"] == "Abierta"].copy()
    if active_df.empty:
        st.info("No hay posiciones abiertas.")
        return

    # Agrupación por ChainID
    grouped = active_df.groupby("ChainID")
    
    for chain_id, group in grouped:
        first_row = group.iloc[0]
        ticker = first_row["Ticker"]
        strategy = first_row["Estrategia"]
        expiry = first_row["Expiry"]
        
        # Métricas agregadas del grupo
        total_bp = group["BuyingPower"].sum()
        total_premium = group["PrimaRecibida"].sum()
        dte = (expiry - date.today()).days
        
        with st.expander(f"📦 {ticker} - {strategy} | Vence: {expiry} (DTE: {dte}) | BP: ${total_bp:,.0f}", expanded=True):
            # Vista resumen de la estrategia
            c1, c2, c3 = st.columns(3)
            c1.metric("Prima Total Recibida", f"${total_premium:,.2f}")
            c2.metric("Patas Activas", len(group))
            c3.metric("Buying Power", f"${total_bp:,.2f}")
            
            # Tabla detallada de las patas
            st.dataframe(
                group[["Side", "OptionType", "Strike", "Delta", "PrimaRecibida", "Contratos", "ID"]],
                use_container_width=True,
                hide_index=True
            )
            
            # Acciones Rápidas para la Estrategia Completa
            if st.button(f"Gestionar Estrategia {ticker}", key=f"btn_manage_{chain_id}"):
                st.session_state["manage_chain_id"] = chain_id
                st.rerun()

    st.divider()
    
    # Panel de Gestión (aparece si seleccionas una estrategia arriba)
    if "manage_chain_id" in st.session_state:
        target_chain = st.session_state["manage_chain_id"]
        target_group = active_df[active_df["ChainID"] == target_chain]
        
        if not target_group.empty:
            st.markdown(f"### 🎯 Gestión de {target_group.iloc[0]['Ticker']} ({target_group.iloc[0]['Estrategia']})")
            
            tab_close, tab_roll = st.tabs(["Cerrar Estrategia Completa", "🔄 Rolar Estrategia"])
            
            with tab_close:
                st.info("Esto cerrará TODAS las patas de esta estrategia a la vez.")
                c1, c2 = st.columns(2)
                stock_price = c1.number_input("Precio Acción al Cierre", value=0.0, step=0.01)
                total_close_cost = c2.number_input("Costo Total de Cierre (Precio del contrato)", value=0.0, step=0.01, help="Pon el precio del contrato (ej: 1.50). NO multipliques por 100.")
                
                # Preview del PnL
                total_entry = target_group["PrimaRecibida"].sum()
                
                # Calculo preliminar
                pnl_preview = (total_entry - total_close_cost) * 100 # x100 por contrato estándar
                
                st.markdown("#### 📊 Resultados del Cierre")
                cp1, cp2 = st.columns(2)
                cp1.metric("PnL Calculado", f"${pnl_preview:,.2f}")
                
                manual_pnl = cp2.number_input("PnL Realizado Manual (TOTAL $)", value=float(pnl_preview), step=1.0, help="Aquí SÍ pon el total en dólares ganados o perdidos (ej: 150.00)")
                
                if st.button("Confirmar Cierre Total", type="primary"):
                    for idx, row in target_group.iterrows():
                        real_idx = df.index[df["ID"] == row["ID"]][0]
                        df.at[real_idx, "Estado"] = "Cerrada"
                        df.at[real_idx, "FechaCierre"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        df.at[real_idx, "PrecioAccionCierre"] = stock_price
                        
                        # Asignar PnL solo a la primera pata para no duplicar en sumas
                        if row["ID"] == target_group.iloc[0]["ID"]:
                            df.at[real_idx, "CostoCierre"] = total_close_cost
                            df.at[real_idx, "PnL_USD_Realizado"] = manual_pnl
                        else:
                            df.at[real_idx, "CostoCierre"] = 0.0
                            df.at[real_idx, "PnL_USD_Realizado"] = 0.0
                            
                    JournalManager.save_with_backup(df)
                    del st.session_state["manage_chain_id"]
                    st.success("Estrategia cerrada completamente.")
                    st.rerun()
            
            with tab_roll:
                st.markdown("#### 1. Cierre de Posición Actual")
                c_r1, c_r2 = st.columns(2)
                roll_close_cost = c_r1.number_input("Costo para cerrar actual (Precio contrato)", value=0.0, step=0.01, help="Ej: 0.50 (NO 50.00)")
                roll_pnl_manual = c_r2.number_input("PnL Realizado de este cierre (TOTAL $)", value=0.0, step=1.0, help="Total en dólares ganados/perdidos")
                
                st.divider()
                st.markdown("#### 2. Apertura de Nueva Posición (Roll)")
                c_n1, c_n2 = st.columns(2)
                new_expiry = c_n1.date_input("Nuevo Vencimiento", value=date.today() + timedelta(days=7))
                new_net_premium = c_n2.number_input("Nueva Prima Neta (Precio contrato)", value=0.0, step=0.01, help="Ej: 1.20 (NO 120.00)")
                
                st.markdown("**Ajuste de Patas (Opcional)**")
                new_legs = []
                for idx, leg in target_group.iterrows():
                    c_l1, c_l2, c_l3 = st.columns([1, 1, 2])
                    n_strike = c_l1.number_input(f"Nuevo Strike ({leg['OptionType']})", value=float(leg['Strike']), key=f"roll_strike_{leg['ID']}")
                    n_delta = c_l2.number_input(f"Nuevo Delta", value=float(leg['Delta']), key=f"roll_delta_{leg['ID']}")
                    c_l3.caption(f"Pata original: {leg['Side']} {leg['OptionType']} @ {leg['Strike']}")
                    
                    new_legs.append({
                        "Side": leg["Side"], "Type": leg["OptionType"], "Strike": n_strike, "Delta": n_delta,
                        "Contratos": leg["Contratos"], "Ticker": leg["Ticker"], "Estrategia": leg["Estrategia"]
                    })
                
                if st.button("🚀 Ejecutar Roll Completo", type="primary"):
                    # 1. Cerrar antiguas
                    for idx, row in target_group.iterrows():
                        real_idx = df.index[df["ID"] == row["ID"]][0]
                        df.at[real_idx, "Estado"] = "Rolada"
                        df.at[real_idx, "FechaCierre"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        if row["ID"] == target_group.iloc[0]["ID"]:
                            df.at[real_idx, "CostoCierre"] = roll_close_cost
                            df.at[real_idx, "PnL_USD_Realizado"] = roll_pnl_manual
                        else:
                            df.at[real_idx, "CostoCierre"] = 0.0
                            df.at[real_idx, "PnL_USD_Realizado"] = 0.0
                    
                    # 2. Abrir nuevas
                    new_chain_id = str(uuid4())[:8]
                    new_rows = []
                    for i, leg in enumerate(new_legs):
                        p_recibida = new_net_premium if i == 0 else 0.0
                        
                        new_rows.append({
                            "ID": str(uuid4())[:8], "ChainID": new_chain_id, "ParentID": target_group.iloc[0]["ID"],
                            "Ticker": leg["Ticker"], "FechaApertura": date.today(), "Expiry": new_expiry,
                            "Estrategia": leg["Estrategia"], "Side": leg["Side"], "OptionType": leg["Type"], 
                            "Strike": leg["Strike"], "Delta": leg["Delta"],
                            "PrimaRecibida": p_recibida, "CostoCierre": 0.0, "Contratos": leg["Contratos"],
                            "BuyingPower": 0.0, "MaxLoss": 0.0, "BreakEven": 0.0, "POP": 0.0,
                            "Estado": "Abierta", "Notas": f"Roll desde {target_chain}",
                            "UpdatedAt": datetime.now().isoformat(), "FechaCierre": pd.NA,
                            "MaxProfitUSD": (p_recibida * leg["Contratos"] * 100), "ProfitPct": 0.0, "PnL_Capital_Pct": 0.0,
                            "PrecioAccionCierre": 0.0, "PnL_USD_Realizado": 0.0
                        })
                    
                    st.session_state.df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                    JournalManager.save_with_backup(st.session_state.df)
                    del st.session_state["manage_chain_id"]
                    st.success("Roll ejecutado con éxito.")
                    st.rerun()

def render_new_trade():
    st.header("➕ Nueva Operación")
    c_top1, c_top2 = st.columns(2)
    ticker = c_top1.text_input("Ticker").upper()
    estrategia = c_top2.selectbox("Estrategia", ESTRATEGIAS)
    
    legs_count = 1
    if "Spread" in estrategia: legs_count = 2
    elif "Iron" in estrategia: legs_count = 4
    elif estrategia in ["Strangle", "Straddle"]: legs_count = 2
    
    st.markdown(f"### 🛠️ Configuración de {estrategia}")
    
    c_p1, c_p2 = st.columns(2)
    total_premium = c_p1.number_input("Prima Neta (Precio contrato)", value=0.0, step=0.01, help="Pon el precio del contrato (ej: 1.50). NO multipliques por 100.")
    total_bp = c_p2.number_input("Buying Power Total ($)", value=0.0, step=100.0)
    
    legs_data = []
    for i in range(legs_count):
        with st.expander(f"Pata {i+1}", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            l_side = c1.selectbox(f"Side {i+1}", SIDES, key=f"side_{i}")
            l_type = c2.selectbox(f"Type {i+1}", OPTION_TYPES, key=f"type_{i}")
            l_strike = c3.number_input(f"Strike {i+1}", key=f"strike_{i}")
            l_delta = c4.number_input(f"Delta {i+1}", key=f"delta_{i}", step=0.01)
            legs_data.append({"Side": l_side, "Type": l_type, "Strike": l_strike, "Delta": l_delta})
            
    expiry = st.date_input("Vencimiento")
    contratos = st.number_input("Contratos", value=1, min_value=1)
    
    if st.button("Registrar Estrategia", type="primary"):
        if not ticker:
            st.error("Ticker obligatorio.")
        else:
            chain_id = str(uuid4())[:8]
            new_rows = []
            for i, leg in enumerate(legs_data):
                p_recibida = total_premium if i == 0 else 0.0
                bp_leg = total_bp if i == 0 else 0.0
                
                new_rows.append({
                    "ID": str(uuid4())[:8], "ChainID": chain_id, "ParentID": None,
                    "Ticker": ticker, "FechaApertura": date.today(), "Expiry": expiry,
                    "Estrategia": estrategia, "Side": leg["Side"], "OptionType": leg["Type"], 
                    "Strike": leg["Strike"], "Delta": leg["Delta"],
                    "PrimaRecibida": p_recibida, "CostoCierre": 0.0, "Contratos": contratos,
                    "BuyingPower": bp_leg, "MaxLoss": 0.0, "BreakEven": 0.0, "POP": 0.0,
                    "Estado": "Abierta", "Notas": f"Parte de {estrategia}",
                    "UpdatedAt": datetime.now().isoformat(), "FechaCierre": pd.NA,
                    "MaxProfitUSD": (p_recibida * contratos * 100), "ProfitPct": 0.0, "PnL_Capital_Pct": 0.0,
                    "PrecioAccionCierre": 0.0, "PnL_USD_Realizado": 0.0
                })
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(new_rows)], ignore_index=True)
            JournalManager.save_with_backup(st.session_state.df)
            st.success("Estrategia registrada!")
            st.rerun()

def main():
    st.set_page_config(page_title="STRIKELOG Pro", layout="wide")
    if "df" not in st.session_state:
        st.session_state.df = JournalManager.load_data()
        
    page = st.sidebar.radio("Navegación", ["Dashboard", "Nueva Operación", "Cartera Activa", "Historial", "Datos / Edición"])
    
    if page == "Dashboard": render_dashboard(st.session_state.df)
    elif page == "Nueva Operación": render_new_trade()
    elif page == "Cartera Activa": render_active_portfolio(st.session_state.df)
    elif page == "Historial":
        st.header("📜 Historial")
        hist = st.session_state.df[st.session_state.df["Estado"] != "Abierta"]
        st.dataframe(hist[["Ticker", "Estrategia", "FechaCierre", "PrecioAccionCierre", "PnL_USD_Realizado", "ProfitPct", "Estado"]], use_container_width=True)
        
    elif page == "Datos / Edición":
        st.header("🛠️ Gestión de Datos")
        tab1, tab2 = st.tabs(["📄 Ver Todo", "✏️ Editar"])
        with tab1:
            st.dataframe(st.session_state.df, use_container_width=True)
        with tab2:
            trade_id = st.selectbox("ID a editar", st.session_state.df["ID"])
            idx = st.session_state.df.index[st.session_state.df["ID"] == trade_id][0]
            row = st.session_state.df.iloc[idx]
            
            with st.form("edit_form"):
                c1, c2, c3, c4 = st.columns(4)
                n_ticker = c1.text_input("Ticker", row["Ticker"])
                n_side = c2.selectbox("Side", SIDES, index=SIDES.index(row["Side"]) if row["Side"] in SIDES else 0)
                n_type = c3.selectbox("Type", OPTION_TYPES, index=OPTION_TYPES.index(row["OptionType"]) if row["OptionType"] in OPTION_TYPES else 0)
                n_strike = c4.number_input("Strike", value=float(row["Strike"]))
                
                c5, c6, c7 = st.columns(3)
                n_prima = c5.number_input("Prima Recibida", value=float(row["PrimaRecibida"]))
                n_costo = c6.number_input("Costo Cierre (Prima)", value=float(row["CostoCierre"]))
                n_stock_close = c7.number_input("Precio Acción Cierre", value=float(row["PrecioAccionCierre"]))
                
                c8, c9 = st.columns(2)
                n_pnl_usd = c8.number_input("PnL USD Realizado (DINERO GANADO/PERDIDO)", value=float(row["PnL_USD_Realizado"]))
                n_estado = c9.selectbox("Estado", ESTADOS, index=ESTADOS.index(row["Estado"]))
                
                n_notas = st.text_area("Notas", row["Notas"])
                
                if st.form_submit_button("Guardar Cambios"):
                    st.session_state.df.at[idx, "Ticker"] = n_ticker
                    st.session_state.df.at[idx, "Side"] = n_side
                    st.session_state.df.at[idx, "OptionType"] = n_type
                    st.session_state.df.at[idx, "Strike"] = n_strike
                    st.session_state.df.at[idx, "PrimaRecibida"] = n_prima
                    st.session_state.df.at[idx, "CostoCierre"] = n_costo
                    st.session_state.df.at[idx, "PrecioAccionCierre"] = n_stock_close
                    st.session_state.df.at[idx, "PnL_USD_Realizado"] = n_pnl_usd
                    st.session_state.df.at[idx, "Notas"] = n_notas
                    st.session_state.df.at[idx, "Estado"] = n_estado
                    JournalManager.save_with_backup(st.session_state.df)
                    st.success("Actualizado!")
                    st.rerun()

if __name__ == "__main__":
    main()
