import streamlit as st
import pandas as pd
import os
import shutil
import re
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
    "Estrategia", "Setup", "Side", "OptionType", "Strike", "Delta", "PrimaRecibida", "CostoCierre", "Contratos", 
    "BuyingPower", "MaxLoss", "BreakEven", "POP",
    "Estado", "Notas", "UpdatedAt", "FechaCierre", "MaxProfitUSD", "ProfitPct", "PnL_Capital_Pct",
    "PrecioAccionCierre", "PnL_USD_Realizado"
]

SETUPS = ["Earnings", "Soporte/Resistencia", "VIX alto", "Tendencial", "Reversión", "Inversión Largo Plazo", "Otro"]

ESTADOS = ["Abierta", "Cerrada", "Rolada", "Asignada"]
ESTRATEGIAS = [
    "CSP (Cash Secured Put)", "CC (Covered Call)", "Collar",
    "Put Credit Spread", "Call Credit Spread", 
    "Put Debit Spread", "Call Debit Spread",
    "Iron Condor", "Iron Fly",
    "Butterfly", "Broken Wing Butterfly (BWB)",
    "Strangle", "Straddle",
    "Calendar", "Diagonal",
    "Ratio Spread", "Backspread", 
    "Long Call", "Long Put",
    "Custom / Other"
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
        # Asegurar que Setup existe
        if "Setup" not in df.columns:
            df["Setup"] = "Otro"
            
        # Intentar recuperar fechas de cierre de las notas si faltan (como en el caso de JBLU)
        def recover_closing_date(row):
            if row.get("Estado") != "Abierta" and (pd.isna(row.get("FechaCierre")) or str(row.get("FechaCierre")) == "nan"):
                # Buscar patrón YYYY-MM-DD en Notas o Estado
                text = str(row.get("Notas", "")) + " " + str(row.get("Estado", ""))
                match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
                if match: return match.group(1)
            return row.get("FechaCierre")
        
        df["FechaCierre"] = df.apply(recover_closing_date, axis=1)
            
        for c in COLUMNS:
            if c not in df.columns:
                if c == "Side": df[c] = "Sell"
                elif c == "OptionType": df[c] = "Put"
                elif c in ["BuyingPower", "MaxLoss", "BreakEven", "POP", "Delta", "PnL_Capital_Pct", "PrecioAccionCierre", "PnL_USD_Realizado"]: df[c] = 0.0
                else: df[c] = pd.NA
        
        df = df[COLUMNS].copy()
        df["FechaApertura"] = pd.to_datetime(df["FechaApertura"], errors='coerce').dt.date
        df["Expiry"] = pd.to_datetime(df["Expiry"], errors='coerce').dt.date
        df["FechaCierre"] = pd.to_datetime(df["FechaCierre"], errors='coerce').dt.date
        
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

def suggest_breakeven(strategy, legs_data, total_premium):
    if not legs_data: return 0.0
    try:
        main_strike = float(legs_data[0]["Strike"])
        if "Put" in strategy or "CSP" in strategy or "Put Credit Spread" in strategy:
            return main_strike - total_premium
        if "Call" in strategy or "CC" in strategy or "Call Credit Spread" in strategy:
            return main_strike + total_premium
    except:
        pass
    return 0.0

def suggest_pop(delta, side):
    """Calcula la probabilidad de éxito aproximada basada en el Delta."""
    abs_delta = abs(delta)
    if side == "Sell":
        return round((1.0 - abs_delta) * 100, 1)
    else:
        return round(abs_delta * 100, 1)

def get_roll_history(df, current_id):
    """Rastrea hacia atrás todos los padres de un trade para obtener la secuencia de roles."""
    history = []
    seen_ids = set()
    curr = current_id
    
    while pd.notna(curr) and str(curr) != "nan" and curr not in seen_ids:
        parent_rows = df[df["ID"] == curr]
        if parent_rows.empty:
            break
        
        row = parent_rows.iloc[0]
        history.append(row)
        seen_ids.add(curr)
        curr = row.get("ParentID")
        
    # El primero en la lista es el actual, el último es el origen original
    return history

# ----------------------------
# UI Components
# ----------------------------
def render_dashboard(df):
    # --- ESTILOS PERSONALIZADOS PARA KPIs ---
    st.markdown("""
        <style>
        [data-testid="stMetricValue"] {
            font-size: 24px;
        }
        .kpi-card {
            background-color: #1e2130;
            padding: 20px;
            border-radius: 10px;
            border-left: 5px solid #00ffa2;
            margin-bottom: 20px;
        }
        .stMetric {
            background-color: rgba(255, 255, 255, 0.05);
            padding: 15px;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        </style>
    """, unsafe_allow_html=True)

    st.title("📊 Cuadro de Mando")
    
    # --- FILTROS ---
    with st.container():
        c_f1, c_f2, c_f3 = st.columns([1, 1, 1])
        all_tickers = ["Todos Tickers"] + sorted(df["Ticker"].unique().tolist())
        ticker_filter = c_f1.selectbox("🔍 Ticker", all_tickers)
        
        meses = {
            "Todo el Historial": "Todos",
            "Este Mes": datetime.now().strftime("%Y-%m"),
            "Mes Pasado": (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m"),
            "Este Año": datetime.now().strftime("%Y")
        }
        periodo_filter = c_f2.selectbox("📅 Periodo", list(meses.keys()))
        setup_filter = c_f3.selectbox("🎯 Setup", ["Todos los Setups"] + SETUPS)
        
        # Aplicar Filtros
        df_view = df.copy()
        if ticker_filter != "Todos Tickers":
            df_view = df_view[df_view["Ticker"] == ticker_filter]
        
        if periodo_filter != "Todo el Historial":
            filtro_val = meses[periodo_filter]
            df_view["FechaFiltro"] = pd.to_datetime(df_view["FechaApertura"]).dt.strftime("%Y-%m" if len(filtro_val)==7 else "%Y")
            df_view = df_view[df_view["FechaFiltro"] == filtro_val]
            
        if setup_filter != "Todos los Setups":
            df_view = df_view[df_view["Setup"] == setup_filter]
        
        closed_trades = df_view[df_view["Estado"].isin(["Cerrada", "Rolada", "Asignada"])].copy()
        open_trades = df_view[df_view["Estado"] == "Abierta"].copy()
        
        # --- KPIs DE ALTO NIVEL ---
        pnl_total = closed_trades["PnL_USD_Realizado"].sum()
        wins_df = closed_trades[closed_trades["PnL_USD_Realizado"] > 0]
        losses_df = closed_trades[closed_trades["PnL_USD_Realizado"] < 0]
        
        wins = len(wins_df)
        losses = len(losses_df)
        total_closed = wins + losses
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        
        capture_eff = wins_df["ProfitPct"].mean() if not wins_df.empty else 0
        total_won = wins_df["PnL_USD_Realizado"].sum()
        total_lost = abs(losses_df["PnL_USD_Realizado"].sum())
        profit_factor = (total_won / total_lost) if total_lost > 0 else (total_won if total_won > 0 else 0.0)
        
        st.divider()
        
        # Fila 1: Métricas Principales con diseño mejorado
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("PnL Realizado", f"${pnl_total:,.2f}", delta=f"${pnl_total:,.2f}" if pnl_total != 0 else None)
        m2.metric("Win Rate", f"{win_rate:.1f}%", help="Porcentaje de operaciones positivas")
        m3.metric("Profit Factor", f"{profit_factor:.2f}x", help="Ratio Ganancia Total / Pérdida Total")
        m4.metric("Captura Media", f"{capture_eff:.1f}%", help="Promedio de beneficio sobre la prima recibida")
        
        st.write("") # Espaciado
        
        # Fila 2: Estadísticas de Eficiencia
        s1, s2, s3, s4 = st.columns(4)
        avg_profit = closed_trades["PnL_USD_Realizado"].mean() if not closed_trades.empty else 0
        s1.markdown(f"**Promedio/Trade:**<br><span style='font-size:18px; color:#00ffa2;'>${avg_profit:,.2f}</span>", unsafe_allow_html=True)
        
        best_ticker = closed_trades.groupby("Ticker")["PnL_USD_Realizado"].sum().idxmax() if not closed_trades.empty else "-"
        s2.markdown(f"**Top Ticker:**<br><span style='font-size:18px; color:#00ffa2;'>{best_ticker}</span>", unsafe_allow_html=True)
        
        total_bp_open = open_trades['BuyingPower'].sum()
        s3.markdown(f"**En Uso (BP):**<br><span style='font-size:18px; color:#ffcc00;'>${total_bp_open:,.0f}</span>", unsafe_allow_html=True)
        
        active_strats = len(open_trades["ChainID"].unique())
        s4.markdown(f"**Estrat. Activas:**<br><span style='font-size:18px; color:#00d9ff;'>{active_strats}</span>", unsafe_allow_html=True)
        
    st.write("")
    
    # --- GRÁFICOS ---
    col_chart1, col_chart2 = st.columns([2, 1])
    
    with col_chart1:
        st.markdown("### 📈 Curva de Equidad")
        if not closed_trades.empty:
            closed_trades["FechaCierre"] = pd.to_datetime(closed_trades["FechaCierre"])
            closed_trades = closed_trades.sort_values("FechaCierre")
            closed_trades["Equity"] = closed_trades["PnL_USD_Realizado"].cumsum()
            
            fig_equity = px.area(closed_trades, x="FechaCierre", y="Equity", 
                                 template="plotly_dark")
            
            fig_equity.update_traces(line_color="#00FFAA", fillcolor="rgba(0, 255, 170, 0.15)", line_width=3)
            fig_equity.update_layout(
                height=380, 
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title=None,
                yaxis_title="Balance ($)",
                hovermode="x unified"
            )
            st.plotly_chart(fig_equity, width="stretch")
        else:
            st.info("No hay datos para mostrar la curva.")

    with col_chart2:
        st.markdown("### 🎯 Por Estrategia")
        if not df_view.empty:
            strat_data = df_view.groupby("Estrategia")["PnL_USD_Realizado"].sum().reset_index()
            # Ordenar para que se vea mejor
            strat_data = strat_data.sort_values("PnL_USD_Realizado", ascending=True)
            
            fig_strat = px.bar(strat_data, x="PnL_USD_Realizado", y="Estrategia", 
                               orientation='h', color="PnL_USD_Realizado",
                               color_continuous_scale="RdYlGn",
                               template="plotly_dark")
            
            fig_strat.update_layout(
                height=380, 
                showlegend=False, 
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="PnL USD",
                yaxis_title=None,
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_strat, width="stretch")

    # Gráfico de barras mensual
    if not closed_trades.empty:
        st.markdown("### 📅 Rendimiento Mensual")
        closed_trades['Mes'] = pd.to_datetime(closed_trades['FechaCierre']).dt.strftime('%b %Y')
        monthly_pnl = closed_trades.groupby('Mes')['PnL_USD_Realizado'].sum().reset_index()
        
        fig_monthly = px.bar(monthly_pnl, x='Mes', y='PnL_USD_Realizado', 
                             color='PnL_USD_Realizado', 
                             color_continuous_scale="RdYlGn",
                             template="plotly_dark")
        fig_monthly.update_layout(
            height=320,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title=None,
            yaxis_title="PnL USD",
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_monthly, width="stretch")

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
        
        # Semáforo DTE
        dte_color = "⚪"
        if dte < 7: dte_color = "🔴"
        elif dte <= 21: dte_color = "🟡"
        else: dte_color = "🟢"
        
        # Identificar historial de Rolls
        roll_chain = get_roll_history(df, first_row["ID"])
        num_rolls = len(roll_chain) - 1 # El actual no cuenta como roll
        
        roll_label = f" 🔄 [ROL #{num_rolls}]" if num_rolls > 0 else ""
        
        with st.expander(f"{dte_color}{roll_label} {ticker} - {strategy} | Vence: {expiry} (DTE: {dte}) | BP: ${total_bp:,.0f}", expanded=False):
            # Vista resumen de la estrategia
            c1, c2, c3 = st.columns(3)
            c1.metric("Prima Total Recibida", f"${total_premium:,.2f}")
            c2.metric("Patas Activas", len(group))
            c3.metric("Buying Power", f"${total_bp:,.2f}")
            
            if num_rolls > 0:
                st.markdown("#### 🕒 Historial de esta posición")
                # Mostrar el camino desde el origen
                reversed_chain = list(reversed(roll_chain))
                origin = reversed_chain[0]
                
                # Resumen de evolución
                st.info(f"📍 **Origen:** Abierto el `{origin['FechaApertura']}` con Strike `{origin['Strike']} {origin['OptionType']}`.")
                
                # Pequeña tabla con la evolución
                hist_data = []
                for i, r in enumerate(reversed_chain):
                    label = "ORIGEN" if i == 0 else f"ROL #{i}"
                    hist_data.append({
                        "Etapa": label,
                        "Fecha": r["FechaApertura"],
                        "Strike": f"{r['Strike']} {r['OptionType']}",
                        "BE": r["BreakEven"],
                        "PnL Realizado": f"${r['PnL_USD_Realizado']:.2f}" if r['Estado'] != 'Abierta' else "-"
                    })
                
                st.table(pd.DataFrame(hist_data))
                
                if num_rolls > 0:
                    last_be = reversed_chain[-2]["BreakEven"]
                    curr_be = first_row["BreakEven"]
                    diff_be = curr_be - last_be
                    be_msg = f"📈 +{diff_be:.2f}" if diff_be > 0 else (f"📉 {diff_be:.2f}" if diff_be < 0 else "➡️ S/C")
                    st.caption(f"**Evolución del BE (último rol):** `{last_be:.2f}` → `{curr_be:.2f}` ({be_msg})")
            
            # Tabla detallada de las patas
            st.dataframe(
                group[["Side", "OptionType", "Strike", "Delta", "PrimaRecibida", "Contratos", "ID"]],
                width="stretch",
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

                if st.button("Cancelar Gestión", key="cancel_close"):
                    del st.session_state["manage_chain_id"]
                    st.rerun()
            
            with tab_roll:
                st.markdown("#### 🔄 Configuración del Roll Parcial o Total")
                st.caption("Selecciona qué patas quieres mover al nuevo vencimiento.")
                
                # Selección de patas a rolar
                legs_to_roll = []
                for idx, leg in target_group.iterrows():
                    c_sel, c_info = st.columns([1, 4])
                    should_roll = c_sel.checkbox("Rolar", value=True, key=f"check_roll_{leg['ID']}")
                    c_info.write(f"**Pata:** {leg['Side']} {leg['OptionType']} @ {leg['Strike']} (ID: {leg['ID']})")
                    if should_roll:
                        legs_to_roll.append(leg)
                
                if not legs_to_roll:
                    st.warning("Selecciona al menos una pata para realizar un Roll.")
                else:
                    st.divider()
                    st.markdown("#### 1. Cierre de Posición Actual")
                    c_r1, c_r2 = st.columns(2)
                    roll_close_cost = c_r1.number_input("Costo de cierre de las patas seleccionadas", value=0.0, step=0.01)
                    roll_pnl_manual = c_r2.number_input("PnL Realizado del cierre actual ($)", value=0.0, step=1.0)
                    
                    st.divider()
                    st.markdown("#### 2. Apertura del Nuevo Vencimiento")
                    c_n1, c_n2 = st.columns(2)
                    new_expiry = c_n1.date_input("Nuevo Vencimiento", value=date.today() + timedelta(days=7))
                    new_net_premium = c_n2.number_input("Nueva Prima Neta ($)", value=0.0, step=0.01)
                    
                    new_legs_data = []
                    for leg in legs_to_roll:
                        st.markdown(f"**Ajuste para: {leg['Side']} {leg['OptionType']}**")
                        c_l1, c_l2 = st.columns(2)
                        n_strike = c_l1.number_input(f"Nuevo Strike", value=float(leg['Strike']), key=f"roll_strike_{leg['ID']}")
                        n_delta = c_l2.number_input(f"Nuevo Delta", value=float(leg['Delta']), key=f"roll_delta_{leg['ID']}")
                        
                        new_legs_data.append({
                            "Side": leg["Side"], "Type": leg["OptionType"], "Strike": n_strike, "Delta": n_delta,
                            "Contratos": leg["Contratos"], "Ticker": leg["Ticker"], "Estrategia": leg["Estrategia"],
                            "OldID": leg["ID"]
                        })
                    
                    c_btn1, c_btn2 = st.columns([1, 1])
                    if c_btn1.button("🚀 Ejecutar Ajuste Seleccionado", type="primary"):
                        # 1. Marcar las patas originales como Roladas
                        for leg in legs_to_roll:
                            real_idx = df.index[df["ID"] == leg["ID"]][0]
                            df.at[real_idx, "Estado"] = "Rolada"
                            df.at[real_idx, "FechaCierre"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            # Solo ponemos el coste en la primera pata del roll para no duplicar sumas
                            if leg["ID"] == legs_to_roll[0]["ID"]:
                                df.at[real_idx, "CostoCierre"] = roll_close_cost
                                df.at[real_idx, "PnL_USD_Realizado"] = roll_pnl_manual
                            else:
                                df.at[real_idx, "CostoCierre"] = 0.0
                                df.at[real_idx, "PnL_USD_Realizado"] = 0.0

                        # 2. Crear las nuevas patas en un nuevo ChainID
                        new_chain_id = str(uuid4())[:8]
                        new_rows = []
                        
                        # Calcular BE y POP sugerido
                        suggested_be_roll = suggest_breakeven(legs_to_roll[0]["Estrategia"], new_legs_data, new_net_premium)
                        suggested_pop_roll = suggest_pop(new_legs_data[0]["Delta"], new_legs_data[0]["Side"])

                        for i, n_leg in enumerate(new_legs_data):
                            p_recibida = new_net_premium if i == 0 else 0.0
                            # Heredamos el BP de la pata original si existe
                            new_rows.append({
                                "ID": str(uuid4())[:8], "ChainID": new_chain_id, "ParentID": n_leg["OldID"],
                                "Ticker": n_leg["Ticker"], "FechaApertura": date.today(), "Expiry": new_expiry,
                                "Estrategia": n_leg["Estrategia"], "Side": n_leg["Side"], "OptionType": n_leg["Type"], 
                                "Strike": n_leg["Strike"], "Delta": n_leg["Delta"],
                                "PrimaRecibida": p_recibida, "CostoCierre": 0.0, "Contratos": n_leg["Contratos"],
                                "BuyingPower": original_bp if i == 0 else 0.0, "MaxLoss": 0.0, 
                                "BreakEven": suggested_be_roll if i == 0 else 0.0, 
                                "POP": suggested_pop_roll if i == 0 else 0.0,
                                "Estado": "Abierta", "Notas": f"Roll parcial desde {target_chain}",
                                "UpdatedAt": datetime.now().isoformat(), "FechaCierre": pd.NA,
                                "MaxProfitUSD": (p_recibida * n_leg["Contratos"] * 100), "ProfitPct": 0.0, "PnL_Capital_Pct": 0.0,
                                "PrecioAccionCierre": 0.0, "PnL_USD_Realizado": 0.0
                            })
                        
                        st.session_state.df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                        JournalManager.save_with_backup(st.session_state.df)
                        del st.session_state["manage_chain_id"]
                        st.success("Ajuste de patas completado.")
                        st.rerun()
                    
                    if c_btn2.button("Cancelar Gestión", key="cancel_roll"):
                        del st.session_state["manage_chain_id"]
                        st.rerun()

def render_new_trade():
    st.header("➕ Nueva Operación")
    c_top1, c_top2, c_top3 = st.columns(3)
    ticker = c_top1.text_input("Ticker").upper()
    estrategia = c_top2.selectbox("Estrategia", ESTRATEGIAS)
    setup_val = c_top3.selectbox("🎯 Setup / Motivo", SETUPS)
    
    legs_count = 1
    if "Spread" in estrategia: legs_count = 2
    elif "Iron" in estrategia: legs_count = 4
    elif "Butterfly" in estrategia: legs_count = 3
    elif estrategia in ["Strangle", "Straddle"]: legs_count = 2
    elif "Ratio" in estrategia: legs_count = 2
    
    if estrategia == "Custom / Other":
        legs_count = st.number_input("Especifique el número de patas", min_value=1, max_value=10, value=1)
    
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
    
    # Cálculos sugeridos
    suggested_be = suggest_breakeven(estrategia, legs_data, total_premium)
    # Usamos el delta de la pata principal para la sugerencia de éxito
    main_delta = legs_data[0]["Delta"] if legs_data else 0.0
    main_side = legs_data[0]["Side"] if legs_data else "Sell"
    suggested_pop = suggest_pop(main_delta, main_side)
    
    st.markdown("### 📊 Métricas Adicionales")
    c_ad1, c_ad2 = st.columns(2)
    be_input = c_ad1.number_input("Break Even (Manual/Sugerido)", value=float(suggested_be), step=0.01)
    pop_input = c_ad2.number_input("Prob. Éxito % (Sugerida)", value=float(suggested_pop), step=0.1)
    
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
                    "Estrategia": estrategia, "Setup": setup_val, "Side": leg["Side"], "OptionType": leg["Type"], 
                    "Strike": leg["Strike"], "Delta": leg["Delta"],
                    "PrimaRecibida": p_recibida, "CostoCierre": 0.0, "Contratos": contratos,
                    "BuyingPower": bp_leg, "MaxLoss": 0.0, "BreakEven": be_input if i == 0 else 0.0, 
                    "POP": pop_input if i == 0 else 0.0,
                    "Estado": "Abierta", "Notas": f"Parte de {estrategia}",
                    "UpdatedAt": datetime.now().isoformat(), "FechaCierre": pd.NA,
                    "MaxProfitUSD": (p_recibida * contratos * 100), "ProfitPct": 0.0, "PnL_Capital_Pct": 0.0,
                    "PrecioAccionCierre": 0.0, "PnL_USD_Realizado": 0.0
                })
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame(new_rows)], ignore_index=True)
            JournalManager.save_with_backup(st.session_state.df)
            st.success("Estrategia registrada!")
            st.rerun()
            
    if st.button("🗑️ Limpiar / Cancelar Formulario"):
        st.rerun()

def main():
    st.set_page_config(page_title="STRIKELOG Pro", layout="wide")
    if "df" not in st.session_state:
        st.session_state.df = JournalManager.load_data()
        
    page = st.sidebar.radio("Navegación", ["Dashboard", "Nueva Operación", "Cartera Activa", "Historial", "Datos / Edición"])
    
    if page == "Dashboard": render_dashboard(st.session_state.df)
    elif page == "Nueva Operación": render_new_trade()
    elif page == "Cartera Activa": render_active_portfolio(st.session_state.df)
def render_history(df):
    st.header("📜 Historial de Operaciones")
    
    # --- Datos de base ---
    hist_df = df[df["Estado"] != "Abierta"].copy()
    if hist_df.empty:
        st.info("Aún no hay operaciones cerradas en el historial.")
        return
        
    # Aseguramos que FechaCierre sea comparable de forma segura
    hist_df["__dt_sort"] = pd.to_datetime(hist_df["FechaCierre"], errors='coerce')
    
    # Alerta de trades sin fecha (como JBLU antes del fix)
    undated = hist_df[hist_df["FechaCierre"].isna()]
    if not undated.empty:
        st.warning(f"⚠️ Se han detectado {len(undated)} operaciones cerradas sin fecha de cierre. Aparecerán al final de la lista.")

    # --- Filtros de Historial ---
    c1, c2, c3 = st.columns(3)
    hist_tickers = ["Todos"] + sorted(hist_df["Ticker"].unique().tolist())
    t_filt = c1.selectbox("Filtrar Ticker", hist_tickers, key="hist_t")
    
    hist_setup = ["Todos"] + SETUPS
    s_filt = c2.selectbox("Filtrar Setup", hist_setup, key="hist_s")
    
    hist_strat = ["Todos"] + ESTRATEGIAS
    e_filt = c3.selectbox("Filtrar Estrategia", hist_strat, key="hist_e")

    # Filtro de Fecha robusto
    st.markdown("📅 **Filtrar por Rango de Cierre**")
    valid_dates = hist_df["__dt_sort"].dropna()
    fecha_min_val = valid_dates.min().date() if not valid_dates.empty else (date.today() - timedelta(days=30))
    date_range = st.date_input("Rango de fechas", [fecha_min_val, date.today()], key="hist_d")
    
    # Aplicar filtros
    if t_filt != "Todos": hist_df = hist_df[hist_df["Ticker"] == t_filt]
    if s_filt != "Todos": hist_df = hist_df[hist_df["Setup"] == s_filt]
    if e_filt != "Todos": hist_df = hist_df[hist_df["Estrategia"] == e_filt]
    
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        # Comparación usando Timestamps para evitar el TypeError
        start_ts = pd.Timestamp(date_range[0])
        end_ts = pd.Timestamp(date_range[1]) + pd.Timedelta(hours=23, minutes=59, seconds=59)
        # Incluimos los que están en rango O los que no tienen fecha si el usuario está buscando un ticker específico
        if t_filt != "Todos":
            hist_df = hist_df[(hist_df["__dt_sort"].isna()) | ((hist_df["__dt_sort"] >= start_ts) & (hist_df["__dt_sort"] <= end_ts))]
        else:
            hist_df = hist_df[(hist_df["__dt_sort"] >= start_ts) & (hist_df["__dt_sort"] <= end_ts)]
    
    if hist_df.empty:
        st.info("No hay operaciones que coincidan con los filtros seleccionados.")
        return

    # Preparar visualización amigable
    display_df = hist_df.copy()
    display_df = display_df.sort_values("__dt_sort", ascending=False, na_position='last')
    display_df["% Gestión"] = display_df["ProfitPct"].map("{:.1f}%".format)
    display_df["PnL USD"] = display_df["PnL_USD_Realizado"].map("${:,.2f}".format)
    display_df["Prima"] = display_df["PrimaRecibida"].map("${:,.2f}".format)
    
    # Mapear nombres internos a nombres visibles para la UI
    display_df = display_df.rename(columns={
        "POP": "Prob. Éxito %",
        "PrecioAccionCierre": "Precio Acción Cierre"
    })
    
    # Columnas a mostrar
    view_cols = [
        "Ticker", "FechaCierre", "PnL USD", "Prima", "% Gestión", "Estrategia", "Setup", 
        "Contratos", "BuyingPower", "Side", "OptionType", "Strike", 
        "Prob. Éxito %", "FechaApertura", "Expiry", "Precio Acción Cierre"
    ]
    
    st.dataframe(display_df[view_cols], width="stretch", hide_index=True)

def main():
    st.set_page_config(page_title="STRIKELOG Pro", layout="wide")
    if "df" not in st.session_state:
        st.session_state.df = JournalManager.load_data()
        
    page = st.sidebar.radio("Navegación", ["Dashboard", "Nueva Operación", "Cartera Activa", "Historial", "Datos / Edición"])
    
    if page == "Dashboard": render_dashboard(st.session_state.df)
    elif page == "Nueva Operación": render_new_trade()
    elif page == "Cartera Activa": render_active_portfolio(st.session_state.df)
    elif page == "Historial": render_history(st.session_state.df)
        
    elif page == "Datos / Edición":
        st.header("🛠️ Gestión de Datos")
        tab1, tab2 = st.tabs(["📄 Ver Todo", "✏️ Editar"])
        with tab1:
            st.dataframe(st.session_state.df, width="stretch")
        with tab2:
            all_ids = ["--- Seleccione un ID ---"] + sorted(st.session_state.df["ID"].tolist())
            # Usamos un key para poder resetear el selectbox programáticamente
            trade_id = st.selectbox("Seleccione el ID del trade que desea modificar:", all_ids, key="edit_selector")
            
            if trade_id != "--- Seleccione un ID ---":
                idx = st.session_state.df.index[st.session_state.df["ID"] == trade_id][0]
                row = st.session_state.df.iloc[idx]
            
                with st.form("edit_form"):
                    c1, c2, c3, c4, c5 = st.columns(5)
                    n_ticker = c1.text_input("Ticker", row["Ticker"])
                    n_side = c2.selectbox("Side", SIDES, index=SIDES.index(row["Side"]) if row["Side"] in SIDES else 0)
                    n_type = c3.selectbox("Type", OPTION_TYPES, index=OPTION_TYPES.index(row["OptionType"]) if row["OptionType"] in OPTION_TYPES else 0)
                    n_strike = c4.number_input("Strike", value=float(row["Strike"]))
                    n_delta = c5.number_input("Delta", value=float(row["Delta"]), step=0.01)
                    
                    ce1, ce2 = st.columns(2)
                    n_setup = ce1.selectbox("Setup", SETUPS, index=SETUPS.index(row["Setup"]) if "Setup" in row and row["Setup"] in SETUPS else 0)
                    n_estatue = ce2.selectbox("Estrategia", ESTRATEGIAS, index=ESTRATEGIAS.index(row["Estrategia"]) if row["Estrategia"] in ESTRATEGIAS else 0)
                    
                    c6, c7, c8, c8_2, c8_3 = st.columns(5)
                    n_prima = c6.number_input("Prima Recibida", value=float(row["PrimaRecibida"]))
                    n_costo = c7.number_input("Costo Cierre (Prima)", value=float(row["CostoCierre"]))
                    n_contracts = c8.number_input("Contratos", value=int(row["Contratos"]), min_value=1)
                    n_bp = c8_2.number_input("Buying Power", value=float(row["BuyingPower"]))
                    n_stock_close = c8_3.number_input("Precio Acción Cierre", value=float(row["PrecioAccionCierre"]))
                    
                    cd1, cd2, cd3 = st.columns(3)
                    n_fecha_ap = cd1.date_input("Fecha Apertura", value=pd.to_datetime(row["FechaApertura"]).date())
                    n_expiry = cd2.date_input("Fecha Vencimiento", value=pd.to_datetime(row["Expiry"]).date())
                    n_fecha_cl = cd3.date_input("Fecha Cierre", value=pd.to_datetime(row["FechaCierre"]).date() if not pd.isna(row["FechaCierre"]) else date.today())
                    
                    c9, c10, c11, c12 = st.columns(4)
                    n_pnl_usd = c9.number_input("PnL USD Realizado", value=float(row["PnL_USD_Realizado"]))
                    n_be = c10.number_input("Break Even", value=float(row["BreakEven"]))
                    n_pop = c11.number_input("Prob. Éxito %", value=float(row["POP"]))
                    n_estado = c12.selectbox("Estado", ESTADOS, index=ESTADOS.index(row["Estado"]))

                    if row["Estado"] != "Abierta":
                        st.info(f"💡 Este trade tiene un beneficio del **{row['ProfitPct']:.1f}%** sobre la prima original.")
                    
                    n_notas = st.text_area("Notas", row["Notas"])
                    
                    if st.form_submit_button("Guardar Cambios"):
                        st.session_state.df.at[idx, "Ticker"] = n_ticker
                        st.session_state.df.at[idx, "Side"] = n_side
                        st.session_state.df.at[idx, "OptionType"] = n_type
                        st.session_state.df.at[idx, "Strike"] = n_strike
                        st.session_state.df.at[idx, "Delta"] = n_delta
                        st.session_state.df.at[idx, "Setup"] = n_setup
                        st.session_state.df.at[idx, "Estrategia"] = n_estatue
                        st.session_state.df.at[idx, "FechaApertura"] = n_fecha_ap
                        st.session_state.df.at[idx, "Expiry"] = n_expiry
                        st.session_state.df.at[idx, "FechaCierre"] = n_fecha_cl.strftime("%Y-%m-%d") if n_estado != "Abierta" else pd.NA
                        st.session_state.df.at[idx, "PrimaRecibida"] = n_prima
                        st.session_state.df.at[idx, "CostoCierre"] = n_costo
                        st.session_state.df.at[idx, "Contratos"] = n_contracts
                        st.session_state.df.at[idx, "BuyingPower"] = n_bp
                        st.session_state.df.at[idx, "PrecioAccionCierre"] = n_stock_close
                        st.session_state.df.at[idx, "PnL_USD_Realizado"] = n_pnl_usd
                        st.session_state.df.at[idx, "BreakEven"] = n_be
                        st.session_state.df.at[idx, "POP"] = n_pop
                        st.session_state.df.at[idx, "Notas"] = n_notas
                        st.session_state.df.at[idx, "Estado"] = n_estado
                        
                        st.session_state.df.at[idx, "MaxProfitUSD"] = n_prima * n_contracts * 100
                        if n_estado != "Abierta":
                            total_gross_premium = n_prima * n_contracts * 100
                            if total_gross_premium != 0:
                                st.session_state.df.at[idx, "ProfitPct"] = (n_pnl_usd / total_gross_premium) * 100
                            else:
                                st.session_state.df.at[idx, "ProfitPct"] = 0.0
                        else:
                            st.session_state.df.at[idx, "ProfitPct"] = 0.0

                        JournalManager.save_with_backup(st.session_state.df)
                        st.success("¡Actualizado con éxito!")
                        st.rerun()

                if st.button("⬅️ Volver a la Lista / Cancelar"):
                    # Al borrar la key del selectbox y hacer rerun, se resetea a la posición original
                    del st.session_state["edit_selector"]
                    st.rerun()

if __name__ == "__main__":
    main()
