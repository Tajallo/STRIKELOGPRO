# 🧮 Guía de Cálculos y Fórmulas - STRIKELOG Pro

Este documento detalla todas las fórmulas matemáticas y lógicas financieras que utiliza la aplicación para calcular métricas de rendimiento, gestión de riesgo y seguimiento de estrategias.

---

## 1. Métricas de Ganancias y Pérdidas (PnL)

Estas fórmulas se aplican cuando se **cierra** una operación, ya sea parcialmente, totalmente, o al rolar.

### ⚠️ Convención de Precios: SIEMPRE POR ACCIÓN

Todos los precios en la app (Prima Neta, Costo de Cierre) se introducen **por acción**, es decir, el valor que muestra tu broker por cada opción:
- **Correcto:** `1.50` (si el broker muestra $1.50)
- **Incorrecto:** `150` (eso sería el total del contrato, NO lo pongas)

La app multiplica internamente por `Contratos × 100` para obtener el total en dólares.

**Para estrategias multi-pata** (Iron Condor, Spreads, etc.), introduce el valor **NETO** de todas las patas combinadas:
- *Ejemplo IC:* Vendes Put Spread por $1.80 + Call Spread por $2.20 → Prima Neta = **$4.00** (no 1.80 y 2.20 por separado)

### Detección de Dirección (Crédito vs Débito)

La dirección se detecta automáticamente según el tipo de estrategia:

| Dirección | Estrategias |
|---|---|
| **Crédito** (ganas si baja) | CSP, CC, Collar, Put Credit Spread, Call Credit Spread, Iron Condor, Iron Fly, Strangle, Straddle, Ratio Spread |
| **Débito** (ganas si sube) | Long Call, Long Put, Put Debit Spread, Call Debit Spread, Butterfly, BWB |
| **Variable** | Calendar, Diagonal, Custom (usa el Side de la primera pata) |

### PnL Realizado en USD (`PnL USD`)
Calcula cuánto dinero real se ganó o perdió en la operación.
*   **Operaciones de Crédito (Venta / Short):**
    $$ PnL = (\text{Prima Entrada} - \text{Precio Cierre}) \times \text{Contratos} \times 100 $$
    *   *Ejemplo CSP:* Vendiste un Put a $1.50 y lo recompras a $0.50 → PnL = (1.50 - 0.50) × 1 × 100 = **$100**
    *   *Ejemplo IC:* Prima neta $3.50, cierre neto $1.20, 2 contratos → PnL = (3.50 - 1.20) × 2 × 100 = **$460**

*   **Operaciones de Débito (Compra / Long):**
    $$ PnL = (\text{Precio Cierre} - \text{Prima Entrada}) \times \text{Contratos} \times 100 $$
    *   *Ejemplo Long Call:* Compraste a $5.00, vendes a $8.00 → PnL = (8.00 - 5.00) × 1 × 100 = **$300**

### Porcentaje de Captura (`Profit %` / `ProfitPct`)
Mide qué porcentaje de la prima máxima se capturó.
$$ \text{Profit \%} = \left( \frac{\text{PnL Total USD}}{\text{Prima Entrada} \times \text{Contratos} \times 100} \right) \times 100 $$
*   100% = Captura máxima (la opción expiró sin valor)
*   50% = Se cerró a la mitad de la prima
*   Valores negativos = Pérdida

**Nota:** `ProfitPct` se calcula automáticamente al cerrar o rolar. Antes de esta corrección, quedaba en 0.0 (bug ya resuelto).

### Retorno sobre Capital (`PnL / BP` / `RoC`)
Mide la eficiencia del uso del capital (Buying Power).
$$ \text{RoC} = \left( \frac{\text{PnL Total USD}}{\text{Buying Power Reservado}} \right) \times 100 $$

---

## 2. Break Even (Punto de Equilibrio)

El precio de la acción al vencimiento donde la operación ni gana ni pierde dinero.

### Estrategias con Break Even SIMPLE (1 valor)

| Estrategia | Fórmula |
|---|---|
| CSP (Cash Secured Put) | `BE = Strike Short Put - Prima Neta` |
| CC (Covered Call) | `BE = Strike Short Call + Prima Neta` |
| Put Credit Spread | `BE = Strike Short Put - Crédito Neto` |
| Call Credit Spread | `BE = Strike Short Call + Crédito Neto` |
| Put Debit Spread | `BE = Strike Long Put - Débito Pagado` |
| Call Debit Spread | `BE = Strike Long Call + Débito Pagado` |
| Long Put | `BE = Strike - Prima Pagada` |
| Long Call | `BE = Strike + Prima Pagada` |
| Calendar / Diagonal | `BE ≈ Strike Vendido ± Prima Neta (según tipo)` |

### Estrategias con Break Even DUAL (2 valores: inferior y superior)

La zona de beneficio máximo se encuentra entre ambos BEs.

| Estrategia | BE Inferior | BE Superior |
|---|---|---|
| **Iron Condor** | `Short Put Strike - Prima Neta` | `Short Call Strike + Prima Neta` |
| **Iron Fly** | `Short Strike (ATM) - Prima Neta` | `Short Strike (ATM) + Prima Neta` |
| **Butterfly** | `Strike Bajo + Débito Pagado` | `Strike Alto - Débito Pagado` |
| **BWB** | `Strike Bajo + Débito Pagado` | `Strike Alto - Débito Pagado` |
| **Strangle** | `Put Strike - Prima Neta` | `Call Strike + Prima Neta` |
| **Straddle** | `Strike - Prima Neta` | `Strike + Prima Neta` |
| **Collar** | `Put Strike + Prima Neta` | `Call Strike - Prima Neta` |

**Ejemplo Iron Condor:**
*   Patas: Buy Put 380, **Sell Put 390**, **Sell Call 420**, Buy Call 430
*   Prima Neta Recibida: $3.50
*   **BE Inferior** = 390 - 3.50 = **$386.50**
*   **BE Superior** = 420 + 3.50 = **$423.50**
*   Zona de Max Profit: $386.50 — $423.50

### Cálculo Dinámico Acumulativo (Campañas con Rolls)
Para estrategias que han sido ajustadas (**Roladas**), la app calcula el BE de toda la campaña ("Break Even de Campaña"), no solo de la operación vigente.

1.  **Crédito Neto de la Cadena:**
    $$ \text{CreditoNeto} = \sum(\text{Primas Históricas}) - \sum(\text{Costos de Cierre Históricos}) $$
    *   *Nota:* Si el resultado es negativo, se considera un Débito Neto.

2.  **Break Even de Campaña (Ajustado):**
    Se recalcula usando la misma fórmula de la estrategia, pero sustituyendo la Prima Neta por el Crédito Neto Acumulado de toda la cadena de rolls.

---

## 3. Probabilidad de Éxito (POP)

Estimación teórica basada en las griegas (Delta) al momento de la apertura.

*   **Venta (Short):**
    $$ POP = (1 - |\text{Delta}|) \times 100 $$
    *   *Ejemplo:* Delta -0.30 (Put OTM). POP = (1 - 0.30) = 70%.
*   **Compra (Long):**
    $$ POP = |\text{Delta}| \times 100 $$
    *   *Ejemplo:* Delta 0.30. POP = 30%.

---

## 4. Métricas del Dashboard

Indicadores clave de rendimiento (KPIs) en la pantalla principal.

*   **Win Rate (Tasa de Acierto):**
    $$ \text{Win Rate} = \frac{\text{Nº Trades Ganadores}}{\text{Total Trades Cerrados}} \times 100 $$

*   **Profit Factor:**
    $$ \text{Profit Factor} = \frac{\text{Suma de Ganancias Brutas}}{\text{Suma de Pérdidas Brutas (en valor absoluto)}} $$
    *   *Interpretación:* Un valor mayor a 1.0 indica rentabilidad. 2.0 significa que ganas $2 por cada $1 que pierdes.

*   **Captura Media (Eficiencia):**
    Promedio simple del `Profit %` de todas las operaciones ganadoras. Indica qué porcentaje de la prima máxima posible sueles quedarte antes de cerrar.

---

## 5. Gestión de Rolls (Ajustes)

### PnL Estimado al Rolar
Cuando ajustas una posición, la app estima tu resultado automáticamente:

*   **Si la posición original era Venta (Crédito):**
    $$ \text{PnL Estimado} = (\text{Prima Entrada Original} - \text{Costo Cierre Actual}) \times \text{Contratos} \times 100 $$

*   **Si la posición original era Compra (Débito):**
    $$ \text{PnL Estimado} = (\text{Costo Cierre Actual} - \text{Prima Entrada Original}) \times \text{Contratos} \times 100 $$

### Genealogía del Trade
La app usa el campo `ParentID` para vincular operaciones.
*   Una operación C errada genera una nueva operación B.
*   B tiene `ParentID` = A.
*   Al analizar B, la función recursiva `get_roll_history` busca A, luego el padre de A, etc., sumando todos sus flujos de caja.
