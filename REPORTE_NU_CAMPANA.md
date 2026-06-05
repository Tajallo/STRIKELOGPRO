# Reporte Detallado de la Campaña: NU (Rueda Consolidadora)

Este reporte detalla cronológicamente la historia de tu posición en **NU** desde la apertura inicial en febrero de 2026, pasando por las asignaciones y ventas de Covered Calls y CSPs, hasta llegar a la posición unificada actual de **200 acciones**.

---

## 📊 Estado Actual de la Posición
- **Acciones Totales**: 200
- **Strike Promedio Ponderado**: **$15.50**
- **Break-Even Real Promedio (Costo Base)**: **$11.95**
- **Primas Netas Totales Capturadas**: **+$715.40 USD** (incluyendo créditos abiertos en juego)
- **Comisiones Acumuladas**: **$5.85 USD**

---

## 🕒 Línea de Tiempo Cronológica y Evolución

### Fase 1: El Origen (Febrero 2026 - Abril 2026)
Iniciaste la campaña vendiendo un **Put Credit Spread (PCS)** con strikes 18.0 / 16.0 el **24 de febrero de 2026**:
- **SP 18.0 Put (Venta)**: Cobraste **+$201.00 USD** ($2.01/acción).
- **BP 16.0 Put (Compra Protección)**: Pagaste **-$88.00 USD** ($0.88/acción).
- **Cierre del BP (01 de abril)**: Vendiste la protección en mercado por **+$132.00 USD** ($1.32/acción), logrando un beneficio de **+$44.00 USD** en esa pata.
- **Asignación del SP (01 de abril)**: El precio cayó por debajo de 18.0, por lo que te asignaron las primeras **100 acciones a $18.00** (ID `7869347a`).
  - *Break-Even inicial*: $18.00 (strike) − $1.13 (neta del PCS) = **$16.87**.
  - *Comisiones de apertura*: $1.30.

---

### Fase 2: Primer Covered Call y Defensas (Abril 2026 - Mayo 2026)
Con las 100 acciones en cartera, empezaste a rentabilizar la posición mediante Covered Calls (CC) y operaciones auxiliares:
- **CC Strike 16.0 (Apertura: 02 de abril | Cierre: 15 de mayo)**: 
  - Cobraste **+$46.00 USD** ($0.46/acción). Expiró sin valor (OTM), capturando el 100% de la prima.
  - *El Break-Even bajó a*: $16.87 − $0.46 = **$16.41**.
- **Defensa PDS Strikes 12.5 / 11.5 (15 de mayo)**:
  - Realizaste un Put Debit Spread defensivo que cerraste el mismo día con un beneficio neto de **+$11.40 USD**.
  - *El Break-Even bajó a*: $16.41 − $0.11 = **$16.30**.

---

### Fase 3: Rueda de CCs y CSPs Paralelos (Mayo 2026)
Continuaste operando Covered Calls sobre tus 100 acciones y, en paralelo, vendiendo CSPs para buscar promediar a la baja:
- **CC Strike 13.0 (Apertura: 20 de mayo | Cierre: 29 de mayo)**:
  - Cobraste **+$8.00 USD** ($0.08/acción), pero tuviste que recomprarlo (*Buy to Close*) por **-$25.00 USD** ($0.25/acción) debido a una subida del precio. Registraste una pérdida de **-$18.30 USD** (con comisiones).
  - *El Break-Even subió ligeramente a*: $16.30 + $0.18 = **$16.48**.
- **CSP Strike 11.5 (Apertura: 20 de mayo | Cierre: 29 de mayo)**:
  - Cobraste **+$9.00 USD** ($0.09/acción). Expiró sin valor.
  - *El Break-Even bajó a*: $16.48 − $0.09 = **$16.39**.
- **CSP Strike 13.0 (Apertura: 29 de mayo | Asignado: 04 de junio)**:
  - Cobraste **+$19.00 USD** ($0.19/acción).
  - Ayer, 4 de junio, expiró ITM y fuiste **asignado de otras 100 acciones a $13.00**.

---

### Fase 4: La Unificación y Situación Actual (04 - 05 de Junio 2026)
Tras la nueva asignación, abriste Covered Calls y CSPs adicionales que se han consolidado hoy:
- **Nuevas Acciones**: 100 acciones a **$13.00**.
- **Acciones Totales Consolidadas**: 200 acciones a un promedio de **$15.50**.
- **Créditos en Juego Activos**:
  - **CC Strike 13.5 (Expira hoy, 05 de junio)**: Aporta **+$16.00 USD** ($0.16/acción) que expira OTM sin valor al final del día.
  - **CC Strike 12.5 (Vence: 12 de junio)**: Aporta **+$15.00 USD** ($0.15/acción).
  - **CSP Strike 11.5 (Vence: 18 de junio)**: Aporta **+$16.00 USD** ($0.16/acción).

---

## 📈 Resumen de Flujo de Caja y PnL de Opciones

| ID | Fecha | Operación | Strike | Prima/Acción | Contratos | PnL Realizado | Estado |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `b0073646` | 24 Feb | Put Credit Spread (Sell Put) | 18.0 | +$2.01 | 1 | **+$201.00 USD** | Asignada |
| `3388f542` | 24 Feb | Put Credit Spread (Buy Put) | 16.0 | -$0.88 | 1 | **+$44.00 USD** | Cerrada |
| `77db2e16` | 02 Abr | CC (Covered Call) | 16.0 | +$0.46 | 1 | **+$46.00 USD** | Cerrada |
| `60da0bb5` | 15 May | Put Debit Spread | 11.5 | +$0.21 | 1 | **+$11.40 USD** | Cerrada |
| `81df0af2` | 20 May | CC (Covered Call) | 13.0 | +$0.08 | 1 | **-$18.30 USD** | Cerrada |
| `461e10bc` | 20 May | CSP (Cash Secured Put) | 11.5 | +$0.09 | 1 | **+$9.00 USD** | Cerrada |
| `31ee7047` | 29 May | CSP (Cash Secured Put) | 13.0 | +$0.19 | 1 | **+$19.00 USD** | Asignada |
| `bf3c80d8` | 29 May | CC (Covered Call) | 13.5 | +$0.16 | 1 | *+$16.00 USD (abierto)* | Abierta |
| `e821ada6` | 04 Jun | CC (Covered Call) | 12.5 | +$0.15 | 1 | *+$15.00 USD (abierto)* | Abierta |
| `b817a518` | 04 Jun | CSP (Cash Secured Put) | 11.5 | +$0.16 | 1 | *+$16.00 USD (abierto)* | Abierta |

---

## 📐 Conciliación Matemática del Break-Even (BE)

$$\text{Precio Compra Medio} = \frac{(100 \times \$18.00) + (100 \times \$13.00)}{200} = \mathbf{\$15.50}$$

$$\text{Primas Totales} = 201 + 44 + 46 + 11.4 - 18.3 + 9 + 19 + 16 (CC) + 15 (CC) + 16 (CSP) = \mathbf{+\$359.10\text{ USD}}$$

*(Por acción: $\$359.10 / 200 = \mathbf{\$1.7955}$)*

Sumando las primas de la primera y segunda campaña unificada y restando comisiones ($5.85):

$$\text{Costo Base Real} = \$15.50 - \text{Primas Totales/Acción} + \text{Comisiones/Acción} = \$15.50 - \$3.5772 + \$0.0292 = \mathbf{\$11.9522}$$

> [!TIP]
> Dado que tu Break-Even real promedio de todo el activo de NU es **$11.95**, cualquier venta por encima de ese nivel (por ejemplo, a $12.00, $12.20 o $12.40) te generará un beneficio neto real en la cartera.
