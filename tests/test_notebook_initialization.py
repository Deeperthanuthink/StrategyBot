"""
Unit tests for Marimo notebook initialization.

Tests that UI elements are present on launch.
Requirements: 1.1
"""

import pytest
import sys
from pathlib import Path
import importlib.util


def test_notebook_file_exists():
    """Test that the notebook file exists."""
    notebook_path = Path("screener.py")
    assert notebook_path.exists(), "screener.py notebook file should exist"


def test_notebook_imports():
    """Test that the notebook can import required modules."""
    # Load the notebook module from file
    spec = importlib.util.spec_from_file_location("screener_notebook", "screener.py")
    notebook_module = importlib.util.module_from_spec(spec)
    
    # Execute the module to populate it
    try:
        spec.loader.exec_module(notebook_module)
    except ImportError as e:
        # If marimo is not installed, skip this test
        if "marimo" in str(e):
            pytest.skip("marimo not installed")
        raise
    
    # Check that the app is defined
    assert hasattr(notebook_module, 'app'), "Notebook should define 'app'"
    assert hasattr(notebook_module, '__generated_with'), "Notebook should have __generated_with"


def test_notebook_has_marimo_app():
    """Test that the notebook defines a Marimo app."""
    try:
        import marimo
    except ImportError:
        pytest.skip("marimo not installed")
    
    # Load the notebook module from file
    spec = importlib.util.spec_from_file_location("screener_notebook", "screener.py")
    notebook_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(notebook_module)
    
    # Check that app is a Marimo App instance
    assert isinstance(notebook_module.app, marimo.App), "app should be a marimo.App instance"


def test_notebook_structure():
    """Test that the notebook has the expected structure."""
    # Read the notebook file
    notebook_path = Path("screener.py")
    content = notebook_path.read_text()
    
    # Check for key components
    assert "import marimo" in content, "Notebook should import marimo"
    assert "@app.cell" in content, "Notebook should have app cells"
    assert "ScreeningEngine" in content, "Notebook should import ScreeningEngine"
    assert "ConfigManager" in content, "Notebook should import ConfigManager"
    assert "StorageManager" in content, "Notebook should import StorageManager"


def test_notebook_has_title():
    """Test that the notebook has a title section."""
    notebook_path = Path("screener.py")
    content = notebook_path.read_text()
    
    # Check for title
    assert "Strategy Stock Screener" in content, "Notebook should have a title"
    assert "mo.md" in content, "Notebook should use markdown for display"
