# 🚀 STRIKELOG Pro

**STRIKELOG Pro** es una bitácora profesional de trading de opciones diseñada para traders que buscan un control exhaustivo de su operativa, análisis de riesgo avanzado y visualización de datos en tiempo real. Construida con **Streamlit** y **Plotly**, ofrece una interfaz limpia, moderna e interactiva.

---

## ✨ Características Principales

### 📊 Dashboard Ejecutivo Interactivo
- **Métricas Clave (KPIs)**: PnL Realizado, Win Rate, Profit Factor, Buying Power en uso y % de Asignaciones.
- **Gráficos Plotly**: Curva de equidad acumulada, distribución de Win/Loss y rendimiento por Ticker/Estrategia.
- **Filtros Avanzados**: Filtra todo tu historial por periodos de tiempo (Mes, Año, Personalizado) o por Tickers específicos.

### 📂 Gestión de Cartera Activa
- **Seguimiento de DTE**: Indicadores visuales de color según los días restantes para el vencimiento (🟢 Seguro, 🟠 Atención, 🔴 Peligro).
- **Cálculo de ROI sobre Capital**: Visualiza el rendimiento potencial de cada operación respecto al capital retenido (Buying Power).
- **Acciones Rápidas**: Cierra posiciones o ejecuta **Rolls (Roleos)** con un solo clic, manteniendo la trazabilidad de la cadena de opciones.

### ➕ Registro de Operaciones Profesional
- **Soporte Credit/Debit**: Manejo automático de estrategias de crédito (ventas) y débito (compras).
- **POP Automático**: Cálculo de la Probabilidad de Ganancia (POP) basado en el **Delta** de la operación.
- **Amplio catálogo de estrategias**: CSP, Covered Calls, Spreads, Iron Condors, Straddles, Strangles, Butterflies y más.

### 🛠️ Herramientas de Datos
- **Edición y Eliminación**: Control total sobre tus datos históricos.
- **Backups Automáticos**: El sistema crea una copia de seguridad cada vez que guardas cambios.
- **Exportación**: Descarga toda tu bitácora en formato CSV en cualquier momento.

---

## 🛠️ Instalación y Uso

### Requisitos Previos
- Python 3.8 o superior
- Pip (gestor de paquetes de Python)

### Instalación
1. Clona este repositorio:
   ```bash
   git clone https://github.com/Tajallo/STRIKELOGPRO.git
   cd STRIKELOGPRO
   ```

2. Instala las dependencias necesarias:
   ```bash
   pip install streamlit pandas plotly
   ```

### Ejecución
Para iniciar la aplicación, ejecuta el siguiente comando en tu terminal:
```bash
streamlit run STRIKELOG.py
```

---

## 🔒 Privacidad y Seguridad
El proyecto incluye un archivo `.gitignore` preconfigurado para asegurar que tus datos reales (`bitacora_opciones.csv`) y tus copias de seguridad locales **nunca** se suban a repositorios públicos. Tu información financiera permanece local y privada.

---

## 📈 Roadmap / Próximas Mejoras
- [ ] Integración con APIs de brokers para importación automática.
- [ ] Calculadora de gestión de riesgo integrada.
- [ ] Diario psicológico con etiquetas de estado emocional.

---
Desarrollado con ❤️ para la comunidad de trading de opciones.
