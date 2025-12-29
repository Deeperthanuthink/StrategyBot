# Implementation Plan

- [x] 1. Create TradingCalendar utility module
  - Create `src/utils/__init__.py` if it doesn't exist
  - Create `src/utils/trading_calendar.py` with TradingCalendar class
  - Implement `__init__` method accepting Tradier API credentials
  - Implement `get_market_calendar()` method to call Tradier `/v1/markets/calendar` endpoint
  - Implement `is_trading_day()` method that queries API and checks status
  - Implement `get_next_trading_day()` method to find next open market day
  - Implement `get_0dte_expiration()` method that returns today if trading day, else next trading day
  - Add fallback logic for when API is unavailable (weekend check + static holidays)
  - Add caching to minimize API calls (cache per month)
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4, 5.1, 5.2, 5.3_

- [x] 2. Integrate TradingCalendar into trading_bot.py
  - [x] 2.1 Update process_metf_symbol() to use TradingCalendar
    - Import TradingCalendar from src.utils.trading_calendar
    - Create TradingCalendar instance using Tradier credentials from config
    - Replace `expiration = date.today()` with `calendar.get_0dte_expiration()`
    - Add logging when expiration is adjusted to next trading day
    - _Requirements: 3.1, 3.2, 3.3, 4.1_

- [x] 3. Integrate TradingCalendar into interactive.py
  - [x] 3.1 Update METF strategy section to use TradingCalendar
    - Import TradingCalendar from src.utils.trading_calendar
    - Create TradingCalendar instance using credentials from trading_bot.config
    - Replace `expiration = date.today()` with `calendar.get_0dte_expiration()`
    - Display user-friendly message when expiration is adjusted
    - Update planned order display to show adjusted expiration with note
    - _Requirements: 3.1, 3.2, 4.2, 4.3_

- [x] 4. Write unit tests for TradingCalendar
  - [ ]* 4.1 Create test file `tests/test_trading_calendar.py`
    - Test `is_trading_day()` returns False for weekends
    - Test `is_trading_day()` returns True for weekdays (mocked API)
    - Test `is_trading_day()` returns False for holidays (mocked API response)
    - Test `get_next_trading_day()` from Saturday returns Monday
    - Test `get_next_trading_day()` from Sunday returns Monday
    - Test `get_next_trading_day()` handles holiday Monday correctly
    - Test `get_0dte_expiration()` returns today on trading day
    - Test `get_0dte_expiration()` returns next trading day on weekend
    - Test fallback behavior when API unavailable
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4_
