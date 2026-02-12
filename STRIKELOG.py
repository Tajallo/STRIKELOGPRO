import streamlit as st
import pandas as pd
import os
import shutil
import re
from datetime import date, datetime, timedelta
from uuid import uuid4
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components

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
    "Estrategia", "Setup", "Tags", "Side", "OptionType", "Strike", "Delta", "PrimaRecibida", "CostoCierre", "Contratos", 
    "BuyingPower", "BreakEven", "BreakEven_Upper", "POP",
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

# Estrategias que tienen dos Break Even (zona de beneficio entre dos strikes)
DUAL_BE_STRATEGIES = ["Iron Condor", "Iron Fly", "Strangle", "Straddle", "Butterfly", "Broken Wing Butterfly (BWB)"]

# Auto-populate de patas según estrategia (Side, OptionType por pata)
LEG_DEFAULTS = {
    "CSP (Cash Secured Put)": [("Sell", "Put")],
    "CC (Covered Call)": [("Sell", "Call")],
    "Put Credit Spread": [("Sell", "Put"), ("Buy", "Put")],
    "Call Credit Spread": [("Sell", "Call"), ("Buy", "Call")],
    "Put Debit Spread": [("Buy", "Put"), ("Sell", "Put")],
    "Call Debit Spread": [("Buy", "Call"), ("Sell", "Call")],
    "Iron Condor": [("Sell", "Put"), ("Buy", "Put"), ("Sell", "Call"), ("Buy", "Call")],
    "Iron Fly": [("Sell", "Put"), ("Buy", "Put"), ("Sell", "Call"), ("Buy", "Call")],
    "Butterfly": [("Buy", "Call"), ("Sell", "Call"), ("Buy", "Call")],
    "Broken Wing Butterfly (BWB)": [("Buy", "Put"), ("Sell", "Put"), ("Buy", "Put")],
    "Strangle": [("Sell", "Put"), ("Sell", "Call")],
    "Straddle": [("Sell", "Put"), ("Sell", "Call")],
    "Collar": [("Sell", "Call"), ("Buy", "Put")],
    "Long Call": [("Buy", "Call")],
    "Long Put": [("Buy", "Put")],
    "Calendar": [("Sell", "Put"), ("Buy", "Put")],
    "Diagonal": [("Sell", "Put"), ("Buy", "Put")],
    "Ratio Spread": [("Sell", "Put"), ("Buy", "Put")],
    "Backspread": [("Buy", "Put"), ("Sell", "Put")],
}

# ----------------------------
# Gestión de Datos
# ----------------------------
class JournalManager:
    @staticmethod
    def save_with_backup(df: pd.DataFrame) -> pd.DataFrame:
        try:
            if os.path.exists(FILE_NAME):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy(FILE_NAME, f"{BACKUP_DIR}/journal_{timestamp}.csv.bak")
            df = JournalManager.normalize_df(df)
            df.to_csv(FILE_NAME, index=False)
            return df
        except PermissionError:
            st.error(f"❌ Error al guardar: El archivo '{FILE_NAME}' está bloqueado. Ciérralo si lo tienes abierto en Excel.")
        except Exception as e:
            st.error(f"❌ Error al guardar: {e}")
        return df

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
                elif c == "Tags": df[c] = ""
                elif c in ["BuyingPower", "BreakEven", "BreakEven_Upper", "POP", "Delta", "PnL_Capital_Pct", "PrecioAccionCierre", "PnL_USD_Realizado"]: df[c] = 0.0
                else: df[c] = pd.NA
        
        df = df[COLUMNS].copy()
        df["FechaApertura"] = pd.to_datetime(df["FechaApertura"], errors='coerce')
        df["Expiry"] = pd.to_datetime(df["Expiry"], errors='coerce')
        df["FechaCierre"] = pd.to_datetime(df["FechaCierre"], errors='coerce')
        
        # Forzar tipo datetime64[ns] para compatibilidad total con Arrow
        df["FechaApertura"] = df["FechaApertura"].fillna(pd.Timestamp.now().normalize())
        df["Expiry"] = df["Expiry"].fillna(pd.Timestamp.now().normalize())
        
        numeric_cols = ["PrimaRecibida", "CostoCierre", "BuyingPower", "BreakEven", "BreakEven_Upper", "POP", "Delta", "MaxProfitUSD", "ProfitPct", "PnL_Capital_Pct", "PrecioAccionCierre", "PnL_USD_Realizado"]
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

# Estrategias cuya prima neta es un CRÉDITO recibido (estrategias vendedoras / neutrales)
CREDIT_STRATEGIES = [
    "CSP (Cash Secured Put)", "CC (Covered Call)", "Collar",
    "Put Credit Spread", "Call Credit Spread",
    "Iron Condor", "Iron Fly",
    "Strangle", "Straddle",
    "Ratio Spread",
]

def detect_strategy_direction(strategy, side_first_leg="Sell"):
    """
    Detecta si una estrategia opera en CRÉDITO (Sell) o DÉBITO (Buy).
    Devuelve 'Sell' para crédito, 'Buy' para débito.
    """
    if strategy in CREDIT_STRATEGIES:
        return "Sell"
    # Para estrategias dual/ambiguas, usar la dirección de la primera pata
    if strategy in ["Custom / Other", "Calendar", "Diagonal"]:
        return side_first_leg
    return "Buy"

def calculate_pnl_metrics(prima_neta, costo_cierre_neto, contracts, strategy, bp=0.0, side_first_leg="Sell"):
    """
    Calcula métricas de PnL de forma estandarizada.
    
    TODOS los precios son POR ACCIÓN (ej: 1.50, NO 150).
    Para multi-pata (Iron Condor, Spreads, etc.), tanto prima_neta como 
    costo_cierre_neto representan el NETO de todas las patas combinadas.
    
    Args:
        prima_neta: Prima neta recibida/pagada por acción (valor del contrato)
        costo_cierre_neto: Costo neto para cerrar por acción
        contracts: Número de contratos
        strategy: Nombre de la estrategia (para detectar crédito/débito)
        bp: Buying Power reservado (para calcular RoC)
        side_first_leg: Side de la primera pata (fallback para estrategias ambiguas)
    
    Returns:
        (pnl_usd, profit_pct, pnl_capital_pct)
    """
    direction = detect_strategy_direction(strategy, side_first_leg)
    
    if direction == "Sell":
        # Crédito: ganas si el costo de cierre es menor que la prima cobrada
        pnl_usd = (prima_neta - costo_cierre_neto) * contracts * 100
        profit_pct = ((prima_neta - costo_cierre_neto) / prima_neta * 100) if prima_neta > 0 else 0.0
    else:
        # Débito: ganas si el precio de cierre es mayor que lo que pagaste
        pnl_usd = (costo_cierre_neto - prima_neta) * contracts * 100
        profit_pct = ((costo_cierre_neto - prima_neta) / prima_neta * 100) if prima_neta > 0 else 0.0
        
    pnl_capital_pct = (pnl_usd / bp * 100) if bp > 0 else 0.0
    return pnl_usd, profit_pct, pnl_capital_pct

def suggest_breakeven(strategy, legs_data, total_premium):
    """
    Calcula Break Even(s) según la estrategia.
    Devuelve una tupla (be_lower, be_upper).
    - Para estrategias de un solo BE: be_upper será 0.0
    - Para estrategias duales: ambos valores estarán poblados
    
    Estrategias duales: Iron Condor, Iron Fly, Butterfly, BWB, Strangle, Straddle
    """
    if not legs_data:
        return (0.0, 0.0)
    
    try:
        premium = abs(total_premium)
        
        # --- IRON CONDOR (4 patas): Sell Put + Buy Put + Sell Call + Buy Call ---
        if strategy == "Iron Condor":
            # Identificar Short Put y Short Call por sus propiedades
            short_put_strike = None
            short_call_strike = None
            for leg in legs_data:
                s = leg.get("Side", "")
                t = leg.get("Type", leg.get("OptionType", ""))
                strike = float(leg.get("Strike", 0))
                if s == "Sell" and t == "Put" and strike > 0:
                    short_put_strike = strike
                elif s == "Sell" and t == "Call" and strike > 0:
                    short_call_strike = strike
            
            if short_put_strike and short_call_strike:
                return (short_put_strike - premium, short_call_strike + premium)
            # Fallback: usar strikes ordenados (patas 1 y 2 suelen ser los shorts)
            strikes = sorted([float(l.get("Strike", 0)) for l in legs_data if float(l.get("Strike", 0)) > 0])
            if len(strikes) >= 4:
                return (strikes[1] - premium, strikes[2] + premium)
            return (0.0, 0.0)
        
        # --- IRON FLY (4 patas): Short Straddle ATM + Long Strangle OTM ---
        if strategy == "Iron Fly":
            short_strikes = []
            for leg in legs_data:
                if leg.get("Side") == "Sell":
                    short_strikes.append(float(leg.get("Strike", 0)))
            if short_strikes:
                atm = short_strikes[0]  # Ambos shorts suelen estar en el mismo strike
                return (atm - premium, atm + premium)
            return (0.0, 0.0)
        
        # --- BUTTERFLY (3 patas): Buy 1 + Sell 2 (ATM) + Buy 1 ---
        if "Butterfly" in strategy:
            strikes = sorted([float(l.get("Strike", 0)) for l in legs_data if float(l.get("Strike", 0)) > 0])
            if len(strikes) >= 3:
                # BE inferior = strike más bajo + débito pagado
                # BE superior = strike más alto - débito pagado
                return (strikes[0] + premium, strikes[-1] - premium)
            return (0.0, 0.0)
        
        # --- STRANGLE (2 patas): Put + Call a diferentes strikes ---
        if strategy == "Strangle":
            put_strike = None
            call_strike = None
            for leg in legs_data:
                t = leg.get("Type", leg.get("OptionType", ""))
                strike = float(leg.get("Strike", 0))
                if t == "Put" and strike > 0:
                    put_strike = strike
                elif t == "Call" and strike > 0:
                    call_strike = strike
            if put_strike and call_strike:
                main_side = legs_data[0].get("Side", "Sell")
                if main_side == "Sell":
                    return (put_strike - premium, call_strike + premium)
                else:
                    return (put_strike - premium, call_strike + premium)
            return (0.0, 0.0)
        
        # --- STRADDLE (2 patas): Put + Call al mismo strike ---
        if strategy == "Straddle":
            strike = float(legs_data[0].get("Strike", 0))
            if strike > 0:
                return (strike - premium, strike + premium)
            return (0.0, 0.0)
        
        # --- COLLAR (2 patas): Sell Call + Buy Put (o viceversa) ---
        if strategy == "Collar":
            put_strike = None
            call_strike = None
            for leg in legs_data:
                t = leg.get("Type", leg.get("OptionType", ""))
                strike = float(leg.get("Strike", 0))
                if t == "Put" and strike > 0:
                    put_strike = strike
                elif t == "Call" and strike > 0:
                    call_strike = strike
            if put_strike and call_strike:
                return (put_strike + premium, call_strike - premium)
            return (0.0, 0.0)
        
        # --- ESTRATEGIAS SIMPLES (1 BE) ---
        main_strike = float(legs_data[0].get("Strike", 0))
        
        # Put Credit Spread / CSP
        if "Put Credit Spread" in strategy or "CSP" in strategy:
            # Buscar el Short Put strike específicamente
            for leg in legs_data:
                if leg.get("Side") == "Sell":
                    main_strike = float(leg.get("Strike", main_strike))
                    break
            return (main_strike - premium, 0.0)
        
        # Call Credit Spread / CC
        if "Call Credit Spread" in strategy or "CC" in strategy:
            for leg in legs_data:
                if leg.get("Side") == "Sell":
                    main_strike = float(leg.get("Strike", main_strike))
                    break
            return (main_strike + premium, 0.0)
        
        # Put Debit Spread
        if "Put Debit Spread" in strategy:
            for leg in legs_data:
                if leg.get("Side") == "Buy":
                    main_strike = float(leg.get("Strike", main_strike))
                    break
            return (main_strike - premium, 0.0)
        
        # Call Debit Spread
        if "Call Debit Spread" in strategy:
            for leg in legs_data:
                if leg.get("Side") == "Buy":
                    main_strike = float(leg.get("Strike", main_strike))
                    break
            return (main_strike + premium, 0.0)
        
        # Long Put
        if strategy == "Long Put":
            return (main_strike - premium, 0.0)
        
        # Long Call
        if strategy == "Long Call":
            return (main_strike + premium, 0.0)
        
        # Calendar / Diagonal - BE aproximado basado en el strike vendido
        if strategy in ["Calendar", "Diagonal"]:
            for leg in legs_data:
                if leg.get("Side") == "Sell":
                    main_strike = float(leg.get("Strike", main_strike))
                    break
            t = legs_data[0].get("Type", legs_data[0].get("OptionType", "Put"))
            if t == "Put":
                return (main_strike - premium, 0.0)
            else:
                return (main_strike + premium, 0.0)
        
        # Ratio Spread / Backspread - BE simple basado en dirección
        if strategy in ["Ratio Spread", "Backspread"]:
            t = legs_data[0].get("Type", legs_data[0].get("OptionType", "Put"))
            if t == "Put":
                return (main_strike - premium, 0.0)
            else:
                return (main_strike + premium, 0.0)
        
        # Fallback genérico
        t = legs_data[0].get("Type", legs_data[0].get("OptionType", "Put"))
        if t == "Put":
            return (main_strike - premium, 0.0)
        else:
            return (main_strike + premium, 0.0)
            
    except Exception:
        return (0.0, 0.0)

def suggest_pop(delta, side):
    """Calcula la probabilidad de éxito aproximada basada en el Delta."""
    abs_delta = abs(delta)
    if side == "Sell":
        return round((1.0 - abs_delta) * 100, 1)
    else:
        return round(abs_delta * 100, 1)

def leg_color_label(side, option_type):
    """Genera una etiqueta HTML coloreada para identificar visualmente cada pata."""
    if side == "Sell":
        bg = "#e74c3c"
        border = "#c0392b"
    else:
        bg = "#27ae60"
        border = "#1e8449"
    return (
        f"<span style='background:{bg}; color:white; padding:4px 12px; "
        f"border-radius:6px; font-size:13px; font-weight:700; "
        f"border:1px solid {border}; letter-spacing:0.5px;'"
        f">{side} {option_type}</span>"
    )

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
        c_f1, c_f2, c_f3, c_f4 = st.columns([1, 1, 1, 1])
        all_tickers = ["Todos Tickers"] + sorted(df["Ticker"].unique().tolist())
        ticker_filter = c_f1.selectbox("🔍 Ticker", all_tickers)
        
        meses = {
            "Todo el Historial": "Todos",
            "Hoy": "today",
            "Esta Semana": "week",
            "Este Mes": datetime.now().strftime("%Y-%m"),
            "Mes Pasado": (datetime.now().replace(day=1) - timedelta(days=1)).strftime("%Y-%m"),
            "Este Año": datetime.now().strftime("%Y")
        }
        periodo_filter = c_f2.selectbox("📅 Periodo", list(meses.keys()))
        setup_filter = c_f3.selectbox("🎯 Setup", ["Todos los Setups"] + SETUPS)
        estado_filter = c_f4.selectbox("📋 Estado", ["Todos"] + ESTADOS)
        
        # Aplicar Filtros
        df_view = df.copy()
        if ticker_filter != "Todos Tickers":
            df_view = df_view[df_view["Ticker"] == ticker_filter]
        
        if periodo_filter != "Todo el Historial":
            filtro_val = meses[periodo_filter]
            if filtro_val == "today":
                today_str = date.today().isoformat()
                df_view = df_view[pd.to_datetime(df_view["FechaApertura"]).dt.date == date.today()]
            elif filtro_val == "week":
                week_start = date.today() - timedelta(days=date.today().weekday())  # Lunes
                df_view = df_view[pd.to_datetime(df_view["FechaApertura"]).dt.date >= week_start]
            else:
                fmt = "%Y-%m" if len(filtro_val) == 7 else "%Y"
                df_view["FechaFiltro"] = pd.to_datetime(df_view["FechaApertura"]).dt.strftime(fmt)
                df_view = df_view[df_view["FechaFiltro"] == filtro_val]
            
        if setup_filter != "Todos los Setups":
            df_view = df_view[df_view["Setup"] == setup_filter]
        
        if estado_filter != "Todos":
            df_view = df_view[df_view["Estado"] == estado_filter]
        
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
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("PnL Realizado", f"${pnl_total:,.2f}", delta=f"${pnl_total:,.2f}" if pnl_total != 0 else None)
        m2.metric("Win Rate", f"{win_rate:.1f}%", help="Porcentaje de operaciones positivas")
        m3.metric("Profit Factor", f"{profit_factor:.2f}x", help="Ratio Ganancia Total / Pérdida Total")
        m4.metric("Captura Media", f"{capture_eff:.1f}%", help="Promedio de beneficio sobre la prima recibida")
        
        # Drawdown máximo
        if not closed_trades.empty:
            sorted_closed = closed_trades.sort_values("FechaCierre")
            equity_series = sorted_closed["PnL_USD_Realizado"].cumsum()
            running_max = equity_series.cummax()
            drawdown = running_max - equity_series
            max_dd = drawdown.max()
        else:
            max_dd = 0.0
        m5.metric("Max Drawdown", f"-${max_dd:,.2f}", help="Mayor caída desde un pico de equidad")
        
        # Racha actual (Streak)
        if not closed_trades.empty:
            sorted_for_streak = closed_trades.sort_values("FechaCierre", ascending=False)
            streak = 0
            streak_type = None
            for _, t in sorted_for_streak.iterrows():
                pnl_val = t["PnL_USD_Realizado"]
                if pnl_val == 0:
                    continue
                current_type = "win" if pnl_val > 0 else "loss"
                if streak_type is None:
                    streak_type = current_type
                if current_type == streak_type:
                    streak += 1
                else:
                    break
            
            if streak > 0 and streak_type:
                if streak_type == "win":
                    streak_text = f"🔥 {streak} win{'s' if streak > 1 else ''} seguido{'s' if streak > 1 else ''}"
                    streak_color = "#00ffa2"
                else:
                    streak_text = f"❄️ {streak} loss{'es' if streak > 1 else ''} seguido{'s' if streak > 1 else ''}"
                    streak_color = "#ff6b6b"
                st.markdown(f"<p style='text-align:center; font-size:16px; color:{streak_color}; margin-top:5px;'>{streak_text}</p>", unsafe_allow_html=True)
        
        st.write("") # Espaciado
        
        # Fila 2: Estadísticas de Eficiencia (colapsadas)
        with st.expander("📊 Detalle Avanzado", expanded=False):
            s1, s2, s3, s4 = st.columns(4)
            avg_profit = closed_trades["PnL_USD_Realizado"].mean() if not closed_trades.empty else 0
            s1.markdown(f"**Promedio/Trade:**<br><span style='font-size:18px; color:#00ffa2;'>${avg_profit:,.2f}</span>", unsafe_allow_html=True)
            
            best_ticker = closed_trades.groupby("Ticker")["PnL_USD_Realizado"].sum().idxmax() if not closed_trades.empty else "-"
            s2.markdown(f"**Top Ticker:**<br><span style='font-size:18px; color:#00ffa2;'>{best_ticker}</span>", unsafe_allow_html=True)
            
            total_bp_open = open_trades['BuyingPower'].sum()
            s3.markdown(f"**Capital Reservado:**<br><span style='font-size:18px; color:#ffcc00;'>${total_bp_open:,.0f}</span>", unsafe_allow_html=True)
            
            active_strats = len(open_trades["ChainID"].unique())
            s4.markdown(f"**Estrat. Activas:**<br><span style='font-size:18px; color:#00d9ff;'>{active_strats}</span>", unsafe_allow_html=True)
        
    st.write("")
    
    # --- GRÁFICOS PRINCIPALES ---
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

    # Rendimiento Mensual (siempre visible, es el segundo gráfico más importante)
    if not closed_trades.empty:
        st.markdown("### 📅 Rendimiento Mensual")
        closed_trades['Mes'] = pd.to_datetime(closed_trades['FechaCierre']).dt.strftime('%b %Y')
        monthly_pnl = closed_trades.groupby('Mes')['PnL_USD_Realizado'].sum().reset_index()
        
        fig_monthly = px.bar(monthly_pnl, x='Mes', y='PnL_USD_Realizado', 
                             color='PnL_USD_Realizado', 
                             color_continuous_scale="RdYlGn",
                             template="plotly_dark")
        fig_monthly.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title=None,
            yaxis_title="PnL USD",
            coloraxis_showscale=False
        )
        st.plotly_chart(fig_monthly, width="stretch")

    # Gráficos de análisis por categoría (colapsados)
    with st.expander("🔍 Análisis por Categoría", expanded=False):
        col_cat1, col_cat2 = st.columns(2)
        
        with col_cat1:
            st.markdown("#### 🎯 PnL por Estrategia")
            if not df_view.empty:
                strat_data = df_view.groupby("Estrategia")["PnL_USD_Realizado"].sum().reset_index()
                strat_data = strat_data.sort_values("PnL_USD_Realizado", ascending=True)
                
                fig_strat = px.bar(strat_data, x="PnL_USD_Realizado", y="Estrategia", 
                                   orientation='h', color="PnL_USD_Realizado",
                                   color_continuous_scale="RdYlGn",
                                   template="plotly_dark")
                fig_strat.update_layout(
                    height=350, 
                    showlegend=False, 
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis_title="PnL USD",
                    yaxis_title=None,
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_strat, width="stretch")
        
        with col_cat2:
            st.markdown("#### 🎯 PnL por Setup")
            if not closed_trades.empty:
                setup_data = closed_trades.groupby("Setup")["PnL_USD_Realizado"].sum().reset_index()
                setup_data = setup_data.sort_values("PnL_USD_Realizado", ascending=True)
                
                fig_setup = px.bar(setup_data, x="PnL_USD_Realizado", y="Setup",
                                   orientation='h', color="PnL_USD_Realizado",
                                   color_continuous_scale="RdYlGn",
                                   template="plotly_dark")
                fig_setup.update_layout(
                    height=350,
                    showlegend=False,
                    margin=dict(l=10, r=10, t=10, b=10),
                    xaxis_title="PnL USD",
                    yaxis_title=None,
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_setup, width="stretch")

def render_active_portfolio(df):
    st.header("📂 Cartera Activa")
    active_df = df[df["Estado"] == "Abierta"].copy()
    if active_df.empty:
        st.info("No hay posiciones abiertas.")
        return

    # Agrupación por ChainID y ordenar por DTE (más urgente primero)
    grouped = active_df.groupby("ChainID")
    
    # Pre-calcular DTE para ordenar
    chain_dte = {}
    for chain_id, group in grouped:
        expiry_val = group.iloc[0]["Expiry"]
        expiry_dt_sort = pd.to_datetime(expiry_val).date() if pd.notna(expiry_val) else date.today()
        chain_dte[chain_id] = (expiry_dt_sort - date.today()).days
    
    sorted_chains = sorted(chain_dte.keys(), key=lambda x: chain_dte[x])
    
    for chain_id in sorted_chains:
        group = active_df[active_df["ChainID"] == chain_id]
        first_row = group.iloc[0]
        ticker = first_row["Ticker"]
        strategy = first_row["Estrategia"]
        expiry = first_row["Expiry"]
        
        # Métricas agregadas del grupo
        total_bp = group["BuyingPower"].sum()
        total_premium = group["PrimaRecibida"].sum()
        
        # Asegurar que expiry es objeto fecha para el cálculo
        expiry_dt = pd.to_datetime(expiry).date() if pd.notna(expiry) else date.today()
        dte = (expiry_dt - date.today()).days
        
        # Días en Trade (DIT)
        apertura_dt = pd.to_datetime(first_row["FechaApertura"]).date() if pd.notna(first_row["FechaApertura"]) else date.today()
        dit = (date.today() - apertura_dt).days
        
        # Semáforo DTE
        dte_color = "⚪"
        if dte < 7: dte_color = "🔴"
        elif dte <= 21: dte_color = "🟡"
        else: dte_color = "🟢"
        
        # Icono de dirección crédito/débito
        strat_dir = detect_strategy_direction(strategy, first_row["Side"])
        dir_icon = "📥" if strat_dir == "Sell" else "📤"
        
        # Identificar historial de Rolls
        roll_chain = get_roll_history(df, first_row["ID"])
        num_rolls = len(roll_chain) - 1 # El actual no cuenta como roll
        
        roll_label = f" 🔄 [ROL #{num_rolls}]" if num_rolls > 0 else ""

        # Cálculos extendidos de la cadena (Rolls + Actual)
        hist_credits = sum(float(r["PrimaRecibida"] or 0) for r in roll_chain)
        # Solo restamos el costo de cierre de las operaciones que ya están cerradas (los pasos previos del roll)
        hist_debits = sum(float(r["CostoCierre"] or 0) for r in roll_chain if r["Estado"] != "Abierta")
        net_credit_chain = hist_credits - hist_debits

        realized_pnl_chain = sum(float(r["PnL_USD_Realizado"] or 0) for r in roll_chain if r["Estado"] != "Abierta")
        
        # Recálculo dinámico del Break Even REAL basado en el Crédito Neto Acumulado
        # Para estrategias duales, calculamos BE inferior y superior
        is_dual_be = strategy in DUAL_BE_STRATEGIES
        calculated_be = 0.0
        calculated_be_upper = 0.0
        
        try:
            if is_dual_be:
                # Para estrategias duales, recalcular usando los datos de las patas del grupo actual
                legs_for_be = [{"Side": r["Side"], "Type": r["OptionType"], "OptionType": r["OptionType"], 
                                "Strike": float(r["Strike"])} for _, r in group.iterrows()]
                calculated_be, calculated_be_upper = suggest_breakeven(strategy, legs_for_be, net_credit_chain)
                
                # Si el cálculo devolvió 0, usar los valores almacenados como fallback
                if calculated_be == 0.0 and calculated_be_upper == 0.0:
                    calculated_be = float(first_row["BreakEven"] or 0)
                    calculated_be_upper = float(first_row.get("BreakEven_Upper", 0) or 0)
            else:
                # Estrategias de un solo BE (lógica original mejorada)
                legs_for_be = [{"Side": first_row["Side"], "Type": first_row["OptionType"], 
                                "OptionType": first_row["OptionType"], "Strike": float(first_row["Strike"])}]
                # Para spreads, incluir ambas patas
                if len(group) > 1:
                    legs_for_be = [{"Side": r["Side"], "Type": r["OptionType"], "OptionType": r["OptionType"],
                                    "Strike": float(r["Strike"])} for _, r in group.iterrows()]
                
                calculated_be, _ = suggest_breakeven(strategy, legs_for_be, net_credit_chain)
                if calculated_be == 0.0:
                    calculated_be = float(first_row["BreakEven"] or 0)
        except Exception as e:
            calculated_be = float(first_row["BreakEven"] or 0)
            calculated_be_upper = float(first_row.get("BreakEven_Upper", 0) or 0)

        # Lógica de visualización directa (sin redondeos, con signo)
        formatted_net = f"${net_credit_chain:,.2f}"
        
        # Etiquetas para el Detalle (Métricas)
        metric_net_label = "Prima Total (Cadena)"
        metric_net_val = formatted_net
        
        # Construcción del Header Limpio
        roll_pnl_str = ""
        # Sin redondeos en PnL de rolls
        if abs(realized_pnl_chain) > 0.01:
            roll_pnl_str = f" • Rolls: ${realized_pnl_chain:,.2f}"

        # Formato con BE dual o simple según estrategia
        if is_dual_be and calculated_be_upper > 0:
            be_display = f"**BE ${calculated_be:,.2f} / ${calculated_be_upper:,.2f}**"
        else:
            be_display = f"**BE ${calculated_be:,.2f}**"
        
        header_text = f"{dte_color}{dir_icon}{roll_label} **{ticker}** • {strategy} • {dte}d (DIT:{dit}d) • {be_display} • Prima: {formatted_net}{roll_pnl_str}"
        
        with st.expander(header_text, expanded=False):
            # Vista resumen de la estrategia
            if is_dual_be and calculated_be_upper > 0:
                st.caption(f"📅 Vencimiento: {expiry_dt} | DIT: {dit}d | BP Reservado: ${total_bp:,.2f} | Zona de Max Profit: ${calculated_be:,.2f} — ${calculated_be_upper:,.2f}")
            else:
                st.caption(f"📅 Vencimiento: {expiry_dt} | DIT: {dit}d | BP Reservado: ${total_bp:,.2f} | BE Original: ${float(first_row['BreakEven'] or 0):.2f}")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(metric_net_label, metric_net_val, help="Crédito neto total (Suma primas - Costos cierre históricos).")
            if is_dual_be and calculated_be_upper > 0:
                c2.metric("BE Campaña (↓ / ↑)", f"${calculated_be:,.2f} / ${calculated_be_upper:,.2f}", help="BEs inferior y superior ajustados con rolls.")
            else:
                c2.metric("Break Even (Campaña)", f"${calculated_be:,.2f}", help="BE ajustado considerando pérdidas/ganancias de rolls anteriores.")
            c3.metric("Capital Reservado", f"${total_bp:,.2f}")
            c4.metric("PnL Realizado (Rolls)", f"${realized_pnl_chain:,.2f}", delta=realized_pnl_chain if realized_pnl_chain != 0 else None)
            
            if num_rolls > 0:
                st.markdown("#### 🕒 Historial de esta posición")
                # Mostrar el camino desde el origen
                reversed_chain = list(reversed(roll_chain))
                origin = reversed_chain[0]
                
                # Resumen de evolución
                origin_date = pd.to_datetime(origin['FechaApertura']).strftime("%Y-%m-%d")
                st.info(f"📍 **Origen:** Abierto el `{origin_date}` con Strike `{origin['Strike']} {origin['OptionType']}`.")
                
                # Pequeña tabla con la evolución
                hist_data = []
                for i, r in enumerate(reversed_chain):
                    label = "ORIGEN" if i == 0 else f"ROL #{i}"
                    f_apertura = pd.to_datetime(r["FechaApertura"]).strftime("%Y-%m-%d")
                    hist_data.append({
                        "Etapa": label,
                        "Fecha": f_apertura,
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
            
            # Detalle de patas con badges de color
            for _, leg_row in group.iterrows():
                st.markdown(
                    f"{leg_color_label(leg_row['Side'], leg_row['OptionType'])} "
                    f"&nbsp; **Strike {leg_row['Strike']}** · "
                    f"Δ {leg_row['Delta']:.2f} · "
                    f"Prima ${leg_row['PrimaRecibida']:.2f} · "
                    f"x{leg_row['Contratos']}",
                    unsafe_allow_html=True
                )
            
            # --- NOTAS RÁPIDAS ---
            current_notes = first_row["Notas"] if pd.notna(first_row["Notas"]) else ""
            new_notes = st.text_area("📝 Notas", value=current_notes, key=f"notes_{chain_id}", height=70, help="Edita las notas de toda la estrategia aquí mismo.")
            
            if new_notes != current_notes:
                if st.button("💾 Guardar Notas", key=f"save_notes_{chain_id}"):
                    # Actualizar notas en todas las patas del ChainID
                    for idx, row in group.iterrows():
                         real_idx = df.index[df["ID"] == row["ID"]][0]
                         df.at[real_idx, "Notas"] = new_notes
                         df.at[real_idx, "UpdatedAt"] = datetime.now().isoformat()
                    
                    st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                    st.success("Notas actualizadas.")
                    st.rerun()
            
            # Acciones Rápidas para la Estrategia Completa
            c_btn_quick, c_btn_manage = st.columns(2)
            
            if c_btn_quick.button(f"⚡ Cerrar Rápido", key=f"btn_quick_{chain_id}"):
                st.session_state[f"quick_close_{chain_id}"] = True
            
            if c_btn_manage.button(f"🎯 Gestionar", key=f"btn_manage_{chain_id}"):
                st.session_state["manage_chain_id"] = chain_id
                st.rerun()
            
            # --- MINI PANEL DE CIERRE RÁPIDO ---
            if st.session_state.get(f"quick_close_{chain_id}", False):
                st.markdown("---")
                qc1, qc2, qc3 = st.columns([2, 2, 1])
                q_close_price = qc1.number_input("Cierre ($/acción)", value=0.0, step=0.01, key=f"qcp_{chain_id}")
                
                # Calcular PnL preview
                q_entry = group["PrimaRecibida"].sum()
                q_contracts = int(first_row["Contratos"])
                q_bp = group["BuyingPower"].sum()
                q_pnl, q_pct, _ = calculate_pnl_metrics(
                    q_entry, q_close_price, q_contracts, strategy, q_bp, first_row["Side"]
                )
                qc2.metric("PnL", f"${q_pnl:,.2f}", delta=f"{q_pct:.0f}%")
                
                if qc3.button("✅ Cerrar", key=f"qcc_{chain_id}", type="primary"):
                    max_profit_usd = q_entry * q_contracts * 100
                    q_profit_pct = (q_pnl / max_profit_usd * 100) if max_profit_usd > 0 else 0.0
                    
                    for idx_q, row_q in group.iterrows():
                        real_idx_q = df.index[df["ID"] == row_q["ID"]][0]
                        df.at[real_idx_q, "Estado"] = "Cerrada"
                        df.at[real_idx_q, "FechaCierre"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        if row_q["ID"] == first_row["ID"]:
                            df.at[real_idx_q, "CostoCierre"] = q_close_price
                            df.at[real_idx_q, "PnL_USD_Realizado"] = q_pnl
                            df.at[real_idx_q, "ProfitPct"] = q_profit_pct
                            df.at[real_idx_q, "PnL_Capital_Pct"] = (q_pnl / q_bp * 100) if q_bp > 0 else 0.0
                        else:
                            df.at[real_idx_q, "CostoCierre"] = 0.0
                            df.at[real_idx_q, "PnL_USD_Realizado"] = 0.0
                            df.at[real_idx_q, "ProfitPct"] = 0.0
                            df.at[real_idx_q, "PnL_Capital_Pct"] = 0.0
                    
                    st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                    # Activar post-mortem prompt
                    st.session_state["post_mortem"] = {"chain_id": chain_id, "ticker": ticker, "pnl": q_pnl}
                    del st.session_state[f"quick_close_{chain_id}"]
                    st.success(f"✅ {ticker} cerrado: ${q_pnl:,.2f}")
                    st.rerun()

    st.divider()
    
    # --- POST-MORTEM PROMPT (aparece después de cerrar un trade) ---
    if "post_mortem" in st.session_state:
        pm = st.session_state["post_mortem"]
        pm_ticker = pm.get("ticker", "")
        pm_pnl = pm.get("pnl", 0)
        pm_chain = pm.get("chain_id", "")
        
        pnl_emoji = "🟢" if pm_pnl >= 0 else "🔴"
        st.markdown(f"### {pnl_emoji} Cierre registrado: **{pm_ticker}** (${pm_pnl:,.2f})")
        
        lesson = st.text_input(
            "💡 ¿Qué aprendiste de esta operación? *(opcional)*",
            placeholder="Ej: Debí cerrar antes al llegar al 50% de captura...",
            key="post_mortem_input"
        )
        
        c_pm1, c_pm2 = st.columns([1, 1])
        if c_pm1.button("💾 Guardar lección", key="pm_save"):
            if lesson.strip():
                # Buscar las filas del trade cerrado y añadir la lección a las notas
                chain_rows = st.session_state.df[st.session_state.df["ChainID"] == pm_chain]
                for idx_pm in chain_rows.index:
                    current_notes = str(st.session_state.df.at[idx_pm, "Notas"] or "")
                    st.session_state.df.at[idx_pm, "Notas"] = f"{current_notes} [LECCIÓN] {lesson.strip()}"
                st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                st.success("📝 Lección guardada en las notas del trade.")
            del st.session_state["post_mortem"]
            st.rerun()
        
        if c_pm2.button("⏭️ Saltar", key="pm_skip"):
            del st.session_state["post_mortem"]
            st.rerun()
        
        st.divider()
    
    # Ancla invisible para scroll automático
    st.markdown("<div id='manage_panel'></div>", unsafe_allow_html=True)
    
    # Panel de Gestión (aparece si seleccionas una estrategia arriba)
    if "manage_chain_id" in st.session_state:
        # Script JS para hacer scroll al ancla
        components.html(
            """
            <script>
                // Esperamos un poco a que el DOM se renderice
                setTimeout(function() {
                    const element = window.parent.document.getElementById('manage_panel');
                    if (element) {
                        element.scrollIntoView({behavior: 'smooth', block: 'start'});
                    }
                }, 300);
            </script>
            """,
            height=0
        )
        
        target_chain = st.session_state["manage_chain_id"]
        target_group = active_df[active_df["ChainID"] == target_chain]
        
        if not target_group.empty:
            
            # Cabecera de Gestión con Botón de Cierre
            c_head1, c_head2 = st.columns([4, 1])
            c_head1.markdown(f"### 🎯 Gestión de {target_group.iloc[0]['Ticker']} ({target_group.iloc[0]['Estrategia']})")
            if c_head2.button("❌ Cerrar Panel", key="top_close_panel"):
                del st.session_state["manage_chain_id"]
                st.rerun()
            
            tab_close, tab_roll, tab_assign = st.tabs(["❌ Cerrar", "🔄 Roll", "📜 Asignación"])
            
            # --- TAB 1: CERRAR (Parcial o Total) ---
            with tab_close:
                current_strategy = target_group.iloc[0]["Estrategia"]
                is_multi_leg = len(target_group) > 1
                direction = detect_strategy_direction(current_strategy, target_group.iloc[0]["Side"])
                is_credit = (direction == "Sell")
                
                # Ayuda contextual según tipo de estrategia
                if is_multi_leg:
                    strategy_type = "Crédito" if is_credit else "Débito"
                    st.info(f"📋 **{current_strategy}** ({strategy_type}) — Precio **neto por acción** para cerrar.")
                else:
                    st.caption("Precio neto por acción para cerrar la posición.")
                
                # Resumen de tiempo en la posición
                manage_apertura = pd.to_datetime(target_group.iloc[0]["FechaApertura"]).date()
                manage_dit = (date.today() - manage_apertura).days
                st.caption(f"⏱️ Posición abierta hace **{manage_dit} días** (desde {manage_apertura})")
                
                c1, c2, c3 = st.columns(3)
                qty_to_close = c1.number_input("Contratos", min_value=1, max_value=int(target_group.iloc[0]["Contratos"]), value=int(target_group.iloc[0]["Contratos"]), step=1)
                total_close_cost = c2.number_input("Precio Cierre ($/acción)", value=0.0, step=0.01)
                stock_price = c3.number_input("Precio Subyacente", value=0.0, step=0.01, help="Opcional, para referencia.")

                is_partial = qty_to_close < int(target_group.iloc[0]["Contratos"])
                
                # Prima neta original (suma de todas las patas, que realmente solo está en pata 0)
                total_entry = target_group["PrimaRecibida"].sum()
                qty_total = int(target_group.iloc[0]["Contratos"])
                total_bp = target_group["BuyingPower"].sum()
                
                # Cálculo de PnL usando la función centralizada
                pnl_preview, profit_pct_preview, roc_preview = calculate_pnl_metrics(
                    prima_neta=total_entry,
                    costo_cierre_neto=total_close_cost,
                    contracts=qty_to_close,
                    strategy=current_strategy,
                    bp=total_bp,
                    side_first_leg=target_group.iloc[0]["Side"]
                )
                    
                st.markdown("#### 📊 Resultado")
                c_res1, c_res2, c_res3 = st.columns(3)
                c_res1.metric("PnL", f"${pnl_preview:,.2f}")
                c_res2.metric("Captura", f"{profit_pct_preview:.1f}%")
                if total_bp > 0:
                    c_res3.metric("RoC", f"{roc_preview:.1f}%")
                
                manual_pnl = st.number_input("PnL Final ($)", value=float(pnl_preview), step=1.0, help="Ajusta solo si tu broker reporta un valor diferente.")
                
                if pnl_preview < -500:
                    st.warning(f"⚠️ Atención: Estás registrando una pérdida significativa de ${pnl_preview:,.2f}")

                btn_label = "✅ Cierre Parcial" if is_partial else "✅ Cerrar Todo"
                
                # Calcular ProfitPct final basado en el PnL que realmente se va a guardar
                max_profit_usd = total_entry * qty_to_close * 100
                final_profit_pct = (manual_pnl / max_profit_usd * 100) if max_profit_usd > 0 else 0.0
                
                if st.button(btn_label, type="primary"):
                    for idx, row in target_group.iterrows():
                        real_idx = df.index[df["ID"] == row["ID"]][0]
                        
                        if is_partial:
                            # 1. Reducir contratos en la posición original
                            df.at[real_idx, "Contratos"] = qty_total - qty_to_close
                            
                            # 2. Crear nueva entrada CERRADA con la cantidad cerrada
                            new_closed_row = row.copy()
                            new_closed_row["ID"] = str(uuid4())[:8]
                            new_closed_row["Contratos"] = qty_to_close
                            new_closed_row["Estado"] = "Cerrada"
                            new_closed_row["FechaCierre"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            new_closed_row["PrecioAccionCierre"] = stock_price
                            
                            # Asignar COSTO, PNL y ProfitPct solo a la primera pata para no duplicar
                            if row["ID"] == target_group.iloc[0]["ID"]:
                                new_closed_row["CostoCierre"] = total_close_cost
                                new_closed_row["PnL_USD_Realizado"] = manual_pnl
                                new_closed_row["ProfitPct"] = final_profit_pct
                                new_closed_row["PnL_Capital_Pct"] = (manual_pnl / total_bp * 100) if total_bp > 0 else 0.0
                            else:
                                new_closed_row["CostoCierre"] = 0.0
                                new_closed_row["PnL_USD_Realizado"] = 0.0
                                new_closed_row["ProfitPct"] = 0.0
                                new_closed_row["PnL_Capital_Pct"] = 0.0
                            
                            # Añadir la fila cerrada
                            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_closed_row])], ignore_index=True)
                            
                        else:
                            # Cierre TOTAL normal
                            df.at[real_idx, "Estado"] = "Cerrada"
                            df.at[real_idx, "FechaCierre"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            df.at[real_idx, "PrecioAccionCierre"] = stock_price
                            if row["ID"] == target_group.iloc[0]["ID"]:
                                df.at[real_idx, "CostoCierre"] = total_close_cost
                                df.at[real_idx, "PnL_USD_Realizado"] = manual_pnl
                                df.at[real_idx, "ProfitPct"] = final_profit_pct
                                df.at[real_idx, "PnL_Capital_Pct"] = (manual_pnl / total_bp * 100) if total_bp > 0 else 0.0
                            else:
                                df.at[real_idx, "CostoCierre"] = 0.0
                                df.at[real_idx, "PnL_USD_Realizado"] = 0.0
                                df.at[real_idx, "ProfitPct"] = 0.0
                                df.at[real_idx, "PnL_Capital_Pct"] = 0.0
                            
                    st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                    # Activar post-mortem prompt
                    st.session_state["post_mortem"] = {"chain_id": target_chain, "ticker": target_group.iloc[0]["Ticker"], "pnl": manual_pnl}
                    del st.session_state["manage_chain_id"]
                    st.success("Operación actualizada correctamente.")
                    st.rerun()

            # --- TAB 2: ROLL ---
            with tab_roll:
                st.markdown("#### 🔄 Configuración del Roll")
                st.caption("Mueve tu posición a una nueva fecha/strike.")
                
                # Selección de patas a rolar
                legs_to_roll = []
                for idx, leg in target_group.iterrows():
                    c_sel, c_info = st.columns([1, 4])
                    should_roll = c_sel.checkbox("Rolar", value=True, key=f"check_roll_{leg['ID']}")
                    c_info.markdown(f"{leg_color_label(leg['Side'], leg['OptionType'])} &nbsp; **@ {leg['Strike']}**", unsafe_allow_html=True)
                    if should_roll:
                        legs_to_roll.append(leg)
                
                if not legs_to_roll:
                    st.warning("Selecciona al menos una pata para realizar un Roll.")
                else:
                    roll_strategy = legs_to_roll[0]["Estrategia"]
                    roll_direction = detect_strategy_direction(roll_strategy, legs_to_roll[0]["Side"])
                    is_roll_credit = (roll_direction == "Sell")
                    
                    st.divider()
                    st.markdown("#### 1. Cierre de Posición Actual")
                    
                    # Estimación de PnL basada en input
                    c_r1, c_r2 = st.columns(2)
                    roll_close_cost = c_r1.number_input("Cierre ($/acción)", value=0.0, step=0.01)
                    
                    total_entry_to_roll = sum(float(l["PrimaRecibida"]) for l in legs_to_roll)
                    qty_roll = int(legs_to_roll[0]["Contratos"]) if legs_to_roll else 1
                    roll_bp = sum(float(l["BuyingPower"]) for l in legs_to_roll)
                    
                    qty_new_roll = st.number_input("Contratos (nuevo roll)", min_value=1, value=qty_roll, step=1)
                    
                    # Dirección robusta basada en tipo de estrategia
                    dir_label = "Crédito" if is_roll_credit else "Débito"
                    st.caption(f"ℹ️ Dirección detectada: **{dir_label}** (Basado en estrategia: {roll_strategy})")

                    # Cálculo de PnL del cierre usando función centralizada
                    est_pnl_val, est_profit_pct, _ = calculate_pnl_metrics(
                        prima_neta=total_entry_to_roll,
                        costo_cierre_neto=roll_close_cost,
                        contracts=qty_roll,
                        strategy=roll_strategy,
                        bp=roll_bp,
                        side_first_leg=legs_to_roll[0]["Side"]
                    )
                    
                    roll_pnl_manual = c_r2.number_input("PnL del Cierre ($)", value=float(est_pnl_val), step=1.0, help="Ajusta si tu broker reporta un valor diferente.")
                    
                    # ProfitPct para las patas que se cierran al rolar
                    roll_max_profit = total_entry_to_roll * qty_roll * 100
                    roll_profit_pct = (roll_pnl_manual / roll_max_profit * 100) if roll_max_profit > 0 else 0.0
                    
                    st.divider()
                    st.markdown("#### 2. Nueva Posición")
                    c_n1, c_n2 = st.columns(2)
                    
                    default_date = date.today() + timedelta(days=7)
                    if pd.notna(target_group.iloc[0]["Expiry"]):
                         current_exp = pd.to_datetime(target_group.iloc[0]["Expiry"]).date()
                         if current_exp >= date.today(): default_date = current_exp + timedelta(days=7)
                    
                    new_expiry = c_n1.date_input("Nuevo Vencimiento", value=default_date)
                    new_net_premium = c_n2.number_input("Nueva Prima ($/acción)", value=0.0, step=0.01)
                    
                    if new_expiry < date.today():
                        st.error("⚠️ Error: La nueva fecha de vencimiento es en el pasado.")
                    
                    new_legs_data = []
                    for leg in legs_to_roll:
                        st.markdown(f"**Ajuste para:** {leg_color_label(leg['Side'], leg['OptionType'])}", unsafe_allow_html=True)
                        c_l1, c_l2 = st.columns(2)
                        n_strike = c_l1.number_input(f"Nuevo Strike", value=float(leg['Strike']), key=f"roll_strike_{leg['ID']}")
                        n_delta = c_l2.number_input(f"Nuevo Delta", value=float(leg['Delta']), key=f"roll_delta_{leg['ID']}")
                        
                        new_legs_data.append({
                            "Side": leg["Side"], "Type": leg["OptionType"], "Strike": n_strike, "Delta": n_delta,
                            "Contratos": qty_new_roll, "Ticker": leg["Ticker"], "Estrategia": leg["Estrategia"],
                            "OldID": leg["ID"]
                        })
                    
                    # ... [Lógica de Pre-cálculo BE insertada en pasos anteriores] ...
                    # Re-insertamos lógica de BE aquí para mantener consistencia con el bloque reemplazado
                    
                    hist_chain_be = get_roll_history(df, legs_to_roll[0]["ID"])
                    hist_credits_be = sum(float(h["PrimaRecibida"] or 0) for h in hist_chain_be)
                    hist_debits_be = sum(float(h["CostoCierre"] or 0) for h in hist_chain_be if h["Estado"] != "Abierta")
                    total_net_credit_for_be = hist_credits_be - hist_debits_be - roll_close_cost + new_net_premium
                    
                    roll_be_lower, roll_be_upper = suggest_breakeven(roll_strategy, new_legs_data, total_net_credit_for_be)
                    is_roll_dual = roll_strategy in DUAL_BE_STRATEGIES
                    
                    if is_roll_dual and roll_be_upper > 0:
                        st.info(f"📊 **Nuevo Break Even Estimado:** `${roll_be_lower:.2f}` / `${roll_be_upper:.2f}` (Crédito Neto Acumulado: `${total_net_credit_for_be:.2f}`)")
                    else:
                        st.info(f"📊 **Nuevo Break Even Estimado:** `${roll_be_lower:.2f}` (Crédito Neto Acumulado: `${total_net_credit_for_be:.2f}`)")

                    c_btn1, c_btn2 = st.columns([1, 1])
                    if c_btn1.button("🚀 Ejecutar Ajuste", type="primary"):
                        if new_expiry < date.today():
                            st.error("No se puede rolar a una fecha pasada.")
                        else:
                            # 1. Marcar ORIGINALES como Roladas
                            for leg in legs_to_roll:
                                real_idx = df.index[df["ID"] == leg["ID"]][0]
                                df.at[real_idx, "Estado"] = "Rolada"
                                df.at[real_idx, "FechaCierre"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                if leg["ID"] == legs_to_roll[0]["ID"]:
                                    df.at[real_idx, "CostoCierre"] = roll_close_cost
                                    df.at[real_idx, "PnL_USD_Realizado"] = roll_pnl_manual
                                    df.at[real_idx, "ProfitPct"] = roll_profit_pct
                                    df.at[real_idx, "PnL_Capital_Pct"] = (roll_pnl_manual / roll_bp * 100) if roll_bp > 0 else 0.0
                                else:
                                    df.at[real_idx, "CostoCierre"] = 0.0
                                    df.at[real_idx, "PnL_USD_Realizado"] = 0.0
                                    df.at[real_idx, "ProfitPct"] = 0.0
                                    df.at[real_idx, "PnL_Capital_Pct"] = 0.0

                            # 2. Crear NUEVAS filas
                            new_chain_id = str(uuid4())[:8]
                            new_rows = []
                            suggested_pop_roll = suggest_pop(new_legs_data[0]["Delta"], new_legs_data[0]["Side"])
                            original_bp = target_group["BuyingPower"].sum() # Mantenemos BP, usuario puede editar luego

                            for i, n_leg in enumerate(new_legs_data):
                                p_recibida = new_net_premium if i == 0 else 0.0
                                new_rows.append({
                                    "ID": str(uuid4())[:8], "ChainID": new_chain_id, "ParentID": n_leg["OldID"],
                                    "Ticker": n_leg["Ticker"], "FechaApertura": pd.Timestamp.now().normalize(), "Expiry": pd.to_datetime(new_expiry).normalize(),
                                    "Estrategia": n_leg["Estrategia"], "Side": n_leg["Side"], "OptionType": n_leg["Type"], 
                                    "Strike": n_leg["Strike"], "Delta": n_leg["Delta"],
                                    "PrimaRecibida": p_recibida, "CostoCierre": 0.0, "Contratos": n_leg["Contratos"],
                                    "BuyingPower": original_bp if i == 0 else 0.0, 
                                    "BreakEven": roll_be_lower if i == 0 else 0.0,
                                    "BreakEven_Upper": roll_be_upper if i == 0 else 0.0,
                                    "POP": suggested_pop_roll if i == 0 else 0.0,
                                    "Estado": "Abierta", "Notas": f"Roll (x{n_leg['Contratos']}) desde ID {n_leg['OldID'][:4]}",
                                    "UpdatedAt": datetime.now().isoformat(), "FechaCierre": pd.NA,
                                    "MaxProfitUSD": (p_recibida * n_leg["Contratos"] * 100), "ProfitPct": 0.0, "PnL_Capital_Pct": 0.0,
                                    "PrecioAccionCierre": 0.0, "PnL_USD_Realizado": 0.0
                                })
                            
                            if new_rows:
                                st.session_state.df = pd.concat([st.session_state.df.dropna(how='all', axis=0), pd.DataFrame(new_rows)], ignore_index=True)
                            
                            st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                            del st.session_state["manage_chain_id"]
                            st.success("Roll ejecutado con éxito.")
                            st.rerun()
            
            # --- TAB 3: ASIGNACIÓN ---
            with tab_assign:
                st.markdown("#### 📜 Asignación")
                st.warning("Marca la estrategia como 'Asignada'.")
                
                c_a1, c_a2 = st.columns(2)
                assign_price = c_a1.number_input("Strike (Precio Asignación)", value=float(target_group.iloc[0]["Strike"]), disabled=True)
                assign_fee = c_a2.number_input("Comisiones ($)", value=0.0)
                
                st.info(f"Se te asignarán {int(target_group.iloc[0]['Contratos']) * 100} acciones de {target_group.iloc[0]['Ticker']} a ${assign_price:.2f}.")
                
                if st.button("Confirmar Asignación", type="primary"):
                    for idx, row in target_group.iterrows():
                        real_idx = df.index[df["ID"] == row["ID"]][0]
                        df.at[real_idx, "Estado"] = "Asignada"
                        df.at[real_idx, "FechaCierre"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        df.at[real_idx, "MaxProfitUSD"] = 0.0 # Reseteamos MaxProfit ya que cambió la naturaleza
                        
                        # En asignación, el PnL de la OPCIÓN suele ser la prima completa que te quedas (si es short)
                        # Pero el "Costo" real es la compra de acciones. 
                        # Simplificación: PnL Realizado = Prima Recibida (ya que la opción expiró/se ejerció) - Comisiones
                        if row["ID"] == target_group.iloc[0]["ID"]:
                            pnl_assign = (row["PrimaRecibida"] * row["Contratos"] * 100) - assign_fee
                            df.at[real_idx, "PnL_USD_Realizado"] = pnl_assign
                            df.at[real_idx, "Notas"] = str(row["Notas"]) + f" [ASIGNADA a {assign_price}]"
                        else:
                            df.at[real_idx, "PnL_USD_Realizado"] = 0.0
                            
                    st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                    del st.session_state["manage_chain_id"]
                    st.success("Operación marcada como Asignada.")
                    st.rerun()

def render_new_trade():
    st.header("➕ Nueva Operación")
    
    # === FASE 1: ¿Qué hiciste? (esencial) ===
    c_top1, c_top2 = st.columns([1, 2])
    ticker = c_top1.text_input("Ticker").upper()
    estrategia = c_top2.selectbox("Estrategia", ESTRATEGIAS)
    
    # Determinar patas según selección
    legs_count = 1
    if "Spread" in estrategia: legs_count = 2
    elif "Iron" in estrategia: legs_count = 4
    elif "Butterfly" in estrategia: legs_count = 3
    elif estrategia in ["Strangle", "Straddle"]: legs_count = 2
    elif "Ratio" in estrategia: legs_count = 2
    
    if estrategia == "Custom / Other":
        legs_count = st.number_input("Número de patas", min_value=1, max_value=10, value=1)
    
    # Obtener defaults de patas para auto-populate
    leg_defaults = LEG_DEFAULTS.get(estrategia, [])
    has_defaults = len(leg_defaults) >= legs_count
    
    # Dirección automática
    strat_dir = detect_strategy_direction(estrategia)
    dir_label = "📥 Crédito" if strat_dir == "Sell" else "📤 Débito"
    
    # Datos principales en una fila compacta
    c_p1, c_p2, c_p3, c_p4 = st.columns(4)
    premium_help = "Precio NETO por acción de todas las patas combinadas." if legs_count > 1 else "Precio por acción (ej: 1.50)."
    total_premium = c_p1.number_input("Prima ($/acción)", value=0.0, step=0.01, help=premium_help)
    contratos = c_p2.number_input("Contratos", value=1, min_value=1)
    expiry = c_p3.date_input("📅 Vencimiento")
    c_p4.markdown(f"<br><span style='font-size:16px;'>**{dir_label}**</span>", unsafe_allow_html=True)
    
    # === FASE 2: Strikes (el dato que realmente cambia por trade) ===
    st.markdown(f"#### ⚡ Strikes — {estrategia}")
    
    with st.form("new_trade_form", clear_on_submit=True):
        legs_data = []
        
        if has_defaults and estrategia != "Custom / Other":
            # --- MODO SIMPLIFICADO: Side/Type con badge de color ---
            strike_cols = st.columns(legs_count)
            for i in range(legs_count):
                def_side, def_type = leg_defaults[i]
                strike_cols[i].markdown(leg_color_label(def_side, def_type), unsafe_allow_html=True)
                l_strike = strike_cols[i].number_input(
                    "Strike", 
                    key=f"strike_{estrategia}_{i}",
                    help=f"Pata {i+1}: {def_side} {def_type}"
                )
                legs_data.append({"Side": def_side, "Type": def_type, "Strike": l_strike, "Delta": 0.0})
        else:
            # --- MODO COMPLETO: para Custom / Other o estrategias sin defaults ---
            for i in range(legs_count):
                default_side_idx = 0
                default_type_idx = 0
                if i < len(leg_defaults):
                    def_side, def_type = leg_defaults[i]
                    default_side_idx = SIDES.index(def_side) if def_side in SIDES else 0
                    default_type_idx = OPTION_TYPES.index(def_type) if def_type in OPTION_TYPES else 0
                
                with st.expander(f"Pata {i+1}", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    l_side = c1.selectbox(f"Side {i+1}", SIDES, index=default_side_idx, key=f"side_{estrategia}_{i}")
                    l_type = c2.selectbox(f"Type {i+1}", OPTION_TYPES, index=default_type_idx, key=f"type_{estrategia}_{i}")
                    l_strike = c3.number_input(f"Strike {i+1}", key=f"strike_{estrategia}_{i}")
                    legs_data.append({"Side": l_side, "Type": l_type, "Strike": l_strike, "Delta": 0.0})
        
        # Delta global (1 solo input para la pata principal)
        main_side = legs_data[0]["Side"] if legs_data else "Sell"
        main_delta = st.number_input("Delta (pata principal)", value=0.0, step=0.01, 
                                      help="Delta de la pata vendida/comprada principal. Se usa para calcular POP.")
        if legs_data:
            legs_data[0]["Delta"] = main_delta
        
        # Cálculos sugeridos
        be_lower, be_upper = suggest_breakeven(estrategia, legs_data, total_premium)
        suggested_pop = suggest_pop(main_delta, main_side)
        is_dual_be = estrategia in DUAL_BE_STRATEGIES
        
        # === FASE 3: Detalles Opcionales (colapsable) ===
        with st.expander("⚙️ Detalles opcionales", expanded=False):
            c_ad1, c_ad2, c_ad3 = st.columns(3)
            setup_val = c_ad1.selectbox("🎯 Setup / Motivo", SETUPS)
            fecha_apertura = c_ad2.date_input("📅 Fecha Apertura", value=date.today(), help="Cambia si registras la operación un día diferente.")
            user_tags = c_ad3.text_input("🏷️ Tags", placeholder="income, hedge", help="Etiquetas separadas por coma")
            
            c_bp1, c_bp2 = st.columns(2)
            total_bp = c_bp1.number_input("Capital Reservado ($)", value=0.0, step=100.0, help="Buying Power reservado por tu broker para esta posición.")
            
            if is_dual_be:
                c_be1, c_be2, c_be3 = st.columns(3)
                be_input = c_be1.number_input("BE Inferior", value=float(be_lower), step=0.01, help="Break Even del lado bajista")
                be_upper_input = c_be2.number_input("BE Superior", value=float(be_upper), step=0.01, help="Break Even del lado alcista")
                pop_input = c_be3.number_input("POP %", value=float(suggested_pop), step=0.1)
            else:
                c_be1, c_be2 = st.columns(2)
                be_input = c_be1.number_input("Break Even", value=float(be_lower), step=0.01)
                be_upper_input = 0.0
                pop_input = c_be2.number_input("POP %", value=float(suggested_pop), step=0.1)
        
        user_notes = st.text_area("📝 Notas", help="Cualquier detalle adicional de la operación", height=70)
        
        submit_button = st.form_submit_button("🚀 Registrar", type="primary", use_container_width=True)

    if submit_button:
        if not ticker:
            st.error("Ticker obligatorio.")
        else:
            # Valores por defecto para campos opcionales que estaban colapsados
            if 'setup_val' not in dir():
                setup_val = "Otro"
            if 'fecha_apertura' not in dir():
                fecha_apertura = date.today()
            if 'user_tags' not in dir():
                user_tags = ""
            if 'total_bp' not in dir():
                total_bp = 0.0
            if 'be_input' not in dir():
                be_input = be_lower
            if 'be_upper_input' not in dir():
                be_upper_input = be_upper
            if 'pop_input' not in dir():
                pop_input = suggested_pop
                
            chain_id = str(uuid4())[:8]
            new_rows = []
            for i, leg in enumerate(legs_data):
                p_recibida = total_premium if i == 0 else 0.0
                bp_leg = total_bp if i == 0 else 0.0
                
                apertura_ts = pd.to_datetime(fecha_apertura).normalize()
                expiry_ts = pd.to_datetime(expiry).normalize()

                new_rows.append({
                    "ID": str(uuid4())[:8], "ChainID": chain_id, "ParentID": None,
                    "Ticker": ticker, "FechaApertura": apertura_ts, "Expiry": expiry_ts,
                    "Estrategia": estrategia, "Setup": setup_val, "Tags": user_tags.strip() if user_tags else "",
                    "Side": leg["Side"], "OptionType": leg["Type"], 
                    "Strike": leg["Strike"], "Delta": leg["Delta"],
                    "PrimaRecibida": p_recibida, "CostoCierre": 0.0, "Contratos": contratos,
                    "BuyingPower": bp_leg, "BreakEven": be_input if i == 0 else 0.0,
                    "BreakEven_Upper": be_upper_input if i == 0 else 0.0,
                    "POP": pop_input if i == 0 else 0.0,
                    "Estado": "Abierta", "Notas": user_notes if user_notes else f"Parte de {estrategia}",
                    "UpdatedAt": datetime.now().isoformat(), "FechaCierre": pd.NA,
                    "MaxProfitUSD": (p_recibida * contratos * 100), "ProfitPct": 0.0, "PnL_Capital_Pct": 0.0,
                    "PrecioAccionCierre": 0.0, "PnL_USD_Realizado": 0.0
                })
            if new_rows:
                new_df = pd.DataFrame(new_rows)
                if st.session_state.df.empty:
                    st.session_state.df = new_df
                else:
                    st.session_state.df = pd.concat([st.session_state.df.dropna(how='all', axis=0), new_df], ignore_index=True)
            st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
            st.success(f"✅ ¡{ticker} registrado!")
            st.rerun()
            
    if st.button("🗑️ Limpiar"):
        st.rerun()


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
    
    # Formatear fechas para visualización limpia
    for col in ["FechaApertura", "Expiry", "FechaCierre"]:
        display_df[col] = pd.to_datetime(display_df[col]).dt.strftime("%Y-%m-%d")
    
    # Mapear nombres internos a nombres visibles para la UI
    display_df = display_df.rename(columns={
        "BuyingPower": "Capital Reservado",
        "OptionType": "Tipo",
        "PrimaRecibida": "PrimaOrig"
    })
    
    # Columnas priorizadas: lo más importante primero
    view_cols = [
        "Ticker", "FechaCierre", "Estado", "PnL USD", "% Gestión", "Estrategia", "Setup", 
        "Prima", "Contratos", "Side", "Tipo", "Strike", 
        "FechaApertura", "Expiry"
    ]
    
    st.dataframe(display_df[view_cols], width="stretch", hide_index=True)
    
    # Exportar historial filtrado
    csv_export = display_df[view_cols].to_csv(index=False).encode('utf-8')
    st.download_button("📥 Exportar historial filtrado (CSV)", data=csv_export, file_name=f"strikelog_historial_{date.today()}.csv", mime="text/csv")

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
            # Ocultar columnas internas/derivadas que no aportan al usuario
            hidden_cols = ["MaxProfitUSD", "PnL_Capital_Pct", "UpdatedAt", "ChainID", "ParentID"]
            visible_cols = [c for c in st.session_state.df.columns if c not in hidden_cols]
            st.dataframe(st.session_state.df[visible_cols], width="stretch")
        with tab2:
            # Crear una lista de opciones descriptivas para el selectbox
            # Formato: "TICKER - ESTRATEGIA - FECHA - (ID)"
            opciones_dict = {
                f"{row['Ticker']} - {row['Estrategia']} ({row['FechaApertura']}) [ID: {row['ID']}]": row['ID'] 
                for int_idx, row in st.session_state.df.iterrows()
            }
            
            # Ordenar las opciones alfabéticamente para facilitar la búsqueda
            opciones_desc = ["--- Seleccione una operación ---"] + sorted(list(opciones_dict.keys()))
            
            sel_desc = st.selectbox("Busque y seleccione la operación a editar:", opciones_desc, key="edit_selector")
            
            if sel_desc != "--- Seleccione una operación ---":
                trade_id = opciones_dict[sel_desc]
                idx = st.session_state.df.index[st.session_state.df["ID"] == trade_id][0]
                row = st.session_state.df.iloc[idx]
            
                with st.form("edit_form"):
                    c1, c2, c3, c4, c5 = st.columns(5)
                    n_ticker = c1.text_input("Ticker", row["Ticker"])
                    n_side = c2.selectbox("Side", SIDES, index=SIDES.index(row["Side"]) if row["Side"] in SIDES else 0)
                    n_type = c3.selectbox("Type", OPTION_TYPES, index=OPTION_TYPES.index(row["OptionType"]) if row["OptionType"] in OPTION_TYPES else 0)
                    n_strike = c4.number_input("Strike", value=float(row["Strike"]))
                    n_delta = c5.number_input("Delta", value=float(row["Delta"]), step=0.01)
                    
                    ce1, ce2, ce3 = st.columns(3)
                    n_setup = ce1.selectbox("Setup", SETUPS, index=SETUPS.index(row["Setup"]) if "Setup" in row and row["Setup"] in SETUPS else 0)
                    n_estrategia = ce2.selectbox("Estrategia", ESTRATEGIAS, index=ESTRATEGIAS.index(row["Estrategia"]) if row["Estrategia"] in ESTRATEGIAS else 0)
                    n_tags = ce3.text_input("Tags", value=str(row.get("Tags", "") or ""), help="Etiquetas separadas por coma")
                    
                    c6, c7, c8, c8_2, c8_3 = st.columns(5)
                    n_prima = c6.number_input("Prima Neta (por acción)", value=float(row["PrimaRecibida"]))
                    n_costo = c7.number_input("Cierre Neto (por acción)", value=float(row["CostoCierre"]))
                    n_contracts = c8.number_input("Contratos", value=int(row["Contratos"]), min_value=1)
                    n_bp = c8_2.number_input("Buying Power", value=float(row["BuyingPower"]))
                    n_stock_close = c8_3.number_input("Precio Acción Cierre", value=float(row["PrecioAccionCierre"]))
                    
                    cd1, cd2, cd3 = st.columns(3)
                    n_fecha_ap = cd1.date_input("Fecha Apertura", value=pd.to_datetime(row["FechaApertura"]).date())
                    n_expiry = cd2.date_input("Fecha Vencimiento", value=pd.to_datetime(row["Expiry"]).date())
                    n_fecha_cl = cd3.date_input("Fecha Cierre", value=pd.to_datetime(row["FechaCierre"]).date() if not pd.isna(row["FechaCierre"]) else date.today())
                    
                    c9, c10, c10b, c11, c12 = st.columns(5)
                    n_pnl_usd = c9.number_input("PnL USD Realizado", value=float(row["PnL_USD_Realizado"]))
                    n_be = c10.number_input("Break Even (Inf)", value=float(row["BreakEven"]))
                    n_be_upper = c10b.number_input("BE Superior", value=float(row.get("BreakEven_Upper", 0) or 0), help="Solo para Iron Condor, Butterfly, Strangle, Straddle")
                    n_pop = c11.number_input("Prob. Éxito %", value=float(row["POP"]))
                    n_estado = c12.selectbox("Estado", ESTADOS, index=ESTADOS.index(row["Estado"]))

                    if row["Estado"] != "Abierta":
                        st.info(f"💡 Este trade tiene un beneficio del **{row['ProfitPct']:.1f}%** sobre la prima original.")
                    
                    n_notas = st.text_area("Notas", row["Notas"])
                    
                    # Resumen de cambios antes de guardar
                    st.warning("⚠️ Revisa los cambios antes de guardar. Se creará un backup automático del CSV actual.")
                    
                    if st.form_submit_button("💾 Guardar Cambios"):
                        st.session_state.df.at[idx, "Ticker"] = n_ticker
                        st.session_state.df.at[idx, "Side"] = n_side
                        st.session_state.df.at[idx, "OptionType"] = n_type
                        st.session_state.df.at[idx, "Strike"] = n_strike
                        st.session_state.df.at[idx, "Delta"] = n_delta
                        st.session_state.df.at[idx, "Setup"] = n_setup
                        st.session_state.df.at[idx, "Estrategia"] = n_estrategia
                        st.session_state.df.at[idx, "Tags"] = n_tags.strip()
                        st.session_state.df.at[idx, "FechaApertura"] = pd.to_datetime(n_fecha_ap)
                        st.session_state.df.at[idx, "Expiry"] = pd.to_datetime(n_expiry)
                        st.session_state.df.at[idx, "FechaCierre"] = pd.to_datetime(n_fecha_cl) if n_estado != "Abierta" else pd.NA
                        st.session_state.df.at[idx, "PrimaRecibida"] = n_prima
                        st.session_state.df.at[idx, "CostoCierre"] = n_costo
                        st.session_state.df.at[idx, "Contratos"] = n_contracts
                        st.session_state.df.at[idx, "BuyingPower"] = n_bp
                        st.session_state.df.at[idx, "PrecioAccionCierre"] = n_stock_close
                        st.session_state.df.at[idx, "PnL_USD_Realizado"] = n_pnl_usd
                        st.session_state.df.at[idx, "BreakEven"] = n_be
                        st.session_state.df.at[idx, "BreakEven_Upper"] = n_be_upper
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

                        st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                        st.success("¡Actualizado con éxito!")
                        st.rerun()

                # Botón eliminar con confirmación doble
                st.divider()
                st.markdown("#### 🗑️ Zona de Peligro")
                if f"confirm_delete_{trade_id}" not in st.session_state:
                    if st.button(f"🗑️ Eliminar operación {row['Ticker']} (ID: {trade_id})", type="secondary"):
                        st.session_state[f"confirm_delete_{trade_id}"] = True
                        st.rerun()
                else:
                    st.error(f"⚠️ ¿Estás SEGURO de eliminar **{row['Ticker']} {row['Estrategia']}** (ID: {trade_id})? Esta acción no se puede deshacer.")
                    c_del1, c_del2 = st.columns(2)
                    if c_del1.button("✅ Sí, eliminar definitivamente", type="primary"):
                        st.session_state.df = st.session_state.df[st.session_state.df["ID"] != trade_id].reset_index(drop=True)
                        st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                        del st.session_state[f"confirm_delete_{trade_id}"]
                        if "edit_selector" in st.session_state:
                            del st.session_state["edit_selector"]
                        st.success("Operación eliminada.")
                        st.rerun()
                    if c_del2.button("❌ Cancelar"):
                        del st.session_state[f"confirm_delete_{trade_id}"]
                        st.rerun()

                if st.button("⬅️ Volver a la Lista / Cancelar"):
                    if "edit_selector" in st.session_state:
                        del st.session_state["edit_selector"]
                    st.rerun()

if __name__ == "__main__":
    main()
