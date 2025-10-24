"""User Agent Loader Utility.

This module provides functionality to load user agents from external files,
enabling dynamic configuration without hardcoding in the source code.
"""

import logging
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)


def load_user_agents_from_file(file_path: Path) -> List[str]:
    """Load user agents from a text file.
    
    Reads a file containing one user agent per line and returns a list
    of valid user agent strings. Handles common edge cases:
    - Empty lines (skipped)
    - Comments starting with # (skipped)
    - Leading/trailing whitespace (stripped)
    
    Args:
        file_path: Path to the file containing user agents
        
    Returns:
        List of user agent strings
        
    Raises:
        FileNotFoundError: If the specified file does not exist
        PermissionError: If the file cannot be read due to permissions
        UnicodeDecodeError: If the file contains invalid UTF-8 characters
        
    Examples:
        >>> user_agents = load_user_agents_from_file(Path("user-agents.txt"))
        >>> len(user_agents) > 0
        True
        >>> all(isinstance(ua, str) for ua in user_agents)
        True
    """
    if not file_path.exists():
        raise FileNotFoundError(f"User agents file not found: {file_path}")
    
    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            user_agents = []
            
            for line_num, line in enumerate(f, start=1):
                # Strip whitespace
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Validate user agent is not too short (minimum reasonable length)
                if len(line) < 10:
                    logger.warning(
                        f"Skipping suspiciously short user agent at line {line_num}: {line[:50]}"
                    )
                    continue
                
                user_agents.append(line)
            
            if not user_agents:
                logger.warning(f"No valid user agents found in {file_path}")
                return []
            
            logger.info(
                f"✅ Successfully loaded {len(user_agents)} user agents from {file_path.name}"
            )
            return user_agents
            
    except UnicodeDecodeError as e:
        logger.error(f"Failed to decode file {file_path}: {e}")
        raise
    except PermissionError as e:
        logger.error(f"Permission denied reading {file_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error reading {file_path}: {e}")
        raise


def get_default_user_agents_file() -> Path:
    """Get the default path to the user agents file.
    
    Looks for user-agents.txt in the project root directory.
    
    Returns:
        Path to the default user agents file
        
    Examples:
        >>> path = get_default_user_agents_file()
        >>> path.name
        'user-agents.txt'
    """
    # Get project root (3 levels up from this file)
    # src/infrastructure/youtube/user_agent_loader.py -> src/infrastructure/youtube -> src/infrastructure -> src -> root
    current_file = Path(__file__)
    
    # Try different possible root locations
    # Option 1: 3 levels up (assuming we're in src/infrastructure/youtube/)
    root_option1 = current_file.parent.parent.parent.parent
    file_option1 = root_option1 / "user-agents.txt"
    
    if file_option1.exists():
        return file_option1
    
    # Option 2: Look for common project markers and find root
    search_path = current_file.parent
    for _ in range(10):  # Max 10 levels up
        if (search_path / "user-agents.txt").exists():
            return search_path / "user-agents.txt"
        if (search_path / "pyproject.toml").exists() or (search_path / "setup.py").exists():
            return search_path / "user-agents.txt"
        if search_path.parent == search_path:  # Reached filesystem root
            break
        search_path = search_path.parent
    
    # Fallback: return the calculated path even if it doesn't exist
    return root_option1 / "user-agents.txt"
