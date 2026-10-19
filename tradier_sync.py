import os
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import requests
import pandas as pd

# Cargar variables de entorno locales desde .env sin dependencias externas
def _load_env_file(filepath: str = ".env"):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()

TRADIER_TOKEN = os.getenv("TRADIER_TOKEN")
ACCOUNT_ID = os.getenv("ACCOUNT_ID")
USE_SANDBOX = os.getenv("USE_SANDBOX", "False").lower() in ("true", "1", "yes")

BASE_URL = "https://sandbox.tradier.com/v1" if USE_SANDBOX else "https://api.tradier.com/v1"


def get_headers(token: Optional[str] = None) -> Dict[str, str]:
    t = token or TRADIER_TOKEN
    return {
        "Authorization": f"Bearer {t}",
        "Accept": "application/json"
    }


def parse_occ_symbol(occ: str) -> Dict[str, Any]:
    """
    Parsea un símbolo OCC estándar (ej: NKE261120C00040000 o GAP).
    Retorna diccionario con ticker, si es opción, expiración, tipo y strike.
    """
    occ = str(occ).strip().upper()
    m = re.match(r"^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$", occ)
    if not m:
        return {
            "symbol": occ,
            "ticker": occ,
            "is_option": False,
            "expiry": None,
            "option_type": "Stock",
            "strike": 0.0
        }
    
    root, yy, mm, dd, opt_type, strike_str = m.groups()
    exp_year = 2000 + int(yy)
    exp_date = f"{exp_year}-{mm}-{dd}"
    strike = int(strike_str) / 1000.0
    
    return {
        "symbol": occ,
        "ticker": root,
        "is_option": True,
        "expiry": exp_date,
        "option_type": "Call" if opt_type == "C" else "Put",
        "strike": strike
    }


def fetch_account_balances(token: Optional[str] = None, account_id: Optional[str] = None) -> Dict[str, Any]:
    """Obtiene balances en vivo desde Tradier."""
    t = token or TRADIER_TOKEN
    acc = account_id or ACCOUNT_ID
    if not t or not acc:
        return {"error": "Credenciales de Tradier no configuradas."}
    
    url = f"{BASE_URL}/accounts/{acc}/balances"
    try:
        resp = requests.get(url, headers=get_headers(t), timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("balances", {})
            return {"success": True, "balances": data}
        return {"error": f"Error Tradier ({resp.status_code}): {resp.text}"}
    except Exception as e:
        return {"error": f"Error de conexión con Tradier: {e}"}


def fetch_open_positions(token: Optional[str] = None, account_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Obtiene las posiciones abiertas actuales en Tradier.
    Devuelve lista normalizada con ticker, strike, expiry, contratos y prima/cost basis.
    """
    t = token or TRADIER_TOKEN
    acc = account_id or ACCOUNT_ID
    if not t or not acc:
        return {"error": "Credenciales de Tradier no configuradas."}
    
    url = f"{BASE_URL}/accounts/{acc}/positions"
    try:
        resp = requests.get(url, headers=get_headers(t), timeout=10)
        if resp.status_code != 200:
            return {"error": f"Error Tradier ({resp.status_code}): {resp.text}"}
        
        pos_raw = resp.json().get("positions", {}).get("position", [])
        if isinstance(pos_raw, dict):
            pos_raw = [pos_raw]
        elif not pos_raw or pos_raw == "null":
            pos_raw = []
            
        parsed_positions = []
        for p in pos_raw:
            raw_sym = p.get("symbol", "")
            occ_info = parse_occ_symbol(raw_sym)
            qty = float(p.get("quantity", 0))
            cost_basis = float(p.get("cost_basis", 0.0))
            date_acq = p.get("date_acquired", "")[:10]
            
            # Determinar Side
            if occ_info["is_option"]:
                side = "Sell" if qty < 0 else "Buy"
                contratos = abs(int(qty))
                # Prima recibida o pagada por contrato
                unit_premium = round(abs(cost_basis) / (contratos * 100), 2) if contratos > 0 else 0.0
            else:
                side = "Buy"
                contratos = abs(int(qty / 100)) if abs(qty) >= 100 else 1
                unit_premium = round(cost_basis / (contratos * 100), 2) if contratos > 0 else 0.0
                
            parsed_positions.append({
                "tradier_id": p.get("id"),
                "raw_symbol": raw_sym,
                "ticker": occ_info["ticker"],
                "is_option": occ_info["is_option"],
                "option_type": occ_info["option_type"],
                "strike": occ_info["strike"],
                "expiry": occ_info["expiry"],
                "side": side,
                "quantity": qty,
                "contratos": contratos,
                "cost_basis": cost_basis,
                "unit_premium": unit_premium,
                "date_acquired": date_acq
            })
            
        return {"success": True, "positions": parsed_positions}
    except Exception as e:
        return {"error": f"Error de conexión con Tradier: {e}"}


def fetch_recent_history(token: Optional[str] = None, account_id: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """Obtiene el historial de transacciones (fills, assignments, fees) recientes de Tradier."""
    t = token or TRADIER_TOKEN
    acc = account_id or ACCOUNT_ID
    if not t or not acc:
        return {"error": "Credenciales no configuradas"}
    
    url = f"{BASE_URL}/accounts/{acc}/history?limit={limit}"
    try:
        resp = requests.get(url, headers=get_headers(t), timeout=10)
        if resp.status_code != 200:
            return {"error": f"Error Tradier ({resp.status_code}): {resp.text}"}
        
        events_raw = resp.json().get("history", {}).get("event", [])
        if isinstance(events_raw, dict):
            events_raw = [events_raw]
        elif not events_raw or events_raw == "null":
            events_raw = []
            
        return {"success": True, "events": events_raw}
    except Exception as e:
        return {"error": f"Error de conexión con Tradier: {e}"}


def reconcile_tradier_with_strikelog(strikelog_open_df: pd.DataFrame, tradier_positions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compara las posiciones abiertas en StrikeLog con las posiciones abiertas en Tradier.
    Identifica:
    - matched: Posiciones sincronizadas perfectamente.
    - missing_in_tradier: En StrikeLog figuran como abiertas pero ya no están en Tradier (probablemente cerradas/roladas/expiradas).
    - new_in_tradier: Posiciones abiertas en Tradier que aún no están registradas en StrikeLog.
    """
    matched = []
    missing_in_tradier = []
    
    # Creamos copia para ir emparejando
    tradier_pool = list(tradier_positions)
    
    for _, log_pos in strikelog_open_df.iterrows():
        # Ignorar si es de otro broker explícito que no sea Tradier
        broker_str = str(log_pos.get("Broker", "")).strip().lower()
        if broker_str and broker_str not in ["tradier", ""]:
            continue
            
        l_ticker = str(log_pos["Ticker"]).strip().upper()
        # Normalizar casos especiales (ej: IIREN -> IREN)
        if l_ticker == "IIREN":
            l_ticker = "IREN"
            
        l_opt_type = str(log_pos["OptionType"]).strip().capitalize()
        l_side = str(log_pos["Side"]).strip().capitalize()
        l_strike = float(log_pos.get("Strike", 0.0))
        l_contratos = int(log_pos.get("Contratos", 1))
        
        l_expiry_val = log_pos.get("Expiry")
        l_expiry = ""
        if pd.notna(l_expiry_val):
            l_expiry = pd.to_datetime(l_expiry_val).strftime("%Y-%m-%d")
            
        # Buscar match en Tradier
        match_idx = -1
        for i, tp in enumerate(tradier_pool):
            if tp["ticker"] == l_ticker and tp["option_type"] == l_opt_type:
                if l_opt_type == "Stock":
                    # Coincidencia de acciones
                    match_idx = i
                    break
                else:
                    # Coincidencia de opción: comparar strike y fecha
                    if abs(tp["strike"] - l_strike) < 0.01:
                        # Si ambas tienen fecha, comparar
                        if tp["expiry"] == l_expiry:
                            match_idx = i
                            break
                        
        if match_idx >= 0:
            matched_tp = tradier_pool.pop(match_idx)
            matched.append({
                "strikelog_id": log_pos["ID"],
                "ticker": l_ticker,
                "strategy": log_pos.get("Estrategia"),
                "log_record": log_pos.to_dict(),
                "tradier_position": matched_tp
            })
        else:
            missing_in_tradier.append({
                "strikelog_id": log_pos["ID"],
                "ticker": l_ticker,
                "strategy": log_pos.get("Estrategia"),
                "side": l_side,
                "option_type": l_opt_type,
                "strike": l_strike,
                "expiry": l_expiry,
                "contratos": l_contratos,
                "log_record": log_pos.to_dict()
            })
            
    # Las que quedaron en tradier_pool no existen en StrikeLog:
    # Filtramos para que SOLO las OPCIONES se consideren 'nuevas en broker' a incorporar en StrikeLog.
    # Cualquier acción de scalping (Medved Trader, etc.) se omite de 'new_in_tradier' para mantener StrikeLog 100% puro de opciones.
    new_in_tradier = [tp for tp in tradier_pool if tp.get("is_option", False)]
    ignored_stocks = [tp for tp in tradier_pool if not tp.get("is_option", False)]
    
    return {
        "matched": matched,
        "missing_in_tradier": missing_in_tradier,
        "new_in_tradier": new_in_tradier,
        "ignored_stocks": ignored_stocks
    }


def render_tradier_sync_modal(JournalManager, df: pd.DataFrame):
    """
    Renderiza el diálogo modal / asistente interactivo de sincronización con Tradier.
    Permite contrastar balances, verificar coincidencia 1:1 e importar o conciliar posiciones.
    """
    import streamlit as st
    from uuid import uuid4

    st.markdown("### 🔄 Sincronización en Vivo con Tradier / Sigma Trade")
    st.caption("Contrasta tus posiciones y balances en tiempo real contra la API oficial de Tradier Brokerage.")

    # 1. Obtener Balances
    with st.spinner("Conectando con Tradier..."):
        bal_res = fetch_account_balances()
        pos_res = fetch_open_positions()

    if not bal_res.get("success") or not pos_res.get("success"):
        err = bal_res.get("error") or pos_res.get("error")
        st.error(f"❌ No se pudo conectar con Tradier: {err}")
        st.info("Verifica que las credenciales en tu archivo `.env` sean correctas y que la cuenta esté activa.")
        if st.button("Cerrar", key="close_sync_err"):
            st.session_state["show_tradier_sync"] = False
            st.rerun()
        return

    balances = bal_res.get("balances", {})
    t_equity = float(balances.get("total_equity", 0.0) or 0.0)
    margin_info = balances.get("margin", {}) or {}
    t_option_bp = float(margin_info.get("option_buying_power") or balances.get("option_buying_power", 0.0) or 0.0)
    t_stock_bp = float(margin_info.get("stock_buying_power") or balances.get("stock_buying_power", 0.0) or 0.0)

    # Métricas de la cuenta en vivo
    b_col1, b_col2, b_col3, b_col4 = st.columns(4)
    b_col1.metric("Cuenta Tradier", ACCOUNT_ID or balances.get("account_number", "6YB72411"))
    b_col2.metric("Total Equity", f"${t_equity:,.2f}")
    b_col3.metric("Option BP Real", f"${t_option_bp:,.2f}")
    b_col4.metric("Stock BP", f"${t_stock_bp:,.2f}")

    st.divider()

    # 2. Reconciliación de Posiciones
    tradier_positions = pos_res.get("positions", [])
    open_df = df[df["Estado"] == "Abierta"].copy()
    recon = reconcile_tradier_with_strikelog(open_df, tradier_positions)

    n_matched = len(recon["matched"])
    n_missing = len(recon["missing_in_tradier"])
    n_new = len(recon["new_in_tradier"])

    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("✅ Coincidentes (100% OK)", f"{n_matched} pos.")
    m_col2.metric("⚠️ En StrikeLog pero no en Broker", f"{n_missing} pos.", help="Posiciones abiertas en tu bitácora que ya no figuran en Tradier (probablemente cerradas o roladas en el broker)")
    m_col3.metric("➕ Nuevas en Broker", f"{n_new} pos.", help="Posiciones abiertas en Tradier que aún no has registrado en StrikeLog")

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    tab_status, tab_history = st.tabs(["📊 Estado de Posiciones", "📜 Historial Reciente de Órdenes"])

    with tab_status:
        n_ignored = len(recon.get("ignored_stocks", []))
        if n_ignored > 0:
            st.info(f"🛡️ **Filtro de Opciones Activo:** Se detectaron {n_ignored} posición(es) de acciones en Tradier (ej: scalping en Medved Trader) que han sido omitidas automáticamente para mantener StrikeLog enfocado exclusivamente en opciones.")
            with st.expander(f"👁️ Ver {n_ignored} posición(es) de acciones en broker (opcional: añadir para Covered Calls)", expanded=False):
                st.caption("Estas acciones están omitidas para no mezclar scalping con opciones. Si compraste 100 acciones expresamente para vender Covered Calls en la Rueda, puedes incorporarlas aquí:")
                for idx_ig, ig in enumerate(recon["ignored_stocks"]):
                    c_ig1, c_ig2 = st.columns([3, 1.5])
                    c_ig1.markdown(f"**{ig['ticker']}** | {ig['quantity']:.0f} acciones @ ${ig['unit_premium']:.2f} (Total: ${abs(ig['cost_basis']):,.2f})")
                    if c_ig2.button(f"➕ Añadir a Rueda (CC)", key=f"btn_add_stock_wheel_{idx_ig}"):
                        new_id = str(uuid4())[:8]
                        new_rec = {
                            "ID": new_id,
                            "ChainID": new_id,
                            "ParentID": pd.NA,
                            "Ticker": ig["ticker"],
                            "FechaApertura": pd.to_datetime(ig["date_acquired"]).normalize() if ig["date_acquired"] else pd.Timestamp.now().normalize(),
                            "Expiry": pd.to_datetime("2099-12-31").normalize(),
                            "Estrategia": "Long Stock (Asignación)",
                            "Setup": "La Rueda (The Wheel)",
                            "Tags": "la-rueda,covered-call",
                            "Side": "Buy",
                            "OptionType": "Stock",
                            "Strike": ig["unit_premium"],
                            "Delta": 1.0,
                            "PrimaRecibida": 0.0,
                            "CostoCierre": 0.0,
                            "Contratos": ig["contratos"],
                            "BuyingPower": ig["unit_premium"] * 100 * ig["contratos"],
                            "BreakEven": ig["unit_premium"],
                            "BreakEven_Upper": 0.0,
                            "POP": 0.0,
                            "Estado": "Abierta",
                            "Notas": f"{int(ig['quantity'])} acciones incorporadas desde Tradier para Covered Calls ({ig['raw_symbol']})",
                            "UpdatedAt": datetime.now().isoformat(),
                            "FechaCierre": pd.NA,
                            "MaxProfitUSD": 0.0,
                            "ProfitPct": 0.0,
                            "PnL_Capital_Pct": 0.0,
                            "PrecioAccionCierre": 0.0,
                            "PnL_USD_Realizado": 0.0,
                            "Comisiones": 0.0,
                            "EarningsDate": pd.NA,
                            "DividendosDate": pd.NA,
                            "Broker": "Tradier",
                            "WheelParentChainID": pd.NA,
                            "CostBaseReal": ig["unit_premium"],
                            "CoveredCallChainID": pd.NA,
                            "CoveredCallPrima": 0.0,
                            "WheelLeg": "long_stock"
                        }
                        new_df = pd.concat([df.dropna(how='all', axis=0), pd.DataFrame([new_rec])], ignore_index=True)
                        st.session_state.df = JournalManager.save_with_backup(new_df)
                        st.success(f"Acciones de {ig['ticker']} agregadas a la cartera para Covered Calls.")
                        st.rerun()

        if n_missing == 0 and n_new == 0:
            st.success("🎉 **¡Sincronización Perfecta!** Todas las posiciones abiertas en StrikeLog coinciden exactamente con tu cartera de opciones en Tradier / Sigma Trade.")
        
        # Tabla de coincidentes
        if n_matched > 0:
            with st.expander(f"✅ Ver {n_matched} posiciones perfectamente alineadas", expanded=False):
                matched_rows = []
                for m in recon["matched"]:
                    tp = m["tradier_position"]
                    matched_rows.append({
                        "Ticker": m["ticker"],
                        "Estrategia": m["strategy"],
                        "Lado": tp["side"],
                        "Tipo": tp["option_type"],
                        "Strike": f"${tp['strike']:.2f}" if tp["strike"] > 0 else "-",
                        "Vencimiento": tp["expiry"] or "-",
                        "Contratos": tp["contratos"],
                        "Prima / Base": f"${tp['unit_premium']:.2f}"
                    })
                st.dataframe(pd.DataFrame(matched_rows), use_container_width=True, hide_index=True)

        # Discrepancias: Faltan en Tradier
        if n_missing > 0:
            st.warning(f"⚠️ **{n_missing} posición(es) registradas como abiertas en StrikeLog no se encuentran en Tradier:**")
            st.caption("Estas operaciones pueden haber sido cerradas, asignadas o roladas en Sigma Trade. Puedes marcarlas como cerradas aquí:")
            for idx_m, mis in enumerate(recon["missing_in_tradier"]):
                c_m1, c_m2, c_m3 = st.columns([3, 1.5, 1.5])
                c_m1.markdown(f"**{mis['ticker']}** | {mis['strategy']} | {mis['side']} {mis['option_type']} Strike ${mis['strike']} Exp: {mis['expiry']}")
                close_price = c_m2.number_input("Precio Cierre ($)", value=0.0, step=0.01, key=f"rec_close_price_{mis['strikelog_id']}")
                if c_m3.button("Marcar Cerrada", key=f"btn_close_rec_{mis['strikelog_id']}", type="secondary"):
                    # Aplicar cierre con backup
                    rec_idx = df.index[df["ID"] == mis["strikelog_id"]]
                    if len(rec_idx) > 0:
                        real_i = rec_idx[0]
                        df.at[real_i, "Estado"] = "Cerrada"
                        df.at[real_i, "FechaCierre"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        df.at[real_i, "CostoCierre"] = close_price
                        df.at[real_i, "UpdatedAt"] = datetime.now().isoformat()
                        st.session_state.df = JournalManager.save_with_backup(df)
                        st.success(f"Posición {mis['ticker']} marcada como cerrada.")
                        st.rerun()

        # Discrepancias: Nuevas en Tradier
        if n_new > 0:
            st.info(f"➕ **{n_new} posición(es) nueva(s) en Tradier listas para incorporar a StrikeLog:**")
            for idx_n, nw in enumerate(recon["new_in_tradier"]):
                c_n1, c_n2, c_n3 = st.columns([3, 1.5, 1.5])
                c_n1.markdown(f"**{nw['ticker']}** | {nw['side']} {nw['option_type']} Strike ${nw['strike']} Exp: {nw['expiry']} (x{nw['contratos']} @ ${nw['unit_premium']})")
                
                # Sugerir estrategia
                strat_suggest = "CSP (Cash Secured Put)" if nw["side"] == "Sell" and nw["option_type"] == "Put" else ("CC (Covered Call)" if nw["side"] == "Sell" and nw["option_type"] == "Call" else "Long Stock")
                sel_strat = c_n2.selectbox("Estrategia", ["CSP (Cash Secured Put)", "CC (Covered Call)", "Long Stock", "Otro"], index=0, key=f"rec_strat_{idx_n}")
                
                if c_n3.button("➕ Añadir a Cartera", key=f"btn_add_rec_{idx_n}", type="primary"):
                    new_id = str(uuid4())[:8]
                    new_rec = {
                        "ID": new_id,
                        "ChainID": new_id,
                        "ParentID": pd.NA,
                        "Ticker": nw["ticker"],
                        "FechaApertura": pd.to_datetime(nw["date_acquired"]).normalize() if nw["date_acquired"] else pd.Timestamp.now().normalize(),
                        "Expiry": pd.to_datetime(nw["expiry"]).normalize() if nw["expiry"] else pd.Timestamp.now().normalize(),
                        "Estrategia": sel_strat,
                        "Setup": "La Rueda (The Wheel)",
                        "Tags": "TradierSync",
                        "Side": nw["side"],
                        "OptionType": nw["option_type"],
                        "Strike": nw["strike"],
                        "Delta": 0.0,
                        "PrimaRecibida": nw["unit_premium"],
                        "CostoCierre": 0.0,
                        "Contratos": nw["contratos"],
                        "BuyingPower": nw["strike"] * 100 * nw["contratos"] if nw["strike"] > 0 else 0.0,
                        "BreakEven": max(0.0, nw["strike"] - nw["unit_premium"]) if nw["option_type"] == "Put" else nw["strike"] + nw["unit_premium"],
                        "BreakEven_Upper": 0.0,
                        "POP": 70.0,
                        "Estado": "Abierta",
                        "Notas": f"Importado automáticamente desde Tradier ({nw['raw_symbol']})",
                        "UpdatedAt": datetime.now().isoformat(),
                        "FechaCierre": pd.NA,
                        "MaxProfitUSD": nw["unit_premium"] * 100 * nw["contratos"],
                        "ProfitPct": 0.0,
                        "PnL_Capital_Pct": 0.0,
                        "PrecioAccionCierre": 0.0,
                        "PnL_USD_Realizado": 0.0,
                        "Comisiones": 0.0,
                        "EarningsDate": pd.NA,
                        "DividendosDate": pd.NA,
                        "Broker": "Tradier",
                        "WheelParentChainID": pd.NA,
                        "CostBaseReal": 0.0,
                        "CoveredCallChainID": pd.NA,
                        "CoveredCallPrima": 0.0,
                        "WheelLeg": "sell_put" if nw["option_type"] == "Put" else ("covered_call" if nw["option_type"] == "Call" else "long_stock")
                    }
                    new_df = pd.concat([df.dropna(how='all', axis=0), pd.DataFrame([new_rec])], ignore_index=True)
                    st.session_state.df = JournalManager.save_with_backup(new_df)
                    st.success(f"Posición {nw['ticker']} agregada con éxito.")
                    st.rerun()

    with tab_history:
        st.caption("Últimas órdenes ejecutadas en Tradier / Sigma Trade.")
        filter_options_only = st.checkbox(
            "🎯 Filtrar solo Opciones (ocultar compras/ventas de acciones de scalping)",
            value=True,
            key="tradier_filter_options_only",
            help="Al estar activo, oculta todas las transacciones de acciones para que tus operaciones de scalping en Medved Trader no saturen el historial de opciones."
        )
        hist_res = fetch_recent_history(limit=100)
        if hist_res.get("success"):
            events = hist_res.get("events", [])
            h_rows = []
            for ev in events:
                trade = ev.get("trade") or {}
                trade_type = str(trade.get("trade_type", "")).lower()
                sym = str(trade.get("symbol", "")).strip().upper()
                is_opt = (trade_type == "option") or bool(re.match(r"^[A-Z]+\d{6}[CP]\d{8}$", sym))
                
                if filter_options_only and not is_opt:
                    continue
                
                tipo_display = "Opción" if is_opt else (trade_type.capitalize() if trade_type else "Acción")
                h_rows.append({
                    "Fecha": ev.get("date", "")[:10],
                    "Instrumento": tipo_display,
                    "Tipo": ev.get("type", "-"),
                    "Descripción": trade.get("description") or ev.get("description", "-"),
                    "Cantidad": trade.get("quantity", "-"),
                    "Precio": f"${trade.get('price', 0.0):.2f}" if trade.get("price") is not None else "-",
                    "Monto ($)": f"${float(ev.get('amount', 0.0)):,.2f}"
                })
            if h_rows:
                st.dataframe(pd.DataFrame(h_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No se encontraron transacciones de opciones en los eventos recientes.")
        else:
            st.info("No se pudieron cargar eventos recientes de historial.")

    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    if st.button("❌ Cerrar Panel de Sincronización", key="btn_close_sync_modal", use_container_width=True):
        st.session_state["show_tradier_sync"] = False
        st.rerun()
