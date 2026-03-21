# 🚀 STRIKELOG Pro | Opcion Sigma Edition

**STRIKELOG Pro** es una bitácora de trading de opciones de nivel profesional, optimizada para la comunidad de **Opcion Sigma**. Esta herramienta no solo registra tus operaciones, sino que te ayuda a gestionar el riesgo, entender tus estadísticas y mantener el control total sobre tus estrategias complejas.

---

## 🧭 Tour por las Pantallas

### 📊 1. Dashboard (Tu Centro de Mando)
Es la primera pantalla que verás. Está diseñada para darte una visión clara de tu salud financiera:
- **KPIs de Rendimiento**: PnL Realizado, % de acierto (*Win Rate*) y Factor de Beneficio.
- **Curva de Equidad**: Un gráfico interactivo que muestra cómo crece tu capital con el tiempo.
- **Análisis por Estrategia**: Descubre visualmente qué te funciona mejor (¿vender Puts o hacer Iron Condors?).
- **Filtros Potentes**: Busca por Ticker (ej: SPY), por motivo de entrada (*Setup*) o por fechas.

### ➕ 2. Nueva Operación (Registro Inteligente)
Aquí es donde empieza todo. La app hace el trabajo duro por ti:
- **Formulario Adaptable**: Si seleccionas "Iron Condor", la app te pedirá las 4 patas automáticamente. Si eliges "CSP", solo una.
- **Asistente de Delta y BE**: Al introducir tus datos, la app te sugiere el **Break Even** y la **Probabilidad de Éxito (POP)** basándose en el Delta de la operación.
- **Setups Personalizados**: Marca si tu entrada fue por *Earnings*, *VIX alto* o *Tendencial* para analizar tu psicología después.

### 📂 3. Cartera Activa (Gestión de Riesgo)
Esta es la "joya de la corona" para el día a día:
- **Semáforo DTE**: Un código de colores te avisa del riesgo:
    - 🟢 **Verde (> 21 días)**: Operación bajo control.
    - 🟡 **Amarillo (7-21 días)**: Atención, evalúa el cierre o ajuste.
    - 🔴 **Rojo (< 7 días)**: Peligro de asignación o aceleración de Gamma.
- **Gestión de Roles (🔄 Roll)**: Única en su clase. Al rolar una posición, la app la vincula con la anterior, permitiéndote ver todo el árbol genealógico del trade y cuánta prima has acumulado en total.
- **Cierre en Bloque**: Cierra estrategias multi-pata con un solo botón y deja que la app calcule el beneficio neto.

### 📜 4. Historial y Datos
- **Filtros Históricos**: Revisa cualquier operación del pasado con detalles técnicos.
- **Editor de Errores**: En la pestaña "Datos / Edición", puedes corregir cualquier número que hayas introducido mal sin romper la base de datos.

---

### 🚀 ¿Qué hace el archivo "Lanzar_App.bat"?

Para que no tengas que usar códigos complicados, he creado el archivo **`Lanzar_App.bat`**. Al hacer doble clic, esto es lo que ocurre por dentro:

1.  **Verifica Python**: Revisa si tienes Python instalado. Si no lo tienes, te avisará con un mensaje claro.
2.  **Configuración Automática (Solo la primera vez)**: 
    - Crea una "cápsula" (entorno virtual) para que la app no interfiera con otros programas.
    - Instala automáticamente las librerías necesarias (*Streamlit, Pandas, Plotly*).
3.  **Inicia la App**: Abre tu navegador habitual (Chrome, Edge, etc.) y carga la interfaz de **STRIKELOG Pro**.

> **Nota IMPORTANTE**: Verás que se abre una "ventana negra" (consola). **No la cierres** mientras estés usando la app, ya que es el motor que la mantiene viva. Puedes minimizarla si te molesta.

---

## ⚙️ Preparación (Solo para el primer uso)

Si es la primera vez que lo instalas en un ordenador nuevo:
1.  **Instala Python**: [Descárgalo aquí](https://www.python.org/downloads/). *Recuerda marcar la casilla "Add Python to PATH" durante la instalación.*
2.  **Doble Clic**: Ejecuta `Lanzar_App.bat`. La primera vez tardará un par de minutos mientras configura todo. ¡Las siguientes veces será instantáneo!

---

## � Seguridad y Privacidad
- **Datos Locales**: Todo se guarda en `bitacora_opciones.csv`. Tus datos financieros **nunca** salen de tu ordenador.
- **Backups Automáticos**: El sistema genera copias de seguridad en la carpeta `backups_journal/` cada vez que guardas algo, protegiendo tu trabajo contra errores accidentales.

---
Desarrollado con ❤️ para la comunidad de **Opcion Sigma**. ¡Buenos trades! 📈
