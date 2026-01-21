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

# Columnas actualizadas con Delta y PnL_Capital_Pct
COLUMNS = [
    "ID", "ChainID", "ParentID", "Ticker", "FechaApertura", "Expiry", 
    "Estrategia", "Type", "Strike", "Delta", "PrimaRecibida", "CostoCierre", "Contratos", 
    "BuyingPower", "MaxLoss", "BreakEven", "POP",
    "Estado", "Notas", "UpdatedAt", "MaxProfitUSD", "ProfitPct", "PnL_Capital_Pct"
]

ESTADOS = ["Abierta", "Cerrada", "Rolada", "Asignada"]
ESTRATEGIAS = [
    "CSP (Cash Secured Put)", "CC (Covered Call)", "Put Credit Spread", 
    "Call Credit Spread", "Put Debit Spread", "Call Debit Spread",
    "Long Call", "Long Put", "Iron Condor", "Iron Fly",
    "Strangle", "Straddle", "Calendar", "Diagonal", "Butterfly", "Custom"
]
TYPES = ["Credit", "Debit"]

# ----------------------------
# Gestión de Datos
# ----------------------------
class JournalManager:
    @staticmethod
    def save_with_backup(df: pd.DataFrame):
        if os.path.exists(FILE_NAME):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy(FILE_NAME, f"{BACKUP_DIR}/journal_{timestamp}.csv.bak")
        df = JournalManager.normalize_df(df)
        df.to_csv(FILE_NAME, index=False)

    @staticmethod
    def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
        # Migración de columnas
        for c in COLUMNS:
            if c not in df.columns:
                if c == "Type": df[c] = "Credit"
                elif c in ["BuyingPower", "MaxLoss", "BreakEven", "POP", "Delta", "PnL_Capital_Pct"]: df[c] = 0.0
                else: df[c] = pd.NA
        
        df = df[COLUMNS].copy()
        df["FechaApertura"] = pd.to_datetime(df["FechaApertura"]).dt.date
        df["Expiry"] = pd.to_datetime(df["Expiry"]).dt.date
        
        numeric_cols = ["PrimaRecibida", "CostoCierre", "BuyingPower", "MaxLoss", "BreakEven", "POP", "Delta", "MaxProfitUSD", "ProfitPct", "PnL_Capital_Pct"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        df["Contratos"] = pd.to_numeric(df["Contratos"], errors='coerce').fillna(1).astype(int)
        df["UpdatedAt"] = datetime.now().isoformat(timespec="seconds")
        return df

    @staticmethod
    def load_data() -> pd.DataFrame:
        if os.path.exists(FILE_NAME):
            try:
                df = pd.read_csv(FILE_NAME)
                return JournalManager.normalize_df(df)
            except Exception as e:
                st.error(f"Error cargando datos: {e}")
                return pd.DataFrame(columns=COLUMNS)
        return pd.DataFrame(columns=COLUMNS)

# ----------------------------
# Lógica de Negocio
# ----------------------------
def calculate_pnl_metrics(row):
    entry = row["PrimaRecibida"]
    exit_price = row["CostoCierre"]
    contracts = row["Contratos"]
    op_type = row["Type"]
    bp = row["BuyingPower"]
    
    # PnL en USD
    if op_type == "Credit":
        pnl_usd = (entry - exit_price) * contracts * 100
        # % sobre la prima (Profit Capturado)
        profit_pct = ((entry - exit_price) / entry * 100) if entry > 0 else 0.0
    else:
        pnl_usd = (exit_price - entry) * contracts * 100
        # % sobre el costo (Retorno de Inversión)
        profit_pct = ((exit_price - entry) / entry * 100) if entry > 0 else 0.0
        
    # % sobre el Capital (Buying Power)
    pnl_capital_pct = (pnl_usd / bp * 100) if bp > 0 else 0.0
    
    return pnl_usd, profit_pct, pnl_capital_pct

def filter_df_by_date(df, period, custom_range=None):
    if df.empty: return df
    today = date.today()
    df_filtered = df.copy()
    
    # Asegurar que FechaApertura sea date para comparar
    df_filtered["FechaApertura"] = pd.to_datetime(df_filtered["FechaApertura"]).dt.date
    
    if period == "Este Mes":
        start_date = today.replace(day=1)
        df_filtered = df_filtered[df_filtered["FechaApertura"] >= start_date]
    elif period == "Este Año":
        start_date = today.replace(month=1, day=1)
        df_filtered = df_filtered[df_filtered["FechaApertura"] >= start_date]
    elif period == "Personalizado" and custom_range and len(custom_range) == 2:
        df_filtered = df_filtered[(df_filtered["FechaApertura"] >= custom_range[0]) & (df_filtered["FechaApertura"] <= custom_range[1])]
    return df_filtered

# ----------------------------
# UI Components
# ----------------------------
def render_dashboard(df):
    st.header("📊 Dashboard Ejecutivo")
    
    # --- FILTROS ---
    c_f1, c_f2, c_f3 = st.columns([1, 1, 1])
    periodo = c_f1.selectbox("Periodo", ["Todos", "Este Mes", "Este Año", "Personalizado"])
    
    custom_range = None
    if periodo == "Personalizado":
        custom_range = c_f2.date_input("Rango", [date.today() - timedelta(days=30), date.today()])
    
    # Filtro por Ticker
    all_tickers = ["Todos"] + sorted(df["Ticker"].unique().tolist())
    ticker_filter = c_f3.selectbox("Filtrar por Ticker", all_tickers)
    
    # Aplicar filtros
    df_view = filter_df_by_date(df, periodo, custom_range)
    if ticker_filter != "Todos":
        df_view = df_view[df_view["Ticker"] == ticker_filter]
    
    # --- MÉTRICAS ---
    closed_trades = df_view[df_view["Estado"].isin(["Cerrada", "Rolada", "Asignada"])].copy()
    open_trades = df_view[df_view["Estado"] == "Abierta"].copy()
    
    pnl_total = 0.0
    wins, losses = 0, 0
    gross_profit, gross_loss = 0.0, 0.0
    assignments = 0
    
    for _, row in closed_trades.iterrows():
        pnl, _, _ = calculate_pnl_metrics(row)
        pnl_total += pnl
        if pnl > 0: wins += 1; gross_profit += pnl
        elif pnl < 0: losses += 1; gross_loss += abs(pnl)
        if row["Estado"] == "Asignada": assignments += 1
            
    total_closed = wins + losses
    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0.0
    assign_rate = (assignments / total_closed * 100) if total_closed > 0 else 0.0
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
    
    st.markdown("""<style>div[data-testid="stMetric"] { background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 15px; border-radius: 10px; }</style>""", unsafe_allow_html=True)
    
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("PnL Realizado", f"${pnl_total:,.2f}")
    k2.metric("Win Rate", f"{win_rate:.1f}%", f"{total_closed} trades")
    k3.metric("Profit Factor", f"{pf:.2f}")
    k4.metric("BP en Uso", f"${open_trades['BuyingPower'].sum():,.2f}")
    k5.metric("% Asignaciones", f"{assign_rate:.1f}%", f"{assignments} asignadas")
    
    st.divider()
    
    if not df_view.empty:
        # --- GRÁFICOS INTERACTIVOS (PLOTLY) ---
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📈 Curva de Equidad")
            if not closed_trades.empty:
                closed_trades["PnL_USD"] = closed_trades.apply(lambda x: calculate_pnl_metrics(x)[0], axis=1)
                closed_trades = closed_trades.sort_values("Expiry")
                closed_trades["CumulativePnL"] = closed_trades["PnL_USD"].cumsum()
                
                fig_equity = px.line(closed_trades, x="Expiry", y="CumulativePnL", 
                                   title="Equidad Acumulada",
                                   labels={"CumulativePnL": "PnL Acumulado ($)", "Expiry": "Fecha"},
                                   template="plotly_white")
                fig_equity.update_traces(line_color='#3B82F6', mode='lines+markers')
                st.plotly_chart(fig_equity, use_container_width=True)
            else: st.info("Sin datos cerrados.")
            
        with col2:
            st.subheader("📊 Distribución Win/Loss")
            if total_closed > 0:
                fig_dist = px.pie(values=[wins, losses], names=["Wins", "Losses"], 
                                color=["Wins", "Losses"],
                                color_discrete_map={"Wins": "#10B981", "Losses": "#EF4444"},
                                hole=0.4)
                st.plotly_chart(fig_dist, use_container_width=True)
            else: st.info("Sin trades cerrados.")

        st.divider()
        
        col3, col4 = st.columns(2)
        with col3:
            st.subheader("🏆 Top Tickers (PnL)")
            if not closed_trades.empty:
                ticker_perf = closed_trades.groupby("Ticker")["PnL_USD"].sum().sort_values(ascending=True).reset_index()
                fig_ticker = px.bar(ticker_perf, x="PnL_USD", y="Ticker", orientation='h',
                                  title="PnL por Ticker",
                                  color="PnL_USD", color_continuous_scale="RdYlGn")
                st.plotly_chart(fig_ticker, use_container_width=True)
            
        with col4:
            st.subheader("🛠️ Rendimiento por Estrategia")
            if not closed_trades.empty:
                strat_perf = closed_trades.groupby("Estrategia")["PnL_USD"].sum().sort_values(ascending=True).reset_index()
                fig_strat = px.bar(strat_perf, x="PnL_USD", y="Estrategia", orientation='h',
                                 title="PnL por Estrategia",
                                 color="PnL_USD", color_continuous_scale="RdYlGn")
                st.plotly_chart(fig_strat, use_container_width=True)

        st.divider()
        
        # Desglose Mensual
        st.subheader("📅 Desglose Mensual")
        if not closed_trades.empty:
            closed_trades["Mes"] = pd.to_datetime(closed_trades["FechaApertura"]).dt.strftime('%Y-%m')
            monthly_pnl = closed_trades.groupby("Mes")["PnL_USD"].sum().reset_index()
            fig_monthly = px.bar(monthly_pnl, x="Mes", y="PnL_USD", 
                               title="PnL Mensual",
                               color="PnL_USD", color_continuous_scale="RdYlGn")
            st.plotly_chart(fig_monthly, use_container_width=True)
        else: st.info("Sin datos históricos.")

def render_active_portfolio(df):
    st.header("📂 Cartera Activa")
    active_df = df[df["Estado"] == "Abierta"].copy()
    
    if active_df.empty:
        st.info("No hay posiciones abiertas.")
        return

    # Cálculo de DTE
    def get_dte_status(expiry):
        days = (expiry - date.today()).days
        if days < 0: return f"🔴 EXPIRADO ({days})"
        if days < 7: return f"🔴 {days} d"
        if days < 15: return f"🟠 {days} d"
        return f"🟢 {days} d"

    active_df["DTE"] = active_df["Expiry"].apply(get_dte_status)
    
    # Mostrar % sobre Capital (Potencial)
    active_df["Potencial_Cap_%"] = active_df.apply(lambda x: (x["PrimaRecibida"] * x["Contratos"] * 100 / x["BuyingPower"] * 100) if x["BuyingPower"] > 0 else 0.0, axis=1)

    display_cols = ["Ticker", "Type", "Estrategia", "Strike", "Delta", "Expiry", "DTE", "PrimaRecibida", "Contratos", "BuyingPower", "Potencial_Cap_%", "ID"]
    st.dataframe(active_df[display_cols], width="stretch")
    
    st.divider()
    
    # Acciones
    tab_close, tab_roll = st.tabs(["🎯 Cerrar / Asignar", "🔄 Ejecutar Roll"])
    with tab_close:
        c1, c2, c3 = st.columns([2, 1, 1])
        to_close = c1.selectbox("Seleccionar Trade", active_df["ID"], key="sel_close")
        close_price = c2.number_input("Precio de Cierre", min_value=0.0, step=0.01, key="price_close")
        close_state = c3.radio("Resultado", ["Cerrada", "Asignada"], horizontal=True)
        if st.button("Confirmar Cierre", type="primary"):
            idx = df.index[df["ID"] == to_close][0]
            df.at[idx, "Estado"] = close_state
            df.at[idx, "CostoCierre"] = close_price
            pnl_usd, profit_pct, pnl_cap_pct = calculate_pnl_metrics(df.iloc[idx])
            df.at[idx, "ProfitPct"] = profit_pct
            df.at[idx, "PnL_Capital_Pct"] = pnl_cap_pct
            JournalManager.save_with_backup(df); st.success("Trade cerrado."); st.rerun()

    with tab_roll:
        to_roll = st.selectbox("Trade a rolear", active_df["ID"], key="sel_roll")
        r_row = df[df["ID"] == to_roll].iloc[0]
        col1, col2 = st.columns(2)
        with col1: r_costo = st.number_input("Costo Cierre (BTC)", min_value=0.0, step=0.01)
        with col2:
            r_prima = st.number_input("Nueva Prima (STO)", min_value=0.0, step=0.01)
            r_expiry = st.date_input("Nuevo Vencimiento", value=r_row["Expiry"] + timedelta(days=7))
            r_strike = st.number_input("Nuevo Strike", value=float(r_row["Strike"]), step=0.5)
            r_delta = st.number_input("Nuevo Delta", value=float(r_row["Delta"]), step=0.01)
        if st.button("Procesar Roll", type="primary"):
            idx = df.index[df["ID"] == to_roll][0]
            df.at[idx, "Estado"] = "Rolada"; df.at[idx, "CostoCierre"] = r_costo
            pnl_usd, profit_pct, pnl_cap_pct = calculate_pnl_metrics(df.iloc[idx])
            df.at[idx, "ProfitPct"] = profit_pct
            df.at[idx, "PnL_Capital_Pct"] = pnl_cap_pct
            
            # POP basado en Delta: (1 - abs(Delta)) * 100
            new_pop = (1 - abs(r_delta)) * 100 if abs(r_delta) <= 1 else 0.0
            
            new_row = {
                "ID": str(uuid4())[:8], "ChainID": r_row["ChainID"], "ParentID": to_roll,
                "Ticker": r_row["Ticker"], "FechaApertura": date.today(), "Expiry": r_expiry,
                "Estrategia": r_row["Estrategia"], "Type": r_row["Type"], "Strike": r_strike, "Delta": r_delta,
                "PrimaRecibida": r_prima, "CostoCierre": 0.0, "Contratos": r_row["Contratos"],
                "BuyingPower": r_row["BuyingPower"], "MaxLoss": r_row["MaxLoss"], "BreakEven": r_row["BreakEven"],
                "POP": new_pop, "Estado": "Abierta", "Notas": f"Roll desde {to_roll}",
                "MaxProfitUSD": (r_prima * r_row["Contratos"] * 100) if r_row["Type"] == "Credit" else 0.0, 
                "ProfitPct": 0.0, "PnL_Capital_Pct": 0.0
            }
            st.session_state.df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            JournalManager.save_with_backup(st.session_state.df); st.success("Roll completado."); st.rerun()

def render_new_trade():
    st.header("➕ Nueva Operación")
    with st.form("new_trade_pro"):
        c1, c2, c3, c4 = st.columns(4)
        ticker = c1.text_input("Ticker").upper()
        op_type = c2.selectbox("Tipo", TYPES)
        estrategia = c3.selectbox("Estrategia", ESTRATEGIAS)
        expiry = c4.date_input("Vencimiento")
        
        c5, c6, c7, c8 = st.columns(4)
        strike = c5.number_input("Strike", step=0.5)
        delta = c6.number_input("Delta (ej: 0.30)", step=0.01, help="Usado para calcular POP automáticamente")
        contratos = c7.number_input("Contratos", min_value=1, value=1)
        prima = c8.number_input("Prima", min_value=0.0, step=0.01)
        
        c9, c10, c11, c12 = st.columns(4)
        bp = c9.number_input("Buying Power", min_value=0.0, step=100.0)
        max_loss = c10.number_input("Max Loss", min_value=0.0, step=10.0)
        be = c11.number_input("Break Even", step=0.1)
        
        # POP automático basado en Delta
        auto_pop = (1 - abs(delta)) * 100 if abs(delta) <= 1 else 0.0
        pop = c12.number_input("POP %", value=float(auto_pop), min_value=0.0, max_value=100.0, step=1.0)
        
        notas = st.text_area("Notas / Tesis")
        
        if st.form_submit_button("🚀 Registrar Trade"):
            if not ticker: st.error("Ticker obligatorio.")
            else:
                final_pop = pop if pop != auto_pop else auto_pop
                
                new_row = {
                    "ID": str(uuid4())[:8], "ChainID": str(uuid4())[:8], "ParentID": None,
                    "Ticker": ticker, "FechaApertura": date.today(), "Expiry": expiry,
                    "Estrategia": estrategia, "Type": op_type, "Strike": strike, "Delta": delta,
                    "PrimaRecibida": prima, "CostoCierre": 0.0, "Contratos": contratos,
                    "BuyingPower": bp, "MaxLoss": max_loss, "BreakEven": be, "POP": final_pop,
                    "Estado": "Abierta", "Notas": notas,
                    "MaxProfitUSD": (prima * contratos * 100) if op_type == "Credit" else 0.0, 
                    "ProfitPct": 0.0, "PnL_Capital_Pct": 0.0
                }
                st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
                JournalManager.save_with_backup(st.session_state.df); st.success("Trade registrado."); st.rerun()

def main():
    st.set_page_config(page_title="STRIKELOG Pro", layout="wide", page_icon="📈")
    if "df" not in st.session_state: st.session_state.df = JournalManager.load_data()
    st.sidebar.title("STRIKELOG Pro")
    page = st.sidebar.radio("Navegación", ["Dashboard", "Nueva Operación", "Cartera Activa", "Historial", "Datos / Edición"])
    
    if page == "Dashboard": render_dashboard(st.session_state.df)
    elif page == "Nueva Operación": render_new_trade()
    elif page == "Cartera Activa": render_active_portfolio(st.session_state.df)
    elif page == "Historial":
        st.header("📜 Historial")
        closed_df = st.session_state.df[st.session_state.df["Estado"].isin(["Cerrada", "Rolada", "Asignada"])].copy()
        if not closed_df.empty:
            st.dataframe(closed_df[["Ticker", "Type", "Estrategia", "FechaApertura", "Expiry", "ProfitPct", "PnL_Capital_Pct", "Estado"]], width="stretch")
        else: st.info("Sin historial.")
    elif page == "Datos / Edición":
        st.header("🛠️ Gestión")
        tab1, tab2, tab3 = st.tabs(["📄 Ver", "✏️ Editar", "🗑️ Eliminar"])
        with tab1:
            st.dataframe(st.session_state.df, width="stretch")
            st.download_button("⬇️ Descargar CSV", st.session_state.df.to_csv(index=False).encode('utf-8'), "strikelog.csv", "text/csv")
        with tab2:
            if not st.session_state.df.empty:
                trade_id = st.selectbox("Seleccionar Trade", st.session_state.df["ID"])
                idx = st.session_state.df.index[st.session_state.df["ID"] == trade_id][0]
                row = st.session_state.df.iloc[idx]
                with st.form("edit_form"):
                    n_ticker = st.text_input("Ticker", row["Ticker"])
                    n_bp = st.number_input("Buying Power", value=float(row["BuyingPower"]))
                    n_state = st.selectbox("Estado", ESTADOS, index=ESTADOS.index(row["Estado"]))
                    if st.form_submit_button("💾 Guardar"):
                        st.session_state.df.at[idx, "Ticker"] = n_ticker
                        st.session_state.df.at[idx, "BuyingPower"] = n_bp
                        st.session_state.df.at[idx, "Estado"] = n_state
                        JournalManager.save_with_backup(st.session_state.df); st.success("Actualizado."); st.rerun()
        with tab3:
            if not st.session_state.df.empty:
                del_id = st.selectbox("Eliminar Trade", st.session_state.df["ID"], key="del")
                if st.button("🗑️ ELIMINAR", type="primary"):
                    st.session_state.df = st.session_state.df[st.session_state.df["ID"] != del_id].reset_index(drop=True)
                    JournalManager.save_with_backup(st.session_state.df); st.success("Eliminado."); st.rerun()

if __name__ == "__main__": main()