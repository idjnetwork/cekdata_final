"""
tests/conftest.py
=================
Konfigurasi pytest dan shared fixtures.
"""
import sys
import os

# Pastikan root project ada di sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
