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
    "PrecioAccionCierre", "PnL_USD_Realizado", "Comisiones", "EarningsDate", "DividendosDate",
    # --- Ciclo de La Rueda ---
    "WheelParentChainID",  # ChainID del PCS original que generó esta posición de acciones
    "CostBaseReal",        # Costo base real de las acciones (strike - primas netas)
    "CoveredCallChainID",  # ChainID del Covered Call vinculado a estas acciones
    "CoveredCallPrima",    # Prima total cobrada por Covered Calls sobre estas acciones
    "WheelLeg",            # 'sell_put' | 'buy_put_open' | 'long_stock' | 'covered_call'
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
                elif c in ["BuyingPower", "BreakEven", "BreakEven_Upper", "POP", "Delta", "PnL_Capital_Pct", "PrecioAccionCierre", "PnL_USD_Realizado", "Comisiones", "CostBaseReal", "CoveredCallPrima"]: df[c] = 0.0
                elif c in ["WheelParentChainID", "CoveredCallChainID", "WheelLeg"]: df[c] = pd.NA
                else: df[c] = pd.NA
        
        df = df[COLUMNS].copy()
        df["FechaApertura"] = pd.to_datetime(df["FechaApertura"], errors='coerce')
        df["Expiry"] = pd.to_datetime(df["Expiry"], errors='coerce')
        df["FechaCierre"] = pd.to_datetime(df["FechaCierre"], errors='coerce')
        df["EarningsDate"] = pd.to_datetime(df["EarningsDate"], errors='coerce')
        df["DividendosDate"] = pd.to_datetime(df["DividendosDate"], errors='coerce')
        
        # Forzar tipo datetime64[ns] para compatibilidad total con Arrow
        df["FechaApertura"] = df["FechaApertura"].fillna(pd.Timestamp.now().normalize())
        df["Expiry"] = df["Expiry"].fillna(pd.Timestamp.now().normalize())
        
        numeric_cols = ["PrimaRecibida", "CostoCierre", "BuyingPower", "BreakEven", "BreakEven_Upper", "POP", "Delta", "MaxProfitUSD", "ProfitPct", "PnL_Capital_Pct", "PrecioAccionCierre", "PnL_USD_Realizado", "Comisiones", "CostBaseReal", "CoveredCallPrima"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            
        df["Contratos"] = pd.to_numeric(df["Contratos"], errors='coerce').fillna(1).astype(int)
        
        # Asegurar que DividendosDate existe y es NA si es nulo
        if "DividendosDate" not in df.columns:
            df["DividendosDate"] = pd.NA
            
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

def calculate_pnl_metrics(prima_neta, costo_cierre_neto, contracts, strategy, bp=0.0, side_first_leg="Sell", comisiones_totales=0.0):
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
        comisiones_totales: Total de comisiones a restar del PnL
    
    Returns:
        (pnl_usd, profit_pct, pnl_capital_pct)
    """
    direction = detect_strategy_direction(strategy, side_first_leg)
    
    if direction == "Sell":
        # Crédito: ganas si el costo de cierre es menor que la prima cobrada
        pnl_usd = (prima_neta - costo_cierre_neto) * contracts * 100 - comisiones_totales
        profit_pct = ((prima_neta - costo_cierre_neto) / prima_neta * 100) if prima_neta > 0 else 0.0
    else:
        # Débito: ganas si el precio de cierre es mayor que lo que pagaste
        pnl_usd = (costo_cierre_neto - prima_neta) * contracts * 100 - comisiones_totales
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

def suggest_pop(delta, side, delta2=0.0):
    """
    Calcula la probabilidad de éxito aproximada basada en el Delta.
    Para estrategias duales (IC, Strangle, Iron Fly), acepta un segundo delta
    de la pata corta secundaria para un cálculo más preciso:
      POP = (1 - |Δ_short_put| - |Δ_short_call|) × 100
    """
    abs_delta = abs(delta)
    if side == "Sell":
        if abs(delta2) > 0:
            # Iron Condor / Strangle: combinar ambas patas cortas
            pop = (1.0 - abs_delta - abs(delta2)) * 100
            return round(max(pop, 0.0), 1)   # mínimo 0%
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
        # --- Fila 1: Filtros principales ---  
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

        # --- Fila 2: Filtros 0DTE y exclusiones ---
        c_f5, c_f6 = st.columns([1, 2])
        filtro_0dte = c_f5.selectbox(
            "⏰ 0DTE",
            ["Todos", "⚡ Solo 0DTE", "🚫 Sin 0DTE"],
            key="dash_0dte",
            help="0DTE = operación cuyo vencimiento coincide con la fecha de apertura"
        )
        all_tickers_excl = sorted(df["Ticker"].dropna().unique().tolist())
        excluir_tickers = c_f6.multiselect(
            "🛋️ Excluir tickers",
            options=all_tickers_excl,
            default=[],
            key="dash_excl",
            placeholder="Selecciona tickers a excluir del análisis..."
        )
        
        # Aplicar Filtros
        df_view = df.copy()

        # --- Calcular flag 0DTE ---
        df_view["__is_0dte"] = (
            pd.to_datetime(df_view["Expiry"], errors="coerce").dt.date ==
            pd.to_datetime(df_view["FechaApertura"], errors="coerce").dt.date
        )

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

        # --- Aplicar filtro 0DTE ---
        if filtro_0dte == "⚡ Solo 0DTE":
            df_view = df_view[df_view["__is_0dte"] == True]
        elif filtro_0dte == "🚫 Sin 0DTE":
            df_view = df_view[df_view["__is_0dte"] == False]

        # --- Excluir tickers seleccionados ---
        if excluir_tickers:
            df_view = df_view[~df_view["Ticker"].isin(excluir_tickers)]
        
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
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        # Formatear delta para asegurar color correcto (si empieza con $ y es negativo, Streamlit a veces lo pone verde)
        pnl_delta_str = f"${pnl_total:,.2f}" if pnl_total >= 0 else f"-${abs(pnl_total):,.2f}"
        m1.metric("PnL Realizado", f"${pnl_total:,.2f}", delta=pnl_delta_str if pnl_total != 0 else None)
        
        total_comisiones = df_view["Comisiones"].sum() if "Comisiones" in df_view.columns else 0.0
        m2.metric("Comisiones", f"${total_comisiones:,.2f}", help="Total de comisiones pagadas")
        
        m3.metric("Win Rate", f"{win_rate:.1f}%", help="Porcentaje de operaciones positivas")
        m4.metric("Profit Factor", f"{profit_factor:.2f}x", help="Ratio Ganancia Total / Pérdida Total")
        m5.metric("Captura Media", f"{capture_eff:.1f}%", help="Promedio de beneficio sobre la prima recibida")
        
        # Drawdown máximo
        if not closed_trades.empty:
            sorted_closed = closed_trades.sort_values("FechaCierre")
            equity_series = sorted_closed["PnL_USD_Realizado"].cumsum()
            running_max = equity_series.cummax()
            drawdown = running_max - equity_series
            max_dd = drawdown.max()
        else:
            max_dd = 0.0
        m6.metric("Max Drawdown", f"-${max_dd:,.2f}", help="Mayor caída desde un pico de equidad")
        
        # --- NUEVA MÉTRICA: Comisiones 0DTE ---
        comisiones_0dte = df_view[df_view["__is_0dte"] == True]["Comisiones"].sum()
        st.info(f"⚡ **Comisiones acumuladas en 0DTE:** ${comisiones_0dte:,.2f}")
        
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
            avg_color = "#00ffa2" if avg_profit >= 0 else "#ff6b6b"
            s1.markdown(f"**Promedio/Trade:**<br><span style='font-size:18px; color:{avg_color};'>${avg_profit:,.2f}</span>", unsafe_allow_html=True)
            
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
        st.plotly_chart(fig_equity, use_container_width=True)
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
        st.plotly_chart(fig_monthly, use_container_width=True)

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
                st.plotly_chart(fig_strat, use_container_width=True)
        
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
                st.plotly_chart(fig_setup, use_container_width=True)

def render_active_portfolio(df):
    if "edit_trade_id" in st.session_state:
        render_inline_edit(st.session_state["edit_trade_id"])
        st.divider()
        st.stop()
        
    st.header("📂 Cartera Activa")
    
    # CSS personalizado para badges y tarjetas
    st.markdown("""
    <style>
    .dte-badge {
        padding: 4px 6px; /* Reducido de 8px */
        border-radius: 6px;
        text-align: center;
        color: white;
        font-weight: bold;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        height: 100%;
        min-height: 42px; /* Reducido de 50px */
        box-shadow: 0 1px 3px rgba(0,0,0,0.15);
        font-size: 14px;
    }
    .dte-val { font-size: 16px; line-height: 1.1; } /* Reducido de 18px */
    .dte-label { font-size: 9px; opacity: 0.9; text-transform: uppercase; }
    
    .tag-pill {
        background-color: #2c3e50;
        color: #bdc3c7;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 11px;
        margin-right: 4px;
        border: 1px solid #34495e;
    }
    .strategy-pill {
        background-color: #1abc9c;
        color: black;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
        margin-right: 6px;
    }
    .earnings-badge {
        background-color: #8e44ad;
        color: white;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: bold;
    }
    .dit-warning {
        color: #e67e22;
        font-weight: bold;
        font-size: 12px;
    }
    .leg-row {
        border-bottom: 1px solid rgba(255,255,255,0.05);
        padding: 4px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    active_df = df[df["Estado"] == "Abierta"].copy()
    if active_df.empty:
        st.info("No hay posiciones abiertas.")
        return

    # ─────────────────────────────────────────────────────────────────────
    # 🔔 BANNER DE EXPIRACIONES PENDIENTES
    # Regla: DTE <= 0 AND Estado == "Abierta"
    # Incluye efecto fin de semana: si el usuario abre el sábado/domingo,
    # el DTE puede ser -1 o -2, pero el contrato sigue sin gestionar.
    # ─────────────────────────────────────────────────────────────────────
    today = date.today()
    expired_chains = {}   # chain_id → primera fila del grupo

    for chain_id, grp in active_df.groupby("ChainID"):
        first = grp.iloc[0]
        option_type = str(first.get("OptionType", ""))
        # Long Stock sin fecha de vencimiento real → ignorar
        if option_type == "Stock":
            continue
        expiry_val = first.get("Expiry")
        if pd.isna(expiry_val):
            continue
        try:
            expiry_date = pd.to_datetime(expiry_val).date()
            dte_val = (expiry_date - today).days
        except:
            continue
        if dte_val <= 0:
            expired_chains[chain_id] = first

    if expired_chains:
        n = len(expired_chains)
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #7b1a1a, #3d0000);
                    border: 2px solid #e74c3c; border-radius:12px;
                    padding:16px 20px; margin-bottom:20px;'>
            <div style='font-size:18px; font-weight:bold; color:#ff6b6b; margin-bottom:4px;'>
                🔔 {n} contrato{'s' if n > 1 else ''} vencido{'s' if n > 1 else ''} pendiente{'s' if n > 1 else ''} de gestionar
            </div>
            <div style='color:#f5b7b1; font-size:13px;'>
                Estos contratos tienen DTE ≤ 0 pero siguen marcados como <b>Abierta</b>.
                Regístralos antes de continuar para que tus métricas sean precisas.
            </div>
        </div>
        """, unsafe_allow_html=True)

        for exp_chain_id, exp_row in expired_chains.items():
            exp_ticker    = exp_row.get("Ticker", "")
            exp_strategy  = exp_row.get("Estrategia", "")
            exp_strike    = exp_row.get("Strike", "")
            exp_option_t  = exp_row.get("OptionType", "")
            exp_dte_label = (pd.to_datetime(exp_row.get("Expiry")).date() - today).days
            exp_wheel_leg = str(exp_row.get("WheelLeg", ""))
            is_cc_wheel   = (exp_wheel_leg == "covered_call" or
                             "covered-call" in str(exp_row.get("Tags", "")))

            dte_badge = f"DTE {exp_dte_label}d" if exp_dte_label < 0 else "DTE 0"

            with st.container():
                st.markdown(f"""
                <div style='background:#1a0000; border:1px solid #c0392b; border-radius:8px;
                            padding:10px 14px; margin-bottom:10px; display:flex; align-items:center;'>
                    <span style='font-size:13px; color:#e74c3c; font-weight:bold; margin-right:8px;'>
                        ⚠️ {exp_ticker}
                    </span>
                    <span style='color:#e6edf3; font-size:13px; margin-right:8px;'>
                        {exp_strategy} — Strike {exp_strike} {exp_option_t}
                    </span>
                    <span style='background:#7b1a1a; color:#ff6b6b; font-size:11px;
                                 padding:2px 8px; border-radius:10px;'>
                        {dte_badge}
                    </span>
                </div>
                """, unsafe_allow_html=True)

                # Botones de acción rápida según tipo de estrategia
                if is_cc_wheel:
                    # CC de La Rueda: dos caminos
                    ba1, ba2 = st.columns(2)
                    if ba1.button(f"⌛ Expiró OTM — Conservar acciones",
                                  key=f"alert_exp_cc_{exp_chain_id}",
                                  help="Cierra el CC a $0.00. Las acciones permanecen en cartera.",
                                  use_container_width=True):
                        # Cierre CC a $0.00
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        cc_exp_idx = st.session_state.df.index[
                            (st.session_state.df["ChainID"] == exp_chain_id) &
                            (st.session_state.df["Estado"] == "Abierta")
                        ]
                        for idx_e in cc_exp_idx:
                            p_e = float(st.session_state.df.at[idx_e, "PrimaRecibida"] or 0)
                            c_e = float(st.session_state.df.at[idx_e, "Contratos"] or 1)
                            pnl_e = p_e * c_e * 100
                            st.session_state.df.at[idx_e, "Estado"] = "Cerrada"
                            st.session_state.df.at[idx_e, "FechaCierre"] = now_str
                            st.session_state.df.at[idx_e, "CostoCierre"] = 0.0
                            st.session_state.df.at[idx_e, "PnL_USD_Realizado"] = pnl_e
                            st.session_state.df.at[idx_e, "Notas"] = (
                                str(st.session_state.df.at[idx_e, "Notas"] or "") +
                                f" [OTM — expirado. Prima íntegra: ${pnl_e:.2f}]"
                            )
                        # Desvincular de la posición de acciones
                        stock_unlink = st.session_state.df.index[
                            (st.session_state.df["CoveredCallChainID"] == exp_chain_id)
                        ]
                        for idx_u in stock_unlink:
                            st.session_state.df.at[idx_u, "CoveredCallChainID"] = pd.NA
                        st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                        st.success(f"✅ CC {exp_ticker} expirado. Acciones conservadas. Puedes vender un nuevo CC.")
                        st.rerun()

                    if ba2.button(f"📜 Asignación (ITM)",
                                  key=f"alert_assign_cc_{exp_chain_id}",
                                  help="El CC expiró ITM. Ve al Panel La Rueda para vender las acciones.",
                                  use_container_width=True):
                        # Redirigir al panel de gestión
                        st.session_state["manage_chain_id"] = exp_chain_id
                        st.rerun()

                elif exp_strategy in ["PCS (Put Credit Spread)", "ICS (Iron Condor)", "CCS (Call Credit Spread)"]:
                    # Spread: expiró o se asigna
                    bs1, bs2 = st.columns(2)
                    if bs1.button(f"✅ Expiró sin valor ($0.00)",
                                  key=f"alert_exp_spread_{exp_chain_id}",
                                  help="Cierra todo el spread a $0.00. Prima cobrada íntegra.",
                                  use_container_width=True):
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        sp_idx = st.session_state.df.index[
                            (st.session_state.df["ChainID"] == exp_chain_id) &
                            (st.session_state.df["Estado"] == "Abierta")
                        ]
                        total_prima_sp = 0.0
                        for idx_s in sp_idx:
                            p_s = float(st.session_state.df.at[idx_s, "PrimaRecibida"] or 0)
                            c_s = float(st.session_state.df.at[idx_s, "Contratos"] or 1)
                            total_prima_sp += p_s * c_s * 100
                        for idx_s in sp_idx:
                            st.session_state.df.at[idx_s, "Estado"] = "Cerrada"
                            st.session_state.df.at[idx_s, "FechaCierre"] = now_str
                            st.session_state.df.at[idx_s, "CostoCierre"] = 0.0
                            st.session_state.df.at[idx_s, "Notas"] = (
                                str(st.session_state.df.at[idx_s, "Notas"] or "") +
                                f" [OTM — expirado sin valor]"
                            )
                        # PnL solo en primera pata
                        first_sp_idx = st.session_state.df.index[
                            (st.session_state.df["ChainID"] == exp_chain_id) &
                            (st.session_state.df["Estado"] == "Cerrada")
                        ]
                        if len(first_sp_idx) > 0:
                            st.session_state.df.at[first_sp_idx[0], "PnL_USD_Realizado"] = total_prima_sp
                        st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                        st.success(f"✅ {exp_ticker} {exp_strategy} cerrado a $0.00. Prima íntegra: ${total_prima_sp:.2f}")
                        st.rerun()

                    if bs2.button(f"📜 Gestionar (Asignación / Parcial)",
                                  key=f"alert_assign_spread_{exp_chain_id}",
                                  help="Abre el panel de gestión completo para este spread.",
                                  use_container_width=True):
                        st.session_state["manage_chain_id"] = exp_chain_id
                        st.rerun()

                else:
                    # Put simple (CSP), Call, etc.
                    bp1, bp2 = st.columns(2)
                    if bp1.button(f"✅ Expiró sin valor ($0.00)",
                                  key=f"alert_exp_put_{exp_chain_id}",
                                  use_container_width=True):
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        put_idx = st.session_state.df.index[
                            (st.session_state.df["ChainID"] == exp_chain_id) &
                            (st.session_state.df["Estado"] == "Abierta")
                        ]
                        total_prima_put = 0.0
                        for idx_p in put_idx:
                            p_p = float(st.session_state.df.at[idx_p, "PrimaRecibida"] or 0)
                            c_p = float(st.session_state.df.at[idx_p, "Contratos"] or 1)
                            total_prima_put += p_p * c_p * 100
                            st.session_state.df.at[idx_p, "Estado"] = "Cerrada"
                            st.session_state.df.at[idx_p, "FechaCierre"] = now_str
                            st.session_state.df.at[idx_p, "CostoCierre"] = 0.0
                            st.session_state.df.at[idx_p, "PnL_USD_Realizado"] = p_p * c_p * 100
                            st.session_state.df.at[idx_p, "Notas"] = (
                                str(st.session_state.df.at[idx_p, "Notas"] or "") +
                                f" [OTM — expirado sin valor]"
                            )
                        st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                        st.success(f"✅ {exp_ticker} expirado. Prima íntegra: ${total_prima_put:.2f}")
                        st.rerun()

                    if bp2.button(f"⚙️ Abrir Gestión Completa",
                                  key=f"alert_manage_put_{exp_chain_id}",
                                  use_container_width=True):
                        st.session_state["manage_chain_id"] = exp_chain_id
                        st.rerun()

        st.markdown("---")

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
        setup = first_row["Setup"]
        tags = str(first_row.get("Tags", "")).split(",") if pd.notna(first_row.get("Tags", "")) else []
        earnings_date = pd.to_datetime(first_row.get("EarningsDate")).date() if pd.notna(first_row.get("EarningsDate")) else None
        dividendos_date = pd.to_datetime(first_row.get("DividendosDate")).date() if pd.notna(first_row.get("DividendosDate")) else None
        
        # Métricas agregadas del grupo
        total_bp = group["BuyingPower"].sum()
        total_premium = group["PrimaRecibida"].sum()
        
        # Asegurar que expiry es objeto fecha par el cálculo
        expiry_dt = pd.to_datetime(expiry).date() if pd.notna(expiry) else date.today()
        dte = (expiry_dt - date.today()).days
        
        # Días en Trade (DIT)
        apertura_dt = pd.to_datetime(first_row["FechaApertura"]).date() if pd.notna(first_row["FechaApertura"]) else date.today()
        dit = (date.today() - apertura_dt).days
        
        # Configuración Badge DTE
        is_stock_position = (first_row.get("OptionType", "") == "Stock")

        if is_stock_position:
            # Las acciones no tienen fecha de vencimiento — mostrar badge neutro
            dte_html = """
            <div class="dte-badge" style="background-color:#2c3e50; min-width:52px;">
                <span class="dte-val" style="font-size:10px;">STOCK</span>
                <span class="dte-label">&infin;</span>
            </div>
            """
        else:
            dte_bg = "#95a5a6"  # gris por defecto
            if dte < 7:   dte_bg = "#e74c3c"  # rojo
            elif dte <= 21: dte_bg = "#f1c40f"  # amarillo
            else:          dte_bg = "#27ae60"  # verde

            dte_html = f"""
            <div class="dte-badge" style="background-color: {dte_bg};">
                <span class="dte-val">{dte}</span>
                <span class="dte-label">DTE</span>
            </div>
            """
        
        # Marcadores visuales
        earnings_txt = ""
        # Prioridad: Si hay fecha, usar el cálculo. Si no, mirar el Setup.
        if earnings_date:
             days_to_earn = (earnings_date - date.today()).days
             if 0 <= days_to_earn <= 14:
                 earnings_txt = f"📢 EARNINGS ({days_to_earn}d)"
        elif setup == "Earnings":
             earnings_txt = "📢 EARNINGS"
             
        div_txt = ""
        if dividendos_date:
            days_to_div = (dividendos_date - date.today()).days
            if 0 <= days_to_div <= 14:
                div_txt = f"💰 DIVIDENDOS ({days_to_div}d)"
            
        dit_display = ""
        if dit > 45:
            dit_display = f" <span class='dit-warning'>🐌 DIT {dit}d</span>"
        else:
            dit_display = f" <span style='color:#7f8c8d; font-size:12px;'>DIT: {dit}d</span>"
            
        # Icono de dirección crédito/débito
        strat_dir = detect_strategy_direction(strategy, first_row["Side"])
        dir_icon = "📥" if strat_dir == "Sell" else "📤"
        
        # Identificar historial de Rolls
        roll_chain = get_roll_history(df, first_row["ID"])
        num_rolls = len(roll_chain) - 1 # El actual no cuenta como roll
        
        roll_label = f" 🔄 x{num_rolls}" if num_rolls > 0 else ""

        # Cálculos extendidos de la cadena (Rolls + Actual)
        # Cálculos extendidos de la cadena (Rolls + Actual)
        # CORRECCIÓN: get_roll_history devuelve solo la rama de UN ID (una pata).
        # Para estrategias multi-pata (IC), la prima está dividida. Debemos sumar
        # la prima de TODO el ChainID de cada paso en la historia.
        
        hist_credits = 0.0
        hist_debits = 0.0
        
        # Iteramos sobre cada paso histórico (cada 'eslabón' de la cadena de esa pata)
        # y buscamos sus "hermanos" de ChainID para sumar la prima completa de la estrategia en ese momento.
        seen_chains = set()
        for r in roll_chain:
            c_id = r["ChainID"]
            if c_id not in seen_chains:
                seen_chains.add(c_id)
                # Buscar todas las patas que pertenecían a ese ChainID
                step_group = df[df["ChainID"] == c_id]
                
                # Sumar créditos (Prima Recibida) de todas las patas de ese paso
                hist_credits += step_group["PrimaRecibida"].sum()
                
                # Sumar débitos (Costo Cierre) solo si ese paso NO es el actual abierto
                # (si es 'Rolada' o 'Cerrada' - aunque en active portfolio el último es 'Abierta')
                # En roll_chain, el índice 0 es el actual (Abierta).
                # Verificar estado de CADA pata individualmente o del grupo?
                # Generalmente todo el grupo cambia de estado junto.
                if r["Estado"] != "Abierta":
                    hist_debits += step_group["CostoCierre"].sum()

        net_credit_chain = hist_credits - hist_debits

        realized_pnl_chain = sum(float(r["PnL_USD_Realizado"] or 0) for r in roll_chain if r["Estado"] != "Abierta")
        
        # Recálculo dinámico del Break Even
        is_dual_be = strategy in DUAL_BE_STRATEGIES
        calculated_be = 0.0
        calculated_be_upper = 0.0

        # Detectar si es un Covered Call vinculado a La Rueda
        is_cc_rueda = (
            strategy == "CC (Covered Call)" and
            ("la-rueda" in str(first_row.get("Tags", "")) or
             "covered-call" in str(first_row.get("Tags", "")) or
             pd.notna(first_row.get("ParentID")))
        )

        # Long Stock: no tiene lógica de opciones — usar el BE guardado (CostBaseReal)
        # El detalle dinámico completo se gestiona en el Panel "La Rueda" más abajo.
        if is_stock_position:
            calculated_be = float(first_row.get("BreakEven", 0) or 0)
            calculated_be_upper = 0.0
        elif is_cc_rueda:
            # CC vinculado a acciones: BE = Strike + prima de ESTA pata únicamente.
            # No usar net_credit_chain (acumulado de toda la historia) ya que
            # confunde con el BE global de las acciones subyacentes.
            strike_cc = float(first_row.get("Strike", 0) or 0)
            prima_actual_cc = abs(float(first_row.get("PrimaRecibida", 0) or 0))
            calculated_be = strike_cc + prima_actual_cc   # BE pata individual
            calculated_be_upper = 0.0
        else:
            try:
                if is_dual_be:
                    legs_for_be = [{"Side": r["Side"], "Type": r["OptionType"], "OptionType": r["OptionType"],
                                    "Strike": float(r["Strike"])} for _, r in group.iterrows()]
                    calculated_be, calculated_be_upper = suggest_breakeven(strategy, legs_for_be, net_credit_chain)

                    if calculated_be == 0.0 and calculated_be_upper == 0.0:
                        calculated_be = float(first_row["BreakEven"] or 0)
                        calculated_be_upper = float(first_row.get("BreakEven_Upper", 0) or 0)
                else:
                    legs_for_be = [{"Side": first_row["Side"], "Type": first_row["OptionType"],
                                    "OptionType": first_row["OptionType"], "Strike": float(first_row["Strike"])}]
                    if len(group) > 1:
                        legs_for_be = [{"Side": r["Side"], "Type": r["OptionType"], "OptionType": r["OptionType"],
                                        "Strike": float(r["Strike"])} for _, r in group.iterrows()]

                    calculated_be, _ = suggest_breakeven(strategy, legs_for_be, net_credit_chain)
                    if calculated_be == 0.0:
                        calculated_be = float(first_row["BreakEven"] or 0)
            except Exception as e:
                calculated_be = float(first_row["BreakEven"] or 0)
                calculated_be_upper = float(first_row.get("BreakEven_Upper", 0) or 0)

        formatted_net = f"${net_credit_chain:,.2f}"
        
        # Header del Expander Limpio
        if is_dual_be and calculated_be_upper > 0:
            be_str = f"${calculated_be:,.2f} / ${calculated_be_upper:,.2f}"
        else:
            be_str = f"${calculated_be:,.2f}"
        
        # Componentes del título expandido
        # Formato: 13 Mar
        try:
            exp_date_obj = pd.to_datetime(first_row["Expiry"])
            exp_str_title = exp_date_obj.strftime("%d %b")
        except:
            exp_str_title = ""
            
        strikes_short = " / ".join(f"{float(r['Strike']):g}" for _, r in group.iterrows())
        
        # Header del Expander Limpio + Earnings/Div Icon (Sin HTML en título expander)
        alerts_list = []
        if earnings_txt: alerts_list.append(f"🚨 {earnings_txt} 🚨")
        if div_txt: alerts_list.append(f"🚨 {div_txt} 🚨")
        
        alerts_str = "   ".join(alerts_list)
        if alerts_str:
            header_title = f"{ticker} {exp_str_title} {strikes_short} {strategy} {roll_label}   {alerts_str}"
        else:
            header_title = f"{ticker} {exp_str_title} {strikes_short} {strategy} {roll_label}"
        
        # Layout de Tarjeta
        c_dte, c_card = st.columns([1, 10])
        
        with c_dte:
            st.markdown(dte_html, unsafe_allow_html=True)
            
        with c_card:
            # Usamos un expander para el detalle, pero el título ya tiene mucha info
            with st.expander(header_title, expanded=False):
                # Sub-header visual con Tags (sin duplicar earnings)
                tags_html = "".join([f"<span class='tag-pill'>{t.strip()}</span>" for t in tags if t.strip()])
                st.markdown(f"{dit_display} &nbsp; {tags_html}", unsafe_allow_html=True)
                
                st.markdown("---")
                
                # Métricas Clave
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Prima Total", formatted_net, help="Crédito neto total de la campaña (incluyendo rolls)")
                if is_cc_rueda:
                    m2.metric(
                        "BE pata CC",
                        be_str,
                        help=(
                            "BE individual del Covered Call = Strike + Prima actual.\n"
                            "El BE real de toda la operación está en el Panel \u2193 La Rueda "
                            "(Strike SP \u2212 primas acumuladas)."
                        )
                    )
                    st.caption("🎯 BE real de la posición completa → ver **Panel La Rueda** ↓")
                else:
                    m2.metric("Break Evens", be_str, help="Puntos de equilibrio ajustados")
                m3.metric("Capital Reservado", f"${total_bp:,.2f}")
                m4.metric("PnL Realizado (Rolls)", f"${realized_pnl_chain:,.2f}", delta=realized_pnl_chain if realized_pnl_chain != 0 else None)
            
                # --- SECCIÓN DE HISTORIAL DE ROLLS (Corregida) ---
                if num_rolls > 0:
                    st.markdown("#### 🕒 Historial de esta posición")
                    
                    # Reconstruir la cadena histórica completa para visualización
                    reversed_chain = list(reversed(roll_chain))
                    if reversed_chain:
                        origin = reversed_chain[0]
                        origin_date = pd.to_datetime(origin['FechaApertura']).strftime("%Y-%m-%d") if pd.notna(origin['FechaApertura']) else "N/A"
                        st.info(f"📍 **Origen:** Abierto el `{origin_date}` con Strike `{origin.get('Strike', '')} {origin.get('OptionType', '')}`.")
                        
                        hist_data = []
                        for i, r in enumerate(reversed_chain):
                            # Etiquetar cada paso
                            if i == 0: label = "ORIGEN"
                            elif i == len(reversed_chain) - 1: label = "ACTUAL" # La última en la lista reversed es la actual
                            else: label = f"ROL #{i}"
                            
                            f_apertura = pd.to_datetime(r["FechaApertura"]).strftime("%Y-%m-%d") if pd.notna(r["FechaApertura"]) else ""
                            
                            # PnL solo tiene sentido para las cerradas (pasos previos)
                            pnl_val = f"${r['PnL_USD_Realizado']:.2f}" if r['Estado'] != 'Abierta' else "-"
                            
                            hist_data.append({
                                "Etapa": label,
                                "Fecha": f_apertura,
                                "Strike": f"{r.get('Strike','')} {r.get('OptionType','')}",
                                "BE": f"{r.get('BreakEven',0):.2f}",
                                "PnL Realizado": pnl_val
                            })
                        
                        # Mostrar tabla
                        st.table(pd.DataFrame(hist_data))
                        
                        # Mostrar evolución del BE
                        if len(reversed_chain) >= 2:
                            prev_be = reversed_chain[-2].get("BreakEven", 0.0)
                            curr_be = first_row.get("BreakEven", 0.0)
                            diff_be = float(curr_be) - float(prev_be)
                            
                            icon_trend = "➡️"
                            if diff_be > 0: icon_trend = "📈"
                            elif diff_be < 0: icon_trend = "📉"
                            
                            st.caption(f"**Evolución del BE (último rol):** `{prev_be:.2f}` → `{curr_be:.2f}` ({icon_trend} {diff_be:+.2f})")
                
                st.markdown("###### 🦵 Patas de la Estrategia")
                
                # Tabla de Legs Custom para mejor alineación
                leg_cols = st.columns([1.5, 1, 1.5, 1, 1.5, 1.5, 1])
                fields = ["Lado", "Tipo", "Strike", "Cnt", "Delta", "Prima", "Edit"]
                for i, f in enumerate(fields):
                    leg_cols[i].markdown(f"**{f}**")
                
                for _, leg in group.iterrows():
                    l_c1, l_c2, l_c3, l_c4, l_c5, l_c6, l_c7 = st.columns([1.5, 1, 1.5, 1, 1.5, 1.5, 1])
                    side_color = "#e74c3c" if leg["Side"] == "Sell" else "#27ae60"
                    l_c1.markdown(f"<span style='color:{side_color}; font-weight:bold;'>{leg['Side']}</span>", unsafe_allow_html=True)
                    l_c2.write(leg["OptionType"])
                    l_c3.write(f"{leg['Strike']}")
                    l_c4.write(f"{int(leg.get('Contratos', 1))}")
                    l_c5.write(f"{leg.get('Delta', 0):.2f}")
                    l_c6.write(f"${leg.get('PrimaRecibida', 0):.2f}")
                    if l_c7.button("✏️", key=f"edit_leg_{leg['ID']}"):
                        st.session_state["edit_trade_id"] = leg["ID"]
                        st.rerun()
                
                st.markdown("---")
                
                # --- NOTAS RÁPIDAS Y CONFIGURACIÓN ---
                c_notes, c_config = st.columns([3, 1])
                current_notes = first_row["Notas"] if pd.notna(first_row["Notas"]) else ""
                new_notes = c_notes.text_area("📝 Notas", value=current_notes, key=f"notes_{chain_id}", height=70, help="Edita las notas de toda la estrategia aquí mismo.")
                
                # Edición rápida de Earnings y Dividendos Date
                current_earnings = pd.to_datetime(first_row.get("EarningsDate")).date() if pd.notna(first_row.get("EarningsDate")) else None
                current_dividendos = pd.to_datetime(first_row.get("DividendosDate")).date() if pd.notna(first_row.get("DividendosDate")) else None
                
                new_earnings = c_config.date_input("📢 Earnings", value=current_earnings, key=f"earn_{chain_id}", help="Fecha de próximos resultados.")
                new_dividendos = c_config.date_input("💰 Dividendos", value=current_dividendos, key=f"div_{chain_id}")
                
                # Detectar cambios
                notes_changed = (new_notes != current_notes)
                earnings_changed = (new_earnings != current_earnings)
                dividendos_changed = (new_dividendos != current_dividendos)
                
                if notes_changed or earnings_changed or dividendos_changed:
                    if st.button("💾 Guardar Cambios", key=f"save_changes_{chain_id}"):
                        # Actualizar notas y earnings en todas las patas del ChainID
                        for idx, row in group.iterrows():
                             real_idx = df.index[df["ID"] == row["ID"]][0]
                             if notes_changed:
                                 df.at[real_idx, "Notas"] = new_notes
                             if earnings_changed:
                                 df.at[real_idx, "EarningsDate"] = pd.to_datetime(new_earnings).normalize() if new_earnings else pd.NA
                             if dividendos_changed:
                                 df.at[real_idx, "DividendosDate"] = pd.to_datetime(new_dividendos).normalize() if new_dividendos else pd.NA
                             
                             df.at[real_idx, "UpdatedAt"] = datetime.now().isoformat()
                        
                        st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                        st.success("Datos actualizados.")
                        st.rerun()
                    
                # Acciones Rápidas
                c_btn_quick, c_btn_manage, c_btn_dup = st.columns(3)
                if c_btn_quick.button(f"⚡ Cerrar Rápido", key=f"btn_quick_{chain_id}"):
                    st.session_state[f"quick_close_{chain_id}"] = True
                
                if c_btn_manage.button(f"🎯 Gestionar / Rol", key=f"btn_manage_{chain_id}"):
                    st.session_state["manage_chain_id"] = chain_id
                    st.rerun()
                
                if c_btn_dup.button(f"📋 Duplicar Express", key=f"btn_dup_{chain_id}", help="Abre el formulario Express con los datos de esta operación pre-rellenados"):
                    st.session_state["express_dup_defaults"] = {
                        "ticker": ticker,
                        "estrategia": strategy,
                        "contratos": int(first_row.get("Contratos", 1)),
                        "prima": float(total_premium),
                        "buying_power": float(total_bp),
                    }
                    st.session_state["nav_override"] = "Nueva Operación"
                    st.rerun()
                
                # --- MINI PANEL DE CIERRE RÁPIDO ---
                if st.session_state.get(f"quick_close_{chain_id}", False):
                    st.markdown("---")
                    qc1, qc2, qc3, qc4 = st.columns([2, 2, 1, 1])
                    q_close_price = qc1.number_input("Cierre ($/acción)", value=0.0, step=0.01, key=f"qcp_{chain_id}")
                    
                    q_entry = group["PrimaRecibida"].sum()
                    q_contracts = int(first_row["Contratos"])
                    q_bp = group["BuyingPower"].sum()
                    # Estimación de comisiones de cierre
                    q_comisiones = sum(float(r.get("Comisiones", 0.0)) for _, r in group.iterrows())
                    cierre_comisiones = 0.0
                    for _, r in group.iterrows():
                        if r.get("Side", "Sell") == "Sell" and q_close_price <= 0.05:
                            pass
                        else:
                            cierre_comisiones += int(r.get("Contratos", 1)) * 0.65
                    q_comisiones += cierre_comisiones

                    q_pnl, q_pct, _ = calculate_pnl_metrics(
                        q_entry, q_close_price, q_contracts, strategy, q_bp, first_row["Side"], q_comisiones
                    )
                    qc2.metric("PnL Est.", f"${q_pnl:,.2f}", delta=f"{q_pct:.0f}%")
                    
                    if qc3.button("✅ Confirmar", key=f"qcc_{chain_id}", type="primary"):
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
                                df.at[real_idx_q, "Comisiones"] = float(row_q.get("Comisiones", 0.0)) + cierre_comisiones
                            else:
                                df.at[real_idx_q, "CostoCierre"] = 0.0
                                df.at[real_idx_q, "PnL_USD_Realizado"] = 0.0
                                df.at[real_idx_q, "ProfitPct"] = 0.0
                                df.at[real_idx_q, "PnL_Capital_Pct"] = 0.0
                        
                        st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                        st.session_state["post_mortem"] = {"chain_id": chain_id, "ticker": ticker, "pnl": q_pnl}
                        del st.session_state[f"quick_close_{chain_id}"]
                        st.success(f"✅ {ticker} cerrado: ${q_pnl:,.2f}")
                        st.rerun()

                    if qc4.button("🚫 Cancelar", key=f"qcc_cancel_{chain_id}"):
                        del st.session_state[f"quick_close_{chain_id}"]
                        st.rerun()

    st.divider()

    # ============================================================
    # --- SECCIÓN: POSICIONES LONG STOCK (CICLO DE LA RUEDA) ---
    # ============================================================
    wheel_stocks = df[
        (df["Estrategia"] == "Long Stock (Asignación)") &
        (df["Estado"] == "Abierta")
    ].copy()

    if not wheel_stocks.empty:
        st.markdown("## 🎡 La Rueda — Posiciones de Acciones Asignadas")
        st.markdown("""
        <style>
        .wheel-card {
            background: linear-gradient(135deg, #0f1f2f, #1a2a1a);
            border: 1px solid #00ffa2;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 14px;
        }
        .cc-tag-yes {
            background: #27ae60; color: white; padding: 4px 12px;
            border-radius: 20px; font-weight: bold; font-size: 13px;
        }
        .cc-tag-no {
            background: #e74c3c; color: white; padding: 4px 12px;
            border-radius: 20px; font-weight: bold; font-size: 13px;
        }
        </style>
        """, unsafe_allow_html=True)

        for _, stock_row in wheel_stocks.iterrows():
            stock_ticker = stock_row["Ticker"]
            stock_chain  = stock_row["ChainID"]
            stock_id     = stock_row["ID"]
            contratos_st = int(stock_row.get("Contratos", 1))
            acciones_st  = contratos_st * 100
            precio_compra = float(stock_row.get("Strike", 0))
            prima_neta_pcs = float(stock_row.get("PrimaRecibida", 0))

            # Costo Base Real guardado
            costo_base_actual = float(stock_row.get("CostBaseReal", stock_row.get("BreakEven", precio_compra)))
            cc_prima_acum     = float(stock_row.get("CoveredCallPrima", 0))
            cc_chain_id       = stock_row.get("CoveredCallChainID")
            tiene_cc          = pd.notna(cc_chain_id) and str(cc_chain_id) != "nan"

            # Buscar si el Buy Put de La Rueda ya fue cerrado (para calcular prima extra)
            wheel_parent_chain = stock_row.get("WheelParentChainID")
            buy_put_prima_extra = 0.0
            buy_put_closed = False
            if pd.notna(wheel_parent_chain):
                bp_rows = df[
                    (df["WheelLeg"] == "buy_put_open") &
                    (df["WheelParentChainID"] == wheel_parent_chain) &
                    (df["Estado"] != "Abierta")
                ]
                if not bp_rows.empty:
                    buy_put_prima_extra = float(bp_rows.iloc[0].get("CostoCierre", 0))
                    buy_put_closed = True

            # --- Calcular Costo Base Real dinámico ---
            # IMPORTANTE: Aplicar abs() a cada prima para evitar dobles negativos.
            # El CostoCierre del Buy Put puede ser negativo (entrada del usuario para PnL),
            # pero su efecto en el BE siempre REDUCE el costo base, no lo sube.
            # CostBase = Strike - |Prima PCS| - |CC acumulado| - |BP vendido|
            total_primas = abs(prima_neta_pcs) + abs(cc_prima_acum) + abs(buy_put_prima_extra)
            costo_base_dinamico = precio_compra - total_primas

            # --- Card de la posición ---
            indicator_html = (
                "<span class='cc-tag-yes'>Covered Call: SÍ ✅</span>"
                if tiene_cc else
                "<span class='cc-tag-no'>Covered Call: NO ⚠️</span>"
            )
            with st.expander(
                f"🎡 {stock_ticker} — {acciones_st} acciones @ ${precio_compra:.2f}  |  BE: ${costo_base_dinamico:.2f}",
                expanded=True
            ):
                st.markdown(f"""
                <div style='margin-bottom:10px;'>
                {indicator_html}
                &nbsp;&nbsp;
                <span style='color:#95a5a6; font-size:12px;'>ChainID: {stock_chain}</span>
                </div>
                """, unsafe_allow_html=True)

                wc1, wc2, wc3, wc4 = st.columns(4)
                wc1.metric("Acciones", f"{acciones_st}")
                wc2.metric("Precio Compra (Strike SP)", f"${precio_compra:.2f}")
                wc3.metric("Primas Acumuladas", f"${total_primas:.2f}",
                           help="PCS + Covered Calls + Buy Put cerrado")
                wc4.metric("💥 Costo Base Real (BE)", f"${costo_base_dinamico:.2f}",
                           delta=f"${costo_base_dinamico - precio_compra:+.2f} vs compra",
                           help="Precio al que estás en breakeven contando todas las primas cobradas")

                # Desglose de primas
                st.markdown("**📊 Desglose: cómo se reduce tu costo base:**")
                d1, d2, d3 = st.columns(3)
                d1.metric("\u2212 Prima neta PCS", f"${prima_neta_pcs:.2f}", help="Crédito neto del spread. Reduce el costo base desde el inicio.")
                d2.metric("\u2212 Covered Calls", f"${cc_prima_acum:.2f}", help="Suma de todas las primas de CC cobradas. Cada una baja más el costo base.")
                if buy_put_closed:
                    d3.metric("\u2212 Buy Put vendido ✅", f"${buy_put_prima_extra:.2f}",
                              help="Prima recibida al vender el Buy Put de protección en mercado. También reduce el costo base.")
                else:
                    d3.metric("\u2212 Buy Put (pendiente)", "$0.00",
                              help="El Buy Put de protección aún está abierto. Véndelo al mercado y registra el cierre para reducir más el costo base.")

                # Fórmula visual BE completa
                st.markdown(f"""
                <div style='background:#0d1117; border:1px solid #30363d; border-radius:8px;
                            padding:10px 14px; margin-top:8px; font-size:12px; color:#8b949e;'>
                <b style='color:#e6edf3;'>📐 Fórmula BE:</b> &nbsp;
                <code style='color:#f39c12;'>{precio_compra:.2f}</code>
                <span style='color:#e74c3c;'> − {prima_neta_pcs:.2f} (PCS)</span>
                <span style='color:#e74c3c;'> − {cc_prima_acum:.2f} (CC)</span>
                <span style='color:#e74c3c;'> − {buy_put_prima_extra:.2f} (BP)</span>
                <span style='color:#f39c12; font-weight:bold;'> = {costo_base_dinamico:.2f}</span>
                </div>
                """, unsafe_allow_html=True)

                st.divider()

                # --- Panel: Añadir / Gestionar Covered Call ---
                if not tiene_cc:
                    st.markdown("#### ➕ Vincular Covered Call")
                    st.caption("Registra una venta de Call sobre estas acciones para reducir el costo base.")
                    cc1, cc2, cc3 = st.columns(3)
                    cc_strike_val  = cc1.number_input("Strike del Call vendido", value=precio_compra * 1.02, step=0.5,
                                                      key=f"cc_strike_{stock_id}")
                    cc_prima_val   = cc2.number_input("Prima cobrada ($/acción)", value=0.0, step=0.01,
                                                      key=f"cc_prima_{stock_id}")
                    cc_expiry_val  = cc3.date_input("Vencimiento del CC", value=date.today() + timedelta(days=30),
                                                    key=f"cc_exp_{stock_id}")

                    nuevo_be = costo_base_dinamico - cc_prima_val
                    if cc_prima_val > 0:
                        st.info(f"📐 Nuevo Costo Base después del CC: **${nuevo_be:.2f}**")

                    if st.button("✅ Añadir Covered Call", type="primary", key=f"btn_add_cc_{stock_id}"):
                        if cc_prima_val <= 0:
                            st.warning("Introduce una prima mayor que 0.")
                        else:
                            # Crear el Covered Call en el journal
                            cc_chain_new = str(uuid4())[:8]
                            cc_new_row = {
                                "ID": str(uuid4())[:8],
                                "ChainID": cc_chain_new,
                                "ParentID": stock_id,
                                "Ticker": stock_ticker,
                                "FechaApertura": date.today().strftime("%Y-%m-%d"),
                                "Expiry": pd.to_datetime(cc_expiry_val).normalize(),
                                "Estrategia": "CC (Covered Call)",
                                "Setup": str(stock_row.get("Setup", "Otro")),
                                "Tags": "la-rueda,covered-call",
                                "Side": "Sell", "OptionType": "Call",
                                "Strike": cc_strike_val, "Delta": -0.3,
                                "PrimaRecibida": cc_prima_val, "CostoCierre": 0.0,
                                "Contratos": contratos_st,
                                "BuyingPower": 0.0,  # Las acciones ya son el colateral
                                "BreakEven": cc_strike_val + cc_prima_val, "BreakEven_Upper": 0.0,
                                "POP": 70.0, "Estado": "Abierta",
                                "Notas": f"CC vinculado a {acciones_st} acciones de {stock_ticker} (WheelChain: {stock_chain})",
                                "UpdatedAt": datetime.now().isoformat(), "FechaCierre": pd.NA,
                                "MaxProfitUSD": cc_prima_val * contratos_st * 100,
                                "ProfitPct": 0.0, "PnL_Capital_Pct": 0.0,
                                "PrecioAccionCierre": 0.0, "PnL_USD_Realizado": 0.0,
                                "Comisiones": contratos_st * 0.65,
                                "EarningsDate": stock_row.get("EarningsDate", pd.NA),
                                "DividendosDate": stock_row.get("DividendosDate", pd.NA),
                                "WheelParentChainID": stock_chain,
                                "CostBaseReal": nuevo_be,
                                "CoveredCallChainID": pd.NA,
                                "CoveredCallPrima": 0.0,
                                "WheelLeg": "covered_call",
                            }
                            # Añadir el CC al journal
                            st.session_state.df = pd.concat(
                                [st.session_state.df, pd.DataFrame([cc_new_row])], ignore_index=True
                            )
                            # Actualizar la posición de acciones: vincular el CC y acumular prima
                            stock_real_idx = st.session_state.df.index[st.session_state.df["ID"] == stock_id][0]
                            st.session_state.df.at[stock_real_idx, "CoveredCallChainID"] = cc_chain_new
                            st.session_state.df.at[stock_real_idx, "CoveredCallPrima"] = cc_prima_acum + cc_prima_val
                            st.session_state.df.at[stock_real_idx, "CostBaseReal"] = nuevo_be
                            st.session_state.df.at[stock_real_idx, "BreakEven"] = nuevo_be

                            st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                            st.success(f"✅ Covered Call añadido. Nuevo costo base: ${nuevo_be:.2f}")
                            st.rerun()
                else:
                    # Hay CC vinculado — mostrar resumen y botón Expirar CC (Escenario B)
                    st.markdown("#### 📋 Covered Call activo")
                    cc_linked = df[df["ChainID"] == cc_chain_id]
                    if not cc_linked.empty:
                        cc_leg = cc_linked.iloc[0]
                        cc_info1, cc_info2, cc_info3 = st.columns(3)
                        cc_info1.metric("Strike CC", f"${float(cc_leg.get('Strike', 0)):.2f}")
                        cc_info2.metric("Prima CC", f"${float(cc_leg.get('PrimaRecibida', 0)):.2f}/acción")
                        try:
                            exp_cc_str = pd.to_datetime(cc_leg["Expiry"]).strftime("%d %b %Y")
                        except:
                            exp_cc_str = "N/A"
                        cc_info3.metric("Vencimiento", exp_cc_str)

                    # --- ESCENARIO B: CC expira OTM — conservar acciones ---
                    st.markdown("---")
                    col_exp1, col_exp2 = st.columns([2, 1])
                    with col_exp1:
                        st.caption(
                            "⌛ Si el CC expiró sin valor (OTM), ciérralo a $0.00. "
                            "Las acciones permanecen intactas y podrás vender un nuevo CC el mes siguiente."
                        )
                    with col_exp2:
                        if st.button(
                            "⌛ Expirar CC (Conservar Acciones)",
                            key=f"btn_expire_cc_{stock_id}",
                            help="Cierra el Covered Call a $0.00 (expirado OTM). Las acciones siguen en cartera."
                        ):
                            st.session_state[f"expire_cc_{stock_id}"] = True

                    if st.session_state.get(f"expire_cc_{stock_id}", False):
                        cc_strike_exp = float(cc_linked.iloc[0].get("Strike", 0)) if not cc_linked.empty else 0.0
                        cc_prima_exp  = float(cc_linked.iloc[0].get("PrimaRecibida", 0)) if not cc_linked.empty else 0.0
                        cc_cntr_exp   = float(cc_linked.iloc[0].get("Contratos", contratos_st)) if not cc_linked.empty else contratos_st
                        pnl_exp_total = cc_prima_exp * cc_cntr_exp * 100

                        st.warning(
                            f"⚠️ Confirmas que el **CC Strike ${cc_strike_exp:.2f}** expiró sin valor (OTM). "
                            f"La prima cobrada de **${cc_prima_exp:.2f}/acción** (${pnl_exp_total:.2f} total) "
                            f"queda como beneficio íntegro. "
                            f"Las **{acciones_st} acciones de {stock_ticker}** se mantienen en cartera."
                        )
                        cexp1, cexp2 = st.columns(2)
                        if cexp1.button("✅ Confirmar Expiración del CC", type="primary",
                                        key=f"confirm_expire_cc_{stock_id}"):
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                            # 1. Cerrar el CC a $0.00 con PnL = prima íntegra
                            cc_exp_rows_idx = st.session_state.df.index[
                                (st.session_state.df["ChainID"] == cc_chain_id) &
                                (st.session_state.df["Estado"] == "Abierta")
                            ]
                            for idx_exp in cc_exp_rows_idx:
                                p_exp = float(st.session_state.df.at[idx_exp, "PrimaRecibida"] or 0)
                                c_exp = float(st.session_state.df.at[idx_exp, "Contratos"] or 1)
                                pnl_row_exp = p_exp * c_exp * 100

                                st.session_state.df.at[idx_exp, "Estado"] = "Cerrada"
                                st.session_state.df.at[idx_exp, "FechaCierre"] = now_str
                                st.session_state.df.at[idx_exp, "CostoCierre"] = 0.0
                                st.session_state.df.at[idx_exp, "PnL_USD_Realizado"] = pnl_row_exp
                                st.session_state.df.at[idx_exp, "Notas"] = (
                                    str(st.session_state.df.at[idx_exp, "Notas"] or "") +
                                    f" [OTM — expirado sin valor. Prima íntegra: ${pnl_row_exp:.2f}]"
                                )

                            # 2. Desvincular el CC de las acciones → queda libre para nuevo CC
                            stock_exp_idx = st.session_state.df.index[
                                st.session_state.df["ID"] == stock_id
                            ][0]
                            st.session_state.df.at[stock_exp_idx, "CoveredCallChainID"] = pd.NA
                            # Nota: CoveredCallPrima mantiene el acumulado histórico (no se borra)

                            st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                            if f"expire_cc_{stock_id}" in st.session_state:
                                del st.session_state[f"expire_cc_{stock_id}"]
                            st.success(
                                f"✅ CC expirado a $0.00. Prima cobrada íntegra: ${pnl_exp_total:.2f}. "
                                f"Las {acciones_st} acciones de {stock_ticker} siguen abiertas. "
                                f"Ya puedes vender un nuevo Covered Call. 🎡"
                            )
                            st.rerun()

                        if cexp2.button("❌ Cancelar", key=f"cancel_expire_cc_{stock_id}"):
                            del st.session_state[f"expire_cc_{stock_id}"]
                            st.rerun()

                    st.caption("💡 Para añadir otro Covered Call tras el vencimiento, usa el botón ⌛ de arriba.")

                # --- Cerrar la posición de acciones ---
                st.divider()
                if st.button("💰 Cerrar Posición (Vender acciones)", key=f"btn_close_stock_{stock_id}"):
                    st.session_state[f"close_stock_{stock_id}"] = True

                if st.session_state.get(f"close_stock_{stock_id}", False):
                    # Default: Strike del CC activo (precio al que nos "compran" si se ejerce),
                    # o precio de compra si no hay CC vinculado.
                    precio_default_venta = precio_compra
                    if tiene_cc and pd.notna(cc_chain_id):
                        cc_ref = df[df["ChainID"] == cc_chain_id]
                        if not cc_ref.empty:
                            precio_default_venta = float(cc_ref.iloc[0].get("Strike", precio_compra))

                    cs1, cs2, cs3 = st.columns(3)
                    precio_venta = cs1.number_input(
                        "Precio Venta ($/acción)",
                        value=precio_default_venta,
                        step=0.01,
                        key=f"sv_{stock_id}",
                        help="Por defecto: Strike del CC activo (precio de ejercicio). Ajusta si es diferente."
                    )
                    pnl_acciones = (precio_venta - costo_base_dinamico) * acciones_st
                    cs2.metric("PnL Estimado", f"${pnl_acciones:,.2f}",
                               help="(Precio Venta - Costo Base Real) × Número de Acciones")

                    if cs3.button("✅ Confirmar Venta", type="primary", key=f"confirm_sv_{stock_id}"):
                        stock_real_idx2 = st.session_state.df.index[st.session_state.df["ID"] == stock_id][0]
                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        # --- Cerrar posición Long Stock ---
                        st.session_state.df.at[stock_real_idx2, "Estado"] = "Cerrada"
                        st.session_state.df.at[stock_real_idx2, "FechaCierre"] = now_str
                        st.session_state.df.at[stock_real_idx2, "CostoCierre"] = precio_venta
                        st.session_state.df.at[stock_real_idx2, "PnL_USD_Realizado"] = pnl_acciones
                        st.session_state.df.at[stock_real_idx2, "PrecioAccionCierre"] = precio_venta
                        st.session_state.df.at[stock_real_idx2, "Notas"] = (
                            str(stock_row.get("Notas", "")) +
                            f" [VENDIDAS a ${precio_venta:.2f} | PnL acumulado: ${pnl_acciones:.2f}]"
                        )

                        # --- ESCENARIO A: Cerrar CC vinculado automáticamente a $0.00 ---
                        # El CC expira In-The-Money (o se ejerce). No lo recompramos: $0.00.
                        cc_cerrado_auto = False
                        if tiene_cc and pd.notna(cc_chain_id):
                            cc_rows_idx = st.session_state.df.index[
                                (st.session_state.df["ChainID"] == cc_chain_id) &
                                (st.session_state.df["Estado"] == "Abierta")
                            ]
                            for idx_cc in cc_rows_idx:
                                cc_row_data = st.session_state.df.loc[idx_cc]
                                prima_cc = float(cc_row_data.get("PrimaRecibida", 0) or 0)
                                contratos_cc = float(cc_row_data.get("Contratos", 1) or 1)
                                pnl_cc = prima_cc * contratos_cc * 100   # Prima cobrada íntegra = beneficio

                                st.session_state.df.at[idx_cc, "Estado"] = "Cerrada"
                                st.session_state.df.at[idx_cc, "FechaCierre"] = now_str
                                st.session_state.df.at[idx_cc, "CostoCierre"] = 0.0
                                st.session_state.df.at[idx_cc, "PnL_USD_Realizado"] = pnl_cc
                                st.session_state.df.at[idx_cc, "PrecioAccionCierre"] = precio_venta
                                st.session_state.df.at[idx_cc, "Notas"] = (
                                    str(st.session_state.df.at[idx_cc, "Notas"] or "") +
                                    f" [ITM — cerrado auto con acciones a $0.00 | PnL CC: ${pnl_cc:.2f}]"
                                )
                            cc_cerrado_auto = True

                        st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                        if f"close_stock_{stock_id}" in st.session_state:
                            del st.session_state[f"close_stock_{stock_id}"]

                        msg = f"🎉 ¡Ciclo de La Rueda completado para {stock_ticker}!"
                        if cc_cerrado_auto:
                            msg += " CC vinculado cerrado automáticamente a $0.00 (ejercido)."
                        msg += f" PnL acumulado Acciones: ${pnl_acciones:,.2f}"
                        st.success(msg)
                        st.rerun()

                    if st.button("🚫 Cancelar venta", key=f"cancel_sv_{stock_id}"):
                        del st.session_state[f"close_stock_{stock_id}"]
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
                
                # Comisiones estimadas de cierre
                comisiones_apertura = sum(float(r.get("Comisiones", 0.0)) for _, r in target_group.iterrows()) / qty_total * qty_to_close
                comisiones_cierre = 0.0
                for _, r in target_group.iterrows():
                    if r.get("Side", "Sell") == "Sell" and total_close_cost <= 0.05:
                        pass
                    else:
                        comisiones_cierre += qty_to_close * 0.65
                comisiones_totales = comisiones_apertura + comisiones_cierre

                # Cálculo de PnL usando la función centralizada
                pnl_preview, profit_pct_preview, roc_preview = calculate_pnl_metrics(
                    prima_neta=total_entry,
                    costo_cierre_neto=total_close_cost,
                    contracts=qty_to_close,
                    strategy=current_strategy,
                    bp=total_bp,
                    side_first_leg=target_group.iloc[0]["Side"],
                    comisiones_totales=comisiones_totales
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
                
                c_close_btn, c_cancel_btn = st.columns([2, 1])
                if c_close_btn.button(btn_label, type="primary", use_container_width=True):
                    for idx, row in target_group.iterrows():
                        real_idx = df.index[df["ID"] == row["ID"]][0]
                        
                        if is_partial:
                            # 1. Reducir contratos en la posición original
                            df.at[real_idx, "Contratos"] = qty_total - qty_to_close
                            df.at[real_idx, "Comisiones"] = float(row.get("Comisiones", 0.0)) / qty_total * (qty_total - qty_to_close)
                            
                            # 2. Crear nueva entrada CERRADA con la cantidad cerrada
                            new_closed_row = row.copy()
                            new_closed_row["ID"] = str(uuid4())[:8]
                            new_closed_row["Contratos"] = qty_to_close
                            new_closed_row["Estado"] = "Cerrada"
                            new_closed_row["FechaCierre"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            new_closed_row["PrecioAccionCierre"] = stock_price
                            
                            # Asignar COSTO, PNL y ProfitPct solo a la primera pata para no duplicar
                            new_closed_row["Comisiones"] = (float(row.get("Comisiones", 0.0)) / qty_total * qty_to_close) + (qty_to_close * 0.65 if not (row.get("Side", "Sell") == "Sell" and total_close_cost <= 0.05) else 0.0)
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
                            df.at[real_idx, "Comisiones"] = float(row.get("Comisiones", 0.0)) + (qty_to_close * 0.65 if not (row.get("Side", "Sell") == "Sell" and total_close_cost <= 0.05) else 0.0)
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

                if c_cancel_btn.button("🚫 Cancelar", key="cancel_close_btn", use_container_width=True):
                    del st.session_state["manage_chain_id"]
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

                    # Comisiones de cierre para el roll
                    roll_comisiones_apertura = sum(float(l.get("Comisiones", 0.0)) for l in legs_to_roll)
                    roll_comisiones_cierre = 0.0
                    for l in legs_to_roll:
                        if l.get("Side", "Sell") == "Sell" and roll_close_cost <= 0.05:
                            pass
                        else:
                            roll_comisiones_cierre += qty_roll * 0.65
                    roll_comisiones_totales = roll_comisiones_apertura + roll_comisiones_cierre

                    # Cálculo de PnL del cierre usando función centralizada
                    est_pnl_val, est_profit_pct, _ = calculate_pnl_metrics(
                        prima_neta=total_entry_to_roll,
                        costo_cierre_neto=roll_close_cost,
                        contracts=qty_roll,
                        strategy=roll_strategy,
                        bp=roll_bp,
                        side_first_leg=legs_to_roll[0]["Side"],
                        comisiones_totales=roll_comisiones_totales
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

                    c_btn1, c_btn2 = st.columns([2, 1])
                    if c_btn1.button("🚀 Ejecutar Ajuste", type="primary", use_container_width=True):
                        if new_expiry < date.today():
                            st.error("No se puede rolar a una fecha pasada.")
                        else:
                            # 1. Marcar ORIGINALES como Roladas
                            for leg in legs_to_roll:
                                real_idx = df.index[df["ID"] == leg["ID"]][0]
                                df.at[real_idx, "Estado"] = "Rolada"
                                df.at[real_idx, "FechaCierre"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                df.at[real_idx, "Comisiones"] = float(leg.get("Comisiones", 0.0)) + (qty_roll * 0.65 if not (leg.get("Side", "Sell") == "Sell" and roll_close_cost <= 0.05) else 0.0)
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
                                    "PrecioAccionCierre": 0.0, "PnL_USD_Realizado": 0.0,
                                    "Comisiones": n_leg["Contratos"] * 0.65,
                                    "EarningsDate": target_group.iloc[0].get("EarningsDate", pd.NA), # Mantener EarningsDate del original
                                    "DividendosDate": target_group.iloc[0].get("DividendosDate", pd.NA) # Mantener DividendosDate
                                })
                            
                            if new_rows:
                                st.session_state.df = pd.concat([st.session_state.df.dropna(how='all', axis=0), pd.DataFrame(new_rows)], ignore_index=True)
                            
                            st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                            del st.session_state["manage_chain_id"]
                            st.success("Roll ejecutado con éxito.")
                            st.rerun()

                    if c_btn2.button("🚫 Cancelar Roll", key="cancel_roll_btn", use_container_width=True):
                        del st.session_state["manage_chain_id"]
                        st.rerun()
            
            # --- TAB 3: ASIGNACIÓN (Ciclo de La Rueda) ---
            with tab_assign:
                current_strategy_assign = target_group.iloc[0]["Estrategia"]
                is_pcs = "Put Credit Spread" in current_strategy_assign
                ticker_assign = target_group.iloc[0]["Ticker"]
                contratos_assign = int(target_group.iloc[0]["Contratos"])
                acciones_asignadas = contratos_assign * 100

                # Identificar las patas del PCS
                sell_put_leg = None
                buy_put_leg = None
                if is_pcs:
                    for _, leg in target_group.iterrows():
                        if leg["Side"] == "Sell" and leg["OptionType"] == "Put":
                            sell_put_leg = leg
                        elif leg["Side"] == "Buy" and leg["OptionType"] == "Put":
                            buy_put_leg = leg

                if is_pcs and sell_put_leg is not None:
                    st.markdown("#### 🎡 Asignación — Inicio del Ciclo de La Rueda")
                    st.markdown("""
                    <div style='background:linear-gradient(135deg,#1a2a1a,#0f1f2f); border:1px solid #00ffa2; 
                         border-radius:10px; padding:16px; margin-bottom:16px;'>
                    <h4 style='color:#00ffa2; margin:0 0 8px 0;'>🎡 Flujo de La Rueda (The Wheel)</h4>
                    <p style='color:#bdc3c7; margin:0; font-size:13px;'>
                    <b style='color:#e74c3c;'>① Sell Put → ASIGNADO</b> &nbsp;|&nbsp;
                    <b style='color:#27ae60;'>② Buy Put → QUEDA ABIERTO</b> &nbsp;|&nbsp;
                    <b style='color:#f39c12;'>③ Se crean 100 acciones × contrato</b>
                    </p>
                    </div>
                    """, unsafe_allow_html=True)

                    strike_sell = float(sell_put_leg["Strike"])
                    prima_sell = float(sell_put_leg["PrimaRecibida"])
                    prima_buy = float(buy_put_leg["PrimaRecibida"]) if buy_put_leg is not None else 0.0

                    col_a1, col_a2 = st.columns(2)
                    with col_a1:
                        st.markdown(f"**🔴 Sell Put a cerrar (Asignado):**")
                        st.markdown(f"- Strike: **${strike_sell:,.2f}**")
                        st.markdown(f"- Prima cobrada: **${prima_sell:.2f}/acción**")
                        st.markdown(f"- Contratos: **{contratos_assign}**")
                    with col_a2:
                        if buy_put_leg is not None:
                            st.markdown(f"**🟢 Buy Put de protección (Queda ABIERTO):**")
                            st.markdown(f"- Strike: **${float(buy_put_leg['Strike']):,.2f}**")
                            st.markdown(f"- Prima pagada (como coste): **${abs(prima_buy):.2f}/acción**")
                            st.markdown(f"- Estado después: `Abierto` para vender al mercado")
                        else:
                            st.info("No se detectó pata Buy Put en este spread.")

                    st.divider()

                    # Cálculo del Costo Base Real
                    # CostBase = Strike Sell Put - (Prima Sell Put - Prima Buy Put)
                    prima_neta_pcs = prima_sell - abs(prima_buy)
                    costo_base_inicial = strike_sell - prima_neta_pcs

                    st.markdown("#### 📐 Costo Base Real de las Acciones")
                    st.markdown(f"""
                    <div style='background:#1e2130; border-radius:8px; padding:14px; border-left:4px solid #f39c12;'>
                    <p style='color:#bdc3c7; margin:0; font-size:13px;'>
                    <b>Fórmula inicial (PCS):</b><br>
                    <code>BE = Strike SP − (Prima SP cobrada − Prima BP pagada)</code><br>
                    <b>= ${strike_sell:.2f} − (${prima_sell:.2f} − ${abs(prima_buy):.2f})</b><br>
                    <b>= ${strike_sell:.2f} − ${prima_neta_pcs:.2f}</b><br>
                    <span style='color:#f39c12; font-size:16px; font-weight:bold;'>= ${costo_base_inicial:.2f} por acción</span>
                    <br><br>
                    <span style='color:#00ffa2; font-size:12px; font-weight:bold;'>Fórmula completa (ciclo La Rueda):</span><br>
                    <code style='color:#00ffa2;'>BE final = Strike SP − Prima PCS − Prima CC acumulada − Prima Buy Put vendido</code><br>
                    <span style='color:#95a5a6; font-size:11px;'>⚠️ Cada prima cobrada REDUCE el costo base (se resta). El BE se actualiza automáticamente.</span>
                    </p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Clave de sesión para el estado del desglose
                    desglose_key = f"wheel_desglose_{target_chain}"
                    is_desglosando = st.session_state.get(desglose_key, False)

                    st.divider()
                    st.info(f"🏦 Se crearán **{acciones_asignadas} acciones** de **{ticker_assign}** con precio de compra ${strike_sell:,.2f}")

                    if not is_desglosando:
                        # --- PASO 1: Botón inicial ---
                        c_assign_btn, c_assign_cancel = st.columns([2, 1])
                        if c_assign_btn.button("🎡 Ejecutar Asignación (La Rueda)", type="primary",
                                               use_container_width=True, key="btn_assign_wheel"):
                            st.session_state[desglose_key] = True
                            st.rerun()

                        if c_assign_cancel.button("🚫 Cancelar", key="cancel_assign_btn",
                                                  use_container_width=True):
                            del st.session_state["manage_chain_id"]
                            st.rerun()

                    else:
                        # --- PASO 2: Mini-formulario de desglose ---
                        st.markdown("""
                        <div style='background:linear-gradient(135deg,#1f1b2e,#0f1f2f);
                             border:1px solid #f39c12; border-radius:10px; padding:16px; margin-bottom:12px;'>
                        <h4 style='color:#f39c12; margin:0 0 6px 0;'>📋 Desglose de primas del PCS</h4>
                        <p style='color:#bdc3c7; margin:0; font-size:13px;'>
                        Como registraste la <b>Prima Neta</b> del spread completo, necesitamos
                        saber cuánto pagaste por la pata de protección (Buy Put) para calcular
                        correctamente el costo base de las acciones y el PnL del Sell Put.
                        </p>
                        </div>
                        """, unsafe_allow_html=True)

                        prima_neta_guardada = prima_sell  # Lo que hay en BD = Prima Neta total del spread

                        dg1, dg2 = st.columns(2)
                        dg1.metric("Prima Neta guardada (Spread completo)", f"${prima_neta_guardada:.2f}/acción",
                                   help="Crédito neto que registraste al abrir el PCS")

                        prima_buy_input = dg2.number_input(
                            "💸 ¿Cuánto pagaste por el Buy Put? ($/acción)",
                            min_value=0.0,
                            max_value=float(prima_neta_guardada),
                            value=0.0,
                            step=0.01,
                            key=f"prima_buy_input_{target_chain}",
                            help=(
                                "Prima que pagaste por la pata larga de protección. "
                                "Ej: Si tu neta fue $1.13 y el BP te costó $0.88, "
                                "el SP valía $2.01."
                            )
                        )

                        # Cálculo automático: SP = Neta + BP (back-calculation)
                        prima_sell_real = prima_neta_guardada + prima_buy_input
                        costo_base_calc = strike_sell - prima_neta_guardada  # BE = Strike - Prima Neta

                        # Desglose visual en tiempo real
                        st.markdown(f"""
                        <div style='background:#0d1117; border:1px solid #30363d; border-radius:8px;
                                    padding:12px 16px; margin:8px 0; font-size:13px;'>
                        <b style='color:#e6edf3;'>🔢 Desglose calculado:</b><br>
                        <span style='color:#e74c3c;'>🔴 Sell Put cobrado
                        = Prima Neta + Prima Buy Put
                        = ${prima_neta_guardada:.2f} + ${prima_buy_input:.2f}
                        = <b>${prima_sell_real:.2f}/acción</b></span><br>
                        <span style='color:#27ae60;'>🟢 Buy Put pagado = <b>${prima_buy_input:.2f}/acción</b>
                        → quedará abierta para vender</span><br>
                        <span style='color:#f39c12; font-weight:bold;'>
                        💥 Costo Base Inicial = ${strike_sell:.2f} − ${prima_neta_guardada:.2f} (prima neta PCS)
                        = <b>${costo_base_calc:.2f}/acción</b></span><br>
                        <span style='color:#95a5a6; font-size:11px;'>
                        ↳ Este es el BE de partida. Se irá reduciendo en el Panel La Rueda
                        cuando vendas el Buy Put (+prima) y añadas Covered Calls (+prima).
                        </span>
                        </div>
                        """, unsafe_allow_html=True)

                        c_conf1, c_conf2 = st.columns([2, 1])
                        confirmar_disabled = (prima_buy_input <= 0.0)
                        if confirmar_disabled:
                            st.caption("⬆️ Introduce la prima del Buy Put para desbloquear la confirmación.")

                        if c_conf1.button("✅ Confirmar y Ejecutar Asignación", type="primary",
                                          use_container_width=True, key="btn_confirm_wheel",
                                          disabled=confirmar_disabled):
                            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            total_comisiones_apertura = sum(
                                float(r.get("Comisiones", 0.0)) for _, r in target_group.iterrows()
                            )

                            # === PASO 1: Marcar SELL PUT como ASIGNADO + corregir prima real ===
                            sell_idx = st.session_state.df.index[
                                st.session_state.df["ID"] == sell_put_leg["ID"]
                            ][0]
                            st.session_state.df.at[sell_idx, "Estado"] = "Asignada"
                            st.session_state.df.at[sell_idx, "FechaCierre"] = now_str
                            st.session_state.df.at[sell_idx, "CostoCierre"] = 0.0
                            # Actualizamos la prima con el valor real desglosado
                            st.session_state.df.at[sell_idx, "PrimaRecibida"] = prima_sell_real
                            pnl_sell_put = (prima_sell_real * contratos_assign * 100) - total_comisiones_apertura
                            st.session_state.df.at[sell_idx, "PnL_USD_Realizado"] = pnl_sell_put
                            st.session_state.df.at[sell_idx, "Notas"] = (
                                str(sell_put_leg.get("Notas", "")) +
                                f" [ASIGNADO @ ${strike_sell:.2f} | SP: ${prima_sell_real:.2f} — La Rueda iniciada]"
                            )
                            st.session_state.df.at[sell_idx, "WheelLeg"] = "sell_put"

                            # === PASO 2: BUY PUT queda ABIERTO — corregir prima real ===
                            if buy_put_leg is not None:
                                buy_idx = st.session_state.df.index[
                                    st.session_state.df["ID"] == buy_put_leg["ID"]
                                ][0]
                                # Guardamos el coste real del BP (negativo = pagamos nosotros)
                                st.session_state.df.at[buy_idx, "PrimaRecibida"] = -prima_buy_input
                                st.session_state.df.at[buy_idx, "Notas"] = (
                                    str(buy_put_leg.get("Notas", "")) +
                                    f" [PROTECCIÓN ${prima_buy_input:.2f}/acción — vender para bajar costo base]"
                                )
                                st.session_state.df.at[buy_idx, "WheelLeg"] = "buy_put_open"
                                st.session_state.df.at[buy_idx, "WheelParentChainID"] = target_chain

                            # === PASO 3: Crear posición Long Stock ===
                            stock_chain_id = str(uuid4())[:8]
                            stock_data = {
                                "ID": str(uuid4())[:8],
                                "ChainID": stock_chain_id,
                                "ParentID": sell_put_leg["ID"],
                                "Ticker": ticker_assign,
                                "FechaApertura": datetime.now().strftime("%Y-%m-%d"),
                                "Expiry": pd.to_datetime("2099-12-31").normalize(),
                                "Estrategia": "Long Stock (Asignación)",
                                "Setup": str(target_group.iloc[0].get("Setup", "Otro")),
                                "Tags": "la-rueda,asignacion",
                                "Side": "Buy",
                                "OptionType": "Stock",
                                "Strike": strike_sell,
                                "Delta": 1.0,
                                "PrimaRecibida": prima_neta_guardada,  # Prima neta = crédito real del PCS
                                "CostoCierre": 0.0,
                                "Contratos": contratos_assign,
                                "BuyingPower": strike_sell * acciones_asignadas,
                                "BreakEven": costo_base_calc,
                                "BreakEven_Upper": 0.0,
                                "POP": 0.0,
                                "Estado": "Abierta",
                                "Notas": (
                                    f"Acciones por asignación PCS | "
                                    f"SP cobrado: ${prima_sell_real:.2f} | "
                                    f"BP pagado: ${prima_buy_input:.2f} | "
                                    f"Neta PCS: ${prima_neta_guardada:.2f} | "
                                    f"Costo base: ${costo_base_calc:.2f}/acción"
                                ),
                                "UpdatedAt": datetime.now().isoformat(),
                                "FechaCierre": pd.NA,
                                "MaxProfitUSD": 0.0,
                                "ProfitPct": 0.0,
                                "PnL_Capital_Pct": 0.0,
                                "PrecioAccionCierre": 0.0,
                                "PnL_USD_Realizado": 0.0,
                                "Comisiones": 0.0,
                                "EarningsDate": target_group.iloc[0].get("EarningsDate", pd.NA),
                                "DividendosDate": target_group.iloc[0].get("DividendosDate", pd.NA),
                                "WheelParentChainID": target_chain,
                                "CostBaseReal": costo_base_calc,
                                "CoveredCallChainID": pd.NA,
                                "CoveredCallPrima": 0.0,
                                "WheelLeg": "long_stock",
                            }
                            st.session_state.df = pd.concat(
                                [st.session_state.df, pd.DataFrame([stock_data])],
                                ignore_index=True
                            )

                            st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                            if desglose_key in st.session_state:
                                del st.session_state[desglose_key]
                            del st.session_state["manage_chain_id"]
                            st.success(
                                f"🎡 ¡La Rueda iniciada! {acciones_asignadas} acciones de {ticker_assign} "
                                f"creadas. Costo base: ${costo_base_calc:.2f}. Buy Put queda abierto (${prima_buy_input:.2f}).",
                                icon="🎡"
                            )
                            st.rerun()

                        if c_conf2.button("↩️ Atrás", key="btn_back_desglose", use_container_width=True):
                            del st.session_state[desglose_key]
                            st.rerun()



                else:
                    # --- Asignación genérica para CSP u otras estrategias ---
                    st.markdown("#### 📜 Asignación")
                    if is_pcs:
                        st.warning("⚠️ No se pudo identificar el Sell Put del spread. Usando flujo genérico.")
                    else:
                        st.info(f"Marcando **{current_strategy_assign}** como Asignada y creando posición de acciones.")

                    assign_leg = target_group.iloc[0]
                    assign_price_gen = float(assign_leg["Strike"])
                    contratos_gen = int(assign_leg["Contratos"])

                    st.info(f"Se te asignarán **{contratos_gen * 100} acciones** de **{ticker_assign}** a **${assign_price_gen:.2f}**.")

                    c_assign_btn2, c_assign_cancel2 = st.columns([2, 1])
                    if c_assign_btn2.button("✅ Confirmar Asignación", type="primary", use_container_width=True, key="btn_assign_generic"):
                        total_comisiones_ap = sum(float(r.get("Comisiones", 0.0)) for _, r in target_group.iterrows())
                        now_str2 = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        for idx_g, row_g in target_group.iterrows():
                            real_idx_g = df.index[df["ID"] == row_g["ID"]][0]
                            df.at[real_idx_g, "Estado"] = "Asignada"
                            df.at[real_idx_g, "FechaCierre"] = now_str2
                            df.at[real_idx_g, "MaxProfitUSD"] = 0.0
                            if row_g["ID"] == assign_leg["ID"]:
                                pnl_gen = (float(row_g["PrimaRecibida"]) * contratos_gen * 100) - total_comisiones_ap
                                df.at[real_idx_g, "PnL_USD_Realizado"] = pnl_gen
                                df.at[real_idx_g, "Notas"] = str(row_g.get("Notas", "")) + f" [ASIGNADA a {assign_price_gen}]"
                            else:
                                df.at[real_idx_g, "PnL_USD_Realizado"] = 0.0

                        # Crear Long Stock genérico
                        stock_chain_id2 = str(uuid4())[:8]
                        prima_gen = float(assign_leg.get("PrimaRecibida", 0.0))
                        cost_base_gen = assign_price_gen - prima_gen
                        stock_row2 = {
                            "ID": str(uuid4())[:8], "ChainID": stock_chain_id2, "ParentID": assign_leg["ID"],
                            "Ticker": ticker_assign, "FechaApertura": datetime.now().strftime("%Y-%m-%d"),
                            "Expiry": pd.to_datetime("2099-12-31").normalize(), "Estrategia": "Long Stock (Asignación)",
                            "Setup": str(assign_leg.get("Setup", "Otro")), "Tags": "la-rueda,asignacion",
                            "Side": "Buy", "OptionType": "Stock", "Strike": assign_price_gen, "Delta": 1.0,
                            "PrimaRecibida": prima_gen, "CostoCierre": 0.0, "Contratos": contratos_gen,
                            "BuyingPower": assign_price_gen * contratos_gen * 100,
                            "BreakEven": cost_base_gen, "BreakEven_Upper": 0.0, "POP": 0.0, "Estado": "Abierta",
                            "Notas": f"Acciones por asignación de {current_strategy_assign}. Costo base: ${cost_base_gen:.2f}",
                            "UpdatedAt": datetime.now().isoformat(), "FechaCierre": pd.NA,
                            "MaxProfitUSD": 0.0, "ProfitPct": 0.0, "PnL_Capital_Pct": 0.0,
                            "PrecioAccionCierre": 0.0, "PnL_USD_Realizado": 0.0, "Comisiones": 0.0,
                            "EarningsDate": assign_leg.get("EarningsDate", pd.NA), "DividendosDate": assign_leg.get("DividendosDate", pd.NA),
                            "WheelParentChainID": target_chain, "CostBaseReal": cost_base_gen,
                            "CoveredCallChainID": pd.NA, "CoveredCallPrima": 0.0, "WheelLeg": "long_stock",
                        }
                        st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([stock_row2])], ignore_index=True)
                        st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                        del st.session_state["manage_chain_id"]
                        st.success("Operación marcada como Asignada y acciones creadas.")
                        st.rerun()

                    if c_assign_cancel2.button("🚫 Cancelar", key="cancel_assign_btn2", use_container_width=True):
                        del st.session_state["manage_chain_id"]
                        st.rerun()

def render_express_0dte():
    """Formulario simplificado para operaciones 0DTE (especialmente SPX)."""
    st.markdown("### ⚡ Registro Express 0DTE")
    st.caption("Diseñado para registrar operaciones 0DTE de SPX rápidamente. Solo los campos esenciales.")
    
    # Verificar si viene de un 'Duplicar'
    dup_defaults = st.session_state.pop("express_dup_defaults", None)

    # --- Estrategias más comunes en 0DTE ---
    express_strategies = [
        "Iron Condor", "Put Credit Spread", "Call Credit Spread",
        "Iron Fly", "Strangle", "Put Debit Spread", "Call Debit Spread",
        "CSP (Cash Secured Put)", "Long Call", "Long Put"
    ]
    
    col_t, col_e, col_c = st.columns([1, 2, 1])
    
    default_ticker = dup_defaults.get("ticker", "SPX") if dup_defaults else "SPX"
    default_strat_idx = express_strategies.index(dup_defaults.get("estrategia")) if dup_defaults and dup_defaults.get("estrategia") in express_strategies else 0
    default_contratos = int(dup_defaults.get("contratos", 1)) if dup_defaults else 1
    
    ticker_exp = col_t.text_input("Ticker", value=default_ticker, key="exp_ticker").upper()
    estrategia_exp = col_e.selectbox("Estrategia", express_strategies, index=default_strat_idx, key="exp_estrategia")
    contratos_exp = col_c.number_input("Contratos", min_value=1, value=default_contratos, key="exp_contratos")
    
    # La fecha de apertura y vencimiento son HOY (0DTE)
    hoy = date.today()
    col_p, col_bp = st.columns(2)
    default_prima = float(dup_defaults.get("prima", 0.0)) if dup_defaults else 0.0
    default_bp = float(dup_defaults.get("buying_power", 0.0)) if dup_defaults else 0.0
    prima_exp = col_p.number_input("💰 Prima recibida ($/acción)", value=default_prima, step=0.01, key="exp_prima")
    bp_exp = col_bp.number_input("🏦 Capital Reservado ($)", value=default_bp, step=100.0, key="exp_bp", help="Buying Power que reserva tu broker")
    
    # --- Cierre (opcional, si ya cerró la operación) ---
    st.markdown("---")
    col_cierre, col_estado = st.columns(2)
    ya_cerro = col_cierre.checkbox("✅ La operación ya está cerrada", value=False, key="exp_cerrada")
    
    cierre_exp = 0.0
    fecha_cierre_exp = hoy
    if ya_cerro:
        cierre_exp = col_cierre.number_input("Precio Cierre ($/acción)", value=0.0, step=0.01, key="exp_cierre")
        fecha_cierre_exp = col_estado.date_input("Fecha Cierre", value=hoy, key="exp_fecha_cierre")
    
    notas_exp = st.text_input("📝 Notas (opcional)", placeholder="Ej: Apertura en mínimo de sesión, VIX alto...", key="exp_notas")
    
    # --- Botón ---
    if st.button("⚡ Registrar Express", type="primary", use_container_width=True, key="exp_submit"):
        if not ticker_exp:
            st.error("Debes indicar un Ticker.")
            return
        
        # Calcular patas automáticamente según estrategia
        leg_defs = LEG_DEFAULTS.get(estrategia_exp, [("Sell", "Put")])
        chain_id = str(uuid4())[:8]
        new_rows_exp = []
        
        direction = detect_strategy_direction(estrategia_exp)
        
        # PnL si ya cerró
        pnl_usd = 0.0
        profit_pct = 0.0
        estado_final = "Abierta"
        fecha_cierre_str = pd.NA
        
        if ya_cerro:
            pnl_usd, profit_pct, _ = calculate_pnl_metrics(
                prima_exp, cierre_exp, contratos_exp, estrategia_exp, bp_exp
            )
            estado_final = "Cerrada"
            fecha_cierre_str = fecha_cierre_exp.strftime("%Y-%m-%d")
        
        for i_leg, (l_side, l_type) in enumerate(leg_defs):
            new_rows_exp.append({
                "ID": str(uuid4()),
                "ChainID": chain_id,
                "ParentID": pd.NA,
                "Ticker": ticker_exp,
                "FechaApertura": hoy.strftime("%Y-%m-%d"),
                "Expiry": hoy.strftime("%Y-%m-%d"),  # 0DTE = vence hoy
                "Estrategia": estrategia_exp,
                "Setup": "Otro",
                "Tags": "0dte,express",
                "Side": l_side,
                "OptionType": l_type,
                "Strike": 0.0,
                "Delta": 0.0,
                "PrimaRecibida": prima_exp if i_leg == 0 else 0.0,
                "CostoCierre": cierre_exp if (i_leg == 0 and ya_cerro) else 0.0,
                "Contratos": contratos_exp,
                "BuyingPower": bp_exp if i_leg == 0 else 0.0,
                "BreakEven": 0.0,
                "BreakEven_Upper": 0.0,
                "POP": 0.0,
                "Estado": estado_final,
                "Notas": notas_exp or f"Express 0DTE – {estrategia_exp}",
                "UpdatedAt": datetime.now().isoformat(),
                "FechaCierre": fecha_cierre_str,
                "MaxProfitUSD": (prima_exp * contratos_exp * 100) if i_leg == 0 else 0.0,
                "ProfitPct": profit_pct if (i_leg == 0 and ya_cerro) else 0.0,
                "PnL_Capital_Pct": (pnl_usd / bp_exp * 100) if (bp_exp > 0 and i_leg == 0 and ya_cerro) else 0.0,
                "PrecioAccionCierre": 0.0,
                "PnL_USD_Realizado": pnl_usd if (i_leg == 0 and ya_cerro) else 0.0,
                "Comisiones": contratos_exp * 0.65,
                "EarningsDate": pd.NA,
                "DividendosDate": pd.NA,
            })
        
        new_df_exp = pd.DataFrame(new_rows_exp)
        st.session_state.df = pd.concat([st.session_state.df, new_df_exp], ignore_index=True)
        st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
        estado_txt = "cerrada" if ya_cerro else "abierta"
        pnl_txt = f" | PnL: ${pnl_usd:,.2f}" if ya_cerro else ""
        st.toast(f"⚡ {ticker_exp} {estrategia_exp} registrada ({estado_txt}){pnl_txt}", icon="🚀")
        # Limpiar claves del formulario express
        for _k in ["exp_ticker", "exp_prima", "exp_cierre", "exp_notas", "exp_bp", "exp_contratos", "exp_estrategia", "exp_cerrada", "exp_fecha_cierre"]:
            if _k in st.session_state:
                del st.session_state[_k]
        st.rerun()


def render_new_trade():
    st.header("➕ Nueva Operación")
    
    tab_completo, tab_express = st.tabs(["📋 Formulario Completo", "⚡ 0DTE Express"])
    
    with tab_express:
        render_express_0dte()
    
    with tab_completo:
    
        # === FASE 1: ¿Qué hiciste? (esencial) ===
        c_top1, c_top2 = st.columns([1, 2])
        ticker = c_top1.text_input("Ticker", key="nt_ticker").upper()
        estrategia = c_top2.selectbox("Estrategia", ESTRATEGIAS, key="nt_estrategia")
        
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
        total_premium = c_p1.number_input("Prima ($/acción)", value=0.0, step=0.01, help=premium_help, key="nt_premium")
        contratos = c_p2.number_input("Contratos", value=1, min_value=1, key="nt_contratos")
        expiry = c_p3.date_input("📅 Vencimiento", key="nt_expiry")
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
            
            # Delta secundaria: para IC, Iron Fly, Strangle y Straddle mejora el cálculo del POP
            is_dual_be = estrategia in DUAL_BE_STRATEGIES
            secondary_delta = 0.0
            if is_dual_be:
                secondary_delta = st.number_input(
                    "Delta (pata secundaria — short call / call side)",
                    value=0.0, step=0.01,
                    help="Delta de la pata corta secundaria (ej: short call en IC). "
                         "Permite calcular el POP correctamente: 1 − |Δ_put| − |Δ_call|. "
                         "Déjalo en 0.00 si solo tienes un lado.",
                    key="nt_delta2"
                )
            
            # Cálculos sugeridos
            be_lower, be_upper = suggest_breakeven(estrategia, legs_data, total_premium)
            suggested_pop = suggest_pop(main_delta, main_side, secondary_delta)
            
            # === FASE 3: Detalles Opcionales (colapsable) ===
            with st.expander("⚙️ Detalles opcionales", expanded=False):
                c_ad1, c_ad2, c_ad3 = st.columns(3)
                setup_val = c_ad1.selectbox("🎯 Setup / Motivo", SETUPS, key="setup_select")
                fecha_apertura = c_ad2.date_input("📅 Fecha Apertura", value=date.today(), help="Cambia si registras la operación un día diferente.", key="f_apert")
                user_tags = c_ad3.text_input("🏷️ Tags", placeholder="income, hedge", help="Etiquetas separadas por coma", key="tags_input")
                
                c_bp1, c_bp2, c_bp3 = st.columns(3)
                buy_pow = c_bp1.number_input("Capital Reservado ($)", value=0.0, step=100.0, help="Buying Power reservado por tu broker para esta posición.", key="bp_input")
                earn_dt = c_bp2.date_input("📢 Fecha Earnings (Opcional)", value=None, help="Si hay resultados próximos, introduce la fecha para trackearlos.", key="earn_input")
                div_dt = c_bp3.date_input("💰 Fecha Dividendos (Opcional)", value=None, help="Si hay dividendos próximos, introduce la fecha.", key="div_input")
                
                if is_dual_be:
                    c_be1, c_be2, c_be3 = st.columns(3)
                    be_input = c_be1.number_input("BE Inferior", value=float(be_lower), step=0.01, help="Break Even del lado bajista", key="be_low")
                    be_upper_input = c_be2.number_input("BE Superior", value=float(be_upper), step=0.01, help="Break Even del lado alcista", key="be_upp")
                    pop_val = c_be3.number_input("POP %", value=float(suggested_pop), step=0.1, key="pop_in")
                else:
                    c_be1, c_be2 = st.columns(2)
                    be_input = c_be1.number_input("Break Even", value=float(be_lower), step=0.01, key="be_single")
                    be_upper_input = 0.0
                    pop_val = c_be2.number_input("POP %", value=float(suggested_pop), step=0.1, key="pop_single")
            
            c_sub, c_canc = st.columns(2)
            submitted = c_sub.form_submit_button("✅ Registrar Operación", type="primary", use_container_width=True)
            canceled = c_canc.form_submit_button("🚫 Limpiar / Cancelar", use_container_width=True)
            
            if canceled:
                st.rerun()
                
            if submitted:
                if not ticker:
                    st.error("Debes indicar un Ticker.")
                    return

                chain_id = str(uuid4())[:8]
                new_rows = []
                
                legs_final = legs_data

                for i_leg, leg in enumerate(legs_final):
                    s_val = leg["Strike"] 
                    new_rows.append({
                        "ID": str(uuid4()),
                        "ChainID": chain_id,
                        "ParentID": pd.NA,
                        "Ticker": ticker,
                        "FechaApertura": fecha_apertura.strftime("%Y-%m-%d"),
                        "Expiry": expiry.strftime("%Y-%m-%d"),
                        "Estrategia": estrategia,
                        "Setup": setup_val,
                        "Tags": user_tags,
                        "Side": leg["Side"],
                        "OptionType": leg["Type"],
                        "Strike": s_val,
                        "Delta": leg["Delta"],
                        "PrimaRecibida": total_premium if i_leg == 0 else 0.0,
                        "CostoCierre": 0.0,
                        "Contratos": contratos,
                        "BuyingPower": buy_pow if i_leg == 0 else 0.0,
                        "BreakEven": be_input,
                        "BreakEven_Upper": be_upper_input,
                        "POP": pop_val,
                        "Estado": "Abierta", "Notas": f"Parte de {estrategia}",
                        "UpdatedAt": datetime.now().isoformat(), "FechaCierre": pd.NA,
                        "MaxProfitUSD": (total_premium * contratos * 100) if i_leg == 0 else 0.0,
                        "ProfitPct": 0.0, "PnL_Capital_Pct": 0.0,
                        "PrecioAccionCierre": 0.0, "PnL_USD_Realizado": 0.0,
                        "Comisiones": contratos * 0.65,
                        "EarningsDate": earn_dt.strftime("%Y-%m-%d") if earn_dt else pd.NA,
                        "DividendosDate": div_dt.strftime("%Y-%m-%d") if div_dt else pd.NA
                    })
                
                if new_rows:
                    new_df = pd.DataFrame(new_rows)
                    st.session_state.df = pd.concat([st.session_state.df, new_df], ignore_index=True)
                    st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
                    _saved_ticker = ticker
                    for _k in ["nt_ticker", "nt_premium", "nt_contratos", "nt_expiry", "nt_estrategia", "nt_delta2"]:
                        if _k in st.session_state:
                            del st.session_state[_k]
                    st.toast(f"✅ {_saved_ticker} registrada correctamente.", icon="🎉")
                    st.rerun()
        




def render_history(df):
    if "edit_trade_id" in st.session_state:
        render_inline_edit(st.session_state["edit_trade_id"])
        st.divider()
        st.stop()

    st.header("📜 Historial de Operaciones")
    
    # --- Datos de base ---
    hist_df = df[df["Estado"] != "Abierta"].copy()
    if hist_df.empty:
        st.info("Aún no hay operaciones cerradas en el historial.")
        return
        
    # Aseguramos que FechaCierre sea comparable de forma segura
    hist_df["__dt_sort"] = pd.to_datetime(hist_df["FechaCierre"], errors='coerce')
    
    # Alerta de trades sin fecha
    undated = hist_df[hist_df["FechaCierre"].isna()]
    if not undated.empty:
        st.warning(f"⚠️ Se han detectado {len(undated)} operaciones cerradas sin fecha de cierre.")

    # =========================================================
    # --- FILTROS EXPANDIDOS ---
    # =========================================================
    with st.expander("🔍 Filtros", expanded=False):
        # Fila 1: Ticker | Estrategia | Setup | Estado
        cf1, cf2, cf3, cf4 = st.columns(4)
        hist_tickers = ["Todos"] + sorted(hist_df["Ticker"].dropna().unique().tolist())
        t_filt = cf1.selectbox("🏷️ Ticker", hist_tickers, key="hist_t")
        
        hist_strat = ["Todos"] + ESTRATEGIAS
        e_filt = cf2.selectbox("📊 Estrategia", hist_strat, key="hist_e")
        
        hist_setup = ["Todos"] + SETUPS
        s_filt = cf3.selectbox("🎯 Setup", hist_setup, key="hist_s")
        
        estados_hist = ["Todos"] + sorted(hist_df["Estado"].dropna().unique().tolist())
        estado_filt = cf4.selectbox("📌 Estado", estados_hist, key="hist_estado")

        # Fila 2: Resultado | Tags | Rango Fecha
        cf5, cf6, cf7 = st.columns([1, 1, 2])
        resultado_filt = cf5.selectbox("💰 Resultado", ["Todos", "✅ Ganadoras", "❌ Perdedoras"], key="hist_resultado")
        tags_filt = cf6.text_input("🔖 Buscar Tag", placeholder="ej: hedge, 0DTE...", key="hist_tags")
        
        valid_dates = hist_df["__dt_sort"].dropna()
        fecha_min_val = valid_dates.min().date() if not valid_dates.empty else (date.today() - timedelta(days=365))
        with cf7:
            st.markdown("📅 **Rango de cierre**")
            date_range = st.date_input(
                "Rango", [fecha_min_val, date.today()], key="hist_d", label_visibility="collapsed"
            )

        # Fila 3: 0DTE | Excluir Tickers
        cf8, cf9 = st.columns([1, 2])
        filtro_0dte_h = cf8.selectbox(
            "⏰ 0DTE",
            ["Todos", "⚡ Solo 0DTE", "🚫 Sin 0DTE"],
            key="hist_0dte",
            help="0DTE = vencimiento mismo día que apertura"
        )
        all_tickers_excl_h = sorted(hist_df["Ticker"].dropna().unique().tolist())
        excluir_tickers_h = cf9.multiselect(
            "🛋️ Excluir tickers",
            options=all_tickers_excl_h,
            default=[],
            key="hist_excl",
            placeholder="Selecciona tickers a excluir..."
        )
        
        # Fila 4: Slider PnL
        chain_pnl_for_slider = hist_df.groupby("ChainID")["PnL_USD_Realizado"].sum()
        pnl_min_sl = float(chain_pnl_for_slider.min()) if not chain_pnl_for_slider.empty else -1000.0
        pnl_max_sl = float(chain_pnl_for_slider.max()) if not chain_pnl_for_slider.empty else 1000.0
        if pnl_min_sl == pnl_max_sl:
            pnl_min_sl -= 1.0
            pnl_max_sl += 1.0
        pnl_range = st.slider(
            "💵 Rango PnL ($)",
            min_value=round(pnl_min_sl, 2),
            max_value=round(pnl_max_sl, 2),
            value=(round(pnl_min_sl, 2), round(pnl_max_sl, 2)),
            key="hist_pnl"
        )

    # =========================================================
    # --- APLICAR FILTROS BÁSICOS (sobre filas individuales) ---
    # =========================================================

    # Calcular flag 0DTE
    hist_df["__is_0dte"] = (
        pd.to_datetime(hist_df["Expiry"], errors="coerce").dt.date ==
        pd.to_datetime(hist_df["FechaApertura"], errors="coerce").dt.date
    )

    if t_filt != "Todos":       hist_df = hist_df[hist_df["Ticker"] == t_filt]
    if s_filt != "Todos":       hist_df = hist_df[hist_df["Setup"] == s_filt]
    if e_filt != "Todos":       hist_df = hist_df[hist_df["Estrategia"] == e_filt]
    if estado_filt != "Todos":  hist_df = hist_df[hist_df["Estado"] == estado_filt]
    if tags_filt.strip():
        hist_df = hist_df[
            hist_df["Tags"].fillna("").str.contains(tags_filt.strip(), case=False, na=False)
        ]
    # Filtro 0DTE
    if filtro_0dte_h == "⚡ Solo 0DTE":
        hist_df = hist_df[hist_df["__is_0dte"] == True]
    elif filtro_0dte_h == "🚫 Sin 0DTE":
        hist_df = hist_df[hist_df["__is_0dte"] == False]

    # Excluir tickers
    if excluir_tickers_h:
        hist_df = hist_df[~hist_df["Ticker"].isin(excluir_tickers_h)]
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_ts = pd.Timestamp(date_range[0])
        end_ts = pd.Timestamp(date_range[1]) + pd.Timedelta(hours=23, minutes=59, seconds=59)
        if t_filt != "Todos":
            hist_df = hist_df[
                (hist_df["__dt_sort"].isna()) |
                ((hist_df["__dt_sort"] >= start_ts) & (hist_df["__dt_sort"] <= end_ts))
            ]
        else:
            hist_df = hist_df[
                (hist_df["__dt_sort"] >= start_ts) & (hist_df["__dt_sort"] <= end_ts)
            ]

    if hist_df.empty:
        st.info("No hay operaciones que coincidan con los filtros seleccionados.")
        return

    # =========================================================
    # --- AGRUPAR POR CHAIN (una operación = un ChainID) ---
    # =========================================================
    chain_summaries = []
    for chain_id, group in hist_df.groupby("ChainID"):
        group_sorted = group.sort_values("PnL_USD_Realizado", ascending=False)
        main_leg = group_sorted.iloc[0]

        # PnL total de la operación (suma de todas las patas)
        total_pnl = group["PnL_USD_Realizado"].sum()

        # Prima neta total (suma de todas las patas)
        prima_total = group["PrimaRecibida"].sum()

        # MaxProfitUSD guardado (solo en pata 0 para evitar duplicados)
        max_profit_usd = group["MaxProfitUSD"].max()

        # % de captura sobre la prima máxima
        if max_profit_usd > 0:
            profit_pct = (total_pnl / max_profit_usd) * 100
        elif prima_total > 0:
            mp_calc = prima_total * int(main_leg["Contratos"]) * 100
            profit_pct = (total_pnl / mp_calc * 100) if mp_calc > 0 else 0.0
        else:
            profit_pct = 0.0

        # Días en trade
        try:
            apertura = pd.to_datetime(main_leg["FechaApertura"]).date()
            cierre_d = pd.to_datetime(main_leg["FechaCierre"]).date() if not pd.isna(main_leg["FechaCierre"]) else date.today()
            dit = (cierre_d - apertura).days
        except:
            dit = 0

        # Strikes resumidos para el label
        strikes_str = " / ".join(
            f"{r['Side'][0]}{r['OptionType'][0]}@{r['Strike']:.0f}"
            for _, r in group.iterrows()
        )

        chain_summaries.append({
            "ChainID":    chain_id,
            "Ticker":     main_leg["Ticker"],
            "Estrategia": main_leg["Estrategia"],
            "Estado":     main_leg["Estado"],
            "FechaCierre":main_leg["FechaCierre"],
            "__dt_sort":  main_leg["__dt_sort"],
            "PnL_Total":  total_pnl,
            "ProfitPct":  profit_pct,
            "Prima_Neta": prima_total,
            "Contratos":  int(main_leg["Contratos"]),
            "DIT":        dit,
            "Setup":      main_leg.get("Setup", "") or "",
            "Tags":       main_leg.get("Tags", "") or "",
            "StrikesStr": strikes_str,
            "_group":     group,
            "_legs":      len(group),
        })

    # --- Filtros sobre los resúmenes de cadena ---
    chain_summaries = [c for c in chain_summaries if pnl_range[0] <= c["PnL_Total"] <= pnl_range[1]]
    if resultado_filt == "✅ Ganadoras":
        chain_summaries = [c for c in chain_summaries if c["PnL_Total"] >= 0]
    elif resultado_filt == "❌ Perdedoras":
        chain_summaries = [c for c in chain_summaries if c["PnL_Total"] < 0]

    # Ordenar por fecha de cierre descendente
    chain_summaries.sort(
        key=lambda x: x["__dt_sort"] if pd.notna(x["__dt_sort"]) else pd.Timestamp.min,
        reverse=True
    )

    if not chain_summaries:
        st.info("No hay operaciones que coincidan con los filtros seleccionados.")
        return

    # =========================================================
    # --- KPIs DE RESUMEN ---
    # =========================================================
    total_ops   = len(chain_summaries)
    total_pnl_all = sum(c["PnL_Total"] for c in chain_summaries)
    ganadoras   = sum(1 for c in chain_summaries if c["PnL_Total"] >= 0)
    win_rate    = (ganadoras / total_ops * 100) if total_ops > 0 else 0.0
    avg_pnl     = total_pnl_all / total_ops if total_ops > 0 else 0.0

    st.divider()
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("📋 Total Ops",       f"{total_ops}")
    k2.metric("💵 PnL Total",        f"${total_pnl_all:,.2f}")
    k3.metric("🏆 Win Rate",         f"{win_rate:.1f}%")
    k4.metric("✅ / ❌",             f"{ganadoras} / {total_ops - ganadoras}")
    k5.metric("📊 PnL Medio",        f"${avg_pnl:,.2f}")
    
    # Comisiones 0DTE en historial
    comisiones_0dte_h = hist_df[hist_df["__is_0dte"] == True]["Comisiones"].sum()
    st.info(f"⚡ **Comisiones acumuladas en 0DTE (en este filtro):** ${comisiones_0dte_h:,.2f}")
    st.divider()

    # =========================================================
    # --- LISTA DE OPERACIONES (acordeón agrupado) ---
    # =========================================================
    st.markdown(f"### 📋 Operaciones ({total_ops})")

    ESTADO_ICON = {"Cerrada": "🔒", "Rolada": "🔄", "Asignada": "📜"}

    for c_data in chain_summaries:
        pnl   = c_data["PnL_Total"]
        pct   = c_data["ProfitPct"]
        pnl_icon = "🟢" if pnl >= 0 else "🔴"
        legs_label = f"{c_data['_legs']} patas" if c_data["_legs"] > 1 else "1 pata"
        estado_icon = ESTADO_ICON.get(c_data["Estado"], "❓")

        try:
            fecha_str = pd.to_datetime(c_data["FechaCierre"]).strftime("%Y-%m-%d")
        except:
            fecha_str = "Sin fecha"
            
        try:
            exp_date_obj = pd.to_datetime(c_data["_group"].iloc[0]["Expiry"])
            exp_str_title = exp_date_obj.strftime("%d %b")
        except:
            exp_str_title = ""

        strikes_short = " / ".join(f"{float(r['Strike']):g}" for _, r in c_data["_group"].iterrows())

        label = (
            f"{pnl_icon} {c_data['Ticker']} {exp_str_title} {strikes_short} {c_data['Estrategia']} "
            f"| {estado_icon} {c_data['Estado']} "
            f"| 📅 {fecha_str} "
            f"| 💵 **${pnl:,.2f}** ({pct:.1f}%) "
            f"| {legs_label}"
        )

        with st.expander(label, expanded=False):
            # Métricas de la operación
            cm1, cm2, cm3, cm4, cm5 = st.columns(5)
            cm1.metric("PnL Realizado", f"${pnl:,.2f}")
            cm2.metric("% Captura",     f"{pct:.1f}%")
            cm3.metric("Prima Neta",    f"${c_data['Prima_Neta']:,.2f}")
            cm4.metric("Contratos",     str(c_data["Contratos"]))
            cm5.metric("DIT",           f"{c_data['DIT']} días")

            # Tags y Setup
            meta_parts = []
            if c_data.get("Setup"): meta_parts.append(f"🎯 Setup: **{c_data['Setup']}**")
            if c_data.get("Tags"):  meta_parts.append(f"🔖 Tags: `{c_data['Tags']}`")
            if meta_parts:
                st.caption(" · ".join(meta_parts))

            # Resumen de strikes
            if c_data["_legs"] > 1:
                st.caption(f"🦵 Strikes: `{c_data['StrikesStr']}`")

            # Desglose de patas
            st.markdown("**📋 Desglose de patas:**")
            group = c_data["_group"]
            
            leg_cols = st.columns([1, 1, 1.5, 1.5, 1.5, 1.5, 2, 1])
            fields = ["Side", "Tipo", "Strike", "Prima", "Cierre", "PnL", "Venc.", "Edit"]
            for i, f in enumerate(fields):
                leg_cols[i].markdown(f"**{f}**")
                
            for _, leg in group.iterrows():
                l_c1, l_c2, l_c3, l_c4, l_c5, l_c6, l_c7, l_c8 = st.columns([1, 1, 1.5, 1.5, 1.5, 1.5, 2, 1])
                side_color = "#e74c3c" if leg["Side"] == "Sell" else "#27ae60"
                l_c1.markdown(f"<span style='color:{side_color}; font-weight:bold;'>{leg['Side']}</span>", unsafe_allow_html=True)
                l_c2.write(leg["OptionType"])
                l_c3.write(f"{float(leg['Strike']):,.2f}" if leg["Strike"] else "-")
                l_c4.write(f"${float(leg['PrimaRecibida']):,.2f}")
                l_c5.write(f"${float(leg['CostoCierre']):,.2f}")
                l_c6.write(f"${float(leg['PnL_USD_Realizado']):,.2f}")
                
                try:
                    exp_str = pd.to_datetime(leg["Expiry"]).strftime("%Y-%m-%d")
                except:
                    exp_str = str(leg.get("Expiry", "-"))
                l_c7.write(exp_str)
                
                if l_c8.button("✏️", key=f"hist_edit_{leg['ID']}"):
                    st.session_state["edit_trade_id"] = leg['ID']
                    st.rerun()

    st.divider()

    # =========================================================
    # --- EXPORTAR ---
    # =========================================================
    export_rows = []
    for c_data in chain_summaries:
        try:
            fecha_str = pd.to_datetime(c_data["FechaCierre"]).strftime("%Y-%m-%d")
        except:
            fecha_str = ""
        export_rows.append({
            "Ticker":      c_data["Ticker"],
            "Estrategia":  c_data["Estrategia"],
            "Estado":      c_data["Estado"],
            "FechaCierre": fecha_str,
            "PnL_USD":     round(c_data["PnL_Total"], 2),
            "Captura_%":   round(c_data["ProfitPct"], 2),
            "Prima_Neta":  round(c_data["Prima_Neta"], 2),
            "Contratos":   c_data["Contratos"],
            "DIT":         c_data["DIT"],
            "Setup":       c_data.get("Setup", ""),
            "Tags":        c_data.get("Tags", ""),
            "Strikes":     c_data["StrikesStr"],
        })
    csv_export = pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8")
    st.download_button(
        "📥 Exportar historial filtrado (CSV)",
        data=csv_export,
        file_name=f"strikelog_historial_{date.today()}.csv",
        mime="text/csv"
    )


def render_inline_edit(trade_id):
    st.header("✏️ Editar Operación")
    
    idx_list = st.session_state.df.index[st.session_state.df["ID"] == trade_id]
    if len(idx_list) == 0:
        st.error("Operación no encontrada.")
        if st.button("⬅️ Volver a la Lista", key=f"back_err_{trade_id}"):
            st.session_state.pop("edit_trade_id", None)
            st.rerun()
        return
        
    idx = idx_list[0]
    row = st.session_state.df.iloc[idx]
    
    st.markdown(f"**Editando: {row['Ticker']} - {row['Estrategia']} ({row['ID']})**")
    
    with st.form(f"edit_form_inline"):
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
        
        cd1, cd2, cd3, cd4, cd5 = st.columns(5)
        n_fecha_ap = cd1.date_input("Fecha Apertura", value=pd.to_datetime(row["FechaApertura"]).date())
        n_expiry = cd2.date_input("Fecha Vencimiento", value=pd.to_datetime(row["Expiry"]).date())
        n_fecha_cl = cd3.date_input("Fecha Cierre", value=pd.to_datetime(row["FechaCierre"]).date() if not pd.isna(row["FechaCierre"]) else date.today())
        n_earnings_date = cd4.date_input("Fecha Earnings", value=pd.to_datetime(row["EarningsDate"]).date() if not pd.isna(row.get("EarningsDate")) else None)
        n_dividendos_date = cd5.date_input("Fecha Dividendos", value=pd.to_datetime(row["DividendosDate"]).date() if not pd.isna(row.get("DividendosDate")) else None)
        
        c9, c10, c10b, c11, c12, c13 = st.columns(6)
        n_pnl_usd = c9.number_input("PnL USD", value=float(row.get("PnL_USD_Realizado", 0) or 0))
        n_be = c10.number_input("BE (Inf)", value=float(row.get("BreakEven", 0) or 0))
        n_be_upper = c10b.number_input("BE Sup", value=float(row.get("BreakEven_Upper", 0) or 0))
        n_pop = c11.number_input("POP %", value=float(row.get("POP", 0) or 0))
        n_comisiones = c12.number_input("Comisiones ($)", value=float(row.get("Comisiones", 0) or 0))
        n_estado = c13.selectbox("Estado", ESTADOS, index=ESTADOS.index(row["Estado"]) if row["Estado"] in ESTADOS else 0)

        if str(row["Estado"]) != "Abierta":
            pct = float(row.get("ProfitPct", 0) or 0)
            st.info(f"💡 Este trade tiene un beneficio del **{pct:.1f}%** sobre la prima original.")
        
        n_notas = st.text_area("Notas", str(row.get("Notas", "") or ""))
        
        st.warning("⚠️ Revisa los cambios antes de guardar. Se creará un backup automático del CSV actual.")
        
        c_sub, c_canc = st.columns(2)
        submit_btn = c_sub.form_submit_button("💾 Guardar Cambios", type="primary", use_container_width=True)
        cancel_btn = c_canc.form_submit_button("🚫 Cancelar", use_container_width=True)

        if submit_btn:
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
            st.session_state.df.at[idx, "Comisiones"] = n_comisiones
            st.session_state.df.at[idx, "Notas"] = n_notas
            st.session_state.df.at[idx, "Estado"] = n_estado
            st.session_state.df.at[idx, "EarningsDate"] = pd.to_datetime(n_earnings_date) if n_earnings_date else pd.NA
            st.session_state.df.at[idx, "DividendosDate"] = pd.to_datetime(n_dividendos_date) if n_dividendos_date else pd.NA
            
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
            st.session_state.pop("edit_trade_id", None)
            st.rerun()

        elif cancel_btn:
            st.session_state.pop("edit_trade_id", None)
            st.rerun()

    st.divider()
    st.markdown("#### 🗑️ Zona de Peligro")
    if f"confirm_delete_{trade_id}" not in st.session_state:
        if st.button(f"🗑️ Eliminar operación {row['Ticker']} (ID: {trade_id[:8]})", type="secondary"):
            st.session_state[f"confirm_delete_{trade_id}"] = True
            st.rerun()
    else:
        st.error(f"⚠️ ¿Estás SEGURO de eliminar {row['Ticker']} (ID: {trade_id[:8]})? Esta acción no se puede deshacer.")
        c_del1, c_del2 = st.columns(2)
        if c_del1.button("✅ Sí, eliminar", type="primary", key=f"conf_del_{trade_id}"):
            st.session_state.df = st.session_state.df[st.session_state.df["ID"] != trade_id].reset_index(drop=True)
            st.session_state.df = JournalManager.save_with_backup(st.session_state.df)
            del st.session_state[f"confirm_delete_{trade_id}"]
            st.session_state.pop("edit_trade_id", None)
            st.success("Operación eliminada.")
            st.rerun()
        if c_del2.button("❌ Cancelar", key=f"canc_del_{trade_id}"):
            del st.session_state[f"confirm_delete_{trade_id}"]
            st.rerun()

def main():
    st.set_page_config(page_title="STRIKELOG Pro", layout="wide")

    # -------------------------------------------------------
    # Fix: Permite usar la coma del teclado como punto decimal
    # en todos los st.number_input de la aplicación.
    # -------------------------------------------------------
    components.html(
        """
        <script>
        (function() {
            function applyCommaFix(doc) {
                doc.addEventListener('keydown', function(e) {
                    if (e.key !== ',') return;
                    var el = doc.activeElement;
                    if (!el) return;
                    var tag = el.tagName ? el.tagName.toUpperCase() : '';
                    if (tag !== 'INPUT') return;
                    e.preventDefault();
                    e.stopPropagation();
                    // Usamos nativeInputValueSetter para que React detecte el cambio
                    var nativeSetter = Object.getOwnPropertyDescriptor(
                        window.parent.HTMLInputElement.prototype, 'value'
                    ).set;
                    var start = el.selectionStart;
                    var end   = el.selectionEnd;
                    var val   = el.value;
                    var newVal = val.slice(0, start) + '.' + val.slice(end);
                    nativeSetter.call(el, newVal);
                    el.setSelectionRange(start + 1, start + 1);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }, true);
            }
            try {
                applyCommaFix(window.parent.document);
            } catch(err) {
                applyCommaFix(document);
            }
        })();
        </script>
        """,
        height=0,
        scrolling=False
    )

    if "df" not in st.session_state:
        st.session_state.df = JournalManager.load_data()
        
    # Soporte para redirección automática (ej: botón Duplicar Express)
    nav_override = st.session_state.pop("nav_override", None)
    
    nav_options = ["Dashboard", "Nueva Operación", "Cartera Activa", "Historial"]
    default_nav_idx = nav_options.index(nav_override) if nav_override in nav_options else 0
    
    page = st.sidebar.radio("Navegación", nav_options, index=default_nav_idx)
    
    if page == "Dashboard": render_dashboard(st.session_state.df)
    elif page == "Nueva Operación": render_new_trade()
    elif page == "Cartera Activa": render_active_portfolio(st.session_state.df)
    elif page == "Historial": render_history(st.session_state.df)
        

if __name__ == "__main__":
    main()
