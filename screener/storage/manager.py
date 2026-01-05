"""Storage manager for persisting screening results and history."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd

from screener.core.models import ScreenerResults, ScreeningSession


class StorageError(Exception):
    """Base exception for storage operations."""
    pass


class StorageManager:
    """Manages persistence of screening results and session history."""
    
    def __init__(self, results_dir: str = "data/screener_results", max_retries: int = 2):
        """
        Initialize the storage manager.
        
        Args:
            results_dir: Directory path for storing screening results
            max_retries: Maximum number of retry attempts for failed operations
        """
        self.results_dir = Path(results_dir)
        self.history_file = self.results_dir / "screener_history.json"
        self.max_retries = max_retries
        
        # Create directory structure if it doesn't exist
        self.results_dir.mkdir(parents=True, exist_ok=True)
    
    def save_results(self, results: ScreenerResults, strategy: str) -> str:
        """
        Save screening results to local storage with timestamp.
        
        Args:
            results: ScreenerResults object to save
            strategy: Strategy name used for screening
            
        Returns:
            Result ID (filename without extension)
            
        Requirements: 6.1
        """
        # Generate result ID with timestamp
        timestamp_str = results.timestamp.strftime("%Y-%m-%d_%H%M%S")
        result_id = f"{timestamp_str}_{strategy}"
        
        # Save as JSON
        json_path = self.results_dir / f"{result_id}.json"
        self._save_as_json(results, json_path)
        
        # Save as CSV
        csv_path = self.results_dir / f"{result_id}.csv"
        self._save_as_csv(results, csv_path)
        
        # Update history log
        self._add_to_history(result_id, results, strategy)
        
        return result_id
    
    def load_results(self, result_id: str) -> ScreenerResults:
        """
        Load screening results by ID with fallback handling.
        
        Args:
            result_id: Result ID (filename without extension)
            
        Returns:
            ScreenerResults object
            
        Raises:
            FileNotFoundError: If result ID doesn't exist
            StorageError: If file cannot be read after retries
            
        Requirements: 6.2, 6.6
        """
        json_path = self.results_dir / f"{result_id}.json"
        
        if not json_path.exists():
            raise FileNotFoundError(f"Results not found for ID: {result_id}")
        
        # Try to load with retry logic
        for attempt in range(self.max_retries + 1):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                
                # Reconstruct ScreenerResults
                results = ScreenerResults(
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    strategy=data['strategy'],
                    filters=data['filters'],
                    stocks=pd.DataFrame(data['stocks']),
                    metadata=data.get('metadata', {})
                )
                
                return results
            except (IOError, OSError, json.JSONDecodeError) as e:
                if attempt < self.max_retries:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    raise StorageError(f"Failed to load results after {self.max_retries + 1} attempts: {e}")
    
    def _save_as_json(self, results: ScreenerResults, path: Path) -> None:
        """
        Save results as JSON file with retry logic.
        
        Requirements: 6.6
        """
        for attempt in range(self.max_retries + 1):
            try:
                with open(path, 'w') as f:
                    data = {
                        'timestamp': results.timestamp.isoformat(),
                        'strategy': results.strategy,
                        'filters': results.filters,
                        'stocks': results.stocks.to_dict(orient='records'),
                        'metadata': results.metadata
                    }
                    json.dump(data, f, indent=2, default=str)
                return  # Success
            except (IOError, OSError) as e:
                if attempt < self.max_retries:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    raise StorageError(f"Failed to save JSON after {self.max_retries + 1} attempts: {e}")
    
    def _save_as_csv(self, results: ScreenerResults, path: Path) -> None:
        """
        Save results as CSV file with retry logic.
        
        Requirements: 6.6
        """
        for attempt in range(self.max_retries + 1):
            try:
                results.stocks.to_csv(path, index=False)
                return  # Success
            except (IOError, OSError) as e:
                if attempt < self.max_retries:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    raise StorageError(f"Failed to save CSV after {self.max_retries + 1} attempts: {e}")
    
    def _add_to_history(self, result_id: str, results: ScreenerResults, strategy: str) -> None:
        """Add entry to screening history log."""
        # Load existing history
        history = self._load_history()
        
        # Create new session entry
        filters_summary = ", ".join([f"{k}={v}" for k, v in results.filters.items()])
        session = {
            'id': result_id,
            'timestamp': results.timestamp.isoformat(),
            'strategy': strategy,
            'num_results': len(results.stocks),
            'filters_summary': filters_summary
        }
        
        # Add to history
        history.append(session)
        
        # Save updated history
        with open(self.history_file, 'w') as f:
            json.dump(history, f, indent=2)
    
    def _load_history(self) -> list:
        """
        Load screening history from file with fallback.
        
        Requirements: 6.6
        """
        if not self.history_file.exists():
            return []
        
        # Try to load with retry logic
        for attempt in range(self.max_retries + 1):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except (IOError, OSError, json.JSONDecodeError) as e:
                if attempt < self.max_retries:
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    # Fallback to empty history if file is corrupted
                    return []
    
    def export_to_csv(self, results: ScreenerResults, path: str) -> None:
        """
        Export screening results to CSV file with all columns.
        
        Args:
            results: ScreenerResults object to export
            path: File path for CSV export
            
        Requirements: 6.3
        """
        # Export DataFrame to CSV with all columns
        results.stocks.to_csv(path, index=False)
    
    def export_to_json(self, results: ScreenerResults, path: str) -> None:
        """
        Export screening results to JSON file with structured data.
        
        Args:
            results: ScreenerResults object to export
            path: File path for JSON export
            
        Requirements: 6.4
        """
        data = {
            'timestamp': results.timestamp.isoformat(),
            'strategy': results.strategy,
            'filters': results.filters,
            'stocks': results.stocks.to_dict(orient='records'),
            'metadata': results.metadata
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def get_history(self, limit: int = 50) -> list:
        """
        Get screening history log.
        
        Args:
            limit: Maximum number of history entries to return (default 50)
            
        Returns:
            List of screening session dictionaries, most recent first
            
        Requirements: 6.5
        """
        history = self._load_history()
        
        # Sort by timestamp descending (most recent first)
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Return limited results
        return history[:limit]
