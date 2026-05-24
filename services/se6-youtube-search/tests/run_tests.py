#!/usr/bin/env python3
"""
Test runner for YouTube Search Service
"""
import sys
import pytest


if __name__ == "__main__":
    # Run tests with coverage
    args = [
        "tests/",
        "-v",
        "--tb=short",
        "--cov=app",
        "--cov-report=term-missing",
        "--cov-report=html",
    ]
    
    sys.exit(pytest.main(args))
