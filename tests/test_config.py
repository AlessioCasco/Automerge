import unittest
import json
import os
import tempfile
import sys
from unittest.mock import patch, mock_open

# Add src directory to path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config import read_config, use_config, validate_config, load_and_validate_config  # noqa: E402


class TestReadConfig(unittest.TestCase):
    """Test the read_config function."""

    def setUp(self):
        self.valid_config = {
            "access_token": "ghp_test_token",
            "owner": "test_owner",
            "github_user": "test_user",
            "repos": ["repo1", "repo2"],
            "filters": ["^\\[DEPENDENCIES\\]", "^\\[Dependabot\\]"]
        }

    def test_read_config_success(self):
        """Test successful config file reading."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(self.valid_config, f)
            temp_path = f.name

        try:
            result = read_config(temp_path)
            self.assertEqual(result, self.valid_config)
        finally:
            os.unlink(temp_path)

    def test_read_config_file_not_found(self):
        """Test reading non-existent config file."""
        with self.assertRaises(OSError) as context:
            read_config("non_existent_file.json")

        self.assertIn("Error reading config file", str(context.exception))

    def test_read_config_invalid_json(self):
        """Test reading config file with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"invalid": json}')  # Invalid JSON
            temp_path = f.name

        try:
            with self.assertRaises(OSError) as context:
                read_config(temp_path)
            self.assertIn("Error reading config file", str(context.exception))
        finally:
            os.unlink(temp_path)

    def test_read_config_permission_denied(self):
        """Test reading config file with no permissions."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(self.valid_config, f)
            temp_path = f.name

        try:
            # Remove read permissions
            os.chmod(temp_path, 0o000)

            with self.assertRaises(OSError) as context:
                read_config(temp_path)

            self.assertIn("Error reading config file", str(context.exception))
        finally:
            # Restore permissions before cleanup
            os.chmod(temp_path, 0o644)
            os.unlink(temp_path)

    @patch("builtins.open", new_callable=mock_open, read_data='{"test": "data"}')
    @patch("json.load")
    def test_read_config_encoding(self, mock_json_load, mock_file):
        """Test that config file is opened with UTF-8 encoding."""
        mock_json_load.return_value = {"test": "data"}

        read_config("test_file.json")

        # Verify the file was opened with UTF-8 encoding
        mock_file.assert_called_once_with("test_file.json", encoding="utf-8")


class TestUseConfig(unittest.TestCase):
    """Test the use_config function."""

    def setUp(self):
        self.config = {
            "string_key": "string_value",
            "list_key": ["item1", "item2"],
            "dict_key": {"nested": "value"},
            "int_key": 42,
            "bool_key": True
        }

    def test_use_config_string_value(self):
        """Test extracting string value from config."""
        result = use_config(self.config, "string_key")
        self.assertEqual(result, "string_value")

    def test_use_config_list_value(self):
        """Test extracting list value from config."""
        result = use_config(self.config, "list_key")
        self.assertEqual(result, ["item1", "item2"])

    def test_use_config_dict_value(self):
        """Test extracting dict value from config."""
        result = use_config(self.config, "dict_key")
        self.assertEqual(result, {"nested": "value"})

    def test_use_config_int_value(self):
        """Test extracting int value from config."""
        result = use_config(self.config, "int_key")
        self.assertEqual(result, 42)

    def test_use_config_bool_value(self):
        """Test extracting bool value from config."""
        result = use_config(self.config, "bool_key")
        self.assertEqual(result, True)

    def test_use_config_missing_key(self):
        """Test extracting non-existent key from config."""
        with self.assertRaises(SystemExit) as context:
            use_config(self.config, "missing_key")

        self.assertEqual(context.exception.code, 1)

    @patch("builtins.print")
    def test_use_config_missing_key_error_message(self, mock_print):
        """Test error message for missing key."""
        with self.assertRaises(SystemExit):
            use_config(self.config, "missing_key")

        mock_print.assert_called_once_with(
            'Error reading key "missing_key" from config')


class TestValidateConfig(unittest.TestCase):
    """Test the validate_config function."""

    def setUp(self):
        self.valid_config = {
            "access_token": "ghp_test_token",
            "owner": "test_owner",
            "github_user": "test_user",
            "repos": ["repo1", "repo2"],
            "filters": ["^\\[DEPENDENCIES\\]", "^\\[Dependabot\\]"]
        }

    def test_validate_config_success(self):
        """Test validation of valid config."""
        # Should not raise any exception
        validate_config(self.valid_config)

    def test_validate_config_missing_access_token(self):
        """Test validation with missing access_token."""
        config = self.valid_config.copy()
        del config["access_token"]

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn(
            "Missing required configuration key: access_token", str(context.exception))

    def test_validate_config_missing_owner(self):
        """Test validation with missing owner."""
        config = self.valid_config.copy()
        del config["owner"]

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("Missing required configuration key: owner",
                      str(context.exception))

    def test_validate_config_missing_github_user(self):
        """Test validation with missing github_user."""
        config = self.valid_config.copy()
        del config["github_user"]

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn(
            "Missing required configuration key: github_user", str(context.exception))

    def test_validate_config_missing_repos(self):
        """Test validation with missing repos."""
        config = self.valid_config.copy()
        del config["repos"]

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("Missing required configuration key: repos",
                      str(context.exception))

    def test_validate_config_missing_filters(self):
        """Test validation with missing filters."""
        config = self.valid_config.copy()
        del config["filters"]

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("Missing required configuration key: filters",
                      str(context.exception))

    def test_validate_config_empty_access_token(self):
        """Test validation with empty access_token."""
        config = self.valid_config.copy()
        config["access_token"] = ""

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("access_token cannot be empty", str(context.exception))

    def test_validate_config_empty_owner(self):
        """Test validation with empty owner."""
        config = self.valid_config.copy()
        config["owner"] = ""

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("owner cannot be empty", str(context.exception))

    def test_validate_config_empty_github_user(self):
        """Test validation with empty github_user."""
        config = self.valid_config.copy()
        config["github_user"] = ""

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("github_user cannot be empty", str(context.exception))

    def test_validate_config_empty_repos_list(self):
        """Test validation with empty repos list."""
        config = self.valid_config.copy()
        config["repos"] = []

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("repos must be a non-empty list", str(context.exception))

    def test_validate_config_repos_not_list(self):
        """Test validation with repos not being a list."""
        config = self.valid_config.copy()
        config["repos"] = "not_a_list"

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("repos must be a non-empty list", str(context.exception))

    def test_validate_config_empty_filters_list(self):
        """Test validation with empty filters list."""
        config = self.valid_config.copy()
        config["filters"] = []

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("filters must be a non-empty list",
                      str(context.exception))

    def test_validate_config_filters_not_list(self):
        """Test validation with filters not being a list."""
        config = self.valid_config.copy()
        config["filters"] = "not_a_list"

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("filters must be a non-empty list",
                      str(context.exception))

    def test_validate_config_repo_not_string(self):
        """Test validation with non-string repo."""
        config = self.valid_config.copy()
        config["repos"] = ["valid_repo", 123, "another_repo"]

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn(
            "Repository at index 1 must be a non-empty string, found: int", str(context.exception))

    def test_validate_config_empty_string_repo(self):
        """Test validation with empty string repo."""
        config = self.valid_config.copy()
        config["repos"] = ["valid_repo", "", "another_repo"]

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn(
            "Repository at index 1 must be a non-empty string", str(context.exception))

    def test_validate_config_whitespace_only_repo(self):
        """Test validation with whitespace-only repo."""
        config = self.valid_config.copy()
        config["repos"] = ["valid_repo", "   ", "another_repo"]

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn(
            "Repository at index 1 must be a non-empty string", str(context.exception))

    def test_validate_config_filter_not_string(self):
        """Test validation with non-string filter."""
        config = self.valid_config.copy()
        config["filters"] = ["^\\[DEPENDENCIES\\]", 456, "^\\[Dependabot\\]"]

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn(
            "Filter at index 1 must be a non-empty string, found: int", str(context.exception))

    def test_validate_config_empty_string_filter(self):
        """Test validation with empty string filter."""
        config = self.valid_config.copy()
        config["filters"] = ["^\\[DEPENDENCIES\\]", "", "^\\[Dependabot\\]"]

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("Filter at index 1 must be a non-empty string",
                      str(context.exception))

    def test_validate_config_whitespace_only_filter(self):
        """Test validation with whitespace-only filter."""
        config = self.valid_config.copy()
        config["filters"] = ["^\\[DEPENDENCIES\\]", "   ", "^\\[Dependabot\\]"]

        with self.assertRaises(ValueError) as context:
            validate_config(config)

        self.assertIn("Filter at index 1 must be a non-empty string",
                      str(context.exception))

    def test_validate_config_additional_keys_allowed(self):
        """Test that additional keys in config are allowed."""
        config = self.valid_config.copy()
        config["extra_key"] = "extra_value"
        config["another_extra"] = {"nested": "data"}

        # Should not raise any exception
        validate_config(config)


class TestLoadAndValidateConfig(unittest.TestCase):
    """Test the load_and_validate_config function."""

    def setUp(self):
        self.valid_config = {
            "access_token": "ghp_test_token",
            "owner": "test_owner",
            "github_user": "test_user",
            "repos": ["repo1", "repo2"],
            "filters": ["^\\[DEPENDENCIES\\]", "^\\[Dependabot\\]"]
        }

    def test_load_and_validate_config_success(self):
        """Test successful loading and validation."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(self.valid_config, f)
            temp_path = f.name

        try:
            result = load_and_validate_config(temp_path)
            self.assertEqual(result, self.valid_config)
        finally:
            os.unlink(temp_path)

    def test_load_and_validate_config_file_not_found(self):
        """Test loading non-existent config file."""
        with self.assertRaises(OSError):
            load_and_validate_config("non_existent_file.json")

    def test_load_and_validate_config_invalid_config(self):
        """Test loading valid JSON but invalid config."""
        invalid_config = {
            "access_token": "ghp_test_token",
            # Missing required keys
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(invalid_config, f)
            temp_path = f.name

        try:
            with self.assertRaises(ValueError):
                load_and_validate_config(temp_path)
        finally:
            os.unlink(temp_path)

    def test_load_and_validate_config_malformed_json(self):
        """Test loading malformed JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"invalid": json content}')
            temp_path = f.name

        try:
            with self.assertRaises(OSError) as context:
                load_and_validate_config(temp_path)
            self.assertIn("Error reading config file", str(context.exception))
        finally:
            os.unlink(temp_path)

    @patch("config.read_config")
    @patch("config.validate_config")
    def test_load_and_validate_config_calls_both_functions(self, mock_validate, mock_read):
        """Test that both read_config and validate_config are called."""
        mock_read.return_value = self.valid_config
        mock_validate.return_value = None

        result = load_and_validate_config("test_file.json")

        mock_read.assert_called_once_with("test_file.json")
        mock_validate.assert_called_once_with(self.valid_config)
        self.assertEqual(result, self.valid_config)


if __name__ == "__main__":
    unittest.main()
