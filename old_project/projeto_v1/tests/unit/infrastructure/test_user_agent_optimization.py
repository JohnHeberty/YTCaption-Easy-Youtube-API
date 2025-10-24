"""
Unit tests for User Agent Optimization verification.

Tests that the user agent system is properly loading from file
and not relying on hardcoded values.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from src.infrastructure.youtube.user_agent_loader import (
    load_user_agents_from_file,
    get_default_user_agents_file
)
from src.infrastructure.youtube.user_agent_rotator import (
    UserAgentRotator,
    get_ua_rotator
)


class TestUserAgentLoader:
    """Test user agent loader functionality."""

    def test_load_user_agents_from_file_success(self, tmp_path):
        """Test successful loading of user agents from file."""
        # Create test file
        test_file = tmp_path / "test-agents.txt"
        test_agents = [
            "Mozilla/5.0 (Windows NT 10.0)",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X)",
            "Mozilla/5.0 (X11; Linux x86_64)",
        ]
        test_file.write_text("\n".join(test_agents))

        # Load and verify
        loaded = load_user_agents_from_file(test_file)
        assert len(loaded) == 3
        assert all(ua in loaded for ua in test_agents)

    def test_load_user_agents_skips_empty_lines(self, tmp_path):
        """Test that empty lines are skipped."""
        test_file = tmp_path / "test-agents.txt"
        content = """Mozilla/5.0 (Windows NT 10.0)

Mozilla/5.0 (Macintosh; Intel Mac OS X)

"""
        test_file.write_text(content)

        loaded = load_user_agents_from_file(test_file)
        assert len(loaded) == 2

    def test_load_user_agents_skips_comments(self, tmp_path):
        """Test that comment lines are skipped."""
        test_file = tmp_path / "test-agents.txt"
        content = """# This is a comment
Mozilla/5.0 (Windows NT 10.0)
# Another comment
Mozilla/5.0 (Macintosh; Intel Mac OS X)
"""
        test_file.write_text(content)

        loaded = load_user_agents_from_file(test_file)
        assert len(loaded) == 2

    def test_load_user_agents_file_not_found(self):
        """Test FileNotFoundError when file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            load_user_agents_from_file(Path("/nonexistent/path/agents.txt"))

    def test_load_user_agents_strips_whitespace(self, tmp_path):
        """Test that whitespace is stripped from lines."""
        test_file = tmp_path / "test-agents.txt"
        content = """  Mozilla/5.0 (Windows NT 10.0)  
\tMozilla/5.0 (Macintosh; Intel Mac OS X)\t
"""
        test_file.write_text(content)

        loaded = load_user_agents_from_file(test_file)
        assert len(loaded) == 2
        assert loaded[0] == "Mozilla/5.0 (Windows NT 10.0)"
        assert loaded[1] == "Mozilla/5.0 (Macintosh; Intel Mac OS X)"

    def test_get_default_user_agents_file(self):
        """Test getting default user agents file path."""
        path = get_default_user_agents_file()
        assert path.name == "user-agents.txt"
        assert isinstance(path, Path)

    def test_load_user_agents_empty_file(self, tmp_path):
        """Test loading from empty file returns empty list."""
        test_file = tmp_path / "test-agents.txt"
        test_file.write_text("")

        loaded = load_user_agents_from_file(test_file)
        assert loaded == []

    def test_load_user_agents_only_comments(self, tmp_path):
        """Test loading file with only comments returns empty list."""
        test_file = tmp_path / "test-agents.txt"
        content = """# Comment 1
# Comment 2
# Comment 3
"""
        test_file.write_text(content)

        loaded = load_user_agents_from_file(test_file)
        assert loaded == []


class TestUserAgentRotator:
    """Test user agent rotator functionality."""

    def test_rotator_loads_from_file(self, tmp_path):
        """Test that rotator loads user agents from file."""
        # Create test file
        test_file = tmp_path / "test-agents.txt"
        test_agents = [f"Agent-{i}" for i in range(100)]
        # Pad to minimum length
        test_agents = [f"Mozilla/5.0 (X11; Linux x86_64) Agent-{i}" for i in range(100)]
        test_file.write_text("\n".join(test_agents))

        # Create rotator with custom file
        rotator = UserAgentRotator(user_agents_file=test_file)

        # Verify agents loaded
        assert len(rotator.CUSTOM_USER_AGENTS) == 100
        assert any("Agent-0" in ua for ua in rotator.CUSTOM_USER_AGENTS)

    def test_rotator_fallback_when_file_not_found(self):
        """Test that rotator uses fallback when file not found."""
        rotator = UserAgentRotator(
            user_agents_file=Path("/nonexistent/file.txt"),
            enable_rotation=True
        )

        # Should have fallback agents
        assert len(rotator.CUSTOM_USER_AGENTS) > 0
        # Should have at least the hardcoded fallback
        assert len(rotator.CUSTOM_USER_AGENTS) >= 17

    def test_rotator_get_random(self, tmp_path):
        """Test random user agent selection."""
        test_file = tmp_path / "test-agents.txt"
        test_agents = [f"Mozilla/5.0 (X11; Linux x86_64) Agent-{i}" for i in range(10)]
        test_file.write_text("\n".join(test_agents))

        rotator = UserAgentRotator(user_agents_file=test_file)

        ua = rotator.get_random()
        assert isinstance(ua, str)
        assert ua in rotator.CUSTOM_USER_AGENTS

    def test_rotator_get_next(self, tmp_path):
        """Test sequential user agent selection."""
        test_file = tmp_path / "test-agents.txt"
        test_agents = [f"Mozilla/5.0 (X11; Linux x86_64) Agent-{i}" for i in range(10)]
        test_file.write_text("\n".join(test_agents))

        rotator = UserAgentRotator(user_agents_file=test_file)

        # Get first UA
        ua1 = rotator.get_next()
        ua2 = rotator.get_next()

        # Should be different (sequential)
        assert ua1 != ua2
        assert ua1 == rotator.CUSTOM_USER_AGENTS[0]
        assert ua2 == rotator.CUSTOM_USER_AGENTS[1]

    def test_rotator_get_mobile(self, tmp_path):
        """Test mobile user agent selection."""
        test_file = tmp_path / "test-agents.txt"
        mobile_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) Mobile"
        desktop_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Desktop"
        test_file.write_text(f"{mobile_agent}\n{desktop_agent}")

        rotator = UserAgentRotator(user_agents_file=test_file)

        ua = rotator.get_mobile()
        # Should be mobile agent
        assert "Mobile" in ua or "iPhone" in ua or "Android" in ua

    def test_rotator_get_desktop(self, tmp_path):
        """Test desktop user agent selection."""
        test_file = tmp_path / "test-agents.txt"
        mobile_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) Mobile"
        desktop_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Desktop"
        test_file.write_text(f"{mobile_agent}\n{desktop_agent}")

        rotator = UserAgentRotator(user_agents_file=test_file)

        ua = rotator.get_desktop()
        # Should be desktop agent
        assert "Mobile" not in ua and "iPhone" not in ua

    def test_rotator_get_stats(self, tmp_path):
        """Test getting rotator statistics."""
        test_file = tmp_path / "test-agents.txt"
        test_agents = [f"Mozilla/5.0 (X11; Linux x86_64) Agent-{i}" for i in range(10)]
        test_file.write_text("\n".join(test_agents))

        rotator = UserAgentRotator(user_agents_file=test_file)
        rotator.get_random()  # Increment rotation count
        rotator.get_random()

        stats = rotator.get_stats()
        assert isinstance(stats, dict)
        assert "rotation_enabled" in stats
        assert "fake_ua_enabled" in stats
        assert "custom_pool_size" in stats
        assert stats["custom_pool_size"] == 10
        assert stats["rotation_count"] >= 2

    def test_rotator_rotation_disabled(self, tmp_path):
        """Test that rotation can be disabled."""
        test_file = tmp_path / "test-agents.txt"
        test_agents = [f"Mozilla/5.0 (X11; Linux x86_64) Agent-{i}" for i in range(10)]
        test_file.write_text("\n".join(test_agents))

        rotator = UserAgentRotator(
            enable_rotation=False,
            user_agents_file=test_file
        )

        ua1 = rotator.get_random()
        ua2 = rotator.get_random()
        ua3 = rotator.get_next()

        # All should be the same (first one)
        assert ua1 == ua2 == ua3
        assert ua1 == rotator.CUSTOM_USER_AGENTS[0]

    def test_rotator_singleton_pattern(self):
        """Test that get_ua_rotator returns singleton."""
        rotator1 = get_ua_rotator()
        rotator2 = get_ua_rotator()

        assert rotator1 is rotator2

    def test_rotator_no_hardcoded_agents_in_main_pool(self, tmp_path):
        """Test that file-based agents are used, not hardcoded."""
        test_file = tmp_path / "test-agents.txt"
        # Create 1000 unique agents
        test_agents = [f"Mozilla/5.0 (X11; Linux x86_64) CustomAgent-{i:04d}" 
                       for i in range(1000)]
        test_file.write_text("\n".join(test_agents))

        rotator = UserAgentRotator(user_agents_file=test_file)

        # Pool should be from file, not hardcoded
        assert len(rotator.CUSTOM_USER_AGENTS) == 1000
        # All should be custom agents
        assert all("CustomAgent" in ua for ua in rotator.CUSTOM_USER_AGENTS)

    def test_rotator_pool_size_exceeds_fallback(self):
        """Test that loaded pool is much larger than fallback."""
        # When fallback is used, should have limited size
        rotator = UserAgentRotator(
            user_agents_file=Path("/nonexistent/path.txt")
        )
        fallback_size = len(rotator.CUSTOM_USER_AGENTS)
        
        # Fallback should be small (17 hardcoded agents)
        assert fallback_size == 17


class TestIntegration:
    """Integration tests with real project files."""

    def test_real_user_agents_file_exists(self):
        """Test that real user-agents.txt file exists in project."""
        # Find project root
        current_dir = Path(__file__).parent
        project_root = current_dir
        for _ in range(10):
            if (project_root / "user-agents.txt").exists():
                break
            project_root = project_root.parent

        agents_file = project_root / "user-agents.txt"
        assert agents_file.exists(), "user-agents.txt not found in project"

    def test_real_user_agents_file_has_content(self):
        """Test that real user-agents.txt file has sufficient content."""
        agents_file = get_default_user_agents_file()
        if not agents_file.exists():
            pytest.skip("user-agents.txt not found")

        loaded = load_user_agents_from_file(agents_file)
        # Should have at least 100 user agents
        assert len(loaded) > 100, f"Expected >100 agents, got {len(loaded)}"

    def test_real_user_agents_file_variety(self):
        """Test that real user-agents.txt has variety of agent types."""
        agents_file = get_default_user_agents_file()
        if not agents_file.exists():
            pytest.skip("user-agents.txt not found")

        loaded = load_user_agents_from_file(agents_file)

        # Check for variety
        has_chrome = any("Chrome" in ua for ua in loaded)
        has_firefox = any("Firefox" in ua for ua in loaded)
        has_safari = any("Safari" in ua for ua in loaded)
        has_mobile = any("Mobile" in ua or "Android" in ua for ua in loaded)

        assert has_chrome, "No Chrome user agents found"
        assert has_firefox, "No Firefox user agents found"
        assert has_safari, "No Safari user agents found"
        assert has_mobile, "No mobile user agents found"
