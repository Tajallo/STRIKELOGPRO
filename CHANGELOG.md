# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Added
- **Timezone-Aware Option Expiration**: Improved option expiration detection by utilizing `America/New_York` timezone and confirming the U.S. market close (16:00 EST/EDT) on the expiration day (DTE 0) before showing options as expired in the pending actions banner.
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
### Fixed
- **Covered Call Assignment Logic**: Corrected the assignment logic for `"CC (Covered Call)"` strategies. Instead of creating a new `"Long Stock (Asignación)"` position when assigned, the system now correctly sells/retires the corresponding shares from the active stock inventory, closing the stock position or reducing its contract size accordingly.
- **CSP Cost Base Contributions**: Fixed an issue where CSP (Cash Secured Put) options closed/expired within a wheel campaign were excluded from the dynamic cost base calculations. Now, extra or rolled CSPs successfully reduce the stock's Break Even.
- **Always Visible Save Changes Button**: Fixed a UI issue where the "💾 Guardar Notas y Fechas" button in the Active Portfolio panel was conditionally rendered only after changes were detected. The button is now always visible at the bottom of the notes and dates section for a clearer and more intuitive experience.
- **Strategy Leg Selection**: Fixed a bug where selecting **Flyagonal** (or other custom strategies) in the trade entry form defaulted to showing only 1 leg. The form now dynamically retrieves the number of legs from the strategy's definition in `LEG_DEFAULTS` automatically.
- **Timeline Rendering**: Fixed an issue where unescaped dollar signs (`$`) in the HTML string caused Streamlit's markdown parser to render raw HTML tags (like `</span>`) as LaTeX math expressions. Replaced `$` with the safe HTML entity `&#36;`.
- **Duplicate Campaign Legs**: Grouped multi-leg strategies (like Put Debit Spreads and Put Credit Spreads) by their `ChainID` in the timeline history. This consolidates them into a single, beautifully formatted card displaying all strikes, combined PnL, and total commissions, rather than showing confusing duplicate entries.
- **Broker Commission Bug & Index Exceptions**: Added `get_fee_rate` helper function to handle broker-specific fees. Tradier now correctly defaults to `$0.65/contract` on indices (`SPX`, `NDX`, `RUT`, `VIX`, `DJX`, `XSP`) and `$0.00` on standard equities/ETFs, while IB always charges `$0.65`.
- **Streamlit Widget Session Caching**: Implemented dynamic keys for commission input fields. This fixes the issue where Streamlit's state cache prevented the commission from resetting when changing the selected broker.
- **Default Broker to Tradier**: Set **Tradier** as the pre-selected default broker when opening the application forms.

