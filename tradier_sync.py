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


def build_occ_symbol(ticker: str, expiry: str, option_type: str, strike: float) -> str:
    """Construye un símbolo OCC estándar (ej: DRAM261127P00051000)."""
    try:
        t = str(ticker).strip().upper()
        exp_dt = pd.to_datetime(expiry)
        exp_str = exp_dt.strftime("%y%m%d")
        ot = "C" if str(option_type).upper().startswith("C") else "P"
        strike_int = int(round(float(strike) * 1000))
        return f"{t}{exp_str}{ot}{strike_int:08d}"
    except Exception:
        return ""


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


def fetch_recent_orders(token: Optional[str] = None, account_id: Optional[str] = None) -> Dict[str, Any]:
    """Obtiene las órdenes recientes (fills de cierres, aperturas y rolls multileg) de Tradier."""
    t = token or TRADIER_TOKEN
    acc = account_id or ACCOUNT_ID
    if not t or not acc:
        return {"error": "Credenciales no configuradas"}
    
    url = f"{BASE_URL}/accounts/{acc}/orders"
    try:
        resp = requests.get(url, headers=get_headers(t), timeout=10)
        if resp.status_code != 200:
            return {"error": f"Error Tradier ({resp.status_code}): {resp.text}"}
        
        orders_raw = resp.json().get("orders", {}).get("order", [])
        if isinstance(orders_raw, dict):
            orders_raw = [orders_raw]
        elif not orders_raw or orders_raw == "null":
            orders_raw = []
            
        return {"success": True, "orders": orders_raw}
    except Exception as e:
        return {"error": f"Error de conexión con Tradier: {e}"}


def sanitize_date_for_df(dt_val: Any) -> str:
    """Sanitiza fechas provenientes de Tradier evitando dtypes tz-aware ('Z') incompatibles con tz-naive de Pandas."""
    if dt_val is None or pd.isna(dt_val) or not str(dt_val).strip():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    s = str(dt_val).strip()
    try:
        ts = pd.to_datetime(s)
        if hasattr(ts, "tz") and ts.tz is not None:
            ts = ts.tz_localize(None)
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        clean = s.replace("Z", "").replace("T", " ")
        return clean[:19]


def extract_recent_fills_and_rolls(
    orders: List[Dict[str, Any]], 
    history_events: Optional[List[Dict[str, Any]]] = None,
    open_positions: Optional[List[Dict[str, Any]]] = None
) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
    """Extrae precios de cierre y detecta parejas de rolls desde órdenes ejecutadas e historial reciente."""
    from collections import defaultdict
    fills_by_symbol: Dict[str, float] = {}
    roll_pairs: List[Dict[str, Any]] = []
    
    open_symbols = set()
    if open_positions:
        open_symbols = {p.get("raw_symbol") for p in open_positions if p.get("raw_symbol")}

    single_closes: List[Dict[str, Any]] = []
    single_opens: List[Dict[str, Any]] = []

    # 1. Analizar órdenes del día / recientes
    for o in orders:
        if o.get("status") != "filled":
            continue
        
        legs = o.get("leg", [])
        if isinstance(legs, dict):
            legs = [legs]
        elif not legs and (o.get("class") == "option" or o.get("option_symbol")):
            # Orden individual (single leg)
            legs = [{
                "side": o.get("side"),
                "option_symbol": o.get("option_symbol"),
                "avg_fill_price": o.get("avg_fill_price"),
                "transaction_date": o.get("transaction_date") or o.get("create_date")
            }]
        
        closing_legs = []
        opening_legs = []
        
        for l in legs:
            side = str(l.get("side", ""))
            sym = l.get("option_symbol") or l.get("symbol")
            price = float(l.get("avg_fill_price", 0.0) or 0.0)
            
            if "close" in side and sym:
                closing_legs.append(l)
                fills_by_symbol[sym] = price
                if len(legs) == 1:
                    single_closes.append(l)
            elif "open" in side and sym:
                opening_legs.append(l)
                fills_by_symbol[sym] = price
                if len(legs) == 1:
                    single_opens.append(l)
                
        # Roll multileg: tiene tanto patas de cierre como de apertura en la misma orden
        if closing_legs and opening_legs:
            for cl in closing_legs:
                cl_parsed = parse_occ_symbol(cl.get("option_symbol"))
                for op in opening_legs:
                    op_parsed = parse_occ_symbol(op.get("option_symbol"))
                    # Coincidencia de ticker y tipo de opción (Call o Put)
                    if cl_parsed.get("ticker") == op_parsed.get("ticker") and cl_parsed.get("option_type") == op_parsed.get("option_type"):
                        roll_pairs.append({
                            "order_id": o.get("id"),
                            "close_symbol": cl.get("option_symbol"),
                            "close_price": float(cl.get("avg_fill_price", 0.0) or 0.0),
                            "close_side": cl.get("side"),
                            "open_symbol": op.get("option_symbol"),
                            "open_price": float(op.get("avg_fill_price", 0.0) or 0.0),
                            "open_side": op.get("side"),
                            "net_price": float(o.get("avg_fill_price", 0.0) or 0.0),
                            "date": cl.get("transaction_date") or o.get("transaction_date")
                        })

    # 1.1 Emparejar órdenes individuales (ej. roll manual de Covered Call o CSP en 2 órdenes separadas)
    for sc in single_closes:
        c_parsed = parse_occ_symbol(sc.get("option_symbol"))
        for so in single_opens:
            o_parsed = parse_occ_symbol(so.get("option_symbol"))
            if c_parsed.get("ticker") == o_parsed.get("ticker") and c_parsed.get("option_type") == o_parsed.get("option_type"):
                c_sym = sc.get("option_symbol")
                o_sym = so.get("option_symbol")
                if c_sym != o_sym:
                    already = any(rp.get("close_symbol") == c_sym and rp.get("open_symbol") == o_sym for rp in roll_pairs)
                    if not already:
                        sc_p = float(sc.get("avg_fill_price", 0.0) or 0.0)
                        so_p = float(so.get("avg_fill_price", 0.0) or 0.0)
                        roll_pairs.append({
                            "order_id": f"single_roll_{c_sym}_{o_sym}",
                            "close_symbol": c_sym,
                            "close_price": sc_p,
                            "close_side": sc.get("side"),
                            "open_symbol": o_sym,
                            "open_price": so_p,
                            "open_side": so.get("side"),
                            "net_price": so_p - sc_p,
                            "date": so.get("transaction_date") or sc.get("transaction_date")
                        })

    # 1.2 Detección de Rolls Multi-Salto (ej. doble roll intradía A -> B y B -> C)
    # Permite encadenar A directamente con C conociendo la pata intermedia B
    direct_rolls = list(roll_pairs)
    chains_by_close = {rp["close_symbol"]: rp for rp in direct_rolls}
    chained_rolls = []
    for rp in direct_rolls:
        target = rp.get("open_symbol")
        if target in chains_by_close:
            next_rp = chains_by_close[target]
            c_sym = rp.get("close_symbol")
            final_sym = next_rp.get("open_symbol")
            already = any(r.get("close_symbol") == c_sym and r.get("open_symbol") == final_sym for r in roll_pairs)
            if not already and c_sym != final_sym:
                chained_rolls.append({
                    "order_id": f"chain_{rp.get('order_id')}_{next_rp.get('order_id')}",
                    "close_symbol": c_sym,
                    "close_price": rp.get("close_price", 0.0),
                    "close_side": rp.get("close_side"),
                    "open_symbol": final_sym,
                    "open_price": next_rp.get("open_price", 0.0),
                    "open_side": next_rp.get("open_side"),
                    "net_price": (rp.get("net_price", 0.0) or 0.0) + (next_rp.get("net_price", 0.0) or 0.0),
                    "date": next_rp.get("date") or rp.get("date"),
                    "intermediate_symbol": target,
                    "intermediate_open_price": rp.get("open_price", 0.0),
                    "intermediate_close_price": next_rp.get("close_price", 0.0)
                })
    if chained_rolls:
        roll_pairs.extend(chained_rolls)

    # 2. Analizar historial reciente (sólo para fills y rolls antiguos no presentes en órdenes)
    if history_events:
        by_date_and_ticker = defaultdict(lambda: {"buy": [], "sell": []})
        for e in history_events:
            if e.get("type") == "trade":
                tr = e.get("trade", {})
                if tr.get("trade_type") == "option":
                    sym = tr.get("symbol", "")
                    parsed = parse_occ_symbol(sym)
                    ticker = parsed.get("ticker")
                    dt = str(e.get("date", ""))[:10]
                    qty = float(tr.get("quantity", 0.0) or 0.0)
                    price = float(tr.get("price", 0.0) or 0.0)
                    if sym and price > 0 and sym not in fills_by_symbol:
                        fills_by_symbol[sym] = price
                    
                    if qty > 0:
                        by_date_and_ticker[(dt, ticker)]["buy"].append({
                            "symbol": sym, "price": price, "qty": qty, "date": e.get("date"), "parsed": parsed
                        })
                    elif qty < 0:
                        by_date_and_ticker[(dt, ticker)]["sell"].append({
                            "symbol": sym, "price": price, "qty": abs(qty), "date": e.get("date"), "parsed": parsed
                        })
        
        for (dt, ticker), group in by_date_and_ticker.items():
            for b in group["buy"]:
                for s in group["sell"]:
                    # Reglas estrictas para historial:
                    # - La pata abierta DEBE estar actualmente abierta en Tradier
                    # - Mismo ticker y mismo tipo de opción
                    # - Distinto vencimiento (evita falsos rolls entre patas de un spread/Iron Condor del mismo día)
                    b_p = b.get("parsed", {})
                    s_p = s.get("parsed", {})
                    if b_p.get("option_type") != s_p.get("option_type"):
                        continue
                    if b_p.get("expiry") == s_p.get("expiry"):
                        continue
                    if open_symbols and s["symbol"] not in open_symbols:
                        continue

                    already = any(rp.get("close_symbol") == b["symbol"] and rp.get("open_symbol") == s["symbol"] for rp in roll_pairs)
                    if not already:
                        roll_pairs.append({
                            "order_id": f"hist_{dt}_{ticker}",
                            "close_symbol": b["symbol"],
                            "close_price": b["price"],
                            "close_side": "buy_to_close",
                            "open_symbol": s["symbol"],
                            "open_price": s["price"],
                            "open_side": "sell_to_open",
                            "net_price": s["price"] - b["price"],
                            "date": b["date"]
                        })

    return fills_by_symbol, roll_pairs


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
    
    # Creamos copia para ir emparejando con contabilidad de contratos
    tradier_pool = []
    for tp in tradier_positions:
        item = dict(tp)
        item["remaining_contratos"] = int(item.get("contratos", 1))
        tradier_pool.append(item)
    
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
            
        # Buscar match en Tradier con contratos disponibles
        match_idx = -1
        for i, tp in enumerate(tradier_pool):
            if tp.get("remaining_contratos", 0) <= 0:
                continue
            if tp["ticker"] == l_ticker and tp["option_type"] == l_opt_type:
                if l_opt_type == "Stock":
                    # Coincidencia de acciones
                    match_idx = i
                    break
                else:
                    # Coincidencia de opción: comparar strike, fecha y lado
                    if abs(tp["strike"] - l_strike) < 0.01:
                        if tp["expiry"] == l_expiry:
                            # Preferir mismo lado si está disponible
                            if tp.get("side", "").strip().capitalize() == l_side:
                                match_idx = i
                                break
                            elif match_idx < 0:
                                match_idx = i
                        
        if match_idx >= 0:
            matched_tp = tradier_pool[match_idx]
            c_matched = min(l_contratos, matched_tp["remaining_contratos"])
            matched_tp["remaining_contratos"] -= c_matched
            matched.append({
                "strikelog_id": log_pos["ID"],
                "ticker": l_ticker,
                "strategy": log_pos.get("Estrategia"),
                "log_record": log_pos.to_dict(),
                "tradier_position": matched_tp,
                "contratos_matched": c_matched
            })
            if c_matched < l_contratos:
                missing_in_tradier.append({
                    "strikelog_id": log_pos["ID"],
                    "ticker": l_ticker,
                    "strategy": log_pos.get("Estrategia"),
                    "side": l_side,
                    "option_type": l_opt_type,
                    "strike": l_strike,
                    "expiry": l_expiry,
                    "contratos": l_contratos - c_matched,
                    "log_record": log_pos.to_dict()
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
            
    # Las que quedaron en tradier_pool con remaining_contratos > 0 no existen (o faltan) en StrikeLog:
    # Filtramos para que SOLO las OPCIONES se consideren 'nuevas en broker' a incorporar en StrikeLog.
    new_in_tradier = []
    for tp in tradier_pool:
        if tp.get("remaining_contratos", 0) > 0 and tp.get("is_option", False):
            tp_rem = dict(tp)
            tp_rem["contratos"] = tp_rem["remaining_contratos"]
            new_in_tradier.append(tp_rem)

    ignored_stocks = [tp for tp in tradier_pool if tp.get("remaining_contratos", 0) > 0 and not tp.get("is_option", False)]
    
    return {
        "matched": matched,
        "missing_in_tradier": missing_in_tradier,
        "new_in_tradier": new_in_tradier,
        "ignored_stocks": ignored_stocks
    }


DEFAULT_ESTRATEGIAS = [
    "CSP (Cash Secured Put)",
    "La Rueda (The Wheel)",
    "CC (Covered Call)", "PMCC (Poor Man's Covered Call)",
    "Collar",
    "Put Credit Spread", "Call Credit Spread", 
    "Put Debit Spread", "Call Debit Spread",
    "Iron Condor", "Iron Fly",
    "Jade Lizard", "Big Lizard",
    "Butterfly", "Broken Wing Butterfly (BWB)", "Flyagonal",
    "Strangle", "Straddle",
    "Long Strangle", "Long Straddle",
    "Calendar", "Diagonal",
    "Ratio Spread", "Backspread", 
    "Covered Put",
    "Short Put (Naked)", "Short Call (Naked)",
    "Long Call", "Long Put",
    "Long Stock", "Long Stock (Asignación)",
    "Custom / Other"
]


def batch_sync_all(JournalManager, df: pd.DataFrame, recon: Dict[str, Any], roll_pairs: List[Dict[str, Any]], fills_by_symbol: Dict[str, float], strat_list: List[str]) -> Tuple[pd.DataFrame, int, int]:
    """
    Sincroniza en lote todas las discrepancias detectadas:
    1. Importa nuevas posiciones (combos multi-pata e individuales).
    2. Cierra o rola las posiciones faltantes con precio sugerido/detectado o introducido.
    Devuelve (updated_df, count_missing_resolved, count_new_imported).
    """
    import streamlit as st
    from uuid import uuid4
    from collections import defaultdict
    from datetime import datetime

    cur_df = df.copy()
    n_imported = 0
    n_resolved = 0

    # 1. Procesar NUEVAS en Tradier
    new_in_tradier = recon.get("new_in_tradier", [])
    if new_in_tradier:
        grouped_new = defaultdict(list)
        for nw in new_in_tradier:
            key = (nw["ticker"], nw["expiry"])
            grouped_new[key].append(nw)

        imported_legs_raw = set()
        new_records = []

        # A) Combos multi-pata
        for (tkr, exp), legs in grouped_new.items():
            if len(legs) > 1:
                combo_strat = "Spread"
                sell_calls = [l for l in legs if l["side"] == "Sell" and l["option_type"] == "Call"]
                buy_calls = [l for l in legs if l["side"] == "Buy" and l["option_type"] == "Call"]
                sell_puts = [l for l in legs if l["side"] == "Sell" and l["option_type"] == "Put"]
                buy_puts = [l for l in legs if l["side"] == "Buy" and l["option_type"] == "Put"]

                if len(sell_calls) == 1 and len(buy_calls) == 1 and len(legs) == 2:
                    combo_strat = "Call Credit Spread" if sell_calls[0]["strike"] < buy_calls[0]["strike"] else "Call Debit Spread"
                elif len(sell_puts) == 1 and len(buy_puts) == 1 and len(legs) == 2:
                    combo_strat = "Put Credit Spread" if sell_puts[0]["strike"] > buy_puts[0]["strike"] else "Put Debit Spread"
                elif len(sell_puts) == 1 and len(sell_calls) == 1 and len(legs) == 2:
                    combo_strat = "Strangle"
                elif len(sell_puts) == 1 and len(buy_puts) == 1 and len(sell_calls) == 1 and len(buy_calls) == 1 and len(legs) == 4:
                    combo_strat = "Iron Condor"

                new_chain_id = str(uuid4())[:8]
                net_credit = sum(l["unit_premium"] * (1 if l["side"] == "Sell" else -1) for l in legs)
                strikes = [l["strike"] for l in legs]
                width = (max(strikes) - min(strikes)) if len(strikes) >= 2 else 0.0
                cnt = legs[0]["contratos"]
                risk_bp = max(0.0, (width - net_credit) * 100 * cnt) if net_credit > 0 else (abs(net_credit) * 100 * cnt)

                for idx_l, leg in enumerate(legs):
                    leg_id = str(uuid4())[:8]
                    be_calc = 0.0
                    if "Call" in combo_strat and sell_calls:
                        be_calc = sell_calls[0]["strike"] + net_credit
                    elif "Put" in combo_strat and sell_puts:
                        be_calc = sell_puts[0]["strike"] - net_credit
                    else:
                        be_calc = leg["strike"]

                    new_records.append({
                        "ID": leg_id,
                        "ChainID": new_chain_id,
                        "ParentID": pd.NA,
                        "Ticker": leg["ticker"],
                        "FechaApertura": pd.to_datetime(leg["date_acquired"]).normalize() if leg["date_acquired"] else pd.Timestamp.now().normalize(),
                        "Expiry": pd.to_datetime(leg["expiry"]).normalize() if leg["expiry"] else pd.Timestamp.now().normalize(),
                        "Estrategia": combo_strat,
                        "Setup": "VIX alto / IV Crush" if "VIX" in tkr else "Otro",
                        "Tags": "TradierSync",
                        "Side": leg["side"],
                        "OptionType": leg["option_type"],
                        "Strike": leg["strike"],
                        "Delta": 0.0,
                        "PrimaRecibida": leg["unit_premium"],
                        "CostoCierre": 0.0,
                        "Contratos": leg["contratos"],
                        "BuyingPower": risk_bp if idx_l == 0 else 0.0,
                        "BreakEven": be_calc,
                        "BreakEven_Upper": 0.0,
                        "POP": 70.0,
                        "Estado": "Abierta",
                        "Notas": f"Combo {combo_strat} importado automáticamente desde Tradier ({leg['raw_symbol']})",
                        "UpdatedAt": datetime.now().isoformat(),
                        "FechaCierre": pd.NA,
                        "MaxProfitUSD": max(0.0, net_credit * 100 * cnt),
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
                        "WheelLeg": pd.NA
                    })
                    imported_legs_raw.add(leg.get("raw_symbol"))
                n_imported += len(legs)

        # B) Patas individuales
        for nw in new_in_tradier:
            if nw.get("raw_symbol") in imported_legs_raw:
                continue

            if nw["side"] == "Sell" and nw["option_type"] == "Put":
                strat_suggest = "CSP (Cash Secured Put)"
            elif nw["side"] == "Sell" and nw["option_type"] == "Call":
                strat_suggest = "Short Call (Naked)" if "VIX" in nw["ticker"] else "CC (Covered Call)"
            elif nw["side"] == "Buy" and nw["option_type"] == "Call":
                strat_suggest = "Long Call"
            elif nw["side"] == "Buy" and nw["option_type"] == "Put":
                strat_suggest = "Long Put"
            elif nw["option_type"] == "Stock":
                strat_suggest = "Long Stock"
            else:
                strat_suggest = "CSP (Cash Secured Put)"

            new_id = str(uuid4())[:8]
            setup_val = "VIX alto / IV Crush" if "VIX" in nw["ticker"] else ("La Rueda (The Wheel)" if ("CSP" in strat_suggest or "Rueda" in strat_suggest or "CC (" in strat_suggest) else "Otro")
            
            parent_id_val = pd.NA
            chain_id_val = new_id
            wheel_parent_val = pd.NA
            cc_chain_val = pd.NA
            cc_prima_val = 0.0

            # 1. Vincular si proviene de un Roll detectado en Tradier
            candidate_rps = [rp for rp in roll_pairs if rp.get("open_symbol") == nw.get("raw_symbol")]
            matched_rp = None
            for rp in candidate_rps:
                c_p = parse_occ_symbol(rp["close_symbol"])
                matches = cur_df[(cur_df["Ticker"] == c_p["ticker"]) & (cur_df["Strike"] == c_p["strike"]) & (cur_df["Expiry"].astype(str).str.startswith(str(c_p["expiry"])))]
                if len(matches) > 0:
                    matched_rp = rp
                    break
            if not matched_rp and candidate_rps:
                matched_rp = next((rp for rp in candidate_rps if rp.get("intermediate_symbol")), candidate_rps[0])

            if matched_rp:
                if matched_rp.get("intermediate_symbol"):
                    inter_sym = matched_rp["intermediate_symbol"]
                    inter_parsed = parse_occ_symbol(inter_sym)
                    existing_inter = cur_df[
                        (cur_df["Ticker"] == inter_parsed["ticker"]) &
                        (cur_df["Strike"] == inter_parsed["strike"]) &
                        (cur_df["Expiry"].astype(str).str.startswith(str(inter_parsed["expiry"])))
                    ]
                    if len(existing_inter) > 0:
                        parent_id_val = existing_inter.iloc[-1]["ID"]
                        chain_id_val = existing_inter.iloc[-1]["ChainID"]
                    else:
                        c_p = parse_occ_symbol(matched_rp["close_symbol"])
                        grand_rows = cur_df[(cur_df["Ticker"] == c_p["ticker"]) & (cur_df["Strike"] == c_p["strike"]) & (cur_df["Expiry"].astype(str).str.startswith(str(c_p["expiry"])))]
                        grand_id = grand_rows.iloc[-1]["ID"] if len(grand_rows) > 0 else pd.NA
                        grand_chain = grand_rows.iloc[-1]["ChainID"] if len(grand_rows) > 0 else new_id
                        
                        inter_id = str(uuid4())[:8]
                        p_in = float(matched_rp.get("intermediate_open_price", 0.0))
                        p_out = float(matched_rp.get("intermediate_close_price", 0.0))
                        inter_rec = {
                            "ID": inter_id,
                            "ChainID": grand_chain,
                            "ParentID": grand_id,
                            "Ticker": inter_parsed["ticker"],
                            "FechaApertura": sanitize_date_for_df(matched_rp.get("date")),
                            "Expiry": pd.to_datetime(inter_parsed["expiry"]).normalize(),
                            "Estrategia": strat_suggest,
                            "Setup": setup_val,
                            "Tags": "TradierSync",
                            "Side": nw["side"],
                            "OptionType": inter_parsed["option_type"],
                            "Strike": inter_parsed["strike"],
                            "Delta": 0.0,
                            "PrimaRecibida": p_in,
                            "CostoCierre": p_out,
                            "Contratos": nw["contratos"],
                            "BuyingPower": inter_parsed["strike"] * 100 * nw["contratos"] if inter_parsed["strike"] > 0 else 0.0,
                            "BreakEven": max(0.0, inter_parsed["strike"] - p_in) if inter_parsed["option_type"] == "Put" else inter_parsed["strike"] + p_in,
                            "BreakEven_Upper": 0.0,
                            "POP": 70.0,
                            "Estado": "Rolada",
                            "Notas": f"Pata intermedia de doble roll intradía ({inter_sym})",
                            "UpdatedAt": datetime.now().isoformat(),
                            "FechaCierre": sanitize_date_for_df(matched_rp.get("date")),
                            "MaxProfitUSD": p_in * 100 * nw["contratos"],
                            "ProfitPct": 0.0,
                            "PnL_Capital_Pct": 0.0,
                            "PrecioAccionCierre": 0.0,
                            "PnL_USD_Realizado": (p_in - p_out) * 100 * nw["contratos"] if nw["side"] == "Sell" else (p_out - p_in) * 100 * nw["contratos"],
                            "Comisiones": 0.0,
                            "EarningsDate": pd.NA,
                            "DividendosDate": pd.NA,
                            "Broker": "Tradier",
                            "WheelParentChainID": grand_chain,
                            "CostBaseReal": 0.0,
                            "CoveredCallChainID": pd.NA,
                            "CoveredCallPrima": 0.0,
                            "WheelLeg": "sell_put" if "CSP" in strat_suggest else pd.NA
                        }
                        cur_df = pd.concat([cur_df, pd.DataFrame([inter_rec])], ignore_index=True)
                        parent_id_val = inter_id
                        chain_id_val = grand_chain
                else:
                    c_p = parse_occ_symbol(matched_rp["close_symbol"])
                    closed_rows = cur_df[(cur_df["Ticker"] == c_p["ticker"]) & (cur_df["Strike"] == c_p["strike"]) & (cur_df["Expiry"].astype(str).str.startswith(str(c_p["expiry"])))]
                    if len(closed_rows) > 0:
                        parent_id_val = closed_rows.iloc[-1]["ID"]
                        chain_id_val = closed_rows.iloc[-1]["ChainID"]

            # 2. Covered Call vinculado a Acción en Cartera (Rueda)
            if nw["side"] == "Sell" and nw["option_type"] == "Call":
                stock_match = cur_df[(cur_df["Ticker"] == nw["ticker"]) & (cur_df["OptionType"] == "Stock") & (cur_df["Estado"] == "Abierta")]
                if len(stock_match) > 0:
                    stock_row = stock_match.iloc[0]
                    stock_idx = stock_match.index[0]
                    if not matched_rp:
                        parent_id_val = stock_row["ID"]
                        chain_id_val = new_id
                    wheel_parent_val = stock_row["ChainID"]
                    cc_chain_val = pd.NA
                    cc_prima_val = 0.0
                    strat_suggest = "CC (Covered Call)"
                    setup_val = "La Rueda (The Wheel)"
                    # Actualizar en las acciones la vinculación con el nuevo CC
                    cur_df.at[stock_idx, "CoveredCallChainID"] = chain_id_val
                    cur_df.at[stock_idx, "CoveredCallPrima"] = nw["unit_premium"]

            new_records.append({
                "ID": new_id,
                "ChainID": chain_id_val,
                "ParentID": parent_id_val,
                "Ticker": nw["ticker"],
                "FechaApertura": pd.to_datetime(nw["date_acquired"]).normalize() if nw["date_acquired"] else pd.Timestamp.now().normalize(),
                "Expiry": pd.to_datetime(nw["expiry"]).normalize() if nw["expiry"] else pd.Timestamp.now().normalize(),
                "Estrategia": strat_suggest,
                "Setup": setup_val,
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
                "WheelParentChainID": wheel_parent_val,
                "CostBaseReal": 0.0,
                "CoveredCallChainID": cc_chain_val,
                "CoveredCallPrima": cc_prima_val,
                "WheelLeg": "sell_put" if "CSP" in strat_suggest else ("covered_call" if "CC (" in strat_suggest else pd.NA)
            })
            n_imported += 1

        if new_records:
            cur_df = pd.concat([cur_df.dropna(how='all', axis=0), pd.DataFrame(new_records)], ignore_index=True)

    # 2. Procesar FALTANTES en Tradier
    missing_in_tradier = recon.get("missing_in_tradier", [])
    for mis in missing_in_tradier:
        occ_sym = build_occ_symbol(mis["ticker"], mis["expiry"], mis["option_type"], mis["strike"])
        sug_close = fills_by_symbol.get(occ_sym, 0.0)
        user_input_val = st.session_state.get(f"rec_close_price_{mis['strikelog_id']}", None)
        close_price = float(user_input_val) if user_input_val is not None else float(sug_close)

        matched_roll = next((rp for rp in roll_pairs if rp["close_symbol"] == occ_sym), None)

        rec_idx = cur_df.index[cur_df["ID"] == mis["strikelog_id"]]
        if len(rec_idx) == 0:
            continue
        real_i = rec_idx[0]

        p_rec = float(cur_df.at[real_i, "PrimaRecibida"] or 0.0)
        cnt = float(cur_df.at[real_i, "Contratos"] or 1.0)
        side_val = str(cur_df.at[real_i, "Side"])

        if matched_roll:
            cur_df.at[real_i, "Estado"] = "Rolada"
            cur_df.at[real_i, "FechaCierre"] = sanitize_date_for_df(matched_roll.get("date"))
            roll_close_p = float(matched_roll.get("close_price", close_price) or close_price)
            cur_df.at[real_i, "CostoCierre"] = roll_close_p
            pnl_realizado = (p_rec - roll_close_p) * 100 * cnt if side_val == "Sell" else (roll_close_p - p_rec) * 100 * cnt
            cur_df.at[real_i, "PnL_USD_Realizado"] = pnl_realizado
            cur_df.at[real_i, "UpdatedAt"] = datetime.now().isoformat()

            # Gestión de roll encadenado (ej. doble roll intradía)
            target_parent_id = mis["strikelog_id"]
            if matched_roll.get("intermediate_symbol"):
                inter_sym = matched_roll["intermediate_symbol"]
                inter_parsed = parse_occ_symbol(inter_sym)
                inter_exists = cur_df[
                    (cur_df["Ticker"] == inter_parsed["ticker"]) &
                    (cur_df["Strike"] == inter_parsed["strike"]) &
                    (cur_df["Expiry"] == inter_parsed["expiry"])
                ]
                if len(inter_exists) == 0:
                    inter_id = str(uuid4())[:8]
                    p_in = float(matched_roll.get("intermediate_open_price", 0.0))
                    p_out = float(matched_roll.get("intermediate_close_price", 0.0))
                    inter_pnl = (p_in - p_out) * 100 * cnt if side_val == "Sell" else (p_out - p_in) * 100 * cnt
                    inter_rec = {
                        "ID": inter_id,
                        "ChainID": cur_df.at[real_i, "ChainID"] if pd.notna(cur_df.at[real_i, "ChainID"]) else inter_id,
                        "ParentID": mis["strikelog_id"],
                        "Ticker": inter_parsed["ticker"],
                        "FechaApertura": sanitize_date_for_df(matched_roll.get("date")),
                        "Expiry": pd.to_datetime(inter_parsed["expiry"]).normalize(),
                        "Estrategia": cur_df.at[real_i, "Estrategia"],
                        "Setup": cur_df.at[real_i, "Setup"],
                        "Tags": "TradierSync",
                        "Side": side_val,
                        "OptionType": inter_parsed["option_type"],
                        "Strike": inter_parsed["strike"],
                        "Delta": 0.0,
                        "PrimaRecibida": p_in,
                        "CostoCierre": p_out,
                        "Contratos": cnt,
                        "BuyingPower": inter_parsed["strike"] * 100 * cnt if inter_parsed["strike"] > 0 else 0.0,
                        "BreakEven": max(0.0, inter_parsed["strike"] - p_in) if inter_parsed["option_type"] == "Put" else inter_parsed["strike"] + p_in,
                        "BreakEven_Upper": 0.0,
                        "POP": 70.0,
                        "Estado": "Rolada",
                        "Notas": f"Pata intermedia de doble roll intradía ({inter_sym})",
                        "UpdatedAt": datetime.now().isoformat(),
                        "FechaCierre": sanitize_date_for_df(matched_roll.get("date")),
                        "MaxProfitUSD": p_in * 100 * cnt,
                        "ProfitPct": 0.0,
                        "PnL_Capital_Pct": 0.0,
                        "PrecioAccionCierre": 0.0,
                        "PnL_USD_Realizado": inter_pnl,
                        "Comisiones": 0.0,
                        "EarningsDate": pd.NA,
                        "DividendosDate": pd.NA,
                        "Broker": "Tradier",
                        "WheelParentChainID": cur_df.at[real_i, "WheelParentChainID"],
                        "CostBaseReal": 0.0,
                        "CoveredCallChainID": pd.NA,
                        "CoveredCallPrima": 0.0,
                        "WheelLeg": cur_df.at[real_i, "WheelLeg"]
                    }
                    cur_df = pd.concat([cur_df, pd.DataFrame([inter_rec])], ignore_index=True)
                    target_parent_id = inter_id
                else:
                    target_parent_id = inter_exists.iloc[-1]["ID"]

            open_parsed = parse_occ_symbol(matched_roll["open_symbol"])
            new_leg_idx = cur_df.index[
                (cur_df["Ticker"] == open_parsed["ticker"]) &
                (cur_df["Strike"] == open_parsed["strike"]) &
                (cur_df["Expiry"] == open_parsed["expiry"]) &
                (cur_df["Estado"] == "Abierta")
            ]
            if len(new_leg_idx) > 0:
                cur_df.at[new_leg_idx[0], "ParentID"] = target_parent_id
            n_resolved += 1
        else:
            cur_df.at[real_i, "Estado"] = "Cerrada"
            cur_df.at[real_i, "FechaCierre"] = sanitize_date_for_df(datetime.now())
            cur_df.at[real_i, "CostoCierre"] = close_price
            pnl_realizado = (p_rec - close_price) * 100 * cnt if side_val == "Sell" else (close_price - p_rec) * 100 * cnt
            cur_df.at[real_i, "PnL_USD_Realizado"] = pnl_realizado
            cur_df.at[real_i, "UpdatedAt"] = datetime.now().isoformat()
            n_resolved += 1

    return cur_df, n_resolved, n_imported


def detect_intraday_closed_trades(orders_list: List[Dict[str, Any]], history_events: List[Dict[str, Any]], current_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Detecta operaciones intradía / 0DTE cerradas que NO estén en current_df.
    Analiza tanto órdenes multileg ejecutadas en la sesión como historial reciente de trades.
    """
    from collections import defaultdict
    existing_keys = set()
    for _, r in current_df.iterrows():
        tkr = str(r.get("Ticker", "")).strip().upper()
        fa = str(r.get("FechaApertura", ""))[:10]
        stk = round(float(r.get("Strike", 0.0) or 0.0), 2)
        ot = str(r.get("OptionType", ""))[:1].upper()
        existing_keys.add((tkr, fa, stk, ot))

    detected = []

    # 1. Detectar desde órdenes multileg de hoy
    open_multilegs = []
    close_multilegs = []
    for o in orders_list:
        if o.get("status") != "filled":
            continue
        cls = o.get("class")
        legs = o.get("leg", [])
        if isinstance(legs, dict):
            legs = [legs]
        if cls == "multileg" and legs:
            sides = [str(l.get("side", "")) for l in legs]
            if all("open" in s for s in sides):
                open_multilegs.append(o)
            elif all("close" in s for s in sides):
                close_multilegs.append(o)

    for op in open_multilegs:
        op_legs = op.get("leg", [])
        if isinstance(op_legs, dict):
            op_legs = [op_legs]
        op_sym_map = {l.get("option_symbol"): l for l in op_legs}
        
        for cl in close_multilegs:
            cl_legs = cl.get("leg", [])
            if isinstance(cl_legs, dict):
                cl_legs = [cl_legs]
            cl_sym_map = {l.get("option_symbol"): l for l in cl_legs}

            if set(op_sym_map.keys()) == set(cl_sym_map.keys()):
                date_str = str(op.get("transaction_date"))[:10]
                first_sym = list(op_sym_map.keys())[0]
                p_occ = parse_occ_symbol(first_sym)
                test_key = (p_occ["ticker"], date_str, round(p_occ["strike"], 2), p_occ["option_type"][:1])
                if test_key in existing_keys:
                    continue

                parsed_legs = []
                for sym, o_l in op_sym_map.items():
                    c_l = cl_sym_map[sym]
                    parsed = parse_occ_symbol(sym)
                    o_side = "Sell" if "sell" in str(o_l.get("side", "")).lower() else "Buy"
                    o_price = float(o_l.get("avg_fill_price", 0.0) or 0.0)
                    c_price = float(c_l.get("avg_fill_price", 0.0) or 0.0)
                    cnt = int(float(o_l.get("quantity", 1.0) or 1.0))
                    
                    if o_side == "Sell":
                        pnl = (o_price - c_price) * 100 * cnt
                    else:
                        pnl = (c_price - o_price) * 100 * cnt

                    comm = (1.94 * cnt) if "SPX" in parsed["ticker"] else 0.0
                    parsed_legs.append({
                        "raw_symbol": sym,
                        "ticker": parsed["ticker"],
                        "option_type": parsed["option_type"],
                        "strike": parsed["strike"],
                        "expiry": parsed["expiry"],
                        "side": o_side,
                        "contratos": cnt,
                        "open_price": o_price,
                        "close_price": c_price,
                        "pnl": pnl,
                        "comisiones": comm,
                        "open_time": op.get("transaction_date"),
                        "close_time": cl.get("transaction_date")
                    })

                sell_calls = [l for l in parsed_legs if l["side"] == "Sell" and l["option_type"] == "Call"]
                buy_calls = [l for l in parsed_legs if l["side"] == "Buy" and l["option_type"] == "Call"]
                sell_puts = [l for l in parsed_legs if l["side"] == "Sell" and l["option_type"] == "Put"]
                buy_puts = [l for l in parsed_legs if l["side"] == "Buy" and l["option_type"] == "Put"]

                combo_name = "Spread"
                if len(sell_calls) == 1 and len(buy_calls) == 1 and len(parsed_legs) == 2:
                    combo_name = "Call Credit Spread" if sell_calls[0]["strike"] < buy_calls[0]["strike"] else "Call Debit Spread"
                elif len(sell_puts) == 1 and len(buy_puts) == 1 and len(parsed_legs) == 2:
                    combo_name = "Put Credit Spread" if sell_puts[0]["strike"] > buy_puts[0]["strike"] else "Put Debit Spread"
                elif len(sell_puts) == 1 and len(sell_calls) == 1 and len(parsed_legs) == 2:
                    combo_name = "Strangle"
                elif len(sell_puts) == 1 and len(buy_puts) == 1 and len(sell_calls) == 1 and len(buy_calls) == 1 and len(parsed_legs) == 4:
                    combo_name = "Iron Condor"

                total_pnl = sum(l["pnl"] for l in parsed_legs)
                detected.append({
                    "source": "orders",
                    "strategy": combo_name,
                    "ticker": parsed_legs[0]["ticker"],
                    "date": date_str,
                    "legs": parsed_legs,
                    "total_pnl": total_pnl,
                    "open_time": op.get("transaction_date"),
                    "close_time": cl.get("transaction_date")
                })

    # 2. Detectar desde historial reciente (días anteriores como ayer)
    hist_by_sym_date = defaultdict(lambda: {"buy": [], "sell": []})
    for ev in history_events:
        if ev.get("type") != "trade":
            continue
        tr = ev.get("trade", {})
        if tr.get("trade_type") != "option":
            continue
        sym = tr.get("symbol", "")
        dt = str(ev.get("date", ""))[:10]
        qty = float(tr.get("quantity", 0.0) or 0.0)
        price = float(tr.get("price", 0.0) or 0.0)
        comm = float(tr.get("commission", 0.0) or 0.0)
        
        if qty > 0:
            hist_by_sym_date[(dt, sym)]["buy"].append({"price": price, "qty": qty, "comm": comm, "raw": ev})
        elif qty < 0:
            hist_by_sym_date[(dt, sym)]["sell"].append({"price": price, "qty": abs(qty), "comm": comm, "raw": ev})

    for (dt, sym), group in hist_by_sym_date.items():
        parsed = parse_occ_symbol(sym)
        test_key = (parsed["ticker"], dt, round(parsed["strike"], 2), parsed["option_type"][:1])
        if test_key in existing_keys:
            continue

        buys = group["buy"]
        sells = group["sell"]
        total_buy_qty = sum(b["qty"] for b in buys)
        total_sell_qty = sum(s["qty"] for s in sells)
        matched_qty = min(total_buy_qty, total_sell_qty)

        if matched_qty > 0:
            avg_buy_price = sum(b["price"] * b["qty"] for b in buys) / total_buy_qty
            avg_sell_price = sum(s["price"] * s["qty"] for s in sells) / total_sell_qty
            total_comm = sum(b.get("comm", 0.0) for b in buys) + sum(s.get("comm", 0.0) for s in sells)
            strat = "Long Call" if parsed["option_type"] == "Call" else "Long Put"
            pnl = (avg_sell_price - avg_buy_price) * 100 * matched_qty

            detected.append({
                "source": "history",
                "strategy": strat,
                "ticker": parsed["ticker"],
                "date": dt,
                "legs": [{
                    "raw_symbol": sym,
                    "ticker": parsed["ticker"],
                    "option_type": parsed["option_type"],
                    "strike": parsed["strike"],
                    "expiry": parsed["expiry"],
                    "side": "Buy",
                    "contratos": int(matched_qty),
                    "open_price": round(avg_buy_price, 2),
                    "close_price": round(avg_sell_price, 2),
                    "pnl": round(pnl, 2),
                    "comisiones": total_comm,
                    "open_time": f"{dt} 09:30:00",
                    "close_time": f"{dt} 16:00:00"
                }],
                "total_pnl": round(pnl, 2),
                "open_time": f"{dt} 09:30:00",
                "close_time": f"{dt} 16:00:00"
            })

    return detected


def import_intraday_trades(JournalManager, df: pd.DataFrame, trades_to_import: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, int]:
    """Importa las operaciones intradía cerradas seleccionadas directamente a la bitácora."""
    from uuid import uuid4
    from datetime import datetime

    cur_df = df.copy()
    new_records = []

    for tr in trades_to_import:
        chain_id = str(uuid4())[:8]
        for leg in tr["legs"]:
            leg_id = str(uuid4())[:8]
            cnt = int(leg["contratos"])
            op_p = float(leg["open_price"])
            cl_p = float(leg["close_price"])
            pnl = float(leg["pnl"])
            side = leg["side"]
            tkr = leg["ticker"]
            comm = leg.get("comisiones", 0.0)
            if not comm and "SPX" in tkr:
                comm = 1.94 * cnt

            bp = op_p * 100 * cnt if side == "Buy" else leg["strike"] * 100 * cnt

            rec = {
                "ID": leg_id,
                "ChainID": chain_id,
                "ParentID": pd.NA,
                "Ticker": tkr,
                "FechaApertura": sanitize_date_for_df(leg.get("open_time") or tr.get("open_time")),
                "Expiry": pd.to_datetime(leg["expiry"]).normalize() if leg.get("expiry") else pd.Timestamp.now().normalize(),
                "Estrategia": tr["strategy"],
                "Setup": "0DTE / Scalping",
                "Tags": "TradierSync,0DTE",
                "Side": side,
                "OptionType": leg["option_type"],
                "Strike": leg["strike"],
                "Delta": 0.0,
                "PrimaRecibida": op_p,
                "CostoCierre": cl_p,
                "Contratos": cnt,
                "BuyingPower": bp,
                "BreakEven": 0.0,
                "BreakEven_Upper": 0.0,
                "POP": 50.0,
                "Estado": "Cerrada",
                "Notas": f"Operación intradía {tr['strategy']} importada desde Tradier ({leg.get('raw_symbol', '')})",
                "UpdatedAt": datetime.now().isoformat(),
                "FechaCierre": sanitize_date_for_df(leg.get("close_time") or tr.get("close_time")),
                "MaxProfitUSD": max(0.0, pnl),
                "ProfitPct": 0.0,
                "PnL_Capital_Pct": 0.0,
                "PrecioAccionCierre": 0.0,
                "PnL_USD_Realizado": round(pnl, 2),
                "Comisiones": comm,
                "EarningsDate": pd.NA,
                "DividendosDate": pd.NA,
                "Broker": "Tradier",
                "WheelParentChainID": pd.NA,
                "CostBaseReal": 0.0,
                "CoveredCallChainID": pd.NA,
                "CoveredCallPrima": 0.0,
                "WheelLeg": pd.NA
            }
            new_records.append(rec)

    if new_records:
        cur_df = pd.concat([cur_df.dropna(how='all', axis=0), pd.DataFrame(new_records)], ignore_index=True)
        if JournalManager is not None:
            cur_df = JournalManager.save_with_backup(cur_df)

    return cur_df, len(trades_to_import)


def render_tradier_sync_modal(JournalManager, df: pd.DataFrame, *args, **kwargs):
    """
    Renderiza el diálogo modal / asistente interactivo de sincronización con Tradier.
    Permite contrastar balances, verificar coincidencia 1:1 e importar o conciliar posiciones.
    """
    import streamlit as st
    from uuid import uuid4

    estrategias = kwargs.get("estrategias") or (args[0] if args else None)
    strat_list = list(estrategias) if estrategias else DEFAULT_ESTRATEGIAS

    st.markdown("### 🔄 Sincronización en Vivo con Tradier / Sigma Trade")
    st.caption("Contrasta tus posiciones y balances en tiempo real contra la API oficial de Tradier Brokerage.")

    # 1. Obtener Balances, Posiciones y Órdenes
    with st.spinner("Conectando con Tradier..."):
        bal_res = fetch_account_balances()
        pos_res = fetch_open_positions()
        orders_res = fetch_recent_orders()
        hist_res = fetch_recent_history(limit=100)

    if not bal_res.get("success") or not pos_res.get("success"):
        err = bal_res.get("error") or pos_res.get("error")
        st.error(f"❌ No se pudo conectar con Tradier: {err}")
        st.info("Verifica que las credenciales en tu archivo `.env` sean correctas y que la cuenta esté activa.")
        if st.button("Cerrar", key="close_sync_err"):
            st.session_state["show_tradier_sync"] = False
            st.rerun()
        return

    orders_list = orders_res.get("orders", []) if orders_res.get("success") else []
    hist_events = hist_res.get("events", []) if hist_res.get("success") else []
    pos_list = pos_res.get("positions", []) if pos_res.get("success") else []
    fills_by_symbol, roll_pairs = extract_recent_fills_and_rolls(orders_list, hist_events, pos_list)

    # Detectar operaciones intradía / 0DTE cerradas que no estén en la bitácora
    intraday_trades = detect_intraday_closed_trades(orders_list, hist_events, df)
    n_intraday = len(intraday_trades)

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

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("✅ Coincidentes (100% OK)", f"{n_matched} pos.")
    m_col2.metric("⚠️ En StrikeLog pero no en Broker", f"{n_missing} pos.", help="Posiciones abiertas en tu bitácora que ya no figuran en Tradier (probablemente cerradas o roladas en el broker)")
    m_col3.metric("➕ Nuevas en Broker", f"{n_new} pos.", help="Posiciones abiertas en Tradier que aún no has registrado en StrikeLog")
    m_col4.metric("⚡ Intradía / 0DTE", f"{n_intraday} ops.", help="Operaciones intradía cerradas en el broker (ej. SPX) listas para incorporar al historial")

    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    is_0dte_active = (st.session_state.get("tradier_active_tab") == "0dte")
    if is_0dte_active:
        tab_intraday, tab_status, tab_history = st.tabs([f"⚡ Intradía / 0DTE ({n_intraday})", "📊 Estado de Posiciones", "📜 Historial Reciente de Órdenes"])
    else:
        tab_status, tab_intraday, tab_history = st.tabs(["📊 Estado de Posiciones", f"⚡ Intradía / 0DTE ({n_intraday})", "📜 Historial Reciente de Órdenes"])

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

        # Banner de Sincronización en Lote Automática
        if n_missing > 0 or n_new > 0:
            c_batch_txt, c_batch_btn = st.columns([2.8, 1.2])
            c_batch_txt.info(f"⚡ **Sincronización Inteligente:** Hay **{n_missing + n_new} operación(es)** con diferencias ({n_missing} para cerrar/rolar y {n_new} nuevas para importar). Puedes revisarlas una a una abajo, o sincronizarlas todas automáticamente si las ves correctas.")
            if c_batch_btn.button("⚡ Sincronizar Todo Automático", key="btn_batch_sync_all", type="primary", use_container_width=True, help="Aplica automáticamente todos los rolls y cierres pendientes e incorpora todas las nuevas posiciones a tu cartera"):
                updated_df, n_res, n_imp = batch_sync_all(JournalManager, df, recon, roll_pairs, fills_by_symbol, strat_list)
                st.session_state.df = JournalManager.save_with_backup(updated_df)
                st.success(f"🎉 ¡Sincronización en lote completada! Se resolvieron {n_res} operaciones y se importaron {n_imp} nuevas.")
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
                        "Contratos": m.get("contratos_matched", tp.get("contratos", 1)),
                        "Prima / Base": f"${tp['unit_premium']:.2f}"
                    })
                st.dataframe(pd.DataFrame(matched_rows), width="stretch", hide_index=True)

        # Discrepancias: Faltan en Tradier
        if n_missing > 0:
            c_mis_hdr, c_mis_all = st.columns([3, 1.2])
            c_mis_hdr.warning(f"⚠️ **{n_missing} posición(es) registradas como abiertas en StrikeLog no se encuentran en Tradier:**")
            if n_missing > 1:
                if c_mis_all.button("⚡ Resolver Todas las Faltantes", key="btn_batch_resolve_missing", help="Aplica automáticamente los rolls detectados o cierra estas posiciones"):
                    updated_df, n_res, _ = batch_sync_all(JournalManager, df, {"missing_in_tradier": recon["missing_in_tradier"], "new_in_tradier": []}, roll_pairs, fills_by_symbol, strat_list)
                    st.session_state.df = JournalManager.save_with_backup(updated_df)
                    st.success(f"Se resolvieron {n_res} posiciones faltantes.")
                    st.rerun()
            st.caption("Estas operaciones pueden haber sido cerradas, asignadas o roladas en Sigma Trade. Puedes marcarlas como cerradas o roladas aquí:")
            for idx_m, mis in enumerate(recon["missing_in_tradier"]):
                occ_sym = build_occ_symbol(mis["ticker"], mis["expiry"], mis["option_type"], mis["strike"])
                sug_close = fills_by_symbol.get(occ_sym, 0.0)
                matched_roll = next((rp for rp in roll_pairs if rp["close_symbol"] == occ_sym), None)

                if matched_roll:
                    st.info(f"🔄 **Roll Detectado en Tradier:** Cerrado @ `${matched_roll['close_price']:.2f}` ➔ Rolado a `{matched_roll['open_symbol']}` @ `${matched_roll['open_price']:.2f}` (Neto: `${abs(matched_roll['net_price']):.2f}`)")

                c_m1, c_m2, c_m3 = st.columns([3, 1.5, 1.5])
                c_m1.markdown(f"**{mis['ticker']}** | {mis['strategy']} | {mis['side']} {mis['option_type']} Strike ${mis['strike']} Exp: {mis['expiry']}")
                close_price = c_m2.number_input(
                    "Precio Cierre ($)",
                    value=float(sug_close),
                    step=0.01,
                    key=f"rec_close_price_{mis['strikelog_id']}",
                    help="Precio de ejecución detectado automáticamente en las órdenes de Tradier" if sug_close > 0 else "Introduce el precio de recompra"
                )
                
                is_short_put = (mis.get("side") == "Sell" and mis.get("option_type") == "Put")
                if matched_roll:
                    if c_m3.button("🔄 Aplicar Roll", key=f"btn_close_rec_{mis['strikelog_id']}", type="primary"):
                        rec_idx = df.index[df["ID"] == mis["strikelog_id"]]
                        if len(rec_idx) > 0:
                            real_i = rec_idx[0]
                            df.at[real_i, "Estado"] = "Rolada"
                            df.at[real_i, "FechaCierre"] = sanitize_date_for_df(matched_roll.get("date"))
                            df.at[real_i, "CostoCierre"] = close_price
                            p_rec = float(df.at[real_i, "PrimaRecibida"] or 0.0)
                            cnt = float(df.at[real_i, "Contratos"] or 1.0)
                            side_val = str(df.at[real_i, "Side"])
                            pnl_realizado = (p_rec - close_price) * 100 * cnt if side_val == "Sell" else (close_price - p_rec) * 100 * cnt
                            df.at[real_i, "PnL_USD_Realizado"] = pnl_realizado
                            df.at[real_i, "UpdatedAt"] = datetime.now().isoformat()
                            
                            target_parent_id = mis["strikelog_id"]
                            if matched_roll.get("intermediate_symbol"):
                                inter_sym = matched_roll["intermediate_symbol"]
                                inter_parsed = parse_occ_symbol(inter_sym)
                                inter_exists = df[
                                    (df["Ticker"] == inter_parsed["ticker"]) &
                                    (df["Strike"] == inter_parsed["strike"]) &
                                    (df["Expiry"] == inter_parsed["expiry"])
                                ]
                                if len(inter_exists) == 0:
                                    inter_id = str(uuid4())[:8]
                                    p_in = float(matched_roll.get("intermediate_open_price", 0.0))
                                    p_out = float(matched_roll.get("intermediate_close_price", 0.0))
                                    inter_pnl = (p_in - p_out) * 100 * cnt if side_val == "Sell" else (p_out - p_in) * 100 * cnt
                                    inter_rec = {
                                        "ID": inter_id,
                                        "ChainID": df.at[real_i, "ChainID"] if pd.notna(df.at[real_i, "ChainID"]) else inter_id,
                                        "ParentID": mis["strikelog_id"],
                                        "Ticker": inter_parsed["ticker"],
                                        "FechaApertura": sanitize_date_for_df(matched_roll.get("date")),
                                        "Expiry": pd.to_datetime(inter_parsed["expiry"]).normalize(),
                                        "Estrategia": df.at[real_i, "Estrategia"],
                                        "Setup": df.at[real_i, "Setup"],
                                        "Tags": "TradierSync",
                                        "Side": side_val,
                                        "OptionType": inter_parsed["option_type"],
                                        "Strike": inter_parsed["strike"],
                                        "Delta": 0.0,
                                        "PrimaRecibida": p_in,
                                        "CostoCierre": p_out,
                                        "Contratos": cnt,
                                        "BuyingPower": inter_parsed["strike"] * 100 * cnt if inter_parsed["strike"] > 0 else 0.0,
                                        "BreakEven": max(0.0, inter_parsed["strike"] - p_in) if inter_parsed["option_type"] == "Put" else inter_parsed["strike"] + p_in,
                                        "BreakEven_Upper": 0.0,
                                        "POP": 70.0,
                                        "Estado": "Rolada",
                                        "Notas": f"Pata intermedia de doble roll intradía ({inter_sym})",
                                        "UpdatedAt": datetime.now().isoformat(),
                                        "FechaCierre": sanitize_date_for_df(matched_roll.get("date")),
                                        "MaxProfitUSD": p_in * 100 * cnt,
                                        "ProfitPct": 0.0,
                                        "PnL_Capital_Pct": 0.0,
                                        "PrecioAccionCierre": 0.0,
                                        "PnL_USD_Realizado": inter_pnl,
                                        "Comisiones": 0.0,
                                        "EarningsDate": pd.NA,
                                        "DividendosDate": pd.NA,
                                        "Broker": "Tradier",
                                        "WheelParentChainID": df.at[real_i, "WheelParentChainID"],
                                        "CostBaseReal": 0.0,
                                        "CoveredCallChainID": pd.NA,
                                        "CoveredCallPrima": 0.0,
                                        "WheelLeg": df.at[real_i, "WheelLeg"]
                                    }
                                    df = pd.concat([df, pd.DataFrame([inter_rec])], ignore_index=True)
                                    target_parent_id = inter_id
                                else:
                                    target_parent_id = inter_exists.iloc[-1]["ID"]

                            open_parsed = parse_occ_symbol(matched_roll["open_symbol"])
                            new_leg_idx = df.index[
                                (df["Ticker"] == open_parsed["ticker"]) &
                                (df["Strike"] == open_parsed["strike"]) &
                                (df["Expiry"] == open_parsed["expiry"]) &
                                (df["Estado"] == "Abierta")
                            ]
                            if len(new_leg_idx) > 0:
                                df.at[new_leg_idx[0], "ParentID"] = target_parent_id

                            st.session_state.df = JournalManager.save_with_backup(df)
                            st.success(f"Posición {mis['ticker']} actualizada como Rolada y enlazada.")
                            st.rerun()
                elif is_short_put:
                    c_btn1, c_btn2, c_btn3 = c_m3.columns(3)
                    if c_btn1.button("Cerrar", key=f"btn_close_rec_{mis['strikelog_id']}", help="Marcar como cerrada normalmente (a precio de mercado o $0 si expiró OTM)"):
                        rec_idx = df.index[df["ID"] == mis["strikelog_id"]]
                        if len(rec_idx) > 0:
                            real_i = rec_idx[0]
                            df.at[real_i, "Estado"] = "Cerrada"
                            df.at[real_i, "FechaCierre"] = sanitize_date_for_df(datetime.now())
                            df.at[real_i, "CostoCierre"] = close_price
                            p_rec = float(df.at[real_i, "PrimaRecibida"] or 0.0)
                            cnt = float(df.at[real_i, "Contratos"] or 1.0)
                            pnl_realizado = (p_rec - close_price) * 100 * cnt
                            df.at[real_i, "PnL_USD_Realizado"] = pnl_realizado
                            df.at[real_i, "UpdatedAt"] = datetime.now().isoformat()
                            st.session_state.df = JournalManager.save_with_backup(df)
                            st.success(f"Posición {mis['ticker']} marcada como cerrada.")
                            st.rerun()
                    if c_btn2.button("🔄 Rolada", key=f"btn_roll_rec_{mis['strikelog_id']}", help="Marcar como Rolada y vincular a la nueva opción abierta del mismo ticker"):
                        rec_idx = df.index[df["ID"] == mis["strikelog_id"]]
                        if len(rec_idx) > 0:
                            real_i = rec_idx[0]
                            df.at[real_i, "Estado"] = "Rolada"
                            df.at[real_i, "FechaCierre"] = sanitize_date_for_df(datetime.now())
                            df.at[real_i, "CostoCierre"] = close_price
                            p_rec = float(df.at[real_i, "PrimaRecibida"] or 0.0)
                            cnt = float(df.at[real_i, "Contratos"] or 1.0)
                            pnl_realizado = (p_rec - close_price) * 100 * cnt
                            df.at[real_i, "PnL_USD_Realizado"] = pnl_realizado
                            df.at[real_i, "UpdatedAt"] = datetime.now().isoformat()
                            
                            new_cands = df.index[
                                (df["Ticker"] == mis["ticker"]) &
                                (df["Estado"] == "Abierta") &
                                (df["ID"] != mis["strikelog_id"])
                            ]
                            if len(new_cands) > 0:
                                df.at[new_cands[-1], "ParentID"] = mis["strikelog_id"]

                            st.session_state.df = JournalManager.save_with_backup(df)
                            st.success(f"Posición {mis['ticker']} marcada como Rolada y enlazada.")
                            st.rerun()
                    if c_btn3.button("📜 Asignada", key=f"btn_assign_rec_{mis['strikelog_id']}", help="Marcar como asignada (te quedaste las acciones). Puedes incorporar las acciones a la Rueda abajo."):
                        rec_idx = df.index[df["ID"] == mis["strikelog_id"]]
                        if len(rec_idx) > 0:
                            real_i = rec_idx[0]
                            df.at[real_i, "Estado"] = "Asignada"
                            df.at[real_i, "FechaCierre"] = sanitize_date_for_df(datetime.now())
                            df.at[real_i, "CostoCierre"] = 0.0
                            p_rec = float(df.at[real_i, "PrimaRecibida"] or 0.0)
                            cnt = float(df.at[real_i, "Contratos"] or 1.0)
                            df.at[real_i, "PnL_USD_Realizado"] = p_rec * 100 * cnt
                            df.at[real_i, "Notas"] = str(df.at[real_i, "Notas"] or "") + " [Asignada en Tradier]"
                            df.at[real_i, "UpdatedAt"] = datetime.now().isoformat()
                            st.session_state.df = JournalManager.save_with_backup(df)
                            st.success(f"Posición {mis['ticker']} marcada como Asignada. Puedes incorporar las acciones resultantes a la Rueda abajo.")
                            st.rerun()
                else:
                    c_btn1, c_btn2 = c_m3.columns(2)
                    if c_btn1.button("Cerrar", key=f"btn_close_rec_{mis['strikelog_id']}"):
                        rec_idx = df.index[df["ID"] == mis["strikelog_id"]]
                        if len(rec_idx) > 0:
                            real_i = rec_idx[0]
                            df.at[real_i, "Estado"] = "Cerrada"
                            df.at[real_i, "FechaCierre"] = sanitize_date_for_df(datetime.now())
                            df.at[real_i, "CostoCierre"] = close_price
                            p_rec = float(df.at[real_i, "PrimaRecibida"] or 0.0)
                            cnt = float(df.at[real_i, "Contratos"] or 1.0)
                            side_val = str(df.at[real_i, "Side"])
                            pnl_realizado = (p_rec - close_price) * 100 * cnt if side_val == "Sell" else (close_price - p_rec) * 100 * cnt
                            df.at[real_i, "PnL_USD_Realizado"] = pnl_realizado
                            df.at[real_i, "UpdatedAt"] = datetime.now().isoformat()
                            st.session_state.df = JournalManager.save_with_backup(df)
                            st.success(f"Posición {mis['ticker']} marcada como cerrada.")
                            st.rerun()
                    if c_btn2.button("🔄 Rolada", key=f"btn_roll_rec_{mis['strikelog_id']}"):
                        rec_idx = df.index[df["ID"] == mis["strikelog_id"]]
                        if len(rec_idx) > 0:
                            real_i = rec_idx[0]
                            df.at[real_i, "Estado"] = "Rolada"
                            df.at[real_i, "FechaCierre"] = sanitize_date_for_df(datetime.now())
                            df.at[real_i, "CostoCierre"] = close_price
                            p_rec = float(df.at[real_i, "PrimaRecibida"] or 0.0)
                            cnt = float(df.at[real_i, "Contratos"] or 1.0)
                            side_val = str(df.at[real_i, "Side"])
                            pnl_realizado = (p_rec - close_price) * 100 * cnt if side_val == "Sell" else (close_price - p_rec) * 100 * cnt
                            df.at[real_i, "PnL_USD_Realizado"] = pnl_realizado
                            df.at[real_i, "UpdatedAt"] = datetime.now().isoformat()

                            new_cands = df.index[
                                (df["Ticker"] == mis["ticker"]) &
                                (df["Estado"] == "Abierta") &
                                (df["ID"] != mis["strikelog_id"])
                            ]
                            if len(new_cands) > 0:
                                df.at[new_cands[-1], "ParentID"] = mis["strikelog_id"]

                            st.session_state.df = JournalManager.save_with_backup(df)
                            st.success(f"Posición {mis['ticker']} marcada como Rolada y enlazada.")
                            st.rerun()

        # Discrepancias: Nuevas en Tradier
        if n_new > 0:
            c_new_hdr, c_new_all = st.columns([3, 1.2])
            c_new_hdr.info(f"➕ **{n_new} posición(es) nueva(s) en Tradier listas para incorporar a StrikeLog:**")
            if n_new > 1:
                if c_new_all.button("⚡ Importar Todas las Nuevas", key="btn_batch_import_new", type="primary", help="Importa automáticamente todos los combos y opciones individuales detectadas"):
                    updated_df, _, n_imp = batch_sync_all(JournalManager, df, {"missing_in_tradier": [], "new_in_tradier": recon["new_in_tradier"]}, roll_pairs, fills_by_symbol, strat_list)
                    st.session_state.df = JournalManager.save_with_backup(updated_df)
                    st.success(f"Se importaron {n_imp} nuevas posiciones con éxito.")
                    st.rerun()
            
            # 1. Detección automática de Combos Multi-Pata (Spreads / Iron Condor / Strangles)
            from collections import defaultdict
            grouped_new = defaultdict(list)
            for nw in recon["new_in_tradier"]:
                key = (nw["ticker"], nw["expiry"])
                grouped_new[key].append(nw)

            for (tkr, exp), legs in grouped_new.items():
                if len(legs) > 1:
                    combo_strat = "Spread"
                    sell_calls = [l for l in legs if l["side"] == "Sell" and l["option_type"] == "Call"]
                    buy_calls = [l for l in legs if l["side"] == "Buy" and l["option_type"] == "Call"]
                    sell_puts = [l for l in legs if l["side"] == "Sell" and l["option_type"] == "Put"]
                    buy_puts = [l for l in legs if l["side"] == "Buy" and l["option_type"] == "Put"]

                    if len(sell_calls) == 1 and len(buy_calls) == 1 and len(legs) == 2:
                        combo_strat = "Call Credit Spread" if sell_calls[0]["strike"] < buy_calls[0]["strike"] else "Call Debit Spread"
                    elif len(sell_puts) == 1 and len(buy_puts) == 1 and len(legs) == 2:
                        combo_strat = "Put Credit Spread" if sell_puts[0]["strike"] > buy_puts[0]["strike"] else "Put Debit Spread"
                    elif len(sell_puts) == 1 and len(sell_calls) == 1 and len(legs) == 2:
                        combo_strat = "Strangle"
                    elif len(sell_puts) == 1 and len(buy_puts) == 1 and len(sell_calls) == 1 and len(buy_calls) == 1 and len(legs) == 4:
                        combo_strat = "Iron Condor"

                    combo_id_key = f"combo_{tkr}_{exp}".replace("-", "_")
                    with st.container():
                        st.markdown(f"📦 **Combo Multi-Pata detectado:** `{tkr}` Exp `{exp}` ({len(legs)} patas)")
                        c_cb1, c_cb2 = st.columns([2.5, 1.5])
                        default_combo_idx = strat_list.index(combo_strat) if combo_strat in strat_list else 0
                        sel_combo_strat = c_cb1.selectbox(f"Estrategia Combo {tkr}", strat_list, index=default_combo_idx, key=f"sel_combo_{combo_id_key}")
                        if c_cb2.button(f"➕ Añadir Combo ({len(legs)} patas)", key=f"btn_combo_{combo_id_key}", type="primary"):
                            new_chain_id = str(uuid4())[:8]
                            combo_recs = []
                            net_credit = sum(l["unit_premium"] * (1 if l["side"] == "Sell" else -1) for l in legs)
                            strikes = [l["strike"] for l in legs]
                            width = (max(strikes) - min(strikes)) if len(strikes) >= 2 else 0.0
                            cnt = legs[0]["contratos"]
                            risk_bp = max(0.0, (width - net_credit) * 100 * cnt) if net_credit > 0 else (abs(net_credit) * 100 * cnt)
                            
                            for idx_l, leg in enumerate(legs):
                                leg_id = str(uuid4())[:8]
                                be_calc = 0.0
                                if "Call" in sel_combo_strat and sell_calls:
                                    be_calc = sell_calls[0]["strike"] + net_credit
                                elif "Put" in sel_combo_strat and sell_puts:
                                    be_calc = sell_puts[0]["strike"] - net_credit
                                else:
                                    be_calc = leg["strike"]

                                combo_recs.append({
                                    "ID": leg_id,
                                    "ChainID": new_chain_id,
                                    "ParentID": pd.NA,
                                    "Ticker": leg["ticker"],
                                    "FechaApertura": pd.to_datetime(leg["date_acquired"]).normalize() if leg["date_acquired"] else pd.Timestamp.now().normalize(),
                                    "Expiry": pd.to_datetime(leg["expiry"]).normalize() if leg["expiry"] else pd.Timestamp.now().normalize(),
                                    "Estrategia": sel_combo_strat,
                                    "Setup": "VIX alto / IV Crush" if "VIX" in tkr else "Otro",
                                    "Tags": "TradierSync",
                                    "Side": leg["side"],
                                    "OptionType": leg["option_type"],
                                    "Strike": leg["strike"],
                                    "Delta": 0.0,
                                    "PrimaRecibida": leg["unit_premium"],
                                    "CostoCierre": 0.0,
                                    "Contratos": leg["contratos"],
                                    "BuyingPower": risk_bp if idx_l == 0 else 0.0,
                                    "BreakEven": be_calc,
                                    "BreakEven_Upper": 0.0,
                                    "POP": 70.0,
                                    "Estado": "Abierta",
                                    "Notas": f"Combo {sel_combo_strat} importado desde Tradier ({leg['raw_symbol']})",
                                    "UpdatedAt": datetime.now().isoformat(),
                                    "FechaCierre": pd.NA,
                                    "MaxProfitUSD": max(0.0, net_credit * 100 * cnt),
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
                                    "WheelLeg": pd.NA
                                })
                            new_comb_df = pd.concat([df.dropna(how='all', axis=0), pd.DataFrame(combo_recs)], ignore_index=True)
                            st.session_state.df = JournalManager.save_with_backup(new_comb_df)
                            st.success(f"Combo {sel_combo_strat} añadido exitosamente ({len(legs)} patas).")
                            st.rerun()
                        st.markdown("---")

            # 2. Incorporación de patas individuales
            st.caption("O si prefieres, añade cada pata individualmente:")
            for idx_n, nw in enumerate(recon["new_in_tradier"]):
                c_n1, c_n2, c_n3 = st.columns([2.5, 2.0, 1.2])
                c_n1.markdown(f"**{nw['ticker']}** | {nw['side']} {nw['option_type']} Strike ${nw['strike']} Exp: {nw['expiry']} (x{nw['contratos']} @ ${nw['unit_premium']})")
                
                # Sugerir estrategia inteligente según Side y OptionType
                if nw["side"] == "Sell" and nw["option_type"] == "Put":
                    strat_suggest = "CSP (Cash Secured Put)"
                elif nw["side"] == "Sell" and nw["option_type"] == "Call":
                    strat_suggest = "Short Call (Naked)" if "VIX" in nw["ticker"] else "CC (Covered Call)"
                elif nw["side"] == "Buy" and nw["option_type"] == "Call":
                    strat_suggest = "Long Call"
                elif nw["side"] == "Buy" and nw["option_type"] == "Put":
                    strat_suggest = "Long Put"
                elif nw["option_type"] == "Stock":
                    strat_suggest = "Long Stock"
                else:
                    strat_suggest = "CSP (Cash Secured Put)"
                
                default_idx = strat_list.index(strat_suggest) if strat_suggest in strat_list else 0
                sel_strat = c_n2.selectbox("Estrategia", strat_list, index=default_idx, key=f"rec_strat_{idx_n}")
                
                if c_n3.button("➕ Añadir a Cartera", key=f"btn_add_rec_{idx_n}", type="primary"):
                    new_id = str(uuid4())[:8]
                    setup_val = "VIX alto / IV Crush" if "VIX" in nw["ticker"] else ("La Rueda (The Wheel)" if ("CSP" in sel_strat or "Rueda" in sel_strat or "CC (" in sel_strat) else "Otro")
                    
                    parent_id_val = pd.NA
                    chain_id_val = new_id
                    wheel_parent_val = pd.NA
                    cc_chain_val = pd.NA
                    cc_prima_val = 0.0

                    # 1. Vincular si proviene de un Roll detectado en Tradier
                    candidate_rps = [rp for rp in roll_pairs if rp.get("open_symbol") == nw.get("raw_symbol")]
                    matched_rp = None
                    for rp in candidate_rps:
                        c_p = parse_occ_symbol(rp["close_symbol"])
                        matches = df[(df["Ticker"] == c_p["ticker"]) & (df["Strike"] == c_p["strike"]) & (df["Expiry"].astype(str).str.startswith(str(c_p["expiry"])))]
                        if len(matches) > 0:
                            matched_rp = rp
                            break
                    if not matched_rp and candidate_rps:
                        matched_rp = next((rp for rp in candidate_rps if rp.get("intermediate_symbol")), candidate_rps[0])

                    if matched_rp:
                        if matched_rp.get("intermediate_symbol"):
                            inter_sym = matched_rp["intermediate_symbol"]
                            inter_parsed = parse_occ_symbol(inter_sym)
                            existing_inter = df[
                                (df["Ticker"] == inter_parsed["ticker"]) &
                                (df["Strike"] == inter_parsed["strike"]) &
                                (df["Expiry"].astype(str).str.startswith(str(inter_parsed["expiry"])))
                            ]
                            if len(existing_inter) > 0:
                                parent_id_val = existing_inter.iloc[-1]["ID"]
                                chain_id_val = existing_inter.iloc[-1]["ChainID"]
                            else:
                                c_p = parse_occ_symbol(matched_rp["close_symbol"])
                                grand_rows = df[(df["Ticker"] == c_p["ticker"]) & (df["Strike"] == c_p["strike"]) & (df["Expiry"].astype(str).str.startswith(str(c_p["expiry"])))]
                                grand_id = grand_rows.iloc[-1]["ID"] if len(grand_rows) > 0 else pd.NA
                                grand_chain = grand_rows.iloc[-1]["ChainID"] if len(grand_rows) > 0 else new_id
                                
                                inter_id = str(uuid4())[:8]
                                p_in = float(matched_rp.get("intermediate_open_price", 0.0))
                                p_out = float(matched_rp.get("intermediate_close_price", 0.0))
                                inter_rec = {
                                    "ID": inter_id,
                                    "ChainID": grand_chain,
                                    "ParentID": grand_id,
                                    "Ticker": inter_parsed["ticker"],
                                    "FechaApertura": sanitize_date_for_df(matched_rp.get("date")),
                                    "Expiry": pd.to_datetime(inter_parsed["expiry"]).normalize(),
                                    "Estrategia": sel_strat,
                                    "Setup": setup_val,
                                    "Tags": "TradierSync",
                                    "Side": nw["side"],
                                    "OptionType": inter_parsed["option_type"],
                                    "Strike": inter_parsed["strike"],
                                    "Delta": 0.0,
                                    "PrimaRecibida": p_in,
                                    "CostoCierre": p_out,
                                    "Contratos": nw["contratos"],
                                    "BuyingPower": inter_parsed["strike"] * 100 * nw["contratos"] if inter_parsed["strike"] > 0 else 0.0,
                                    "BreakEven": max(0.0, inter_parsed["strike"] - p_in) if inter_parsed["option_type"] == "Put" else inter_parsed["strike"] + p_in,
                                    "BreakEven_Upper": 0.0,
                                    "POP": 70.0,
                                    "Estado": "Rolada",
                                    "Notas": f"Pata intermedia de doble roll intradía ({inter_sym})",
                                    "UpdatedAt": datetime.now().isoformat(),
                                    "FechaCierre": sanitize_date_for_df(matched_rp.get("date")),
                                    "MaxProfitUSD": p_in * 100 * nw["contratos"],
                                    "ProfitPct": 0.0,
                                    "PnL_Capital_Pct": 0.0,
                                    "PrecioAccionCierre": 0.0,
                                    "PnL_USD_Realizado": (p_in - p_out) * 100 * nw["contratos"] if nw["side"] == "Sell" else (p_out - p_in) * 100 * nw["contratos"],
                                    "Comisiones": 0.0,
                                    "EarningsDate": pd.NA,
                                    "DividendosDate": pd.NA,
                                    "Broker": "Tradier",
                                    "WheelParentChainID": grand_chain,
                                    "CostBaseReal": 0.0,
                                    "CoveredCallChainID": pd.NA,
                                    "CoveredCallPrima": 0.0,
                                    "WheelLeg": "sell_put" if "CSP" in sel_strat else pd.NA
                                }
                                df = pd.concat([df, pd.DataFrame([inter_rec])], ignore_index=True)
                                parent_id_val = inter_id
                                chain_id_val = grand_chain
                        else:
                            c_p = parse_occ_symbol(matched_rp["close_symbol"])
                            closed_rows = df[(df["Ticker"] == c_p["ticker"]) & (df["Strike"] == c_p["strike"]) & (df["Expiry"].astype(str).str.startswith(str(c_p["expiry"])))]
                            if len(closed_rows) > 0:
                                parent_id_val = closed_rows.iloc[-1]["ID"]
                                chain_id_val = closed_rows.iloc[-1]["ChainID"]

                    # 2. Covered Call vinculado a Acción en Cartera (Rueda)
                    if (sel_strat == "CC (Covered Call)" or (nw["side"] == "Sell" and nw["option_type"] == "Call")):
                        stock_match = df[(df["Ticker"] == nw["ticker"]) & (df["OptionType"] == "Stock") & (df["Estado"] == "Abierta")]
                        if len(stock_match) > 0:
                            stock_row = stock_match.iloc[0]
                            stock_idx = stock_match.index[0]
                            if not matched_rp:
                                parent_id_val = stock_row["ID"]
                                chain_id_val = new_id
                            wheel_parent_val = stock_row["ChainID"]
                            cc_chain_val = pd.NA
                            cc_prima_val = 0.0
                            sel_strat = "CC (Covered Call)"
                            setup_val = "La Rueda (The Wheel)"
                            df.at[stock_idx, "CoveredCallChainID"] = chain_id_val
                            df.at[stock_idx, "CoveredCallPrima"] = nw["unit_premium"]

                    new_rec = {
                        "ID": new_id,
                        "ChainID": chain_id_val,
                        "ParentID": parent_id_val,
                        "Ticker": nw["ticker"],
                        "FechaApertura": pd.to_datetime(nw["date_acquired"]).normalize() if nw["date_acquired"] else pd.Timestamp.now().normalize(),
                        "Expiry": pd.to_datetime(nw["expiry"]).normalize() if nw["expiry"] else pd.Timestamp.now().normalize(),
                        "Estrategia": sel_strat,
                        "Setup": setup_val,
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
                        "WheelParentChainID": wheel_parent_val,
                        "CostBaseReal": 0.0,
                        "CoveredCallChainID": cc_chain_val,
                        "CoveredCallPrima": cc_prima_val,
                        "WheelLeg": "sell_put" if "CSP" in sel_strat else ("covered_call" if "CC (" in sel_strat else pd.NA)
                    }
                    new_df = pd.concat([df.dropna(how='all', axis=0), pd.DataFrame([new_rec])], ignore_index=True)
                    st.session_state.df = JournalManager.save_with_backup(new_df)
                    st.success(f"Posición {nw['ticker']} agregada con éxito.")
                    st.rerun()

    with tab_intraday:
        st.caption("⚡ Operaciones abiertas y cerradas en la misma sesión (scalping, 0DTE, combos intradía en SPX/SPXW, etc.).")
        if n_intraday == 0:
            st.success("🎉 **¡Al día!** No hay operaciones intradía o 0DTE pendientes de importar. Todas están reflejadas en tu bitácora.")
        else:
            c_it_top1, c_it_top2 = st.columns([3, 1.5])
            c_it_top1.info(f"Se detectaron **{n_intraday} operación(es)** intradía cerradas en Tradier listas para incorporar al historial:")
            if c_it_top2.button(f"⚡ Importar Todas ({n_intraday})", key="btn_import_all_intraday", type="primary", use_container_width=True):
                updated_df, count_imp = import_intraday_trades(JournalManager, df, intraday_trades)
                st.session_state.df = updated_df
                st.success(f"🎉 ¡Éxito! Se importaron {count_imp} operaciones intradía a tu bitácora.")
                st.rerun()

            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            for idx_it, it in enumerate(intraday_trades):
                pnl_color = "🟢" if it["total_pnl"] >= 0 else "🔴"
                with st.container():
                    c_r1, c_r2, c_r3 = st.columns([2.5, 1.8, 1.2])
                    c_r1.markdown(f"**{it['ticker']}** | `{it['strategy']}` | Fecha: `{it['date']}`")
                    c_r2.markdown(f"**Resultado:** {pnl_color} **${it['total_pnl']:+,.2f}** ({len(it['legs'])} pata{'s' if len(it['legs']) > 1 else ''})")
                    if c_r3.button("➕ Importar", key=f"btn_import_single_intra_{idx_it}", type="secondary", use_container_width=True):
                        updated_df, _ = import_intraday_trades(JournalManager, df, [it])
                        st.session_state.df = updated_df
                        st.success(f"Operación {it['strategy']} {it['ticker']} importada exitosamente.")
                        st.rerun()

                    with st.expander(f"Ver detalle de patas ({it['ticker']})", expanded=False):
                        p_df = []
                        for lg in it["legs"]:
                            p_df.append({
                                "Símbolo": lg.get("raw_symbol"),
                                "Lado": lg["side"],
                                "Tipo": lg["option_type"],
                                "Strike": f"${lg['strike']:.2f}",
                                "Vencimiento": lg["expiry"],
                                "Contratos": lg["contratos"],
                                "Apertura": f"${lg['open_price']:.2f}",
                                "Cierre": f"${lg['close_price']:.2f}",
                                "PnL ($)": f"${lg['pnl']:+,.2f}"
                            })
                        st.dataframe(pd.DataFrame(p_df), hide_index=True, use_container_width=True)
                    st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

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
                st.dataframe(pd.DataFrame(h_rows), width="stretch", hide_index=True)
            else:
                st.info("No se encontraron transacciones de opciones en los eventos recientes.")
        else:
            st.info("No se pudieron cargar eventos recientes de historial.")

    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    if st.button("❌ Cerrar Panel de Sincronización", key="btn_close_sync_modal", use_container_width=True):
        st.session_state["show_tradier_sync"] = False
        st.rerun()
