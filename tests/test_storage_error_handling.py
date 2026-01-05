"""Unit tests for storage error handling.

Tests write failure recovery and read failure fallback.
Requirements: 6.6
"""

import tempfile
import shutil
import os
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open, MagicMock
import pytest
import pandas as pd
import json

from screener.core.models import ScreenerResults
from screener.storage import StorageManager, StorageError


def test_save_json_retries_on_io_error():
    """
    Test that save operations retry on IO errors.
    
    Requirements: 6.6
    """
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir, max_retries=2)
        
        results = ScreenerResults(
            timestamp=datetime.now(),
            strategy='pcs',
            filters={'min_volume': 1000000},
            stocks=pd.DataFrame({'ticker': ['AAPL'], 'price': [150.0]}),
            metadata={}
        )
        
        # Mock open to fail twice then succeed
        call_count = {'count': 0}
        original_open = open
        
        def mock_open_func(*args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] <= 2:
                raise IOError("Simulated IO error")
            return original_open(*args, **kwargs)
        
        with patch('builtins.open', side_effect=mock_open_func):
            # This should succeed after retries
            result_id = storage.save_results(results, 'pcs')
        
        # Verify the result was eventually saved
        assert result_id is not None
        
    finally:
        shutil.rmtree(temp_storage_dir)


def test_save_json_raises_error_after_max_retries():
    """
    Test that save operations raise StorageError after max retries.
    
    Requirements: 6.6
    """
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir, max_retries=1)
        
        results = ScreenerResults(
            timestamp=datetime.now(),
            strategy='pcs',
            filters={'min_volume': 1000000},
            stocks=pd.DataFrame({'ticker': ['AAPL'], 'price': [150.0]}),
            metadata={}
        )
        
        # Mock open to always fail
        with patch('builtins.open', side_effect=IOError("Persistent IO error")):
            with pytest.raises(StorageError) as exc_info:
                storage.save_results(results, 'pcs')
            
            assert "Failed to save JSON" in str(exc_info.value)
            assert "attempts" in str(exc_info.value)
        
    finally:
        shutil.rmtree(temp_storage_dir)


def test_load_results_retries_on_io_error():
    """
    Test that load operations retry on IO errors.
    
    Requirements: 6.6
    """
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir, max_retries=2)
        
        # First, save a result normally
        results = ScreenerResults(
            timestamp=datetime.now(),
            strategy='pcs',
            filters={'min_volume': 1000000},
            stocks=pd.DataFrame({'ticker': ['AAPL'], 'price': [150.0]}),
            metadata={}
        )
        result_id = storage.save_results(results, 'pcs')
        
        # Now mock open to fail twice then succeed for reading
        call_count = {'count': 0}
        original_open = open
        
        def mock_open_func(path, *args, **kwargs):
            if 'r' in args or kwargs.get('mode') == 'r':
                call_count['count'] += 1
                if call_count['count'] <= 2:
                    raise IOError("Simulated read error")
            return original_open(path, *args, **kwargs)
        
        with patch('builtins.open', side_effect=mock_open_func):
            # This should succeed after retries
            loaded_results = storage.load_results(result_id)
        
        # Verify the result was loaded
        assert loaded_results.strategy == 'pcs'
        
    finally:
        shutil.rmtree(temp_storage_dir)


def test_load_results_raises_error_after_max_retries():
    """
    Test that load operations raise StorageError after max retries.
    
    Requirements: 6.6
    """
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir, max_retries=1)
        
        # Create a dummy file
        result_id = "2025-01-04_143000_pcs"
        json_path = Path(temp_storage_dir) / f"{result_id}.json"
        json_path.touch()
        
        # Mock open to always fail for reading
        def mock_open_func(path, *args, **kwargs):
            if 'r' in args or kwargs.get('mode') == 'r':
                raise IOError("Persistent read error")
            return open(path, *args, **kwargs)
        
        with patch('builtins.open', side_effect=mock_open_func):
            with pytest.raises(StorageError) as exc_info:
                storage.load_results(result_id)
            
            assert "Failed to load results" in str(exc_info.value)
            assert "attempts" in str(exc_info.value)
        
    finally:
        shutil.rmtree(temp_storage_dir)


def test_load_history_returns_empty_on_corrupted_file():
    """
    Test that load_history returns empty list when history file is corrupted.
    
    Requirements: 6.6
    """
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir, max_retries=1)
        
        # Create a corrupted history file
        history_path = Path(temp_storage_dir) / "screener_history.json"
        with open(history_path, 'w') as f:
            f.write("{ invalid json }")
        
        # get_history should return empty list as fallback
        history = storage.get_history()
        
        assert history == [], "Corrupted history file should return empty list"
        
    finally:
        shutil.rmtree(temp_storage_dir)


def test_load_nonexistent_file_raises_file_not_found():
    """
    Test that loading non-existent results raises FileNotFoundError.
    
    Requirements: 6.6
    """
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir)
        
        with pytest.raises(FileNotFoundError) as exc_info:
            storage.load_results("nonexistent_id")
        
        assert "Results not found" in str(exc_info.value)
        
    finally:
        shutil.rmtree(temp_storage_dir)


def test_csv_save_retries_on_error():
    """
    Test that CSV save operations retry on errors.
    
    Requirements: 6.6
    """
    temp_storage_dir = tempfile.mkdtemp()
    
    try:
        storage = StorageManager(results_dir=temp_storage_dir, max_retries=2)
        
        results = ScreenerResults(
            timestamp=datetime.now(),
            strategy='pcs',
            filters={'min_volume': 1000000},
            stocks=pd.DataFrame({'ticker': ['AAPL'], 'price': [150.0]}),
            metadata={}
        )
        
        # Mock DataFrame.to_csv to fail twice then succeed
        call_count = {'count': 0}
        original_to_csv = pd.DataFrame.to_csv
        
        def mock_to_csv(self, *args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] <= 2:
                raise IOError("Simulated CSV write error")
            return original_to_csv(self, *args, **kwargs)
        
        with patch.object(pd.DataFrame, 'to_csv', mock_to_csv):
            # This should succeed after retries
            result_id = storage.save_results(results, 'pcs')
        
        # Verify the result was eventually saved
        assert result_id is not None
        
    finally:
        shutil.rmtree(temp_storage_dir)
