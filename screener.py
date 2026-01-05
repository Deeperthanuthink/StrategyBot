"""
Marimo notebook for interactive stock screening.

This notebook provides an interactive interface for screening stocks
based on various options trading strategies using Finviz Elite data.
"""

import marimo

__generated_with = "0.18.4"
app = marimo.App(width="full")


@app.cell
def _():
    """Import required modules."""
    import marimo as mo
    import pandas as pd
    from datetime import datetime
    import os
    from pathlib import Path

    # Import screener components
    from screener.core.engine import ScreeningEngine
    from screener.finviz.client import FinvizClient
    from screener.storage.manager import StorageManager
    from screener.config.manager import ConfigManager
    from screener.strategies.discovery import discover_strategies
    return (
        ConfigManager,
        FinvizClient,
        ScreeningEngine,
        StorageManager,
        datetime,
        mo,
        os,
        pd,
    )


@app.cell
def _(mo):
    """Display notebook title and description."""
    mo.md("""
    # Strategy Stock Screener

    Interactive stock screening tool for options trading strategies.
    Screen stocks using Finviz Elite data and analyze them for specific trading strategies.
    """)
    return


@app.cell
def _(ConfigManager, FinvizClient, ScreeningEngine, StorageManager, os):
    """Initialize core components."""
    # Load configuration
    config_manager = ConfigManager()

    # Initialize storage manager
    storage_manager = StorageManager(
        results_dir=config_manager.get("storage.results_dir", "data/screener_results")
    )

    # Initialize Finviz client (if credentials available)
    finviz_username = os.getenv("FINVIZ_USERNAME")
    finviz_password = os.getenv("FINVIZ_PASSWORD")

    finviz_client = None
    if finviz_username and finviz_password:
        try:
            from screener.finviz.client import FinvizCredentials
            credentials = FinvizCredentials(email=finviz_username, password=finviz_password)
            finviz_client = FinvizClient(credentials=credentials)
            finviz_client.authenticate()
            finviz_status = "✓ Finviz Elite connected"
        except Exception as e:
            finviz_status = f"✗ Finviz connection failed: {str(e)}"
    else:
        finviz_status = "⚠ Finviz credentials not found in environment"

    # Initialize screening engine
    screening_engine = ScreeningEngine(finviz_client=finviz_client)
    return config_manager, finviz_client, finviz_status, screening_engine, storage_manager


@app.cell
def _(finviz_status, mo):
    """Display connection status."""
    mo.md(f"""
    **Connection Status:** {finviz_status}

    ---
    """)
    return


@app.cell
def _(screening_engine):
    """Get available strategies."""
    available_strategies = screening_engine.get_available_strategies()
    return (available_strategies,)


@app.cell
def _(available_strategies, mo):
    """Create strategy selector UI component."""
    # Create dropdown for strategy selection
    strategy_selector = mo.ui.dropdown(
        options=available_strategies,
        value=available_strategies[0] if available_strategies else None,
        label="Select Trading Strategy"
    )

    mo.md(f"""
    ## Strategy Selection

    {strategy_selector}
    """)
    return (strategy_selector,)


@app.cell
def _(config_manager, screening_engine, strategy_selector):
    """Load default filters for selected strategy."""
    if strategy_selector.value:
        strategy = screening_engine.load_strategy(strategy_selector.value)
        default_filters = strategy.default_filters

        # Try to load saved preferences
        saved_prefs = config_manager.get(f"preferences.{strategy_selector.value}")

        # Use saved preferences if available, otherwise use defaults
        if saved_prefs:
            active_filters = saved_prefs
        else:
            active_filters = default_filters
    else:
        default_filters = {}
        active_filters = {}
    return active_filters, strategy


@app.cell
def _(active_filters, mo):
    """Create filter panel UI component."""
    # Create UI elements for each filter
    filter_inputs = {}

    # Numeric filters
    if "min_market_cap" in active_filters:
        filter_inputs["min_market_cap"] = mo.ui.number(
            start=0,
            stop=1e13,
            value=active_filters.get("min_market_cap", 2_000_000_000),
            label="Min Market Cap ($)",
            step=100_000_000
        )

    if "min_volume" in active_filters:
        filter_inputs["min_volume"] = mo.ui.number(
            start=0,
            stop=1e10,
            value=active_filters.get("min_volume", 1_000_000),
            label="Min Volume (shares)",
            step=100_000
        )

    if "price_min" in active_filters:
        filter_inputs["price_min"] = mo.ui.number(
            start=0,
            stop=10000,
            value=active_filters.get("price_min", 20),
            label="Min Price ($)",
            step=5
        )

    if "price_max" in active_filters:
        filter_inputs["price_max"] = mo.ui.number(
            start=0,
            stop=10000,
            value=active_filters.get("price_max", 200),
            label="Max Price ($)",
            step=10
        )

    if "rsi_min" in active_filters:
        filter_inputs["rsi_min"] = mo.ui.slider(
            start=0,
            stop=100,
            value=active_filters.get("rsi_min", 40),
            label="Min RSI",
            step=5
        )

    if "rsi_max" in active_filters:
        filter_inputs["rsi_max"] = mo.ui.slider(
            start=0,
            stop=100,
            value=active_filters.get("rsi_max", 70),
            label="Max RSI",
            step=5
        )

    if "beta_min" in active_filters:
        filter_inputs["beta_min"] = mo.ui.number(
            start=0,
            stop=10,
            value=active_filters.get("beta_min", 0.5),
            label="Min Beta",
            step=0.1
        )

    if "beta_max" in active_filters:
        filter_inputs["beta_max"] = mo.ui.number(
            start=0,
            stop=10,
            value=active_filters.get("beta_max", 1.5),
            label="Max Beta",
            step=0.1
        )

    if "weekly_perf_min" in active_filters:
        filter_inputs["weekly_perf_min"] = mo.ui.number(
            start=-100,
            stop=100,
            value=active_filters.get("weekly_perf_min", -5),
            label="Min Weekly Performance (%)",
            step=1
        )

    if "weekly_perf_max" in active_filters:
        filter_inputs["weekly_perf_max"] = mo.ui.number(
            start=-100,
            stop=100,
            value=active_filters.get("weekly_perf_max", 10),
            label="Max Weekly Performance (%)",
            step=1
        )

    if "earnings_buffer_days" in active_filters:
        filter_inputs["earnings_buffer_days"] = mo.ui.number(
            start=0,
            stop=365,
            value=active_filters.get("earnings_buffer_days", 14),
            label="Earnings Buffer (days)",
            step=1
        )

    # Boolean filters
    if "above_sma20" in active_filters:
        filter_inputs["above_sma20"] = mo.ui.checkbox(
            value=active_filters.get("above_sma20", True),
            label="Price Above SMA20"
        )

    if "above_sma50" in active_filters:
        filter_inputs["above_sma50"] = mo.ui.checkbox(
            value=active_filters.get("above_sma50", True),
            label="Price Above SMA50"
        )

    if "optionable" in active_filters:
        filter_inputs["optionable"] = mo.ui.checkbox(
            value=active_filters.get("optionable", True),
            label="Optionable"
        )

    if "shortable" in active_filters:
        filter_inputs["shortable"] = mo.ui.checkbox(
            value=active_filters.get("shortable", True),
            label="Shortable"
        )

    # Create dictionary UI
    filter_panel = mo.ui.dictionary(filter_inputs)
    return (filter_panel,)


@app.cell
def _(filter_panel, mo):
    """Display filter panel."""
    mo.md(f"""
    ## Screening Filters

    Adjust the filters below to customize your stock screen:

    {filter_panel}
    """)
    return


@app.cell
def _(mo):
    """Create run screening button."""
    run_button = mo.ui.button(label="Run Screen", kind="success")
    save_prefs_button = mo.ui.button(label="Save Preferences", kind="neutral")

    mo.md(f"""
    ---

    {run_button} {save_prefs_button}
    """)
    return run_button, save_prefs_button


@app.cell
def _(config_manager, filter_panel, save_prefs_button, strategy_selector):
    """Save filter preferences when button is clicked."""
    save_status = ""

    if save_prefs_button.value:
        try:
            # Get current filter values
            current_filters = {k: v.value for k, v in filter_panel.value.items()}

            # Save to config
            config_manager.set(f"preferences.{strategy_selector.value}", current_filters)
            config_manager.save()

            save_status = "✓ Preferences saved successfully"
        except Exception as e:
            save_status = f"✗ Error saving preferences: {str(e)}"
    return (save_status,)


@app.cell
def _(mo, save_status):
    """Display save status."""
    if save_status:
        mo.md(f"""
        {save_status}
        """)
    return


@app.cell
def _(filter_panel, pd, run_button, screening_engine, strategy_selector, finviz_client):
    """Execute screening when button is clicked."""
    screening_results = None
    screening_error = None
    filter_values = {}

    if run_button.value:
        try:
            # Get filter values from the panel
            filter_values = {k: v.value for k, v in filter_panel.value.items()}

            # Check if Finviz client is available
            if finviz_client is None:
                screening_error = "Finviz Elite credentials not configured. Please add FINVIZ_USERNAME and FINVIZ_PASSWORD to your .env file."
            else:
                # Run the screening with Finviz client
                print(f"Running screen for strategy: {strategy_selector.value}")
                print(f"Filter values: {filter_values}")
                
                screening_results = screening_engine.screen_stocks(
                    strategy_name=strategy_selector.value,
                    filters=filter_values
                )
                
                print(f"Screening complete. Found {len(screening_results.stocks)} stocks")
        except Exception as e:
            import traceback
            screening_error = f"Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            print(f"Screening error: {screening_error}")
    
    return screening_error, screening_results, filter_values


@app.cell
def _(mo, screening_error, screening_results):
    """Create results table UI component."""
    results_table = None  # Initialize to None

    if screening_error:
        results_display = mo.md(f"""
        ## Screening Results

        **Error:** {screening_error}
        """)
    elif screening_results is not None:
        # Get the stocks DataFrame
        stocks_df = screening_results.stocks

        if len(stocks_df) == 0:
            results_display = mo.md("""
            ## Screening Results

            No stocks matched the screening criteria. Try relaxing some filters.
            """)
        else:
            # Select key columns for display
            display_columns = []
            if 'ticker' in stocks_df.columns:
                display_columns.append('ticker')
            if 'company_name' in stocks_df.columns:
                display_columns.append('company_name')
            if 'price' in stocks_df.columns:
                display_columns.append('price')
            if 'volume' in stocks_df.columns:
                display_columns.append('volume')
            if 'market_cap' in stocks_df.columns:
                display_columns.append('market_cap')
            if 'rsi' in stocks_df.columns:
                display_columns.append('rsi')
            if 'iv_rank' in stocks_df.columns:
                display_columns.append('iv_rank')
            if 'strategy_score' in stocks_df.columns:
                display_columns.append('strategy_score')

            # Create table with available columns
            if display_columns:
                display_df = stocks_df[display_columns].copy()

                # Format numeric columns
                if 'price' in display_df.columns:
                    display_df['price'] = display_df['price'].apply(lambda x: f"${x:.2f}")
                if 'market_cap' in display_df.columns:
                    display_df['market_cap'] = display_df['market_cap'].apply(
                        lambda x: f"${x/1e9:.2f}B" if x >= 1e9 else f"${x/1e6:.2f}M"
                    )
                if 'strategy_score' in display_df.columns:
                    display_df['strategy_score'] = display_df['strategy_score'].apply(lambda x: f"{x:.1f}")

                # Create table UI
                results_table = mo.ui.table(
                    display_df,
                    selection="single",
                    label=f"Found {len(stocks_df)} stocks"
                )

                results_display = mo.md(f"""
                ## Screening Results

                {results_table}
                """)
            else:
                results_display = mo.md("""
                ## Screening Results

                Results available but no displayable columns found.
                """)
    else:
        results_display = mo.md("""
        ## Screening Results

        Click "Run Screen" to see results.
        """)

    results_display
    return (results_table,)


@app.cell
def _(results_table, screening_results, strategy):
    """Get selected stock and perform detailed analysis."""
    selected_stock_data = None
    stock_analysis = None

    if results_table is not None and results_table.value is not None:
        # Get selected row indices
        selected_indices = results_table.value

        if len(selected_indices) > 0:
            # Get the first selected stock
            selected_idx = selected_indices[0]
            selected_row = screening_results.stocks.iloc[selected_idx]

            # Convert row to StockData
            from screener.core.models import StockData

            selected_stock_data = StockData(
                ticker=selected_row.get('ticker', ''),
                company_name=selected_row.get('company_name', ''),
                price=float(selected_row.get('price', 0)),
                volume=int(selected_row.get('volume', 0)),
                avg_volume=int(selected_row.get('avg_volume', 0)),
                market_cap=float(selected_row.get('market_cap', 0)),
                rsi=float(selected_row.get('rsi', 50)),
                sma20=float(selected_row.get('sma20', 0)),
                sma50=float(selected_row.get('sma50', 0)),
                sma200=float(selected_row.get('sma200', 0)),
                beta=float(selected_row.get('beta', 1.0)),
                implied_volatility=float(selected_row.get('implied_volatility', 0)),
                iv_rank=float(selected_row.get('iv_rank', 50)),
                option_volume=int(selected_row.get('option_volume', 0)),
                sector=selected_row.get('sector', ''),
                industry=selected_row.get('industry', ''),
                earnings_date=selected_row.get('earnings_date'),
                earnings_days_away=int(selected_row.get('earnings_days_away', 999)),
                perf_week=float(selected_row.get('perf_week', 0)),
                perf_month=float(selected_row.get('perf_month', 0)),
                perf_quarter=float(selected_row.get('perf_quarter', 0)),
            )

            # Perform detailed analysis
            try:
                stock_analysis = strategy.analyze_stock(selected_stock_data)
            except Exception as e:
                print(f"Error analyzing stock: {e}")
    return selected_stock_data, stock_analysis


@app.cell
def _(mo, selected_stock_data, stock_analysis):
    """Create stock detail view UI component."""
    if stock_analysis is not None and selected_stock_data is not None:
        # Format support levels
        support_levels_str = ", ".join([f"${level:.2f}" for level in stock_analysis.support_levels[:5]])

        # Format recommended strikes
        short_strike = stock_analysis.recommended_strikes.get('short', 0)
        long_strike = stock_analysis.recommended_strikes.get('long', 0)

        # Format notes
        notes_list = "\n".join([f"- {note}" for note in stock_analysis.notes])

        detail_view = mo.md(f"""
        ## Stock Detail: {selected_stock_data.ticker}

        ### {selected_stock_data.company_name}

        **Current Price:** ${selected_stock_data.price:.2f}  
        **Strategy Score:** {stock_analysis.strategy_score:.1f}/100  
        **Trade Recommendation:** {stock_analysis.trade_recommendation}

        ---

        ### Analysis Details

        **Support Levels:** {support_levels_str}

        **Recommended Strikes:**
        - Short Put: ${short_strike:.2f}
        - Long Put: ${long_strike:.2f}

        **Probability of Profit:** {stock_analysis.probability_of_profit:.1f}%

        **Premium Estimate:** ${stock_analysis.estimated_premium:.2f} per spread

        **Max Risk:** ${stock_analysis.max_risk:.2f}

        **Return on Risk:** {stock_analysis.return_on_risk:.1f}%

        **Risk Assessment:** {stock_analysis.risk_assessment}

        ---

        ### Notes

        {notes_list}
        """)
    else:
        detail_view = mo.md("""
        ## Stock Detail

        Select a stock from the results table to see detailed analysis.
        """)

    detail_view
    return


@app.cell
def _(mo, screening_results):
    """Create export controls UI component."""
    if screening_results is not None and len(screening_results.stocks) > 0:
        export_csv_button = mo.ui.button(label="Export to CSV", kind="neutral")
        export_json_button = mo.ui.button(label="Export to JSON", kind="neutral")

        export_controls = mo.md(f"""
        ---

        ## Export Results

        {export_csv_button} {export_json_button}
        """)
    else:
        export_csv_button = None
        export_json_button = None
        export_controls = mo.md("")

    export_controls
    return export_csv_button, export_json_button


@app.cell
def _(
    datetime,
    export_csv_button,
    export_json_button,
    screening_results,
    storage_manager,
):
    """Handle export button clicks."""
    export_status = ""

    if export_csv_button is not None and export_csv_button.value:
        try:
            # Generate filename with timestamp
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"screening_results_{timestamp_str}.csv"
            csv_path = f"data/screener_results/{csv_filename}"

            # Export to CSV
            storage_manager.export_to_csv(screening_results, csv_path)
            export_status = f"✓ Results exported to {csv_filename}"
        except Exception as e:
            export_status = f"✗ Error exporting to CSV: {str(e)}"

    if export_json_button is not None and export_json_button.value:
        try:
            # Generate filename with timestamp
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_filename = f"screening_results_{timestamp_str}.json"
            json_path = f"data/screener_results/{json_filename}"

            # Export to JSON
            storage_manager.export_to_json(screening_results, json_path)
            export_status = f"✓ Results exported to {json_filename}"
        except Exception as e:
            export_status = f"✗ Error exporting to JSON: {str(e)}"
    return (export_status,)


@app.cell
def _(export_status, mo):
    """Display export status."""
    if export_status:
        mo.md(f"""
        {export_status}
        """)
    return


if __name__ == "__main__":
    app.run()
