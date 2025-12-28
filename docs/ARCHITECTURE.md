# Options Trading Bot - Architecture

## System Overview

This document provides a comprehensive view of the Options Trading Bot architecture, including all components, their relationships, and data flows.

## High-Level Architecture

```mermaid
flowchart TB
    subgraph UI["User Interface Layer"]
        CLI[interactive.py<br/>Command Line Interface]
        MAIN[main.py<br/>Scheduled Execution]
        DEMO[demo.py<br/>Demo Mode]
    end

    subgraph CORE["Core Orchestration"]
        TB[TradingBot<br/>Main Orchestrator]
        SCHED[Scheduler<br/>Cron-based Execution]
    end

    subgraph CONFIG["Configuration"]
        CM[ConfigManager]
        CFG[config.json]
        MODELS[Config Models]
    end

    subgraph BROKER["Broker Abstraction Layer"]
        BF[BrokerFactory]
        BC[BaseBrokerClient<br/>Abstract Interface]
        AC[AlpacaClient]
        TC[TradierClient]
    end

    subgraph STRATEGY["Strategy Engine"]
        SC[StrategyCalculator<br/>Put Credit Spreads]
        CS[CollarStrategy<br/>Multi-Strategy Calculator]
        TCC[TieredCoveredCallCalculator]
        METF[METFStrategy<br/>0DTE EMA-based]
        CCR[CoveredCallRoller]
        CBT[CostBasisTracker]
    end

    subgraph POSITIONS["Position Management"]
        PS[PositionService]
        PM[Position Models]
        PV[Position Validation]
    end

    subgraph ORDERS["Order Management"]
        OM[OrderManager]
        OV[OrderValidator]
        TV[TradeVerification]
    end

    subgraph LOGGING["Logging & Monitoring"]
        BL[BotLogger]
        LA[LoggerAdapter]
    end

    subgraph EXTERNAL["External Services"]
        ALPACA[(Alpaca API)]
        TRADIER[(Tradier API)]
        MKT[(Market Data)]
    end

    %% UI to Core
    CLI --> TB
    MAIN --> SCHED
    SCHED --> TB
    DEMO --> TB

    %% Core to Config
    TB --> CM
    CM --> CFG
    CM --> MODELS

    %% Core to Broker
    TB --> BF
    BF --> BC
    BC --> AC
    BC --> TC

    %% Broker to External
    AC --> ALPACA
    TC --> TRADIER
    AC --> MKT
    TC --> MKT

    %% Core to Strategy
    TB --> SC
    TB --> CS
    TB --> TCC
    TB --> METF
    TB --> CCR
    CCR --> CBT

    %% Core to Positions
    TB --> PS
    PS --> PM
    PS --> PV

    %% Core to Orders
    TB --> OM
    OM --> OV
    CLI --> TV
    TV --> OM

    %% Logging
    TB --> BL
    BL --> LA

    %% Strategy to Broker
    SC --> BC
    CS --> BC
    TCC --> BC
    METF --> BC
    PS --> BC
    OM --> BC
```

## Component Details

### 1. User Interface Layer

```mermaid
flowchart LR
    subgraph Interactive["interactive.py"]
        BANNER[Display Banner]
        SELECT[Symbol Selection]
        STRAT[Strategy Selection]
        VERIFY[Trade Verification]
        EXEC[Execute Trade]
    end

    BANNER --> SELECT --> STRAT --> VERIFY --> EXEC

    subgraph Strategies["Available Strategies"]
        PCS[Put Credit Spread]
        CC[Covered Call]
        WS[Wheel Strategy]
        PC[Protected Collar]
        TCC[Tiered CC]
        METF[METF 0DTE]
        IC[Iron Condor]
        IB[Iron Butterfly]
        LS[Long Straddle]
        SS[Short Strangle]
        JL[Jade Lizard]
        BL[Big Lizard]
        DC[Double Calendar]
        BF[Butterfly]
        BWB[Broken Wing BF]
        MP[Married Put]
        LCC[Laddered CC]
    end

    STRAT --> Strategies
```

### 2. Broker Abstraction Layer

```mermaid
classDiagram
    class BaseBrokerClient {
        <<abstract>>
        +authenticate() bool
        +get_current_price(symbol) float
        +get_option_chain(symbol, expiration) List
        +get_positions() List
        +get_position(symbol) Position
        +submit_spread_order(order) OrderResult
        +submit_collar_order(...) OrderResult
        +is_market_open() bool
    }

    class AlpacaClient {
        -api_key: str
        -api_secret: str
        -paper: bool
        +authenticate() bool
        +get_current_price(symbol) float
        +submit_spread_order(order) OrderResult
    }

    class TradierClient {
        -api_token: str
        -account_id: str
        -base_url: str
        +authenticate() bool
        +get_option_chain(symbol, expiration) List
        +submit_spread_order(order) OrderResult
    }

    class BrokerFactory {
        +create_broker(type, credentials) BaseBrokerClient
    }

    BaseBrokerClient <|-- AlpacaClient
    BaseBrokerClient <|-- TradierClient
    BrokerFactory ..> BaseBrokerClient : creates
```

### 3. Strategy Engine

```mermaid
flowchart TB
    subgraph Calculators["Strategy Calculators"]
        SC[StrategyCalculator]
        
        subgraph CollarModule["collar_strategy.py"]
            COL[CollarCalculator]
            CCC[CoveredCallCalculator]
            WC[WheelCalculator]
            LCC[LadderedCCCalculator]
            DCC[DoubleCalendarCalculator]
            BFC[ButterflyCalculator]
            MPC[MarriedPutCalculator]
            LSC[LongStraddleCalculator]
            IBC[IronButterflyCalculator]
            SSC[ShortStrangleCalculator]
            ICC[IronCondorCalculator]
        end
        
        TCC[TieredCoveredCallCalculator]
        METF[METFStrategy]
        CCR[CoveredCallRoller]
    end

    subgraph Inputs["Inputs"]
        PRICE[Current Price]
        CHAIN[Option Chain]
        POS[Positions]
        CFG[Config Parameters]
    end

    subgraph Outputs["Outputs"]
        STRIKES[Strike Prices]
        EXP[Expiration Dates]
        QTY[Quantities]
        ORDERS[Order Specs]
    end

    Inputs --> Calculators --> Outputs
```

### 4. METF Strategy (0DTE)

```mermaid
flowchart TB
    subgraph METF["METF Strategy"]
        direction TB
        
        subgraph Symbols["Supported Symbols"]
            SPX[SPX/SPXW<br/>25-35pt spreads]
            SPY[SPY<br/>2-5pt spreads]
            QQQ[QQQ<br/>3-6pt spreads]
        end
        
        subgraph Signal["Signal Generation"]
            EMA20[20 EMA]
            EMA40[40 EMA]
            TREND{Trend?}
        end
        
        subgraph EntryTimes["Entry Times (EST)"]
            T1[12:30 PM]
            T2[1:00 PM]
            T3[1:30 PM]
            T4[2:00 PM]
            T5[2:30 PM]
            T6[2:45 PM]
        end
        
        subgraph Spreads["Spread Types"]
            PCS[Put Credit Spread<br/>Bullish: 20 EMA > 40 EMA]
            CCS[Call Credit Spread<br/>Bearish: 20 EMA < 40 EMA]
        end
    end

    EMA20 --> TREND
    EMA40 --> TREND
    TREND -->|Bullish| PCS
    TREND -->|Bearish| CCS
    
    EntryTimes --> Signal
```

### 5. Order Flow

```mermaid
sequenceDiagram
    participant User
    participant CLI as interactive.py
    participant TV as TradeVerification
    participant TB as TradingBot
    participant OM as OrderManager
    participant OV as OrderValidator
    participant BC as BrokerClient
    participant API as Broker API

    User->>CLI: Select Strategy
    CLI->>TB: Initialize (dry_run=true)
    TB->>TB: Calculate Orders
    TB-->>CLI: Planned Orders
    CLI->>TV: verify_planned_orders()
    TV->>User: Display Order Details
    User->>TV: Type "CONFIRM"
    TV-->>CLI: Confirmed
    CLI->>TB: Initialize (dry_run=false)
    TB->>OM: Submit Orders
    OM->>OV: Validate Orders
    OV-->>OM: Validation Result
    OM->>BC: submit_spread_order()
    BC->>API: POST /orders
    API-->>BC: Order Result
    BC-->>OM: OrderResult
    OM-->>TB: TradeResult
    TB-->>CLI: ExecutionSummary
    CLI->>User: Display Results
```

### 6. Position Management

```mermaid
classDiagram
    class PositionService {
        -broker_client: BaseBrokerClient
        -logger: BotLogger
        +get_long_positions(symbol) PositionSummary
        +get_available_shares(symbol) int
    }

    class PositionSummary {
        +symbol: str
        +total_shares: int
        +available_shares: int
        +current_price: float
        +average_cost_basis: float
        +existing_short_calls: List
        +long_options: List
    }

    class CoveredCallOrder {
        +symbol: str
        +strike: float
        +expiration: date
        +quantity: int
        +estimated_premium: float
    }

    class CostBasisTracker {
        +calculate_effective_cost_basis()
        +track_premium_collected()
    }

    PositionService --> PositionSummary
    PositionService --> CoveredCallOrder
    CostBasisTracker --> PositionSummary
```

### 7. Configuration

```mermaid
flowchart LR
    subgraph ConfigFiles["Configuration Files"]
        JSON[config.json]
        ENV[.env]
    end

    subgraph ConfigManager["ConfigManager"]
        LOAD[load_config]
        VALIDATE[validate]
    end

    subgraph Models["Config Models"]
        CFG[Config]
        ALPACA[AlpacaCredentials]
        TRADIER[TradierCredentials]
        LOG[LoggingConfig]
    end

    JSON --> LOAD
    ENV --> LOAD
    LOAD --> VALIDATE
    VALIDATE --> Models
```

## Data Flow Summary

```mermaid
flowchart TB
    subgraph Input["Input Sources"]
        USER[User Input]
        CONFIG[Configuration]
        MARKET[Market Data]
        POSITIONS[Account Positions]
    end

    subgraph Processing["Processing"]
        STRATEGY[Strategy Calculation]
        VALIDATION[Order Validation]
        VERIFICATION[User Verification]
    end

    subgraph Output["Output"]
        ORDERS[Order Submission]
        LOGS[Logging]
        RESULTS[Execution Results]
    end

    Input --> Processing --> Output
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Broker Integration | Alpaca API, Tradier API |
| Configuration | JSON, Environment Variables |
| Logging | Python logging, Custom BotLogger |
| Testing | pytest |
| CI/CD | GitHub Actions |

## File Structure

```
lumibot-trading-bot/
├── interactive.py          # Main CLI interface
├── main.py                 # Scheduled execution entry
├── demo.py                 # Demo/simulation mode
├── config/
│   └── config.json         # Trading configuration
├── src/
│   ├── bot/
│   │   └── trading_bot.py  # Main orchestrator
│   ├── brokers/
│   │   ├── base_client.py  # Abstract broker interface
│   │   ├── alpaca_client.py
│   │   ├── tradier_client.py
│   │   └── broker_factory.py
│   ├── strategy/
│   │   ├── strategy_calculator.py
│   │   ├── collar_strategy.py
│   │   ├── tiered_covered_call_strategy.py
│   │   ├── metf_strategy.py
│   │   ├── covered_call_roller.py
│   │   └── cost_basis_tracker.py
│   ├── positions/
│   │   ├── position_service.py
│   │   ├── models.py
│   │   └── validation.py
│   ├── order/
│   │   ├── order_manager.py
│   │   └── order_validator.py
│   ├── config/
│   │   ├── config_manager.py
│   │   └── models.py
│   ├── logging/
│   │   ├── bot_logger.py
│   │   └── logger_adapter.py
│   └── scheduler/
│       └── scheduler.py
├── tests/                  # Test suite
├── logs/                   # Log files
└── docs/                   # Documentati