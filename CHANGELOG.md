# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Fixed
- **Timeline Rendering**: Fixed an issue where unescaped dollar signs (`$`) in the HTML string caused Streamlit's markdown parser to render raw HTML tags (like `</span>`) as LaTeX math expressions. Replaced `$` with the safe HTML entity `&#36;`.
- **Duplicate Campaign Legs**: Grouped multi-leg strategies (like Put Debit Spreads and Put Credit Spreads) by their `ChainID` in the timeline history. This consolidates them into a single, beautifully formatted card displaying all strikes, combined PnL, and total commissions, rather than showing confusing duplicate entries.
