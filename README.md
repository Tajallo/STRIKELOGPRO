# 🚀 STRIKELOG Pro | Opcion Sigma Edition

**STRIKELOG Pro** es una bitácora de trading de opciones de nivel profesional, optimizada para la comunidad de **Opcion Sigma**. Esta herramienta no solo registra tus operaciones, sino que te ayuda a gestionar el riesgo, entender tus estadísticas y mantener el control total sobre tus estrategias complejas.

---

## 🧭 Tour por las Pantallas

### 📊 1. Dashboard (Tu Centro de Mando)
Es la primera pantalla que verás, diseñada para darte una visión clara de tu salud financiera y rendimiento operativo:
- **KPIs de Rendimiento**: PnL Realizado, Win Rate, Profit Factor y Captura Media.
- **📈 Curva de Equidad**: Gráfico interactivo que muestra el crecimiento real de tu capital.
- **📅 Filtros de Élite**:
    - **Control 0DTE**: Filtra instantáneamente para ver solo tus operaciones intradía o excluirlas para ver tu rendimiento swing.
    - **Exclusión de Tickers**: Quita tickers específicos (ej. SPX) para analizar el resto de tu cartera sin ruido.
    - **Setups y Periodos**: Analiza tu eficacia por estrategia o por motivo de entrada.

### ➕ 2. Nueva Operación (Registro Inteligente)
- **Formulario Adaptable**: Detección automática de patas según la estrategia (Iron Condor, Butterfly, Spreads).
- **Asistente Técnico**: Sugerencias automáticas de **Break Even** y **POP (Probabilidad de Éxito)** según el Delta.
- **Fix Decimal Colector**: Olvida los errores de teclado; si pulsas la coma `,` el sistema la convierte automáticamente a punto `.` para que Streamlit la procese correctamente.

### 📂 3. Cartera Activa (Gestión de Riesgo)
- **🚨 Semáforo DTE**: Alertas visuales críticas según la cercanía al vencimiento (Rojo < 7 días, Amarillo 7-21, Verde > 21).
- **🔄 Gestión de Roles (Roll)**: Rastreo completo de la "cadena de rolls". Puedes ver cuánta prima neta has acumulado desde el origen del trade y cómo ha evolucionado tu Break Even.
- **🎯 Paneles de Gestión**: Formulario unificado para Cierre, Roll o Asignación con botones de **Cancelar** para evitar errores accidentales.

### 📜 4. Historial Agrupado (La Bitácora Definitiva)
- **Vista de Estrategia**: En lugar de filas sueltas, verás cada operación agrupada (ej: tu Iron Condor aparece como un único bloque expandible).
- **Desglose de Patas**: Al expandir, ves exactamente qué pasó con cada pata, su strike, delta y PnL individual.
- **Filtros Avanzados**: Busca por etiquetas (Tags), rango de PnL exacto, resultado (Ganadoras/Perdedoras) o estado final (Cerrada, Rolada, Asignada).

---

## 🛠️ Innovaciones Técnicas Recientes
- **Contabilidad de Precisión**: Consolidación de prima y Buying Power en la "pata principal" para cálculos exactos de % de captura en estrategias multi-pata.
- **Migración Automática**: El sistema limpia y normaliza tu base de datos cada vez que arranca para asegurar que no hay inconsistencias.
- **Modo Intradía**: Soporte nativo para traders de 0DTE con detección automática por fecha de vencimiento.

---

### 🚀 ¿Qué hace el archivo "Lanzar_App.bat"?

Para que no tengas que usar códigos complicados, he creado el archivo **`Lanzar_App.bat`**. Al hacer doble clic:

1.  **Crea una "cápsula" (entorno virtual)**: Mantiene el programa aislado y estable.
2.  **Instala librerías**: Baja automáticamente *Streamlit, Pandas, Plotly* y lo necesario.
3.  **Inicia la App**: Lanza la interfaz profesional en tu navegador favorito.

> **Nota**: Verás una ventana negra (consola). **Minimízala pero no la cierres** mientras usas la app.

---

## ⚙️ Preparación (Solo primer uso)
1.  **Instala Python**: [Descárgalo aquí](https://www.python.org/downloads/). *Marca la casilla "Add Python to PATH".*
2.  **Doble Clic**: Ejecuta `Lanzar_App.bat`. La primera vez tardará un poco en configurar, luego será instantáneo.

---

## 🛡️ Seguridad y Privacidad
- **Datos 100% Locales**: Todo vive en `bitacora_opciones.csv` dentro de tu carpeta. Nada sube a la nube.
- **Backups Blindados**: Copias de seguridad automáticas con marca de tiempo en `backups/` cada vez que guardas cambios.

---
Desarrollado con ❤️ para la comunidad de **Opcion Sigma**. ¡Buenos trades! 📈
