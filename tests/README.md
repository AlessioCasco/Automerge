# Test Suite for Automerge Tool

This directory contains comprehensive tests for the automerge tool functionality.

## Test Files

### `test_ai_functionality.py` - **AI Features Test Suite**
Unified test suite for all AI-related functionality including:
- **Multi-Provider Support**: GitHub Copilot (via proxy) and Claude Code (direct API)
- **Confidence Score Calculation**: AI-powered PR risk assessment
- **Metadata Tracking**: Provider info, model, token usage in comments
- **SSL Handling**: Development environment SSL verification bypass
- **Error Handling**: Robust fallback mechanisms
- **Environment Detection**: Development vs production environment logic
- **Auto-merge Logic**: Decision making for automatic PR merging

**Key Test Cases:**
- AI calculator initialization with different providers
- API calls to both GitHub Copilot and Claude Code
- Response parsing with different formats
- Environment detection (dev vs prod)
- Confidence score calculation with metadata
- Fallback confidence calculation
- Auto-merge decision logic
- Error handling and edge cases
- SSL verification disable for development
- Unknown provider handling
- Missing API key handling
- PR processor AI integration

### `test_github_client.py` - **GitHub API Client Tests**
Tests for GitHub API interactions including:
- PR fetching and filtering
- Comment management
- Terraform plan extraction
- Merge operations
- Approval status checking

### `test_pr_processor.py` - **PR Processing Logic Tests**
Tests for PR categorization and processing:
- PR list creation and categorization
- AI confidence score integration
- Test PR processing
- Auto-merge logic integration

### `test_config.py` - **Configuration Management Tests**
Tests for configuration file handling:
- JSON configuration loading
- Validation logic
- Required field checking
- AI configuration validation

### `test_utils.py` - **Utility Functions Tests**
Tests for utility functions:
- PR information formatting
- API error formatting
- Merge state checking
- Branch update logic

### `test_main.py` - **Main Application Tests**
Integration tests for the main application:
- End-to-end workflow testing
- Configuration integration
- Error handling

### `test_dismissed_prs.py` - **Dismissed PR Handling Tests**
Tests for handling dismissed PRs:
- Re-approval logic
- Dismissal detection
- Status management

### `test_conf.py` - **Configuration Tests**
Additional configuration tests:
- Environment variable handling
- Default value management
- Configuration validation

## Running Tests

### Run All Tests
```bash
python -m unittest discover tests -v
```

### Run Specific Test File
```bash
python -m unittest tests.test_ai_functionality -v
```

### Run Specific Test Case
```bash
python -m unittest tests.test_ai_functionality.TestAIFunctionality.test_ai_calculator_initialization -v
```

## Test Coverage

The test suite covers:
- ✅ **AI Functionality**: Complete coverage of multi-provider AI features
- ✅ **GitHub Integration**: API calls, PR management, comments
- ✅ **Configuration**: Loading, validation, environment variables
- ✅ **Error Handling**: Network errors, API failures, fallback logic
- ✅ **Edge Cases**: Missing data, invalid responses, unknown providers
- ✅ **Integration**: End-to-end workflow testing

## Mock Strategy

Tests use comprehensive mocking to:
- **Isolate Units**: Test individual components without external dependencies
- **Control Responses**: Simulate various API responses (success, error, timeout)
- **Avoid Network Calls**: Prevent actual API calls during testing
- **Test Edge Cases**: Simulate error conditions and edge cases

## Key Mock Patterns

```python
# Mock HTTP responses
@patch('ai_confidence.requests.post')
def test_api_call(self, mock_post):
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = {"content": [{"text": "SCORE: 85%"}]}
    mock_post.return_value = mock_response

# Mock GitHub client
mock_github_client = Mock()
mock_github_client.get_last_terraform_plan.return_value = "No changes"
```

## Notes

- **AI Tests**: Focus on functionality rather than actual AI responses
- **SSL Tests**: Include environment variable handling for development
- **Error Tests**: Verify graceful degradation and fallback mechanisms
- **Integration Tests**: Ensure components work together correctly
