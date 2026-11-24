# Changelog

All notable changes to this project will be documented in this file.

- **Detección e Importación Automática de Operaciones Intradía / 0DTE (SPX/SPXW y Scalping)**:
  - **Motor Intradía (`detect_intraday_closed_trades` e `import_intraday_trades`)**: Desarrollado un motor inteligente en `tradier_sync.py` capaz de escanear tanto órdenes multileg ejecutadas en la sesión actual (`/orders`) como el historial de trades recientes (`/history`) para detectar operaciones abiertas y cerradas en el mismo día (*round-trips intradía / 0DTE*) que no figuran en las posiciones abiertas de Tradier.
  - **Nueva Pestaña en Asistente Tradier (`⚡ Intradía / 0DTE`)**: Se añadió una pestaña dedicada y una métrica de conteo en el panel de sincronización de Tradier que desglosa las operaciones intradía detectadas (Spreads, Iron Condors, compras/ventas), mostrando strikes, precios de apertura y cierre, PnL bruto y comisiones, con opciones de importación individual o en lote (`⚡ Importar Todas`).
  - **Consolidación de Operaciones SPXW**: Registro exacto de las operaciones del 23-Nov (3 Call Debit Spreads: 7260/7270 por -$45, 7270/7280 por -$50, 7270/7285 por +$65; pérdida neta en efectivo de -$42.72) y del 24-Nov (Bull Put Spread 7195/7205 por +$10 e Iron Condor por +$20).

- **Unificación Global de `ChainID` en Campañas de Rolls y Consolidación de PnL Neto Real en el Historial**:
  - **Integridad de PnL en Rolls**: Se corrigió un problema estructural por el cual cada roll generaba un nuevo `ChainID`, provocando que el Historial mostrara cada roll como un trade huérfano y la pata de cierre como una ganancia aislada no compensada (ej. en F mostraba +$255 en lugar de descontar los -$224 del roll previo).
  - **Propagación Retroactiva en Toda la Bitácora**: Se ejecutó un algoritmo de genealogía sobre toda la bitácora que unificó bajo el `ChainID` raíz 53 operaciones de rolls históricos (afectando a campañas de F, NKE, NFLX, NVO, RKT, SOFI, DRAM, CIFR, IREN, etc.).
  - **Visualización Consolidada**: Cada campaña de rolls ahora se presenta en el Historial como una única operación continua cuyo PnL total refleja con absoluta fidelidad el resultado neto real de toda la campaña (ej. F: -$224 + $255 = +$31.00; NKE: -$45 - $82 + $157 = +$30.00; NFLX: -$213.3 - $111.3 + $474.7 = +$150.10).


- **Corrección de Indicador de Vencimiento y Cantidad de Acciones para Posiciones de Stock (NKE / GAP)**:
  - **Badge de Vencimiento `∞ Stock`**: Las posiciones de tenencia de acciones procedentes de asignación tienen configurada internamente la fecha perpetua `2099-12-31`. El formateador de encabezados interpretaba el mes y día (`31 Dec`) en vez de reconocer que se trataba de una posición de acciones sin vencimiento. Se corrigió para mostrar siempre `:blue-background[**∞ Stock**]`.
  - **Alineación de Unidades (`100 acc.`)**: Para posiciones de stock se calculaba `{int(qty)} acc.` mostrando erróneamente `1 acc.` en lugar de multiplicar los contratos de asignación por 100 (`100 acc.`).


- **Corrección de Importación y Visualización de Covered Calls (GAP 22C 31-Dic)**:
  - **Independencia de ChainID para Covered Calls**: Al importar un Covered Call desde Tradier, se asignaba por error el `ChainID` de la posición de acciones al registro de la opción, provocando que se fusionaran bajo una sola fila en Cartera Activa y ocultando el Covered Call. Se corrigió tanto en `batch_sync_all` como en el modal de sincronización individual para que la opción conserve su propio `ChainID` de cadena/roll y se vincule a las acciones vía `WheelParentChainID` y actualizando `CoveredCallChainID` en el registro del stock.
  - **Trazabilidad de Rolls en Covered Calls**: Se restauró la genealogía completa del roll de GAP (`23C 20-Nov @ $0.01` marcado como `Rolada` con PnL de +$154 -> `22C 31-Dic @ $0.81` abierto con 9 rolls acumulados y 41 DTE).
  - **Métricas Directas en La Rueda**: En el bucle de `Covered Calls Activos` del panel La Rueda, se renderizan directamente las métricas del registro activo (`cc_row`) en lugar del primer registro histórico del ChainID, garantizando la visualización inmediata del strike actual ($22.00) y su fecha de vencimiento (31 Dic 2026).


- **Fila de Encabezados y Tabulación en La Rueda (Posiciones de Acciones Asignadas)**:
  - **Cabecera de Columnas Dedicada**: Se incorporó una barra superior con estilo de panel/tarjeta (`background: rgba(255,255,255,0.025)`, borde sutil y esquinas redondeadas) situada justo sobre las posiciones de acciones en La Rueda, definiendo con exactitud sus 7 columnas:
    - `Ticker` (68px, centrado)
    - `Vencimiento` (90px, centrado)
    - `Estrategia` (120px, centrado)
    - `Acciones` (85px, centrado)
    - `Covered Call` (160px, centrado)
    - `BE Base` (175px, centrado)
    - `Precio Compra` (150px, centrado)
  - **Aislamiento CSS Específico (`.wheel-position-anchor`)**: Mediante la regla `:has(.wheel-position-anchor)`, se aplicó el dimensionamiento y centrado milimétrico a los badges de los expanders de La Rueda de forma completamente aislada, evitando que hereden el ancho de la columna de opciones de Cartera Activa y garantizando que el indicador de Covered Call (`Covered Call: SÍ ✅` / `Covered Call: NO ⚠️`) no se trunque.

- **Fila de Encabezados de Columna para Cartera Activa e Historial de Operaciones**:
  - **Alineación Perfecta con los Badges Tabulados**: Se añadió una barra superior de encabezados estilizada tipo tarjeta justo encima de la lista de Cartera Activa y del Historial de Operaciones, indicando claramente el concepto de cada columna:
    - **Cartera Activa**:
      - `DTE` (encima del badge lateral de vencimiento)
      - `Ticker` (68px, centrado)
      - `Vencimiento` (90px, centrado)
      - `Estrategia & Strikes` (220px, centrado)
      - `Contratos` (75px, centrado)
      - `Rolls` (90px, centrado)
      - `BE Subyacente` (175px, centrado)
      - `Cierre BE (Broker)` (245px, alineado a la izquierda)
      - `Alertas` (ancho dinámico)
    - **Historial de Operaciones**:
      - `Ticker` (68px, centrado)
      - `Vencimiento` (90px, centrado)
      - `Estrategia & Strikes` (220px, centrado)
      - `Estado` (105px, centrado)
      - `Fecha Cierre` (115px, centrado)
      - `PnL Realizado` (130px, centrado)
      - `% Retorno` (95px, centrado)
      - `Patas / Contr.` (115px, centrado)
  - **Diseño Moderno Tipo Terminal Financiero**: Tipografía en mayúsculas pequeñas (`11px`, `font-weight: 700`, color `#8b949e`), espaciado exacto (`gap: 6px`) y padding que compensa la flecha desplegable del expander (`padding-left: 34px`) con contenedor semitransparente estilizado.

- **Sincronización Inteligente con Tradier / Sigma Trade y Corrección de Rolls y Timezone**:
  - **Corrección de Error Crítico de Timezone en `batch_sync_all`**: Solucionado el fallo `TypeError: Invalid value '...Z' for dtype 'datetime64[us]'` / `ValueError: Passed data is timezone-aware, incompatible with 'tz=None'`. Se implementó el helper `sanitize_date_for_df()` para limpiar fechas ISO con sufijo 'Z' provenientes de la API de Tradier y convertirlas en formato compatible tz-naive antes de almacenarlas en `FechaCierre`.
  - **Eliminación de Falsos Rolls en Cierres Multileg (Spreads e Iron Condors)**:
    - Se restringió la detección de rolls para no confundir órdenes de cierre complejas (como el cierre del Iron Condor de SPXW) con rolls. Si todas las patas de una orden tienen side `_to_close`, se tratan exclusivamente como ejecuciones de cierre y se capturan sus precios reales de ejecución (`fills_by_symbol`) sin generar emparejamientos espurios de roll.
    - Se sanearon los eventos de historial para exigir que cualquier pata de apertura pertenezca a las posiciones actualmente abiertas en Tradier y cuente con distinta fecha de expiración, evitando el emparejamiento indebido entre patas de spreads cerradas el mismo día.
  - **Detección y Reconstrucción Automática de Rolls Encadenados (Multi-Hop / Doble Roll Intradía)**:
    - Reconocimiento de secuencias de roll en el mismo día (ej. RKLB: `27-Nov -> 04-Dic -> 11-Dic`). El sistema detecta la pata intermedia abierta y cerrada en el mismo día (`04-Dic`), calcula su PnL realizado independiente, la registra como `Rolada` con su genealogía completa (`3ef54406 -> 04-Dic -> 11-Dic`) y mantiene la trazabilidad intacta sin dejar posiciones huérfanas ni duplicadas.
  - **Sincronización de Órdenes Individuales (Single-Leg Rolls)**:
    - Soporte completo para órdenes individuales `class: option` (ej. roll manual de Covered Call de GAP: cierre de 23C y apertura de 22C). Se extraen fills de patas individuales y se emparejan automáticamente como roll al coincidir ticker, tipo de opción y encontrarse abierta la nueva pata.
  - **Vinculación Automática con La Rueda para Covered Calls Importados**:
    - Al incorporar un Covered Call desde Tradier (como GAP 22C 31-Dic), se detecta la tenencia de acciones subyacentes en cartera y se asocia automáticamente con `ParentID`, `WheelParentChainID` y `WheelLeg = 'covered_call'`, activando de inmediato el bloque de Covered Call activo y la actualización del Costo Base Real.
  - **Conciliación Total de Cartera**: Posiciones de SPXW, RKLB, GAP e IREN perfectamente sincronizadas y cuadradas al 100% (20 posiciones activas en StrikeLog correspondientes a las 18 de Tradier, 0 discrepancias).

- **Diseño Visual con Badges y Tabulación en 8 Columnas para Historial de Operaciones**:
  - **Alineación Vertical Continua**: Las tarjetas de operaciones en el Historial se organizan ahora en una cuadrícula de 8 columnas fijas con recuadros redondeados, facilitando el escaneo visual de operaciones pasadas:
    - **Columna 1 (Ticker)**: Ancho fijo (68px), centrado con recuadro violeta.
    - **Columna 2 (Vencimiento)**: Ancho fijo (90px), centrado con recuadro azul (`📅 20 Nov` o `∞ Stock`).
    - **Columna 3 (Estrategia y Strikes)**: Ancho fijo (220px), centrado con recuadro gris y nomenclatura compacta (`12.5 CSP`, `7610/7660 IC`, etc.).
    - **Columna 4 (Estado)**: Ancho fijo (105px), centrado con código de color (`🔄 Rolada` en azul, `🔒 Cerrada` en verde, `📜 Asignada` en naranja).
    - **Columna 5 (Fecha de Cierre)**: Ancho fijo (115px), centrado en gris (`📅 YYYY-MM-DD`).
    - **Columna 6 (PnL Realizado)**: Ancho fijo (130px), centrado con fondo verde (`💵 +$XX.XX`) para beneficios o rojo (`💵 -$XX.XX`) para pérdidas.
    - **Columna 7 (% Captura / Retorno)**: Ancho fijo (95px), centrado con verde (`📈 +XX%`) o rojo (`📉 -XX%`).
    - **Columna 8 (Patas y Contratos)**: Ancho fijo (115px), centrado en gris (`1 pata (x1)`, `4 patas (x1)`).
  - **Interior de Tarjetas de Historial**: Métricas en tarjetas oscuras translúcidas con hover, y barra de encabezado dedicada para el desglose de patas cerradas.

- **Corrección de Renderizado en Fórmula Visual de Break-Even (La Rueda)**:
  - **Eliminación de Bloque de Código Indentado**: Se eliminó la sangría accidental de espacios en la cadena HTML de la fórmula que provocaba que Markdown la interpretara erróneamente como un bloque de código `<pre><code>`. Los chips de cálculo (Compra, PCS/CSP, Covered Calls, Buy Put, Defensas, Fees y BE Final) ahora se ensamblan en una línea horizontal continua limpia.

- **Modernización y Organización Visual del Interior de Posiciones y Panel de La Rueda**:
  - **Encabezados Tabulados en La Rueda**: Las posiciones de asignación en La Rueda adoptan el mismo sistema de recuadros tabulados (`:violet-background`, `:blue-background`, `:green-background`, `:orange-background`), integrando el estado del Covered Call (`Covered Call: SÍ ✅` / `NO ⚠️`), el BE Base y el precio de compra en badges alineados.
  - **Tarjetas Métricas KPI Interiores**: Enriquecimiento visual de `st.metric` dentro de todas las tarjetas colapsables con fondos oscuros translúcidos, bordes sutiles, hover dinámico y etiquetas tipográficas de estilo terminal financiero.
  - **Línea de Tiempo del Historial de la Campaña Reestilizada**: Las tarjetas de eventos de La Rueda incorporan `backdrop-filter`, bordes de precisión, chips monospace para cada parámetro de ejecución (`Strike`, `Contratos`, `Prima`) y badges de PnL iluminados en verde/rojo según el resultado.
  - **Fórmula de Break-Even de Alta Precisión**: Presentación visual tipo bloque de cómputo financiero con términos coloreados por concepto (compra, créditos de put, CCs, fees) y resultado final destacado en verde esmeralda.
  - **Gestión Visual de Covered Calls Activos**: Recuadros dedicados con acento lateral cyan, métricas ordenadas y botón de expiración OTM estilizado.
  - **Interior de Cartera Activa**: Badges modernos para las fases de vencimiento Theta, tarjeta destacada para el escenario de asignación Reg-T, sustitución de `st.table` por `st.dataframe` nativo para el historial de rolls y barra de encabezado dedicada para las patas de la estrategia.

- **Tabulación Perfecta en Columnas Fijas para Encabezados de Cartera Activa**:
  - **Alineación Vertical Continua**: Las tarjetas colapsables de Cartera Activa ahora organizan sus recuadros en un sistema de 7 columnas fijas y tabuladas verticalmente, garantizando que todos los datos coincidan fila tras fila:
    - **Columna 1 (Ticker)**: Ancho fijo (68px), centrado con recuadro violeta.
    - **Columna 2 (Vencimiento)**: Ancho fijo (90px), centrado con recuadro azul (`📅 20 Nov` o `∞ Stock`).
    - **Columna 3 (Estrategia y Strikes)**: Ancho fijo (220px), centrado con recuadro gris y nomenclatura limpia y compacta (`11.5 CSP`, `23 CC`, `7385/7395/7025/7035 IC`, `19/21 Put Debit Spread`, etc.).
    - **Columna 4 (Contratos/Acciones)**: Ancho fijo (75px), centrado con recuadro gris (`X contr.` o `X acc.`).
    - **Columna 5 (Rolls)**: Ancho fijo (90px), centrado. Siempre presente (`🔄 X rolls` o `🔄 0 rolls`) para que ninguna fila sufra desfase de columnas.
    - **Columna 6 (BE Subyacente)**: Ancho fijo (175px), centrado con recuadro verde o morado (`🎯 BE Suby: $XX.XX` o `📌 BE Stock: $XX.XX`).
    - **Columna 7 (Cierre BE / Broker)**: Ancho fijo (245px), alineado a la izquierda con recuadro naranja (`🎯 Cierre: $X.XX (Tradier: +$YYY)` o `🎯 Cierre: --` para acciones).
    - **Columna 8+ (Alertas)**: Ancho adaptable al final para eventos inminentes (`🚨 EARNINGS`, `💰 DIVIDENDOS`).
  - **CSS Flexbox Avanzado**: Reglas de estilizado `:nth-of-type(1)` a `:nth-of-type(7)` inyectadas en `summary p` con `nowrap` y scroll horizontal de seguridad, logrando una presentación estética tipo tabla moderna interactiva.

- **Diseño Visual con Badges y Recuadros en Encabezados de Cartera Activa**:
  - **Transformación de Líneas de Texto en Cuadros Visuales**: Los encabezados de las tarjetas en Cartera Activa pasan de ser texto plano separado por puntos a componerse de recuadros visuales independientes (badges/chips) con esquinas redondeadas, sombra sutil y códigos de color según el tipo de dato.
  - **Paleta de Colores por Información**:
    - **Ticker**: Recuadro morado `:violet-background` para rápida identificación del subyacente.
    - **Fecha de Expiración**: Recuadro azul `:blue-background` con icono de calendario (`📅 15 Jan` o `∞ Stock`).
    - **Estrategia y Strikes**: Recuadro gris oscuro `:gray-background` con strike y estrategia.
    - **Contratos**: Recuadro gris `:gray-background` con la cantidad activa.
    - **Rolls**: Recuadro azul `:blue-background` destacando la cantidad de rolls acumulados (`🔄 X rolls`).
    - **BE Subyacente**: Recuadro verde `:green-background` con el precio de equilibrio del subyacente (`🎯 BE Suby: $XX.XX`).
    - **Cierre BE Opción / Broker BE**: Recuadro naranja `:orange-background` con el precio de cierre y P/L Tradier BE (`🎯 Cierre BE: $X.XX`).
    - **Alertas**: Recuadros rojo (`🚨 EARNINGS`) y amarillo (`💰 DIVIDENDOS`) para eventos corporativos inminentes.
  - **CSS Premium para Expander**: Estilo personalizado que aporta espaciado uniforme, hover reactivo y profundidad visual a la cabecera.

- **Visualización de BE Subyacente en Líneas de Cartera Activa**:
  - **Doble Indicador de Break-Even en Encabezados**: Cada tarjeta colapsable de Cartera Activa ahora muestra visiblemente el **`🎯 BE Subyacente: $XX.XX`** (precio de la acción para estar en tablas a vencimiento) además de **`🎯 Cierre BE Opción: $X.XX`** y el punto de equilibrio en broker (`P/L Tradier BE: $YYY`).
  - **Cobertura Universal de Estrategias**: Visible en todas las operaciones de opciones individuales (CSPs, Covered Calls) y spreads, permitiendo ver de un vistazo el precio del activo subyacente sin necesidad de abrir la tarjeta.

- **Reconciliación y Enlace Genealógico Completo de Rolls (IREN, CIFR, DRAM, NU, F)**:
  - **Reconstrucción Integral de Cadenas de Rolls**: Cotejo exhaustivo contra la API de historial y órdenes ejecutadas en Tradier Brokerage para restablecer los vínculos de parentesco (`ParentID`) en todas las posiciones activas de la cartera.
  - **IREN**: Enlace de la campaña de Strike $30 (4 rolls acumulados: 32P Exp 16-Oct ➔ 32P Exp 23-Oct ➔ 30P Exp 27-Nov ➔ 30P Exp 11-Dic ➔ 30P Exp 15-Ene) y Strike $32 (3 rolls acumulados: 36P Exp 16-Oct ➔ 32P Exp 18-Dic ➔ 32P Exp 15-Ene).
  - **CIFR**: Enlace de la campaña de Strike $11 (3 rolls acumulados: 11.5P Exp 16-Oct ➔ 11P Exp 13-Nov ➔ 11P Exp 18-Dic ➔ 11P Exp 15-Ene) y Strike $12 (4 rolls acumulados: 13.5P Exp 09-Oct ➔ 13P Exp 16-Oct ➔ 12P Exp 18-Dic ➔ 12P Exp 15-Ene ➔ 12P Exp 19-Mar).
  - **DRAM**: Enlace completo de Strike $52 (4 rolls acumulados: 54P Exp 16-Oct ➔ 53P Exp 30-Oct ➔ 52P Exp 27-Nov ➔ 52P Exp 04-Dic ➔ 52P Exp 15-Ene) y Strike $51 (5 rolls acumulados).
  - **NU**: Enlace del roll multileg de hoy 19-Nov (Orden #160824832, 3 contratos 12.5P Exp 20-Nov @ $0.41 ➔ 12.0P Exp 11-Dic @ $0.45).
  - **F (Ford)**: Enlace del roll multileg de 5 contratos de Strike 12.0P Exp 20-Nov @ $0.69 ➔ Exp 27-Nov @ $0.70 (Orden #160827156), y discriminación exacta en Strike 11.5P entre los 2 contratos originales y el contrato rolado (Orden #160820920).
  - **Exactitud en Break-Even Global y Métricas de Cartera Activa**: Con todas las cadenas conectadas, el cálculo de `P/L Tradier BE`, `Cierre BE Opción` y los badges de rolls reflejan al milímetro el resultado real consolidado.

- **Validación en Lote Automática y Detección de Rolls Multi-Día en Tradier Sync**:
  - **Botón `⚡ Sincronizar Todo Automático`**: Al abrir el asistente con discrepancias detectadas, se añade un banner principal superior que permite aplicar de un solo clic todas las operaciones pendientes (rolls emparejados, cierres de posiciones faltantes e importación masiva de nuevos combos e individuales).
  - **Validación en Lote por Sección**: Botón complementario `⚡ Resolver Todas las Faltantes` en la sección de posiciones faltantes y `⚡ Importar Todas las Nuevas` en la sección de incorporaciones para operar por bloques.
  - **Preservación Total de Validación Individual**: Se mantienen 100% operativos los botones fila a fila (`Cerrar`, `🔄 Rolada`, `📜 Asignada`, `➕ Añadir Combo`, `➕ Añadir a Cartera`), permitiendo revisar minuciosamente cada operación cuando se desee.
  - **Detección Retroactiva de Rolls desde Historial (`/history`)**: El motor de conciliación ahora inspecciona las últimas 100 transacciones del historial de Tradier además de las órdenes del día, detectando automáticamente rolls ejecutados días atrás sin obligar a sincronizar el mismo día.
  - **Botón Manual `🔄 Rolada` en Discrepancias**: Incorporado en todas las operaciones faltantes para que el usuario pueda marcar un roll y vincular la posición padre/hijo directamente sin editar la bitácora a mano.

- **Conciliación Inteligente por Contratos y Flujos de Cierre / Asignación en Tradier Sync**:
  - **Desglose Exacto de Operaciones VIX**: Separación del spread de VIX 20/24C en dos operaciones independientes de 1 contrato cada una con sus primas de ejecución reales desde el historial de órdenes de Tradier: Orden #156561713 ($1.08 crédito neto, BP $292, BE $21.08, MaxProfit $108) y Orden #156564261 ($1.05 crédito neto, BP $295, BE $21.05, MaxProfit $105).
  - **Contabilidad de Contratos Parciales / Agrupados**: Algoritmo de reconciliación en `tradier_sync.py` actualizado para llevar contabilidad por contratos disponibles (`remaining_contratos`), permitiendo que múltiples entradas o coberturas individuales en StrikeLog concilien al 100% contra posiciones consolidadas en el broker sin falsas advertencias de "faltantes".
  - **Soporte Nativo de Asignación en Sincronización**: En el panel de discrepancias, cuando una opción Short Put / CSP ya no está abierta en Tradier, se ofrece tanto el botón para cierre estándar (con precio de fill precargado u OTM a $0) como el botón `📜 Asignada` para registrar la asignación y coordinar la incorporación de las 100 acciones a La Rueda (`Long Stock (Asignación)`).

- **Detección Automática de Precios de Cierre y Rolls en Tradier Sync**:
  - **Auto-relleno de Precios de Cierre desde Órdenes Reales**: El asistente de sincronización ahora consulta las órdenes ejecutadas en Tradier (`/accounts/{id}/orders`) para buscar la pata de cierre (`buy_to_close` o `sell_to_close`) de cualquier posición faltante, rellenando automáticamente el precio de recompra exacto (ej. `$12.61` y `$13.20` en DRAM) en lugar de mostrar `$0.00`.
  - **Identificación Automática de Rolls Multileg**: Al detectar órdenes de tipo roll (cierre de un contrato antiguo y apertura simultánea de un nuevo vencimiento/strike), la interfaz notifica el roll detectado, muestra el crédito neto del ajuste y ofrece el botón `🔄 Aplicar Roll`. Al pulsarlo, marca la posición previa como `Rolada`, registra el costo de cierre real y enlaza automáticamente el `ParentID` en la nueva pata abierta para conservar intacta la cadena histórica de la campaña.
  - **Corrección de Genealogía en Rolls de DRAM**: Se vincularon formalmente los contratos rolados de DRAM (`DRAM 51P Exp 27-Nov -> Exp 11-Dic` y `DRAM 52P Exp 27-Nov -> Exp 04-Dic`), asignando el estado `Rolada` y enlazando los `ParentID` correspondientes.
  - **Soporte Robusto para `pd.NA`**: En `calculate_open_positions_net_otm_profit` y en el árbol genealógico de campañas de `JournalManager`, se corrigió la evaluación booleana directa sobre `ParentID` (`while curr_parent and ...`), sustituyéndola por comprobaciones seguras con `pd.notna(...)` y un registro de identificadores visitados (`seen_parents`).
  - **Detección Automática de Combos Multi-Pata (Spreads, Strangles, Condors)**: Al sincronizar con Tradier, se agrupan automáticamente las posiciones que comparten subyacente y vencimiento, detectando la estrategia combinada (ej. `Call Credit Spread`) y permitiendo añadirlas con 1 solo clic bajo el mismo `ChainID`, calculando el crédito neto real y el Buying Power correcto de la estructura.
  - **Catálogo Completo de Estrategias al Añadir desde Tradier**: Al incorporar nuevas posiciones detectadas en Tradier, el desplegable de `Estrategia` ahora despliega las **32 estrategias completas** de StrikeLog con preselección inteligente según lado y tipo de opción (distinguiendo además ventas desnudas en índices como VIX de Covered Calls).
  - **Recarga Dinámica de Módulo (`importlib.reload`)**: Se evita el error `unexpected keyword argument` causado por la caché de módulos en memoria de Streamlit al recargar en caliente los cambios en `tradier_sync`.
  - **Helpers de Conversión Segura (`safe_float`, `safe_int`, `safe_str`)**: Centralización de funciones auxiliares seguras ante `pd.NA`, `np.nan` y `None` para evitar que campos nulos procedentes de la importación o sincronización provoquen excepciones de ambigüedad booleana en Streamlit.
  - **Deprecación de Streamlit `use_container_width` en DataFrames**: Se actualizaron las tablas interactivas de `tradier_sync.py` y `STRIKELOG.py` a `width="stretch"` según los nuevos estándares de Streamlit para eliminar advertencias en consola.

- **Indicador de P/L del Broker para Break-Even Global en Posiciones Roladas (`P/L Tradier/IB BE`)**:
  - **Claridad Total en Posiciones Defendidas/Roladas**: Al rolar opciones, los brokers (como Tradier o Interactive Brokers) reinician el P/L no realizado a cero en el nuevo contrato, lo que suele generar la falsa ilusión de estar ganando cuando la posición general aún arrastra pérdidas previas.
  - **Etiqueta en el Encabezado de Cartera Activa**: Para cualquier posición con rolls activos (`num_rolls > 0`), se añade automáticamente junto a `🎯 Cierre BE Opción` el P/L exacto que debe verse en la pantalla del broker para alcanzar el Break-Even global (ej: `🎯 Cierre BE Opción: $0.42 (P/L Tradier BE: +$923)`).
  - **Métrica y Tooltip Enriquecidos**: La métrica `Cierre BE Opción` dentro de la tarjeta ahora incorpora el subtítulo `Tradier BE: +$923` con un tooltip explicativo que desglosa el número de rolls compensados y el importe total en dólares de los ajustes previos.
  - **Escape de Símbolos `$` contra KaTeX**: Se escaparon los caracteres `$` en los títulos de tarjetas colapsables (`header_title`) para evitar que el renderizador markdown de Streamlit interprete los símbolos de dólar dobles como ecuaciones matemáticas LaTeX en lugar de montos de divisa.

- **Aislamiento y Blindaje de Scalping en Acciones (Medved Trader) en Tradier Sync**:
  - **Filtro Automático Anti-Scalping**: La reconciliación con Tradier (`tradier_sync.py`) ahora discrimina automáticamente cualquier posición de acciones puras (`is_option = False`) que no pertenezca a StrikeLog, omitiéndola automáticamente para que no aparezca en *"➕ Nuevas en Broker"* ni altere la bitácora de opciones.
  - **Desplegable Opcional de Acciones para Covered Calls / La Rueda**: Si el trader compra 100, 200 o más acciones deliberadamente para vender Covered Calls, se muestra un desplegable opcional con el botón `➕ Añadir a Rueda (CC)` para incorporarlas con 1 solo clic como `Long Stock`, calculando contratos (múltiplos de 100) y costo base exactos.
  - **Preservación 100% Intacta de Asignaciones de CSP**: Las acciones provenientes de asignación en la Rueda (como `GAP` y `NKE`) se siguen reconociendo y emparejando al 100% contra Tradier.
  - **Filtro de Opciones en Historial de Órdenes**: Se añadió el filtro `🎯 Filtrar solo Opciones (ocultar compras/ventas de acciones de scalping)` (activo por defecto) y se amplió el límite a 100 eventos en la pestaña de historial reciente, evitando que órdenes de scalping de Medved saturen la vista.

- **Métrica de Beneficio Neto Real si las Opciones Expiran OTM (`calculate_open_positions_net_otm_profit`)**:
  - En **Cartera Activa** y en el **Cuadro de Mando (Dashboard)**, la tarjeta **`💵 Primas Pendientes`** ahora desglosa tanto el crédito bruto ingresado (**$4,042 USD**) como el **beneficio neto real si todas expiran OTM (+${net_profit_if_otm:,.0f} USD)**.
  - El cálculo rastrea recursivamente el árbol de `ParentID` de cada posición activa para deducir las pérdidas/costes contables asumidos en los rolls y defensas pasadas de la misma campaña, dando la cifra matemática exacta de ganancia neta libre de polvo y paja.
- **Sincronización en Vivo y Asistida con Tradier Brokerage / Sigma Trade**:
  - **Módulo Independiente `tradier_sync.py`**: Integración segura vía API REST de Tradier con lectura de variables protegidas en `.env` (ignorado en `.gitignore`), implementando parser nativo sin requerir dependencias externas adicionales (`python-dotenv`).
  - **Botón `🔄 Sinc. Tradier` en Cartera Activa**: Permite contrastar con un solo clic los balances de cuenta en tiempo real (`Total Equity`, `Option BP Real`, `Stock BP`) frente al cálculo interno de StrikeLog.
  - **Reconciliación 1:1 de Posiciones**: Compara al milímetro las posiciones abiertas de StrikeLog contra las de Tradier, verificando strikes, fechas de vencimiento, lado (Sell/Buy), tipo de opción y contratos.
  - **Gestión Asistida de Novedades**: Detección de operaciones cerradas o roladas en el broker para actualizar su cierre en la bitácora con precio real, y detección de nuevas aperturas en Tradier para agregarlas a la cartera activa con 1 solo clic.
  - **Visor de Historial de Transacciones**: Pestaña dedicada con las últimas 25 ejecuciones (fills, montos y descripciones) directo desde Tradier.
- **Edición de Fecha de Vencimiento (`Expiry`) en Patas y Operaciones Activas**:
  - **Formulario de Pata Individual (`✏️ Editar esta pata`)**: Se añadió el selector de `Fecha Vencimiento` para permitir corregir o actualizar la expiración de cualquier pata abierta (especialmente útil si se olvidó ajustar la fecha al ejecutar un Roll).
  - **Sincronización Opcional Multi-Pata**: En estrategias con múltiples patas, se incluyó una casilla para aplicar el nuevo vencimiento a todas las patas de la operación simultáneamente.
  - **Edición a Nivel de Operación (`✏️ Editar`)**: Se integró el campo `Fecha Vencimiento` en el popover general de edición de la operación para posiciones con vencimiento unificado, con control estricto de inicialización (`pe_expiry`).
  - **Persistencia y Reactividad Inmediata**: Guarda con backup automático (`JournalManager.save_with_backup`), actualizando `UpdatedAt` y recalculando al instante el DTE y los indicadores visuales.
- **Cálculo de Margen Tradier (Reg-T) vs Asignación 100% Cash y Resumen Ejecutivo en Cartera Activa**:
  - **Margen Real de Tradier (Reg-T Margin / BP Effect)**: Se añadió el cálculo del margen real retenido por Tradier (`calculate_tradier_margin`, aprox. 20% del strike en CSPs vendidas + valor de stock asignado), diferenciándolo del compromiso de asignación total en efectivo (`calculate_position_bp`).
  - **Resumen Informativo Limpio en Cartera Activa y Dashboard**: Se integraron tarjetas KPI ejecutivas directas y sin alarmas visuales:
    - `📦 Posiciones Abiertas`: Conteo total de operaciones y desglose por tipo (CSPs, CCs, Stock).
    - `🏦 Margen Bloqueado Tradier`: Refleja el margen real bloqueado en el broker con delta del Option BP libre para seguir operando.
    - `🔒 Asignación 100% Cash`: Efectivo requerido en caso de asignación total al contado.
    - `💵 Primas Pendientes`: Crédito acumulado en posiciones abiertas a capturar si expiran OTM.
    - `🎯 Tickers Activos`: Número de subyacentes únicos en cartera.
  - **Métricas Individuales por Tarjeta de Posición**: En cada operación abierta se muestra cara a cara el capital necesario al 100% cash (`100% Cash Asignación`) y el margen retenido por Tradier (`Margen Tradier`).
  - **Configuración Persistente de Cuenta (`config_cuenta.json`)**: Gestión persistente de capital de cuenta y configuración de cuenta accesible desde el Sidebar.
  - **Auto-cálculo y Corrección de Buying Power (BP)**: Normalización automática de Buying Power para todas las CSPs y acciones con BP = 0 en la bitácora (`bitacora_opciones.csv`) y auto-sugerencia en los formularios de registro de operaciones.
- **Resolución de Advertencias de Inicialización de Variables (Punto 1)**: Se corrigieron todas las posibles variables no inicializadas reportadas por el linter estático (`col_note_cc` en el panel de notas de La Rueda, `stock_id` y `acciones_st` en la asignación de Covered Calls, y `t_tot_lifetime` / `t_open_lifetime` en el cálculo de métricas de Historial).
- **Modernización y Rediseño Premium del Rendimiento Mensual (Punto 2)**:
  - Se sustituyó el gráfico anterior por un diseño visual moderno, ordenado **cronológicamente por año y mes** (evitando el orden alfabético previo que mezclaba meses).
  - Etiquetas legibles en español (`Ene 2026`, `Feb 2026`, etc.) y colores contrastados: Verde Esmeralda (`#00FFA2`) para meses en positivo y Rojo Coral (`#FF4D4D`) para meses en negativo.
  - Etiquetas de datos directas sobre las barras (`+$X.XX` / `-$X.XX`), grid sutil, y tooltip enriquecido con PnL, número de operaciones, Win Rate del mes y comisiones.
  - Se añadieron 4 tarjetas métricas KPI clave sobre el gráfico: **🏆 Mejor Mes**, **🔻 Peor Mes**, **📊 Media Mensual** y **🎯 Consistencia (% meses positivos)**.
- **Estrategia por Defecto: CSP (Cash Secured Put) (Punto 3)**: Se reordenó la lista de estrategias (`ESTRATEGIAS`) colocando `CSP (Cash Secured Put)` en la primera posición (índice 0) para que aparezca seleccionada por defecto al abrir la pestaña de "Nueva Operación".
- **Sincronización Multi-Fuente de Calendario y Corrección de Dividendos (Punto 4)**:
  - Se actualizó el motor de sincronización de calendario contrastando automáticamente **Yahoo Finance** con la API de **Nasdaq** (`api.nasdaq.com/api/analyst/...` y `/api/quote/.../dividends`).
  - **Corrección de fechas pasadas en dividendos**: Anteriormente Yahoo Finance devolvía la fecha del último dividendo ya pagado (fechas pasadas), lo que provocaba que las alertas de proximidad de dividendos (`<= 14d`) nunca saltaran. Ahora el sistema detecta si la fecha está en el pasado y, si la empresa reparte dividendos habitualmente, proyecta el ciclo trimestral correspondiente (`+91 días` hacia adelante) indicándolo como `📅 Estimado Trimestral (Previo: DD/MM/AAAA)`.
  - Si tanto Yahoo como Nasdaq tienen fecha confirmada para Earnings, se valida con `✅ Verificado (Yahoo + Nasdaq)`. Si hay discrepancias, se resalta para advertir al trader.
  - Se incorporó un **Informe de Verificación Multi-Fuente interactivo** desplegable en **Cartera Activa** al sincronizar, permitiendo inspeccionar la fecha y el origen/estado de cada ticker activo.
- **Exclusión de Roles de Pérdidas en Dashboard e Historial**: Se corrigió el cálculo de victorias y derrotas (`Win Rate`, `losses`, rachas y ratio `✅ / ❌`) para excluir las operaciones con estado `Rolada`. Los roles son defensas/ajustes de una posición viva y no pérdidas definitivas; computarlos como derrotas inflaba artificialmente el contador de pérdidas (en la base de datos representaban 12 de 56 pérdidas, distorsionando el Win Rate real del 72.2% al 67.4%). Los roles siguen registrándose y computando en el flujo de caja (`PnL_USD_Realizado`), pero no penalizan las estadísticas de acierto del trader a menos que se filtre explícitamente por `Estado: Rolada`.
- **Botón de Restablecimiento Rápido de Filtros en Dashboard e Historial (Punto 2)**: Se añadieron botones de `🔄 Restablecer Filtros` accesibles con un solo clic tanto en el **Cuadro de Mando (Dashboard)** como en el **Historial**. Incluyen detección reactiva de filtros activos (`🟢 Filtros activos`) y reseteo inmediato de todos los selectores, multiselectores y deslizadores a sus valores iniciales sin desconfigurar la sesión.
- **Visualización de Cantidad Total de Operaciones al Filtrar por Ticker (Punto 3)**:
  - En el **Dashboard**: Se incorporó una métrica fija **`📋 Total Ops`** que cuantifica las operaciones únicas (`ChainID`) activas y cerradas. Cuando se filtra por un ticker específico (ej: `NKE`), se muestra un banner destacado con el recuento histórico completo: total de operaciones realizadas, cuántas siguen abiertas, cuántas cerradas (desglosadas en victorias, derrotas y roles), contratos acumulados y PnL neto histórico.
  - En el **Historial**: La métrica **`📋 Total Ops`** ahora incluye un indicador delta del total histórico del ticker (`De X tot (Y ab)`) y un banner resumen para tener visibilidad instantánea del volumen total de operaciones ejecutadas en dicho subyacente.
- **NKE Comprehensive Audit & Post-Earnings Recovery Strategy**: Conducted a full cash-flow and multi-scope Break-Even audit across all 16 historical operations for Nike (NKE) following the earnings gap down to ~$32. Calculated exact direct BE ($38.97) and consolidated global BE ($40.27). Formulated and documented `PLAN_ESTRATEGIA_NKE_OCTUBRE_2026.txt` with the tactical optimal Covered Call roadmap (Strike $37.00 for Nov 20-27, +15.6% upside buffer) and late-October defensive Down & Out roll execution for the Nov 06 $36.00 CSP.
- **Added `BITACORA_NKE_NOTAS.txt` & `PLAN_ESTRATEGIA_NKE_OCTUBRE_2026.txt`**: Added comprehensive reference logs and actionable date-by-date trade management plans for NKE.

- **0DTE Express Live Clean Profit Preview**: Added a real-time **Profit Limpio (PnL Neto Realizado)** preview box with metric cards (`💰 Profit Limpio (Neto)`, `🎯 Captura %`, `📈 RoC %`, and `💸 Comisiones Totales`) inside the **⚡ 0DTE Express** form when marking a trade as closed (`✅ La operación ya está cerrada`). Traders can now instantly review their exact clean profit net of all commissions before confirming registration.
- **Historial Performance Optimization & Pagination**: Implemented server-side pagination in the **Historial** view (20 operations per page default with selector for 10, 20, 50, 100, and dual top/bottom pagination navigation controls) and disabled heavy state dumping (`DEBUG_LOG = False`). This drastically reduced the DOM node count (from ~1,700+ buttons down to <100), eliminating Streamlit reload bottlenecks, preventing dropped button click events, and ensuring instant opening of edit and delete popups/modals.
- **Fixed Button Click Drops in Expanders via Persistent `on_click` Callbacks**: Wired all trade edit and full chain delete buttons across **Historial**, **Cartera Activa**, and the inline edit danger zone with Streamlit `on_click` callbacks (`_cb_set_edit_trade`, `_cb_set_delete_chain`, `_cb_exec_delete_chain`, `_cb_exec_delete_single_or_chain`). This resolves Streamlit's event-drop behavior inside collapsed/re-rendered expanders and ensures clicking `✏️ Editar` or `🗑️ Eliminar` immediately opens the edit form or full confirmation banner.
- **Purged Erroneous 4-Leg SPX Trade**: Removed the 4 erroneous legs of the 0-strike closed SPX Iron Condor (`ChainID: 11d8a851`) directly from `bitacora_opciones.csv` with an automatic backup in `backups_journal/`.
- **Robust Top-Level Panels for Trade Edit & Full Deletion**: Replaced experimental `@st.dialog` (which was throwing `'open()' is not a valid Streamlit command`) with dedicated top-level confirmation and edit panels in both **Cartera Activa** and **Historial**. Clicking `🗑️ Eliminar` now immediately presents a prominent confirmation banner at the top of the view to safely delete all legs of the `ChainID`, while `✏️ Editar` displays the full inline form with all fields and a danger zone.
- **Direct Trade Edition & Full Chain Deletion in Portfolio & History**: Added explicit `✏️ Editar Operación` and `🗑️ Eliminar Operación Completa` action buttons across both **Historial** and **Cartera Activa** cards. Deleting a multi-leg operation now safely removes all legs associated with its `ChainID` from the database in a single step, preventing orphaned trade records.
- **Tradier Pro Fee Schedule Update ($10/mo Plan)**: Updated `get_fee_rate` for Tradier accounts under the $10/mo flat-fee plan. Standard equities and ETFs remain at `$0.00`, while `SPX` defaults to `$0.97/contract` ($0.35 Tradier commission + $0.60 CBOE proprietary index exchange fee + ~$0.02 OCC/regulatory pass-through) and other major indices default to `$0.95/contract`.
- **0DTE & 1DTE Express Form Enhancements**: Added explicit `Fecha Apertura` and `Fecha Vencimiento` date selectors alongside the `⌛ Operación Expirada OTM` sub-checkbox. This provides full support for both 0DTE and 1DTE short-term express trades while ensuring exact PnL and fee accounting.
- **Expanded Strategy & Setup / Motivo Catalogs**: Added new popular option strategies and entry reasons across the entire application:
  - **New Strategies**: *"La Rueda (The Wheel)"*, *"PMCC (Poor Man's Covered Call)"*, *"Jade Lizard"*, *"Big Lizard"*, *"Long Straddle"*, *"Long Strangle"*, *"Covered Put"*, *"Short Put (Naked)"*, *"Short Call (Naked)"*, and *"Long Stock"*, complete with automatic default leg population, credit/debit direction tagging, and Break-Even formulas.
  - **New Setups / Motivos**: Added *"La Rueda (The Wheel)"*, *"VIX alto / IV Crush"*, *"Ruptura (Breakout)"*, *"Rango Lateral"*, *"Sobrecompra / Sobreventa (RSI)"*, *"0DTE / Intradía"*, *"Cobertura / Hedging"*, and *"Dividendo"*.
- **NKE Option Assignment & Wheel Base Recalculation**: Registered the assignment of 100 shares of Nike (NKE) at strike $45.00 from the CSP sequence with the real dynamic Break-Even of $43.05, factoring in net PnL from previous spread rolls.
- **Fixed Wheel Dynamic BE Double-Counting Bug**: Fixed an issue in `JournalManager.calculate_stock_dynamic_be` and the Wheel rendering loop where assigned options (`Estado == 'Asignada'` or matching `ParentID`) had their PnL added twice (once as `PrimaRecibida` of the stock and once again in `extra_campana_pnl`), which previously distorted the dynamic Break-Even calculation.
- **Fixed LaTeX Math Formatting Glitch in Expander Titles**: Escaped raw dollar signs (`\$`) in Streamlit expander headers across La Rueda cards to prevent text (e.g. `* * • 🎯 BEBase`) from unintentionally rendering as LaTeX math formulas.
- **GAP Covered Call Roll Up & Out**: Registered the GAP Covered Call roll from the Aug 28, 2026 $23.00 Call (bought to close at $1.06) to the Sep 4, 2026 $24.00 Call (sold to open at $0.52) for a net debit of $0.54, raising the strike by $1.00 and updating the campaign break-even.
- **Recursive Wheel Campaign Dynamic BE Tracking**: Upgraded `calculate_stock_dynamic_be` and La Rueda panel with full recursive traversal of campaign parent/child/roll relationships. The system now accurately factors in multi-generation Covered Call rolls and debits/credits into the true net Cost Basis (`CostBaseReal`) and active stock Break-Even.
- **Wheel Campaign Metadata Propagation on Rolls**: Updated roll execution in `STRIKELOG.py` to preserve `WheelParentChainID` and `WheelLeg` on newly created rolled legs.
- **NKE Option Roll**: Registered the Nike (NKE) roll from the Aug 21, 2026 $45.00 Put (rebought at $4.81) to the Sep 4, 2026 $45.00 Put (sold at $5.19) for a net credit of $0.38, matching actual broker fills.
- **Roll Panel Net Credit/Debit Preview**: Added a dynamic green/orange/blue informational alert box in the Roll panel showing the exact Net Credit (e.g. +$0.38), Net Debit, or neutral/zero state of the roll in real time as user updates the close and new premium inputs.
- **Roll Panel Label Clarifications**: Renamed inputs in the roll panel to make them explicitly clear: `"Cierre ($/acción)"` became `"Costo de Recompra (Buy to Close) ($/acción)"` and `"Nueva Prima ($/acción)"` became `"Nueva Prima Recibida (Sell to Open) ($/acción)"`.
- **Manual CSV Reload Button**: Added a `🔄 Recargar desde Disco` button in the sidebar to allow users to force refresh the Streamlit in-memory cache directly from the `bitacora_opciones.csv` file without needing to reload the browser.
### Fixed
- **NFLX Campaign PnL Audit**: Corrected the NFLX October $75.00 Put position entries in the database to align with gross option premiums ($6.87) and buyback prices ($1.92 and $5.55). Set the final campaign card PnL to display exactly **+$40.00 USD** in green, resolving a PnL discrepancy and ensuring perfect synchronization between the app and the broker.





- **Main Dashboard UX & Statistics Enhancements**:
  - **🚀 Cartera Activa Executive Summary Banner**: Added a top-level summary banner to the main Dashboard displaying active trade count, total pending unearned premium credit, and reserved Buying Power.
  - **💰 PnL Neto Real Metric**: Added **`💰 PnL Neto Real`** metric calculating true net profits after broker commissions ($PnL_{Net} = PnL_{Gross} - Commissions$).
  - **⚖️ Expectativa Matemática por Trade (Expectancy)**: Added mathematical expectancy per trade calculation ($\text{Expectancy} = (\text{WinRate} \times \text{AvgWin}) - (\text{LossRate} \times \text{AvgLoss})$) indicating expected average gain/loss per new trade.
  - **🚦 Health Status Semaphores**: Added color-coded health status badges to KPIs (🟢 Saludable / 🟢 Excelente / 🟢 Sistema Ganador) so traders instantly recognize healthy vs risky performance metrics.
- **For-Dummies Contextual Guidance & Safety Net Cards**:
  - **Put Assignment Scenario Card**: Added an interactive summary card on active short Put positions showing exact worst-case assignment figures (*"If assigned today, you buy 100 shares at $75.00, and your real net cost base will be $71.06/share"*).
  - **DTE Phase Guidance Banner**: Added color-coded DTE phase guidance banners (🟢 Theta Harvest >30d, 🟡 Sweet Spot 21-30d, 🟠 Management 7-21d, 🔴 Expiration Risk ≤7d) advising when to take 50%-75% profit vs when to manage/roll.
  - **Roll Contract Scaling Risk Warning**: Added an automatic alert in the Roll configuration panel when increasing contract count (e.g. 1 to 2 contracts), warning users about increased Buying Power requirements and risk exposure.
- **Option & Stock BE Metrics in Card Header & Metrics Bar**: 
  - Added **`🏷️ Cierre BE Opción`** metric directly to active option cards and headers displaying the maximum option buyback price to achieve a $0.00 global PnL.
  - Added **`🏷️ BE Venta Stock`** metric directly to assigned stock cards and headers displaying the exact selling price per share needed to achieve a $0.00 global PnL on Wheel campaigns (e.g., $22.71 for GAP stock).
  - Upgraded **⚡ Cerrar Rápido** with dual PnL metrics (**PnL Etapa Actual** vs **PnL Global Campaña**) and an automatic warning box if a buyback price exceeds the campaign's accumulated net credit.
- **Timezone-Aware Option Expiration**: Improved option expiration detection by utilizing `America/New_York` timezone and confirming the U.S. market close (16:00 EST/EDT) on the expiration day (DTE 0) before showing options as expired in the pending actions banner.
- **Quick Close Partial Contracts**: Added a contract quantity selector (`Contratos`) directly to the **⚡ Cerrar Rápido** mini-panel when a position has multiple contracts (e.g. 2 contracts of NFLX). Users can now partially close specific contract quantities directly from Quick Close, leaving remaining contracts open.
- **Multiple Active Covered Calls**: Upgraded the Covered Call management block on Wheel stock cards to support listing, tracking, and expiring multiple active Covered Calls simultaneously. It also allows adding a new Covered Call if the active CC contracts are less than the total stock contracts.
- **Wheel Campaign Merger**: Added an interactive tool **🔗 Unificar Ciclos de La Rueda (Fusionar Posiciones)** in the active portfolio to merge multiple active stock positions of the same ticker, averaging their strikes, consolidating contracts, and automatically re-linking all child history entries.
- **Selective Leg Closing**: Enhanced the "Cerrar" tab in the management panel with checkboxes, allowing users to select and close individual legs of a multi-leg strategy (like an Iron Condor or a Put Credit Spread) independently. The app dynamically recalculates net premiums, closing costs, and PnL exclusively for the selected legs, leaving the unselected legs open and manageable under the original `ChainID`.
- **Wheel Campaign Selector**: Added a selectbox in the trade entry form that dynamically displays open wheel campaigns (stock positions) for the selected ticker. Selecting a campaign automatically links the new option by populating `ParentID`, `WheelParentChainID`, and `WheelLeg`. For Covered Calls, it also updates the active CC reference (`CoveredCallChainID` and `CoveredCallPrima`) on the parent stock row.
- **Flyagonal Strategy Support**: Added native support for the 6-leg hybrid Flyagonal strategy. Includes automatic suggestion of front-month and back-month expiration dates (front-month base + 30 days default for long Put protective leg).
- **Independent Leg Expirations**: Added a checkbox `📅 Usar vencimientos independientes por pata` and a vertical vertical-form layout for multi-expiry strategies (Flyagonal, Calendar, Diagonal). Leg expirations are written individually to the `Expiry` column in the CSV.
- **Venc. Column in Portfolio Table**: Added a dedicated `Venc.` column to the Active Portfolio leg breakdown table to clearly view individual expiration dates.
- **Dynamic Broker Commissions**: Replaced hardcoded `$0.65` commissions with a dynamic system aware of the selected Broker (`IB` defaults to `$0.65/contract`, `Tradier` defaults to `$0.00`). Closing, rolling, and assignment commissions dynamically inherit broker configurations.
- **La Rueda Enhancements**: 
  - Dynamic campaign linking to trace full historical NU wheel cycles (original PCS, intermediate CSP assignment, defensive spreads, Covered Calls, and active assigned stock).
  - Total campaign commission aggregation factored into dynamic `Costo Base Real (BE)` calculation.
  - Side-by-side notes editors for active stock and covered calls.
- **Break Even Explanation Panel**: Added a dynamic informational card below the active portfolio history table that breaks down and explains the math behind the break-even calculation step-by-step for multi-leg strategies.
- **Step-by-step BE Explanation Box**: Added a detailed, contract-weighted breakdown panel below the history table for active option campaign positions with rolls, detailing credits/debits from the opening and closed legs chronologically.
- **Active Portfolio Expander Formatting & Hierarchy**: Enhanced active trade expander title strings with bold typography (`**Ticker**`, `**Strikes**`, `**BE Price**`), clean bullet separators (`•`), and explicit Break Even badges (`📌 BE Venta Stock`, `🎯 BE Subyacente: $Lower – $Upper` range for dual-BE strategies, `🎯 Cierre BE Opción` for single-sided option spreads).
### Fixed
- **Dashboard NameError Fix**: Restored missing high-level KPI variable definitions (`pnl_total`, `wins_df`, `losses_df`, `win_rate`, `profit_factor`, `expectancy_trade`) in `render_dashboard()` to resolve `NameError: name 'pnl_total' is not defined`.
- **Iron Fly / Iron Butterfly Strategy Detection**: Fixed 4-leg strategy auto-detection in `detect_strategy_from_legs()` to properly classify positions where Short Put Strike == Short Call Strike as **Iron Fly / Iron Butterfly** instead of mislabeling them as Iron Condor.
- **Contract-Weighted Roll Calculations**: Fixed a mathematical bug where premiums and break-evens were summed directly per share across steps with different contract counts (e.g. 1 contract vs 2 contracts). The calculations are now properly weighted by contracts (in total dollars) and then divided by the active/new contract count to yield a mathematically precise Break-Even and Prima Total.
- **Break Even & Net Premium Math**: Corrected the calculation of net premiums in the Active Portfolio's historical roll view. The app now accurately sums premiums based on trade side (`Sell` = credit, `Buy` = debit) and correctly aggregates total campaign PnL across all chained legs to reflect the precise Break Even.
- **Streamlit Deprecations**: Replaced deprecated `st.components.v1.html` with `st.html(..., unsafe_allow_javascript=True)` and updated dataframe `use_container_width` argument to `width="stretch"` or `width="content"` to resolve runtime warnings and ensure future compatibility.
- **Local Variable Initialization Bug**: Fixed `UnboundLocalError: cannot access local variable 'legs_for_be'` in the Active Portfolio view by properly scoping the variables.
- **PnL Metric Decimal Precision**: Fixed a cosmetic issue displaying excessive decimal places in the realized PnL delta metrics.
- **PnL Filter Precision**: Rounded historical PnL sums to 2 decimal places to resolve float precision issues that caused transactions to be incorrectly excluded from the history view under the PnL slider filter.
- **Covered Call Assignment Logic**: Corrected the assignment logic for `"CC (Covered Call)"` strategies. Instead of creating a new `"Long Stock (Asignación)"` position when assigned, the system now correctly sells/retires the corresponding shares from the active stock inventory, closing the stock position or reducing its contract size accordingly.
- **CSP Cost Base Contributions**: Fixed an issue where CSP (Cash Secured Put) options closed/expired within a wheel campaign were excluded from the dynamic cost base calculations. Now, extra or rolled CSPs successfully reduce the stock's Break Even.
- **Always Visible Save Changes Button**: Fixed a UI issue where the "💾 Guardar Notas y Fechas" button in the Active Portfolio panel was conditionally rendered only after changes were detected. The button is now always visible at the bottom of the notes and dates section for a clearer and more intuitive experience.
- **Strategy Leg Selection**: Fixed a bug where selecting **Flyagonal** (or other custom strategies) in the trade entry form defaulted to showing only 1 leg. The form now dynamically retrieves the number of legs from the strategy's definition in `LEG_DEFAULTS` automatically.
- **Timeline Rendering**: Fixed an issue where unescaped dollar signs (`$`) in the HTML string caused Streamlit's markdown parser to render raw HTML tags (like `</span>`) as LaTeX math expressions. Replaced `$` with the safe HTML entity `&#36;`.
- **Duplicate Campaign Legs**: Grouped multi-leg strategies (like Put Debit Spreads and Put Credit Spreads) by their `ChainID` in the timeline history. This consolidates them into a single, beautifully formatted card displaying all strikes, combined PnL, and total commissions, rather than showing confusing duplicate entries.
- **Broker Commission Bug & Index Exceptions**: Added `get_fee_rate` helper function to handle broker-specific fees. Tradier now correctly defaults to `$0.65/contract` on indices (`SPX`, `NDX`, `RUT`, `VIX`, `DJX`, `XSP`) and `$0.00` on standard equities/ETFs, while IB always charges `$0.65`.
- **Streamlit Widget Session Caching**: Implemented dynamic keys for commission input fields. This fixes the issue where Streamlit's state cache prevented the commission from resetting when changing the selected broker.
- **Default Broker to Tradier**: Set **Tradier** as the pre-selected default broker when opening the application forms.
- **Pandas Concatenation FutureWarning**: Fixed a `FutureWarning` during DataFrame concatenation when adding new trades in `STRIKELOG.py`. Handled empty DataFrame initialization explicitly and excluded all-NA columns prior to calling `pd.concat`, ensuring clean execution without runtime warnings.


