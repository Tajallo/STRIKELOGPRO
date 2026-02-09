# 🧮 Guía de Cálculos y Fórmulas - STRIKELOG Pro

Este documento detalla todas las fórmulas matemáticas y lógicas financieras que utiliza la aplicación para calcular métricas de rendimiento, gestión de riesgo y seguimiento de estrategias.

---

## 1. Métricas de Ganancias y Pérdidas (PnL)

Estas fórmulas se aplican cuando se **cierra** una operación, ya sea parcialmente o totalmente.

### PnL Realizado en USD (`PnL USD`)
Calcula cuánto dinero real se ganó o perdió en la operación.
*   **Operaciones de Crédito (Venta / Short):**
    $$ PnL = (\text{Prima Entrada} - \text{Precio Salida}) \times \text{Contratos} \times 100 $$
    *   *Ejemplo:* Vendiste un Put a 1.50 y lo recompras a 0.50. Ganancia = (1.50 - 0.50) * 100 = $100.

*   **Operaciones de Débito (Compra / Long):**
    $$ PnL = (\text{Precio Salida} - \text{Prima Entrada}) \times \text{Contratos} \times 100 $$
    *   *Ejemplo:* Compraste un Call a 2.00 y lo vendes a 2.50. Ganancia = (2.50 - 2.00) * 100 = $50.

### Retorno sobre la Operación (`Profit %`)
Porcentaje de beneficio respecto al riesgo asumido o prima inicial.
$$ \text{Profit \%} = \left( \frac{\text{PnL Unitario}}{\text{Prima Inicial Unitarian}} \right) \times 100 $$

### Retorno sobre Capital (`PnL / BP`)
Mide la eficiencia del uso del capital (Buying Power).
$$ \text{RoC} = \left( \frac{\text{PnL Total USD}}{\text{Buying Power Reservado}} \right) \times 100 $$

---

## 2. Break Even (Punto de Equilibrio)

El precio de la acción al vencimiento donde la operación ni gana ni pierde dinero.

### Cálculo Estático (Nueva Operación)
Al abrir un trade nuevo sin historia previa:
*   **Estrategias Put (Bajistas/Neutrales):**
    $$ BE = \text{Strike} - \text{Prima Total Recibida} $$
*   **Estrategias Call (Alcistas/Neutrales):**
    $$ BE = \text{Strike} + \text{Prima Total Recibida} $$

### Cálculo Dinámico Acumulativo (Campañas con Rolls)
Para estrategias que han sido ajustadas (**Roladas**), la app calcula el BE de toda la campaña ("Break Even de Campaña"), no solo de la operación vigente.

1.  **Crédito Neto de la Cadena:**
    $$ \text{CreditoNeto} = \sum(\text{Primas Históricas}) - \sum(\text{Costos de Cierre Históricos}) $$
    *   *Nota:* Si el resultado es negativo, se considera un Débito Neto.

2.  **Break Even de Campaña (Ajustado):**
    *   **Puts:** $ BE = \text{Strike Actual} - \text{CreditoNeto} $
        *   *Si tienes un Débito Neto, el BE sube (es peor).*
    *   **Calls:** $ BE = \text{Strike Actual} + \text{CreditoNeto} $
        *   *Si tienes un Débito Neto, el BE baja (es peor).*

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
