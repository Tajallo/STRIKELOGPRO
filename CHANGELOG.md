# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Added
- **Flyagonal Strategy Support**: Added native support for the 6-leg hybrid Flyagonal strategy. Includes automatic suggestion of front-month and back-month expiration dates (front-month base + 30 days default for long Put protective leg).
- **Independent Leg Expirations**: Added a checkbox `📅 Usar vencimientos independientes por pata` and a vertical vertical-form layout for multi-expiry strategies (Flyagonal, Calendar, Diagonal). Leg expirations are written individually to the `Expiry` column in the CSV.
- **Venc. Column in Portfolio Table**: Added a dedicated `Venc.` column to the Active Portfolio leg breakdown table to clearly view individual expiration dates.
- **Dynamic Broker Commissions**: Replaced hardcoded `$0.65` commissions with a dynamic system aware of the selected Broker (`IB` defaults to `$0.65/contract`, `Tradier` defaults to `$0.00`). Closing, rolling, and assignment commissions dynamically inherit broker configurations.
- **La Rueda Enhancements**: 
  - Dynamic campaign linking to trace full historical NU wheel cycles (original PCS, intermediate CSP assignment, defensive spreads, Covered Calls, and active assigned stock).
  - Total campaign commission aggregation factored into dynamic `Costo Base Real (BE)` calculation.
  - Side-by-side notes editors for active stock and covered calls.
### Fixed
- **Always Visible Save Changes Button**: Fixed a UI issue where the "💾 Guardar Notas y Fechas" button in the Active Portfolio panel was conditionally rendered only after changes were detected. The button is now always visible at the bottom of the notes and dates section for a clearer and more intuitive experience.
- **Strategy Leg Selection**: Fixed a bug where selecting **Flyagonal** (or other custom strategies) in the trade entry form defaulted to showing only 1 leg. The form now dynamically retrieves the number of legs from the strategy's definition in `LEG_DEFAULTS` automatically.
- **Timeline Rendering**: Fixed an issue where unescaped dollar signs (`$`) in the HTML string caused Streamlit's markdown parser to render raw HTML tags (like `</span>`) as LaTeX math expressions. Replaced `$` with the safe HTML entity `&#36;`.
- **Duplicate Campaign Legs**: Grouped multi-leg strategies (like Put Debit Spreads and Put Credit Spreads) by their `ChainID` in the timeline history. This consolidates them into a single, beautifully formatted card displaying all strikes, combined PnL, and total commissions, rather than showing confusing duplicate entries.
- **Broker Commission Bug & Index Exceptions**: Added `get_fee_rate` helper function to handle broker-specific fees. Tradier now correctly defaults to `$0.65/contract` on indices (`SPX`, `NDX`, `RUT`, `VIX`, `DJX`, `XSP`) and `$0.00` on standard equities/ETFs, while IB always charges `$0.65`.
- **Streamlit Widget Session Caching**: Implemented dynamic keys for commission input fields. This fixes the issue where Streamlit's state cache prevented the commission from resetting when changing the selected broker.
- **Default Broker to Tradier**: Set **Tradier** as the pre-selected default broker when opening the application forms.
