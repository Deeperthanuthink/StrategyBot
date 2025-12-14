"""Unit tests for CostBasisTracker."""

import pytest
import json
import tempfile
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from src.strategy.cost_basis_tracker import (
    CostBasisTracker, 
    CostBasisSummary, 
    StrategyImpact, 
    CostBasisData
)


@pytest.fixture
def temp_data_dir():
    """Create a temporary directory for test data."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = Mock()
    logger.log_info = Mock()
    logger.log_error = Mock()
    logger.log_warning = Mock()
    return logger


@pytest.fixture
def tracker(temp_data_dir, mock_logger):
    """Create a CostBasisTracker instance with temporary data directory."""
    return CostBasisTracker(data_directory=temp_data_dir, logger=mock_logger)


@pytest.fixture
def sample_strategy_impact():
    """Create a sample strategy impact for testing."""
    return StrategyImpact(
        strategy_type="initial_covered_calls",
        execution_date=date.today(),
        premium_collected=500.0,
        contracts_executed=5,
        cost_basis_reduction_per_share=1.67
    )


class TestCostBasisTracker:
    """Test cases for CostBasisTracker."""


@pytest.fixture
def tracker_with_data(temp_data_dir, mock_logger):
    """Create tracker with pre-populated data."""
    tracker = CostBasisTracker(data_directory=temp_data_dir, logger=mock_logger)
    
    # Add sample data for TLT
    tracker.calculate_strategy_impact(
        symbol="TLT",
        premium_collected=750.0,
        shares_covered=300,
        strategy_type="initial_covered_calls",
        original_cost_basis_per_share=95.50
    )
    
    return tracker


@pytest.fixture
def integration_tracker(temp_data_dir, mock_logger):
    """Create a tracker for integration testing."""
    return CostBasisTracker(data_directory=temp_data_dir, logger=mock_logger)


class TestCostBasisSummaryGeneration:
    """Test cases for cost basis summary generation."""

    def test_get_cost_basis_summary_basic(self, tracker_with_data, mock_logger):
        """Test basic cost basis summary generation."""
        summary = tracker_with_data.get_cost_basis_summary("TLT")
        
        assert summary.symbol == "TLT"
        assert summary.total_shares == 300
        assert summary.original_cost_basis_per_share == 95.50
        assert summary.total_original_cost == 95.50 * 300
        assert summary.cumulative_premium_collected == 750.0
        assert summary.effective_cost_basis_per_share == 95.50 - (750.0 / 300)
        assert summary.total_cost_basis_reduction == 750.0
        assert abs(summary.cost_basis_reduction_percentage - (750.0 / 300 / 95.50 * 100)) < 0.01
        
        mock_logger.log_info.assert_called()

    def test_get_cost_basis_summary_multiple_strategies(self, tracker_with_data, mock_logger):
        """Test cost basis summary with multiple strategy executions."""
        # Add a roll strategy
        tracker_with_data.update_cumulative_premium("TLT", 200.0, "roll", 2)
        
        summary = tracker_with_data.get_cost_basis_summary("TLT")
        
        assert summary.cumulative_premium_collected == 950.0  # 750 + 200
        assert summary.effective_cost_basis_per_share == 95.50 - (950.0 / 300)
        assert summary.total_cost_basis_reduction == 950.0

    def test_get_cost_basis_summary_symbol_not_found(self, tracker, mock_logger):
        """Test cost basis summary for non-existent symbol."""
        with pytest.raises(ValueError, match="No cost basis data found for AAPL"):
            tracker.get_cost_basis_summary("AAPL")

    def test_get_cost_basis_summary_case_insensitive(self, tracker_with_data, mock_logger):
        """Test cost basis summary with different case symbols."""
        summary_upper = tracker_with_data.get_cost_basis_summary("TLT")
        summary_lower = tracker_with_data.get_cost_basis_summary("tlt")
        summary_mixed = tracker_with_data.get_cost_basis_summary("Tlt")
        
        assert summary_upper.symbol == summary_lower.symbol == summary_mixed.symbol == "TLT"
        assert summary_upper.cumulative_premium_collected == summary_lower.cumulative_premium_collected
        assert summary_upper.effective_cost_basis_per_share == summary_lower.effective_cost_basis_per_share


class TestEffectiveCostBasisCalculations:
    """Test cases for effective cost basis calculations."""

    def test_calculate_effective_cost_basis_basic(self, tracker):
        """Test basic effective cost basis calculation."""
        effective_cost = tracker.calculate_effective_cost_basis(
            original_cost=100.0,
            premium_collected=500.0,
            shares=200
        )
        
        # Effective cost = 100.0 - (500.0 / 200) = 100.0 - 2.5 = 97.5
        assert effective_cost == 97.5

    def test_calculate_effective_cost_basis_zero_premium(self, tracker):
        """Test effective cost basis with zero premium."""
        effective_cost = tracker.calculate_effective_cost_basis(
            original_cost=50.0,
            premium_collected=0.0,
            shares=100
        )
        
        assert effective_cost == 50.0

    def test_calculate_effective_cost_basis_high_premium(self, tracker):
        """Test effective cost basis with premium exceeding original cost."""
        effective_cost = tracker.calculate_effective_cost_basis(
            original_cost=10.0,
            premium_collected=1500.0,  # $15 per share
            shares=100
        )
        
        # Should not go negative, minimum is 0.0
        assert effective_cost == 0.0

    def test_calculate_effective_cost_basis_invalid_parameters(self, tracker):
        """Test effective cost basis calculation with invalid parameters."""
        with pytest.raises(ValueError, match="Original cost must be positive"):
            tracker.calculate_effective_cost_basis(-10.0, 100.0, 100)
        
        with pytest.raises(ValueError, match="Premium collected cannot be negative"):
            tracker.calculate_effective_cost_basis(100.0, -50.0, 100)
        
        with pytest.raises(ValueError, match="Shares must be positive"):
            tracker.calculate_effective_cost_basis(100.0, 100.0, 0)


class TestCostBasisReductionPercentage:
    """Test cases for cost basis reduction percentage calculations."""

    def test_cost_basis_reduction_percentage_basic(self, tracker):
        """Test basic cost basis reduction percentage calculation."""
        # Initialize with data
        tracker.calculate_strategy_impact(
            symbol="NVDA",
            premium_collected=1000.0,
            shares_covered=100,
            original_cost_basis_per_share=200.0
        )
        
        summary = tracker.get_cost_basis_summary("NVDA")
        
        # Premium per share = 1000 / 100 = 10.0
        # Percentage = (10.0 / 200.0) * 100 = 5.0%
        assert abs(summary.cost_basis_reduction_percentage - 5.0) < 0.01

    def test_cost_basis_reduction_percentage_high_premium(self, tracker):
        """Test cost basis reduction percentage with high premium."""
        tracker.calculate_strategy_impact(
            symbol="TSLA",
            premium_collected=2500.0,
            shares_covered=100,
            original_cost_basis_per_share=250.0
        )
        
        summary = tracker.get_cost_basis_summary("TSLA")
        
        # Premium per share = 2500 / 100 = 25.0
        # Percentage = (25.0 / 250.0) * 100 = 10.0%
        assert abs(summary.cost_basis_reduction_percentage - 10.0) < 0.01

    def test_cost_basis_reduction_percentage_zero_cost_basis(self, tracker):
        """Test cost basis reduction percentage with zero original cost basis."""
        tracker.calculate_strategy_impact(
            symbol="FREE",
            premium_collected=100.0,
            shares_covered=100,
            original_cost_basis_per_share=0.01  # Very small cost basis
        )
        
        summary = tracker.get_cost_basis_summary("FREE")
        
        # Should handle very small cost basis without division by zero
        assert summary.cost_basis_reduction_percentage > 0


class TestStrategyImpactCalculation:
    """Test cases for strategy impact calculation."""

    def test_calculate_strategy_impact_new_symbol(self, tracker, mock_logger):
        """Test strategy impact calculation for new symbol."""
        impact = tracker.calculate_strategy_impact(
            symbol="AAPL",
            premium_collected=600.0,
            shares_covered=200,
            strategy_type="initial_covered_calls",
            original_cost_basis_per_share=150.0
        )
        
        assert impact.strategy_type == "initial_covered_calls"
        assert impact.execution_date == date.today()
        assert impact.premium_collected == 600.0
        assert impact.contracts_executed == 2  # 200 shares / 100
        assert impact.cost_basis_reduction_per_share == 3.0  # 600 / 200
        
        mock_logger.log_info.assert_called()

    def test_calculate_strategy_impact_existing_symbol(self, tracker):
        """Test strategy impact calculation for existing symbol."""
        # First strategy
        tracker.calculate_strategy_impact(
            symbol="TLT",
            premium_collected=400.0,
            shares_covered=200,
            original_cost_basis_per_share=95.0
        )
        
        # Second strategy (roll)
        impact = tracker.calculate_strategy_impact(
            symbol="TLT",
            premium_collected=150.0,
            shares_covered=100,
            strategy_type="roll"
        )
        
        assert impact.strategy_type == "roll"
        assert impact.premium_collected == 150.0
        assert impact.cost_basis_reduction_per_share == 1.5  # 150 / 100
        
        # Check cumulative data
        summary = tracker.get_cost_basis_summary("TLT")
        assert summary.cumulative_premium_collected == 550.0  # 400 + 150

    def test_calculate_strategy_impact_invalid_parameters(self, tracker):
        """Test strategy impact calculation with invalid parameters."""
        with pytest.raises(ValueError, match="Premium collected cannot be negative"):
            tracker.calculate_strategy_impact("AAPL", -100.0, 100, original_cost_basis_per_share=50.0)
        
        with pytest.raises(ValueError, match="Shares covered must be positive"):
            tracker.calculate_strategy_impact("AAPL", 100.0, 0, original_cost_basis_per_share=50.0)
        
        with pytest.raises(ValueError, match="Invalid strategy type"):
            tracker.calculate_strategy_impact("AAPL", 100.0, 100, "invalid_type", 50.0)
        
        with pytest.raises(ValueError, match="Original cost basis per share required"):
            tracker.calculate_strategy_impact("AAPL", 100.0, 100)

    def test_calculate_strategy_impact_invalid_cost_basis(self, tracker):
        """Test strategy impact calculation with invalid cost basis."""
        with pytest.raises(ValueError, match="Original cost basis per share must be positive"):
            tracker.calculate_strategy_impact(
                "AAPL", 100.0, 100, original_cost_basis_per_share=-10.0
            )


class TestCumulativePremiumUpdates:
    """Test cases for cumulative premium updates."""

    def test_update_cumulative_premium_basic(self, tracker):
        """Test basic cumulative premium update."""
        # Initialize symbol
        tracker.calculate_strategy_impact(
            symbol="SPY",
            premium_collected=300.0,
            shares_covered=100,
            original_cost_basis_per_share=400.0
        )
        
        # Update with additional premium
        tracker.update_cumulative_premium("SPY", 150.0, "roll", 1)
        
        summary = tracker.get_cost_basis_summary("SPY")
        assert summary.cumulative_premium_collected == 450.0  # 300 + 150
        
        # Check strategy history
        history = tracker.get_strategy_history("SPY")
        assert len(history) == 2
        assert history[1].strategy_type == "roll"
        assert history[1].premium_collected == 150.0

    def test_update_cumulative_premium_symbol_not_found(self, tracker):
        """Test cumulative premium update for non-existent symbol."""
        with pytest.raises(ValueError, match="No cost basis data found for UNKNOWN"):
            tracker.update_cumulative_premium("UNKNOWN", 100.0)

    def test_update_cumulative_premium_negative_premium(self, tracker):
        """Test cumulative premium update with negative premium."""
        # Initialize symbol
        tracker.calculate_strategy_impact(
            symbol="QQQ",
            premium_collected=200.0,
            shares_covered=100,
            original_cost_basis_per_share=300.0
        )
        
        with pytest.raises(ValueError, match="Additional premium cannot be negative"):
            tracker.update_cumulative_premium("QQQ", -50.0)


class TestStrategyHistory:
    """Test cases for strategy history tracking."""

    def test_get_strategy_history_basic(self, tracker):
        """Test basic strategy history retrieval."""
        # Add multiple strategies
        tracker.calculate_strategy_impact(
            symbol="IWM",
            premium_collected=200.0,
            shares_covered=100,
            original_cost_basis_per_share=180.0
        )
        
        tracker.update_cumulative_premium("IWM", 75.0, "roll", 1)
        tracker.update_cumulative_premium("IWM", 100.0, "roll", 1)
        
        history = tracker.get_strategy_history("IWM")
        
        assert len(history) == 3
        assert history[0].strategy_type == "initial_covered_calls"
        assert history[1].strategy_type == "roll"
        assert history[2].strategy_type == "roll"
        
        # Should be sorted by execution date
        for i in range(1, len(history)):
            assert history[i-1].execution_date <= history[i].execution_date

    def test_get_strategy_history_empty(self, tracker):
        """Test strategy history for non-existent symbol."""
        history = tracker.get_strategy_history("NONEXISTENT")
        assert history == []

    def test_get_strategy_history_case_insensitive(self, tracker):
        """Test strategy history with case insensitive symbol lookup."""
        tracker.calculate_strategy_impact(
            symbol="VTI",
            premium_collected=150.0,
            shares_covered=100,
            original_cost_basis_per_share=220.0
        )
        
        history_upper = tracker.get_strategy_history("VTI")
        history_lower = tracker.get_strategy_history("vti")
        history_mixed = tracker.get_strategy_history("Vti")
        
        assert len(history_upper) == len(history_lower) == len(history_mixed) == 1
        assert history_upper[0].premium_collected == history_lower[0].premium_collected


class TestDataValidation:
    """Test cases for data validation and error handling."""

    def test_validate_data_integrity_valid_data(self, tracker):
        """Test data integrity validation with valid data."""
        tracker.calculate_strategy_impact(
            symbol="DIA",
            premium_collected=400.0,
            shares_covered=200,
            original_cost_basis_per_share=350.0
        )
        
        tracker.update_cumulative_premium("DIA", 100.0, "roll", 1)
        
        is_valid, errors = tracker.validate_data_integrity("DIA")
        
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_data_integrity_symbol_not_found(self, tracker):
        """Test data integrity validation for non-existent symbol."""
        is_valid, errors = tracker.validate_data_integrity("MISSING")
        
        assert is_valid is False
        assert len(errors) == 1
        assert "No data found for symbol MISSING" in errors[0]

    def test_validate_data_integrity_premium_mismatch(self, tracker):
        """Test data integrity validation with premium mismatch."""
        # Initialize symbol
        tracker.calculate_strategy_impact(
            symbol="XLF",
            premium_collected=300.0,
            shares_covered=100,
            original_cost_basis_per_share=35.0
        )
        
        # Manually corrupt the cumulative premium to test validation
        data = tracker._data_cache["XLF"]
        data.cumulative_premium_collected = 500.0  # Incorrect value
        
        is_valid, errors = tracker.validate_data_integrity("XLF")
        
        assert is_valid is False
        assert any("Premium mismatch" in error for error in errors)


class TestUtilityMethods:
    """Test cases for utility methods."""

    def test_get_all_tracked_symbols(self, tracker):
        """Test getting all tracked symbols."""
        # Initially empty
        symbols = tracker.get_all_tracked_symbols()
        assert symbols == []
        
        # Add some symbols
        tracker.calculate_strategy_impact("AAPL", 100.0, 100, original_cost_basis_per_share=150.0)
        tracker.calculate_strategy_impact("MSFT", 200.0, 100, original_cost_basis_per_share=300.0)
        
        symbols = tracker.get_all_tracked_symbols()
        assert set(symbols) == {"AAPL", "MSFT"}

    def test_remove_symbol_data(self, tracker, mock_logger):
        """Test removing symbol data."""
        # Add symbol
        tracker.calculate_strategy_impact("GOOG", 500.0, 100, original_cost_basis_per_share=2500.0)
        
        # Remove symbol
        result = tracker.remove_symbol_data("GOOG")
        assert result is True
        
        # Verify removal
        symbols = tracker.get_all_tracked_symbols()
        assert "GOOG" not in symbols
        
        # Try to remove non-existent symbol
        result = tracker.remove_symbol_data("NONEXISTENT")
        assert result is False

    def test_remove_symbol_data_case_insensitive(self, tracker):
        """Test removing symbol data with case insensitive lookup."""
        tracker.calculate_strategy_impact("AMZN", 300.0, 100, original_cost_basis_per_share=3000.0)
        
        result = tracker.remove_symbol_data("amzn")
        assert result is True
        
        symbols = tracker.get_all_tracked_symbols()
        assert "AMZN" not in symbols


class TestDataSerialization:
    """Test cases for data serialization and deserialization."""

    def test_strategy_impact_serialization(self, sample_strategy_impact):
        """Test StrategyImpact serialization and deserialization."""
        # Convert to dict
        impact_dict = sample_strategy_impact.to_dict()
        
        assert impact_dict['strategy_type'] == "initial_covered_calls"
        assert impact_dict['premium_collected'] == 500.0
        assert impact_dict['contracts_executed'] == 5
        assert isinstance(impact_dict['execution_date'], str)
        
        # Convert back from dict
        restored_impact = StrategyImpact.from_dict(impact_dict)
        
        assert restored_impact.strategy_type == sample_strategy_impact.strategy_type
        assert restored_impact.premium_collected == sample_strategy_impact.premium_collected
        assert restored_impact.execution_date == sample_strategy_impact.execution_date

    def test_cost_basis_data_serialization(self, tracker):
        """Test CostBasisData serialization and deserialization."""
        # Create some data
        tracker.calculate_strategy_impact(
            symbol="TEST",
            premium_collected=250.0,
            shares_covered=100,
            original_cost_basis_per_share=100.0
        )
        
        data = tracker._data_cache["TEST"]
        
        # Convert to dict
        data_dict = data.to_dict()
        
        assert data_dict['symbol'] == "TEST"
        assert data_dict['original_cost_basis_per_share'] == 100.0
        assert data_dict['cumulative_premium_collected'] == 250.0
        assert len(data_dict['strategy_history']) == 1
        
        # Convert back from dict
        restored_data = CostBasisData.from_dict(data_dict)
        
        assert restored_data.symbol == data.symbol
        assert restored_data.original_cost_basis_per_share == data.original_cost_basis_per_share
        assert restored_data.cumulative_premium_collected == data.cumulative_premium_collected
        assert len(restored_data.strategy_history) == len(data.strategy_history)


class TestErrorHandling:
    """Test cases for error handling scenarios."""

    def test_initialization_with_invalid_directory(self, mock_logger):
        """Test initialization with invalid data directory."""
        # Test that initialization fails gracefully with invalid path
        with pytest.raises(FileNotFoundError):
            CostBasisTracker(data_directory="/invalid/path/that/cannot/be/created", logger=mock_logger)

    def test_corrupted_data_file_handling(self, temp_data_dir, mock_logger):
        """Test handling of corrupted data file."""
        # Create corrupted data file
        data_file = Path(temp_data_dir) / "cost_basis_data.json"
        with open(data_file, 'w') as f:
            f.write("invalid json content")
        
        # Should handle gracefully and start with empty cache
        tracker = CostBasisTracker(data_directory=temp_data_dir, logger=mock_logger)
        
        assert len(tracker.get_all_tracked_symbols()) == 0
        mock_logger.log_error.assert_called()

    def test_save_data_permission_error(self, tracker):
        """Test handling of permission errors during data save."""
        # First add some data without triggering save
        from src.strategy.cost_basis_tracker import CostBasisData
        tracker._data_cache["TEST"] = CostBasisData(
            symbol="TEST",
            original_cost_basis_per_share=50.0,
            total_shares=100,
            cumulative_premium_collected=100.0,
            strategy_history=[],
            last_updated=datetime.now()
        )
        
        # Mock the open function to raise PermissionError
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            # The save should fail and re-raise as RuntimeError
            with pytest.raises(RuntimeError, match="Failed to save cost basis data"):
                tracker._save_data()


class TestCostBasisIntegration:
    """Integration test cases for cost basis tracking across multiple strategy executions."""

    def test_end_to_end_cost_basis_tracking_single_symbol(self, integration_tracker):
        """Test end-to-end cost basis tracking with multiple strategy executions for single symbol."""
        symbol = "TLT"
        original_cost_basis = 95.50
        total_shares = 300
        
        # Step 1: Initial covered call strategy
        impact1 = integration_tracker.calculate_strategy_impact(
            symbol=symbol,
            premium_collected=750.0,  # $2.50 per share
            shares_covered=total_shares,
            strategy_type="initial_covered_calls",
            original_cost_basis_per_share=original_cost_basis
        )
        
        # Verify initial impact
        assert impact1.premium_collected == 750.0
        assert impact1.cost_basis_reduction_per_share == 2.50
        
        summary1 = integration_tracker.get_cost_basis_summary(symbol)
        assert summary1.cumulative_premium_collected == 750.0
        assert abs(summary1.effective_cost_basis_per_share - 93.0) < 0.01  # 95.50 - 2.50
        
        # Step 2: First roll
        integration_tracker.update_cumulative_premium(symbol, 200.0, "roll", 2)
        
        summary2 = integration_tracker.get_cost_basis_summary(symbol)
        assert summary2.cumulative_premium_collected == 950.0
        assert abs(summary2.effective_cost_basis_per_share - 92.33) < 0.01  # 95.50 - (950/300)
        
        # Step 3: Second roll
        integration_tracker.update_cumulative_premium(symbol, 150.0, "roll", 1)
        
        summary3 = integration_tracker.get_cost_basis_summary(symbol)
        assert summary3.cumulative_premium_collected == 1100.0
        assert abs(summary3.effective_cost_basis_per_share - 91.83) < 0.01  # 95.50 - (1100/300)
        
        # Step 4: Verify strategy history
        history = integration_tracker.get_strategy_history(symbol)
        assert len(history) == 3
        assert history[0].strategy_type == "initial_covered_calls"
        assert history[1].strategy_type == "roll"
        assert history[2].strategy_type == "roll"
        
        # Step 5: Verify total cost basis reduction
        total_reduction = sum(impact.premium_collected for impact in history)
        assert total_reduction == 1100.0
        
        # Step 6: Verify cost basis reduction percentage
        expected_percentage = (1100.0 / 300) / 95.50 * 100  # ~3.83%
        assert abs(summary3.cost_basis_reduction_percentage - expected_percentage) < 0.01

    def test_end_to_end_cost_basis_tracking_multiple_symbols(self, integration_tracker):
        """Test end-to-end cost basis tracking with multiple symbols."""
        # Symbol 1: TLT
        integration_tracker.calculate_strategy_impact(
            symbol="TLT",
            premium_collected=600.0,
            shares_covered=200,
            original_cost_basis_per_share=95.0
        )
        
        # Symbol 2: SPY
        integration_tracker.calculate_strategy_impact(
            symbol="SPY",
            premium_collected=800.0,
            shares_covered=100,
            original_cost_basis_per_share=400.0
        )
        
        # Symbol 3: QQQ
        integration_tracker.calculate_strategy_impact(
            symbol="QQQ",
            premium_collected=1200.0,
            shares_covered=300,
            original_cost_basis_per_share=350.0
        )
        
        # Verify all symbols are tracked
        tracked_symbols = integration_tracker.get_all_tracked_symbols()
        assert set(tracked_symbols) == {"TLT", "SPY", "QQQ"}
        
        # Verify individual summaries
        tlt_summary = integration_tracker.get_cost_basis_summary("TLT")
        assert tlt_summary.cumulative_premium_collected == 600.0
        assert abs(tlt_summary.effective_cost_basis_per_share - 92.0) < 0.01  # 95.0 - 3.0
        
        spy_summary = integration_tracker.get_cost_basis_summary("SPY")
        assert spy_summary.cumulative_premium_collected == 800.0
        assert abs(spy_summary.effective_cost_basis_per_share - 392.0) < 0.01  # 400.0 - 8.0
        
        qqq_summary = integration_tracker.get_cost_basis_summary("QQQ")
        assert qqq_summary.cumulative_premium_collected == 1200.0
        assert abs(qqq_summary.effective_cost_basis_per_share - 346.0) < 0.01  # 350.0 - 4.0
        
        # Add rolls to each symbol
        integration_tracker.update_cumulative_premium("TLT", 100.0, "roll", 1)
        integration_tracker.update_cumulative_premium("SPY", 200.0, "roll", 1)
        integration_tracker.update_cumulative_premium("QQQ", 300.0, "roll", 2)
        
        # Verify updated summaries
        tlt_summary_updated = integration_tracker.get_cost_basis_summary("TLT")
        assert tlt_summary_updated.cumulative_premium_collected == 700.0
        
        spy_summary_updated = integration_tracker.get_cost_basis_summary("SPY")
        assert spy_summary_updated.cumulative_premium_collected == 1000.0
        
        qqq_summary_updated = integration_tracker.get_cost_basis_summary("QQQ")
        assert qqq_summary_updated.cumulative_premium_collected == 1500.0

    def test_cost_basis_persistence_across_restarts(self, temp_data_dir, mock_logger):
        """Test cost basis persistence across application restarts."""
        # Create first tracker instance
        tracker1 = CostBasisTracker(data_directory=temp_data_dir, logger=mock_logger)
        
        # Add data
        tracker1.calculate_strategy_impact(
            symbol="NVDA",
            premium_collected=1500.0,
            shares_covered=100,
            original_cost_basis_per_share=500.0
        )
        
        tracker1.update_cumulative_premium("NVDA", 300.0, "roll", 1)
        
        # Get summary from first instance
        summary1 = tracker1.get_cost_basis_summary("NVDA")
        history1 = tracker1.get_strategy_history("NVDA")
        
        # Create second tracker instance (simulating restart)
        tracker2 = CostBasisTracker(data_directory=temp_data_dir, logger=mock_logger)
        
        # Verify data persistence
        summary2 = tracker2.get_cost_basis_summary("NVDA")
        history2 = tracker2.get_strategy_history("NVDA")
        
        assert summary1.cumulative_premium_collected == summary2.cumulative_premium_collected
        assert summary1.effective_cost_basis_per_share == summary2.effective_cost_basis_per_share
        assert len(history1) == len(history2)
        assert history1[0].premium_collected == history2[0].premium_collected
        assert history1[1].premium_collected == history2[1].premium_collected
        
        # Add more data to second instance
        tracker2.update_cumulative_premium("NVDA", 200.0, "roll", 1)
        
        # Create third tracker instance
        tracker3 = CostBasisTracker(data_directory=temp_data_dir, logger=mock_logger)
        
        # Verify all data is still there
        summary3 = tracker3.get_cost_basis_summary("NVDA")
        history3 = tracker3.get_strategy_history("NVDA")
        
        assert summary3.cumulative_premium_collected == 2000.0  # 1500 + 300 + 200
        assert len(history3) == 3

    def test_cost_basis_tracking_with_initial_and_roll_strategies(self, integration_tracker):
        """Test cost basis tracking with both initial strategies and rolls."""
        symbol = "AAPL"
        
        # Initial covered call strategy
        initial_impact = integration_tracker.calculate_strategy_impact(
            symbol=symbol,
            premium_collected=900.0,
            shares_covered=300,
            strategy_type="initial_covered_calls",
            original_cost_basis_per_share=180.0
        )
        
        assert initial_impact.strategy_type == "initial_covered_calls"
        assert initial_impact.cost_basis_reduction_per_share == 3.0  # 900 / 300
        
        # Multiple rolls
        roll_premiums = [150.0, 200.0, 175.0, 225.0]
        for i, premium in enumerate(roll_premiums):
            integration_tracker.update_cumulative_premium(symbol, premium, "roll", 1)
        
        # Verify final state
        final_summary = integration_tracker.get_cost_basis_summary(symbol)
        total_expected_premium = 900.0 + sum(roll_premiums)  # 1650.0
        
        assert final_summary.cumulative_premium_collected == total_expected_premium
        assert abs(final_summary.effective_cost_basis_per_share - 174.5) < 0.01  # 180.0 - (1650/300)
        
        # Verify strategy history
        history = integration_tracker.get_strategy_history(symbol)
        assert len(history) == 5  # 1 initial + 4 rolls
        assert history[0].strategy_type == "initial_covered_calls"
        assert all(h.strategy_type == "roll" for h in history[1:])
        
        # Verify cumulative premium calculation
        calculated_total = sum(h.premium_collected for h in history)
        assert calculated_total == total_expected_premium

    def test_tlt_ticker_specific_scenarios(self, integration_tracker):
        """Test specific scenarios using TLT ticker as specified in requirements."""
        symbol = "TLT"
        original_cost = 96.25  # Realistic TLT cost basis
        shares = 500  # 5 contracts worth
        
        # Scenario 1: Initial covered call strategy on TLT
        integration_tracker.calculate_strategy_impact(
            symbol=symbol,
            premium_collected=625.0,  # $1.25 per share premium
            shares_covered=shares,
            strategy_type="initial_covered_calls",
            original_cost_basis_per_share=original_cost
        )
        
        initial_summary = integration_tracker.get_cost_basis_summary(symbol)
        assert initial_summary.original_cost_basis_per_share == original_cost
        assert initial_summary.cumulative_premium_collected == 625.0
        assert abs(initial_summary.effective_cost_basis_per_share - 95.0) < 0.01  # 96.25 - 1.25
        
        # Scenario 2: TLT calls expire ITM, need to roll
        roll_credit = 187.5  # $0.375 per share credit for roll
        integration_tracker.update_cumulative_premium(symbol, roll_credit, "roll", 3)
        
        roll_summary = integration_tracker.get_cost_basis_summary(symbol)
        assert roll_summary.cumulative_premium_collected == 812.5  # 625 + 187.5
        expected_effective_cost = original_cost - (812.5 / shares)  # 96.25 - 1.625 = 94.625
        assert abs(roll_summary.effective_cost_basis_per_share - expected_effective_cost) < 0.01
        
        # Scenario 3: Multiple rolls throughout the year
        quarterly_rolls = [125.0, 150.0, 175.0, 200.0]  # Varying roll credits
        for roll_premium in quarterly_rolls:
            integration_tracker.update_cumulative_premium(symbol, roll_premium, "roll", 2)
        
        final_summary = integration_tracker.get_cost_basis_summary(symbol)
        total_premium = 625.0 + 187.5 + sum(quarterly_rolls)  # 1462.5
        assert final_summary.cumulative_premium_collected == total_premium
        
        # Calculate expected final effective cost basis
        expected_final_cost = original_cost - (total_premium / shares)  # 96.25 - 2.925 = 93.325
        assert abs(final_summary.effective_cost_basis_per_share - expected_final_cost) < 0.01
        
        # Verify cost basis reduction percentage
        expected_percentage = (total_premium / shares) / original_cost * 100  # ~3.04%
        assert abs(final_summary.cost_basis_reduction_percentage - expected_percentage) < 0.01
        
        # Scenario 4: Verify strategy history for TLT
        tlt_history = integration_tracker.get_strategy_history(symbol)
        assert len(tlt_history) == 6  # 1 initial + 1 first roll + 4 quarterly rolls
        assert tlt_history[0].strategy_type == "initial_covered_calls"
        assert all(h.strategy_type == "roll" for h in tlt_history[1:])
        
        # Verify data integrity
        is_valid, errors = integration_tracker.validate_data_integrity(symbol)
        assert is_valid is True
        assert len(errors) == 0

    def test_high_volume_cost_basis_tracking(self, integration_tracker):
        """Test cost basis tracking with high volume of transactions."""
        symbol = "SPY"
        original_cost = 450.0
        shares = 1000  # 10 contracts
        
        # Initial strategy
        integration_tracker.calculate_strategy_impact(
            symbol=symbol,
            premium_collected=2000.0,  # $2.00 per share
            shares_covered=shares,
            original_cost_basis_per_share=original_cost
        )
        
        # Simulate many roll transactions (e.g., weekly rolls)
        weekly_rolls = []
        for week in range(52):  # One year of weekly rolls
            premium = 50.0 + (week % 10) * 5  # Varying premiums 50-95
            weekly_rolls.append(premium)
            integration_tracker.update_cumulative_premium(symbol, premium, "roll", 2)
        
        # Verify final state
        final_summary = integration_tracker.get_cost_basis_summary(symbol)
        total_expected = 2000.0 + sum(weekly_rolls)
        
        assert final_summary.cumulative_premium_collected == total_expected
        
        # Verify effective cost basis calculation
        expected_effective_cost = original_cost - (total_expected / shares)
        assert abs(final_summary.effective_cost_basis_per_share - expected_effective_cost) < 0.01
        
        # Verify strategy history
        history = integration_tracker.get_strategy_history(symbol)
        assert len(history) == 53  # 1 initial + 52 rolls
        
        # Verify data integrity with large dataset
        is_valid, errors = integration_tracker.validate_data_integrity(symbol)
        assert is_valid is True
        assert len(errors) == 0

    def test_backup_and_restore_functionality(self, integration_tracker, temp_data_dir):
        """Test backup and restore functionality for cost basis data."""
        # Add test data
        symbols_data = [
            ("AAPL", 150.0, 200, 400.0),
            ("MSFT", 300.0, 100, 600.0),
            ("GOOGL", 2500.0, 50, 1000.0)
        ]
        
        for symbol, cost_basis, shares, premium in symbols_data:
            integration_tracker.calculate_strategy_impact(
                symbol=symbol,
                premium_collected=premium,
                shares_covered=shares,
                original_cost_basis_per_share=cost_basis
            )
        
        # Create backup
        backup_path = integration_tracker.backup_data()
        assert Path(backup_path).exists()
        
        # Verify backup content
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)
        
        assert 'backup_timestamp' in backup_data
        assert 'symbols' in backup_data
        assert len(backup_data['symbols']) == 3
        assert set(backup_data['symbols'].keys()) == {"AAPL", "MSFT", "GOOGL"}
        
        # Modify original data
        integration_tracker.update_cumulative_premium("AAPL", 100.0, "roll", 1)
        integration_tracker.remove_symbol_data("MSFT")
        
        # Verify changes
        assert "MSFT" not in integration_tracker.get_all_tracked_symbols()
        aapl_summary = integration_tracker.get_cost_basis_summary("AAPL")
        assert aapl_summary.cumulative_premium_collected == 500.0  # 400 + 100
        
        # Restore from backup (replace mode)
        integration_tracker.restore_from_backup(backup_path, merge=False)
        
        # Verify restoration
        restored_symbols = integration_tracker.get_all_tracked_symbols()
        assert set(restored_symbols) == {"AAPL", "MSFT", "GOOGL"}
        
        # Verify AAPL data was restored to original state
        aapl_summary_restored = integration_tracker.get_cost_basis_summary("AAPL")
        assert aapl_summary_restored.cumulative_premium_collected == 400.0  # Original value
        
        # Verify MSFT was restored
        msft_summary = integration_tracker.get_cost_basis_summary("MSFT")
        assert msft_summary.cumulative_premium_collected == 600.0

    def test_merge_backup_functionality(self, integration_tracker, temp_data_dir):
        """Test backup merge functionality."""
        # Add initial data
        integration_tracker.calculate_strategy_impact(
            symbol="TSLA",
            premium_collected=800.0,
            shares_covered=100,
            original_cost_basis_per_share=250.0
        )
        
        # Create backup
        backup_path = integration_tracker.backup_data()
        
        # Add new data after backup
        integration_tracker.calculate_strategy_impact(
            symbol="NVDA",
            premium_collected=1200.0,
            shares_covered=100,
            original_cost_basis_per_share=500.0
        )
        
        integration_tracker.update_cumulative_premium("TSLA", 150.0, "roll", 1)
        
        # Clear all data
        integration_tracker.remove_symbol_data("TSLA")
        integration_tracker.remove_symbol_data("NVDA")
        
        # Add different data
        integration_tracker.calculate_strategy_impact(
            symbol="AMD",
            premium_collected=300.0,
            shares_covered=100,
            original_cost_basis_per_share=120.0
        )
        
        # Restore with merge
        integration_tracker.restore_from_backup(backup_path, merge=True)
        
        # Verify merge results
        symbols = integration_tracker.get_all_tracked_symbols()
        assert set(symbols) == {"TSLA", "AMD"}  # TSLA from backup, AMD from current
        
        # Verify TSLA was restored to backup state (without the roll)
        tsla_summary = integration_tracker.get_cost_basis_summary("TSLA")
        assert tsla_summary.cumulative_premium_collected == 800.0  # Original backup value
        
        # Verify AMD data was preserved
        amd_summary = integration_tracker.get_cost_basis_summary("AMD")
        assert amd_summary.cumulative_premium_collected == 300.0


class TestCostBasisEdgeCases:
    """Test cases for edge cases and boundary conditions."""

    def test_very_small_premium_amounts(self, tracker):
        """Test cost basis tracking with very small premium amounts."""
        tracker.calculate_strategy_impact(
            symbol="PENNY",
            premium_collected=0.01,  # 1 cent total
            shares_covered=100,
            original_cost_basis_per_share=0.50
        )
        
        summary = tracker.get_cost_basis_summary("PENNY")
        assert summary.cumulative_premium_collected == 0.01
        assert abs(summary.effective_cost_basis_per_share - 0.4999) < 0.0001  # 0.50 - 0.0001
        assert summary.cost_basis_reduction_percentage > 0

    def test_very_large_premium_amounts(self, tracker):
        """Test cost basis tracking with very large premium amounts."""
        tracker.calculate_strategy_impact(
            symbol="EXPENSIVE",
            premium_collected=50000.0,  # $500 per share
            shares_covered=100,
            original_cost_basis_per_share=1000.0
        )
        
        summary = tracker.get_cost_basis_summary("EXPENSIVE")
        assert summary.cumulative_premium_collected == 50000.0
        assert abs(summary.effective_cost_basis_per_share - 500.0) < 0.01  # 1000 - 500
        assert abs(summary.cost_basis_reduction_percentage - 50.0) < 0.01

    def test_premium_exceeding_cost_basis(self, tracker):
        """Test cost basis tracking when premium exceeds original cost basis."""
        tracker.calculate_strategy_impact(
            symbol="PROFITABLE",
            premium_collected=2000.0,  # $20 per share
            shares_covered=100,
            original_cost_basis_per_share=15.0
        )
        
        summary = tracker.get_cost_basis_summary("PROFITABLE")
        assert summary.cumulative_premium_collected == 2000.0
        assert summary.effective_cost_basis_per_share == 0.0  # Should not go negative
        assert summary.cost_basis_reduction_percentage > 100.0

    def test_single_share_calculations(self, tracker):
        """Test cost basis calculations with single share (edge case)."""
        # Note: This is unrealistic for covered calls but tests the math
        tracker.calculate_strategy_impact(
            symbol="SINGLE",
            premium_collected=5.0,
            shares_covered=1,
            original_cost_basis_per_share=100.0
        )
        
        summary = tracker.get_cost_basis_summary("SINGLE")
        assert summary.total_shares == 1
        assert summary.cumulative_premium_collected == 5.0
        assert abs(summary.effective_cost_basis_per_share - 95.0) < 0.01
        assert abs(summary.cost_basis_reduction_percentage - 5.0) < 0.01

    def test_zero_premium_strategy(self, tracker):
        """Test cost basis tracking with zero premium (break-even strategy)."""
        tracker.calculate_strategy_impact(
            symbol="BREAKEVEN",
            premium_collected=0.0,
            shares_covered=100,
            original_cost_basis_per_share=50.0
        )
        
        summary = tracker.get_cost_basis_summary("BREAKEVEN")
        assert summary.cumulative_premium_collected == 0.0
        assert summary.effective_cost_basis_per_share == 50.0
        assert summary.cost_basis_reduction_percentage == 0.0

    def test_fractional_shares_handling(self, tracker):
        """Test cost basis calculations with fractional share scenarios."""
        # Test with shares that don't divide evenly into contracts
        tracker.calculate_strategy_impact(
            symbol="FRACTIONAL",
            premium_collected=333.33,  # Odd premium amount
            shares_covered=150,  # 1.5 contracts worth
            original_cost_basis_per_share=75.75
        )
        
        summary = tracker.get_cost_basis_summary("FRACTIONAL")
        assert summary.cumulative_premium_collected == 333.33
        expected_effective_cost = 75.75 - (333.33 / 150)  # 75.75 - 2.2222 = 73.5278
        assert abs(summary.effective_cost_basis_per_share - expected_effective_cost) < 0.01