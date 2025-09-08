![CI](https://github.com/AlessioCasco/automerge/actions/workflows/ci.yml/badge.svg)
![Lint & tests](https://github.com/AlessioCasco/automerge/actions/workflows/at-every-commit.yml/badge.svg)
![Docker Build](https://github.com/AlessioCasco/automerge/actions/workflows/build_and_push.yml/badge.svg)
# Automerge for GitHub and Atlantis

Used to automatically merge terraform dependencies pull requests in GitHub that result in no differences.

Tools like [dependabot](https://github.com/dependabot) or [renovate](https://github.com/renovatebot/renovate) can create a lot of pull requests if you have different providers or modules in your terraform code. Most of the time these changes result in no terraform differences and can be merged automatically without any intervention.

Automerge does exactly this: Checks every PR that has a title that matches a specific string, plans it and if the terraform plan results in `No changes` it approves and merges the PR.

It works along with the [atlantis](runatlantis.io) tool.

## Dependencies
Automerge (for now) works only with [github](github.com) repos and [atlantis](runatlantis.io), so you need to have a working Atlantis installation to use it.

## Configuration
```json
{
  "access_token" : "token",
  "filters" : [
    "^\\[DEPENDENCIES\\] Update Terraform",
    "^\\[DEPENDABOT\\]",
    "^\\[Dependabot\\]"
  ],
  "github_user" : "AlessioCasco",
  "owner" : "my_company",
  "repos" : [
    "terraform-vault",
    "terraform-aws"
  ],
  "enable_ai_confidence_score" : false,
  "enable_ai_automerge_action" : false,
  "ai_provider" : "github",
  "ai_config" : {
    "github" : {
      "api_base" : "http://localhost:4141",
      "model" : "claude-sonnet-4"
    },
    "claude-code" : {
      "api_base" : "https://api.anthropic.com",
      "api_key" : "your_anthropic_api_key_here",
      "model" : "claude-3-5-sonnet-20241022"
    }
  }
}
```

* `access_token`: Token (classic) from GitHub that needs to have the following Scopes:
  * Full control of private repositories.
* `filters`: Regex that Automerge uses to filter the pull requests it has to consider.
  * This is usually what you set in the [prefix](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#commit-message) option for dependabot or the equivalent [commitMessagePrefix](https://docs.renovatebot.com/configuration-options/#commitmessageprefix) option for renovate.
  * Be aware that you need to escape the backslashes in the JSON string to properly represent the regular expressions, [see the configuration section](#configuration) for an example.
* `github_user`: GitHub user that owns the `access_token`.
* `owner`: Owner of the repos where we want to check the pull requests.
* `repos`: list of repo names that you want to check pull requests from (note that they all need to be under the same owner).
  * ie `https://github.com/Owner/repo/`
* `enable_ai_confidence_score`: Enable AI-powered confidence score calculation using GitHub Copilot (default: false).
  * When enabled, the system analyzes PRs to determine if they can be safely merged automatically.
  * Requires GitHub token with Copilot API permissions.
* `enable_ai_automerge_action`: Enable automatic merging for PRs with 100% confidence in development environments (default: false).
  * Only works when `enable_ai_confidence_score` is also enabled.
  * Auto-merge is restricted to development environments only.
  * Requires 100% confidence score for auto-merge.
* `disable_pr_comments`: Disable posting comments to PRs and print AI analysis only to terminal (default: false).
  * When enabled, AI confidence score analysis is printed to terminal instead of being posted as PR comments.
  * Useful for testing or when you want to avoid cluttering PRs with comments.
  * AI analysis is still performed and logged to terminal.
* `repos`: List of repositories to process for standard automerge (required).
  * These repositories are processed for standard merge and planning logic.
  * Can be empty to disable standard processing while keeping AI analysis.
  * When empty, prints "No repositories configured, skipping pull request processing".
* `ai_repos`: List of repositories to process with AI analysis (optional).
  * These repositories are processed with AI analysis when PRs have diffs.
  * AI analysis is performed during the standard processing cycle.
  * Useful for repositories that need AI-powered confidence scoring.
* `ai_provider`: Choose the AI provider for confidence score calculation (default: "github").
  * Options: "github" (GitHub Copilot via proxy) or "claude-code" (Claude Code direct API).
  * Required when `enable_ai_confidence_score` is enabled.
* `ai_config`: Configuration for the selected AI provider.
  * **For GitHub Copilot**: Requires `api_base` (proxy URL) and `model` (model name).
  * **For Claude Code**: Requires `api_base` (API URL), `api_key` (Anthropic API key), and `model` (model name).
* `test_prs`: List of specific PRs to analyze for AI confidence score testing (optional).
  * Each test PR should have `repo` (string) and `pr_number` (integer) fields.
  * These PRs are analyzed regardless of their merge status when AI is enabled.
  * Useful for testing AI features on specific PRs.


### AI Provider Configuration

The tool supports two AI providers for confidence score calculation:

#### GitHub Copilot (via proxy)
```json
{
  "ai_provider": "github",
  "ai_config": {
    "github": {
      "api_base": "http://localhost:4141",
      "model": "claude-sonnet-4"
    }
  }
}
```

#### Claude Code (direct API)
```json
{
  "ai_provider": "claude-code",
  "ai_config": {
    "claude-code": {
      "api_base": "https://api.anthropic.com",
      "api_key": "your_anthropic_api_key_here",
      "model": "claude-sonnet-4"
    }
  }
}
```

**Note:** If you encounter SSL certificate verification errors in local development environments, you can disable SSL verification by setting the environment variable:
```bash
export DISABLE_SSL_VERIFY=true
```
This should only be used in development/testing environments, never in production.

## GitHub Config
### Branch protection
If you [Require status checks from Atlantis to pass before merging](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks) on your [Branch protection rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule), make sure that the atlantis ones are set to `atlantis/plan` only.
Automerge will never apply anything (for now) so having an `atlantis/apply` check set as required will break the ability for automerge to merge pull requests.
This because automerge does not `bypass branch protections`. Before merging any pull request it waits that all checks are green.

### Codeowners
Since the GitHub user leveraged by Automerge has to be able to comment, approve and merge pull requests, depending on your GitHub configs it may be required to add such a user in the [codeowners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) file and also as writer for the repository.

## AI Confidence Score Feature

Automerge includes an AI-powered feature that analyzes pull requests to determine if they can be safely merged automatically. This feature uses GitHub Copilot to calculate confidence scores (0-100%) based on various factors.

### How It Works

1. **Context Extraction**: The system extracts relevant information from PRs:
   - Title and description
   - Repository and branch information
   - Labels
   - Terraform plan output from comments

2. **AI Analysis**: GitHub Copilot analyzes the PR context and provides a confidence score with explanation

3. **Environment Detection**: The system determines if the PR targets a development environment based on branch patterns

4. **Auto-Merge Logic**: Auto-merge is only enabled when:
   - `enable_ai_automerge_action` is set to `true`
   - The PR targets a development environment
   - The confidence score is exactly 100%

### Safety Rules

- **Production Protection**: Production/protected branches are never auto-merged
- **Development Only**: Only development environments can be auto-merged
- **100% Confidence**: Confidence score must be 100% for auto-merge
- **Fallback Logic**: System continues working even if AI is unavailable

### AI Repository Processing

The tool now supports AI analysis for specific repositories during the standard processing cycle:

1. **Standard Processing**: All repositories are processed normally
   - PRs are categorized based on their state
   - Standard merge and planning logic applies

2. **AI Analysis**: For repositories in the `ai_repos` list, when PRs have diffs:
   - AI confidence score analysis is performed
   - Auto-merge is applied if conditions are met (100% confidence + dev environment)
   - Robust error handling for various failure scenarios

3. **Integration**: AI analysis is seamlessly integrated into the existing workflow
   - No separate processing cycles
   - No additional wait times
   - Maintains existing behavior for non-AI repositories

### AI Failure Handling

The system now provides detailed feedback when AI analysis cannot be performed:

- **No Plan Found**: When Atlantis hasn't generated a plan yet
- **Plan in Progress**: When Atlantis is still running the plan
- **Lock Conflicts**: When another PR has acquired the lock
- **Plan Errors**: When the Terraform plan contains errors
- **AI Service Errors**: When the AI service is unavailable

Each failure includes:
- Clear reason for the failure
- Detailed explanation
- Recommended action for resolution

### Example Output

The system adds a formatted comment to each analyzed PR:

```
🤖 **AI Confidence Score Analysis**

**Confidence Score:** 95%

**Explanation:** Safe provider update with no breaking changes

**Environment:** Development

**Auto-merge Status:** ❌ Disabled

---
*This analysis was performed by GitHub Copilot AI to assess the safety of automatic merging.*
```

### Environment Variables

You can also control the AI features via environment variables:

- `ENABLE_AI_CONFIDENCE_SCORE`: Override AI confidence score setting
- `ENABLE_AI_AUTOMERGE_ACTION`: Override AI auto-merge setting
- `LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)

### Logging Configuration

The tool supports detailed logging for debugging AI interactions:

```bash
# Enable debug logging via CLI
python -m src.main --config config.json --log_level DEBUG

# Enable debug logging via environment variable
export LOG_LEVEL=DEBUG
python -m src.main --config config.json
```

Debug logging will show:
- 🤖 AI API call details (URL, model, headers, payload)
- 🔍 PR analysis context (title, repository, branches, environment)
- 📝 Generated prompts and their length
- ✅ AI responses and parsing results
- 📊 Confidence scores and explanations
- 🔄 Fallback logic usage
- ❌ Error details and exceptions

### Terraform Plan Analysis

The AI confidence score calculation now specifically analyzes Terraform plans from the `tl-terraform` user:

- **Multi-comment Plans**: Handles plans split across multiple comments
- **Continuation Detection**: Recognizes "Continued plan output from previous comment." headers
- **Chronological Order**: Combines plan parts in the correct sequence
- **Latest Plan**: Always uses the most recent plan from the specified user

The system will:
1. Fetch all comments from the PR
2. Filter comments by the `tl-terraform` user
3. Sort by creation date (newest first)
4. Identify the latest complete plan (including continuations)
5. Combine all plan parts in chronological order
6. Remove continuation headers for clean output

### Empty Lists Handling

The system gracefully handles empty repository lists:

#### Empty `repos` List
```json
{
  "repos": [],
  "ai_repos": ["terraform-ops", "terraform-k8s"]
}
```

**Behavior:**
- ✅ **Standard Processing**: Skipped (no repositories to process)
- ✅ **AI Processing**: Continues for repositories in `ai_repos`
- ✅ **Test PRs**: Still processed if configured
- ✅ **Message**: "No repositories configured, skipping pull request processing"

#### Empty `ai_repos` List
```json
{
  "repos": ["terraform-vault", "terraform-aws"],
  "ai_repos": []
}
```

**Behavior:**
- ✅ **Standard Processing**: Continues normally
- ✅ **AI Processing**: Skipped (no AI repositories configured)
- ✅ **Test PRs**: Still processed if configured

#### Both Lists Empty
```json
{
  "repos": [],
  "ai_repos": []
}
```

**Behavior:**
- ✅ **Standard Processing**: Skipped
- ✅ **AI Processing**: Skipped
- ✅ **Test PRs**: Still processed if configured
- ✅ **Use Case**: Useful for testing specific PRs only

### Terraform Plan Extraction

The system now extracts Terraform plans from GitHub status checks instead of PR comments. This approach is more reliable and provides access to complete plan information.

#### How It Works

1. **PR Details Fetch**: The system fetches PR details from the GitHub PR endpoint (e.g., `https://api.github.com/repos/TrueLayer/terraform-ops/pulls/23750`)
   - **URL Support**: Also supports issues URLs (e.g., `https://api.github.com/repos/TrueLayer/terraform-ops/issues/23724`) which are automatically converted to pulls URLs
2. **Statuses URL Extraction**: Extracts `statuses_url` field from the PR data response
3. **Status Checks Fetch**: Makes a second API call to the `statuses_url` to get the list of status checks
4. **Context Filtering**: Filters status checks for contexts starting with `atlantis/plan:` (note the colon)
5. **Environment Extraction**: Extracts environment and project information from the context element after the colon
6. **Multiple Plans Support**: Processes multiple `atlantis/plan:` status checks (one per project/environment)
7. **Atlantis URL Fetching**: Each status check contains a `target_url` pointing to the Atlantis job page
8. **Plan Extraction**: Fetches the Atlantis job page and extracts Terraform plan content from HTML
9. **Plan Combination**: Combines all plans from different projects/environments with environment information

#### Status Check Contexts

The system looks for status checks with contexts starting with `atlantis/plan:` (note the colon):

- `atlantis/plan:dev` - Development environment plan
- `atlantis/plan:prod` - Production environment plan  
- `atlantis/plan:project-dev` - Specific project in development environment
- `atlantis/plan:project-prod` - Specific project in production environment
- `atlantis/plan:staging` - Staging environment plan

#### Environment Detection

The system automatically detects environment and project information from the context element:

- **Environment Detection**: 
  - `dev`, `development`, `staging`, `test` → `development`
  - `prod`, `production`, `live` → `production`
  - Unknown patterns → defaults to `development`

- **Project Extraction**: 
  - Extracts project name by removing environment indicators
  - Example: `project-dev` → project: `project`, environment: `development`

#### URL Format Support

The system supports both PR and issues URLs:

**PR URLs** (preferred):
```
https://api.github.com/repos/TrueLayer/terraform-ops/pulls/23750
```

**Issues URLs** (automatically converted):
```
https://api.github.com/repos/TrueLayer/terraform-ops/issues/23724
→ https://api.github.com/repos/TrueLayer/terraform-ops/pulls/23724
```

#### Atlantis URL Format

Status checks contain `target_url` fields pointing to Atlantis job pages:
```
https://atlantis.truelayer.cloud/jobs/58c5a09b-f21c-4801-8afb-2d0678623e63
```

#### Plan Extraction Patterns

The system extracts Terraform plans from Atlantis HTML using multiple patterns:

1. **`<pre>` Tags**: Looks for Terraform plans in `<pre>` HTML tags
2. **`<div>` Tags**: Searches for plans in `<div>` elements with plan-related classes
3. **Plan Summary**: Identifies plans by the summary pattern `Plan: X to add, Y to change, Z to destroy.`

#### Combined Plan Format

When multiple plans are found, they are combined with detailed environment information:

```
=== Terraform Plan: dev ===
Environment: development
Project: dev
Context: atlantis/plan:dev
==================================================
Terraform will perform the following actions:

# aws_s3_bucket.dev-example will be created
+ resource "aws_s3_bucket" "dev-example" {
    + bucket = "dev-example-bucket"
    + id     = "dev-example-bucket"
  }

Plan: 1 to add, 0 to change, 0 to destroy.
==================================================
=== End Plan: dev ===

=== Terraform Plan: project-dev ===
Environment: development
Project: project
Context: atlantis/plan:project-dev
==================================================
[Terraform plan content for project in dev environment]
==================================================
=== End Plan: project-dev ===
```

#### Advantages of Status Check Approach

- **Reliability**: Status checks are more reliable than comment parsing
- **Completeness**: Access to full plan information from Atlantis
- **Multiple Projects**: Support for multiple projects/environments in a single PR
- **Real-time**: Status checks are updated in real-time as plans complete
- **Structured Data**: More structured approach than HTML comment parsing

### Example Plan Detection

```bash
# Test Terraform plan extraction
python test_terraform_plan.py
```

This will show:
- Plan length and preview
- Detection of continuation patterns
- Debug information if no plan is found

For a PR like [TrueLayer/terraform-ops#23680](https://github.com/TrueLayer/terraform-ops/pull/23680):

- **Type**: Provider update
- **Changes**: Adding new S3 bucket field (non-breaking)
- **Environment**: Development
- **Confidence Score**: 100%
- **Result**: Auto-merge enabled

### Test PRs Configuration

You can specify specific PRs for AI testing in your configuration:

```json
{
  "test_prs": [
    {
      "repo": "terraform-ops",
      "pr_number": 23680
    },
    {
      "repo": "terraform-aws",
      "pr_number": 123
    }
  ]
}
```

These PRs will be analyzed for AI confidence scores regardless of their merge status, making them perfect for testing the AI functionality.

### Error Handling

The system includes robust error handling:

- **AI Service Unavailable**: Falls back to pattern-based analysis
- **Network Errors**: Logs errors and continues with fallback
- **Invalid Responses**: Uses default confidence scores
- **Configuration Errors**: Disables AI features gracefully

### Testing AI Features

Run the AI feature tests:

```bash
python -m unittest tests.test_ai_confidence -v
```

Or test the complete functionality:

```bash
python test_ai_example.py
```

### Testing Test PRs Feature

Run the test PRs feature tests:

```bash
python -m unittest tests.test_test_prs -v
```

Or test the complete functionality:

```bash
python test_test_prs_example.py
```

## Esempi di Utilizzo

### Configurazione Completa con AI Integrato

```json
{
  "access_token": "your_github_token",
  "filters": [
    "^\\[DEPENDENCIES\\] Update Terraform",
    "^\\[DEPENDABOT\\]"
  ],
  "github_user": "your_user",
  "owner": "your_org",
  "repos": [
    "terraform-vault",
    "terraform-aws",
    "terraform-ops",
    "terraform-k8s"
  ],
  "enable_ai_confidence_score": true,
  "enable_ai_automerge_action": true,
  "disable_pr_comments": false,
  "ai_repos": [
    "terraform-ops",
    "terraform-k8s"
  ],
  "ai_provider": "claude-code",
  "ai_config": {
    "claude-code": {
      "api_base": "https://api.anthropic.com",
      "api_key": "your_anthropic_api_key",
      "model": "claude-sonnet-4"
    }
  }
}
```

### Flusso di Esecuzione Integrato

```
📊 Processing all repositories...

🔍 Analyzing PRs in terraform-vault...
   - PR 123: No changes detected → Ready for merge
   - PR 124: Has diffs → Standard unlock process

🔍 Analyzing PRs in terraform-aws...
   - PR 125: No comments → Triggering plan
   - PR 126: Error in plan → Triggering plan

🔍 Analyzing PRs in terraform-ops (AI-enabled)...
   - PR 127: Has diffs → AI analysis triggered
     🤖 Processing AI analysis for PR 127 in repo terraform-ops (AI-enabled repo)
     📋 Manual merge required for PR 127 (confidence: 85%, dev: false)
     → Standard unlock process

🔍 Analyzing PRs in terraform-k8s (AI-enabled)...
   - PR 128: Has diffs → AI analysis triggered
     🤖 Processing AI analysis for PR 128 in repo terraform-k8s (AI-enabled repo)
     🚀 Auto-merging PR 128 (100% confidence, dev environment)
     → Auto-merge completed, skip standard unlock

✅ Processing completed
```

### Logica di Integrazione

1. **Categorizzazione Standard**
   - Tutte le PR vengono categorizzate normalmente
   - `pr_with_diffs`: PR con cambiamenti che necessitano review

2. **AI Analysis per Repo Configurati**
   - Solo per repo in `ai_repos` e quando `enable_ai_confidence_score: true`
   - Controllo se AI comment già esistente (evita duplicati)
   - Recupero piano Terraform dai commenti

3. **Validazione Piano**
   - **Nessun piano**: Commento di errore AI
   - **Piano in corso**: Commento di errore AI
   - **Lock conflict**: Commento di errore AI
   - **Errori piano**: Commento di errore AI
   - **Piano valido**: Analisi AI

4. **Auto-Merge Decision**
   - **100% confidence + ambiente dev**: Auto-merge immediato
   - **Altri casi**: Standard unlock process

### Vantaggi della Nuova Architettura

1. **Integrazione Seamless**
   - Nessun ciclo separato
   - Nessun tempo di attesa aggiuntivo
   - Mantiene comportamento esistente per repo non-AI

2. **Efficienza**
   - Processing singolo per tutte le PR
   - AI analysis solo quando necessario
   - Evita duplicazione di analisi

3. **Flessibilità**
   - Configurazione per repo specifici
   - Attivazione/disattivazione per ambiente
   - Fallback graceful su errori

4. **Robustezza**
   - Gestione errori dettagliata
   - Continuità servizio anche con problemi AI
   - Logging completo per debugging

### Messaggi di Output

#### AI Analysis Avviata
```
🤖 Processing AI analysis for PR 127 in repo terraform-ops (AI-enabled repo)
```

#### Auto-Merge Eseguito
```
🚀 Auto-merging PR 128 (100% confidence, dev environment)
```

#### Manual Merge Richiesto
```
📋 Manual merge required for PR 127 (confidence: 85%, dev: false)
```

#### Errore AI
```
❌ Error during AI analysis for PR 127: Network timeout
```

### Casi d'Uso

#### Ambiente di Sviluppo
```json
{
  "enable_ai_automerge_action": true,
  "ai_repos": ["terraform-ops", "terraform-k8s"],
  "disable_pr_comments": true
}
```

#### Ambiente di Produzione
```json
{
  "enable_ai_automerge_action": false,
  "ai_repos": ["terraform-ops"],
  "disable_pr_comments": false
}
```

#### Testing
```json
{
  "enable_ai_confidence_score": true,
  "enable_ai_automerge_action": false,
  "ai_repos": ["terraform-ops"],
  "test_prs": [
    {"repo": "terraform-ops", "pr_number": 23680}
  ]
}
```

### Disabilitazione Commenti PR

Il parametro `disable_pr_comments` permette di controllare dove viene mostrata l'analisi AI:

#### Con commenti abilitati (comportamento predefinito)
```json
{
  "enable_ai_confidence_score": true,
  "disable_pr_comments": false,
  "ai_provider": "claude-code"
}
```

**Risultato**: L'analisi AI viene postata come commento sulla PR e stampata sul terminale.

#### Con commenti disabilitati
```json
{
  "enable_ai_confidence_score": true,
  "disable_pr_comments": true,
  "ai_provider": "claude-code"
}
```

**Risultato**: L'analisi AI viene stampata solo sul terminale, nessun commento viene aggiunto alla PR.

#### Output del Terminale con Commenti Disabilitati
```
🤖 AI Confidence Score Analysis for PR 123 in repo terraform-ops:
   Confidence Score: 85%
   Explanation: This is a safe update to the Terraform provider that only adds new fields without breaking changes
   Environment: Development
   Auto-merge Status: ❌ Disabled
   AI Provider: Claude Code (claude-sonnet-4)
   Token Usage: 150 input, 75 output
   ---
   *This analysis was performed by Claude Code AI to assess the safety of automatic merging.*
PR 123 in repo terraform-ops: AI Confidence Score 85% - ❌ Disabled
```

### Messaggi di Errore AI

#### Nessun Piano Trovato
```
🤖 AI Confidence Score Analysis Failed for PR 128 in repo terraform-ops:
   Status: ❌ AI Analysis Failed
   Reason: No Terraform plan found
   Details: Atlantis has not yet generated a plan for this PR, or the plan has been deleted.
   Recommendation: Wait for Atlantis to complete the plan or trigger a new plan manually.
   ---
   *AI analysis could not be performed due to the above issue. Please check the PR status and try again later.*
```

#### Piano in Corso
```
🤖 AI Confidence Score Analysis Failed for PR 129 in repo terraform-ops:
   Status: ❌ AI Analysis Failed
   Reason: Plan still in progress
   Details: Atlantis is still running the plan for this PR.
   Recommendation: Wait for the plan to complete before AI analysis can be performed.
   ---
   *AI analysis could not be performed due to the above issue. Please check the PR status and try again later.*
```

#### Conflitto di Lock
```
🤖 AI Confidence Score Analysis Failed for PR 130 in repo terraform-k8s:
   Status: ❌ AI Analysis Failed
   Reason: Lock conflict detected
   Details: Another PR has acquired the lock for this project.
   Recommendation: Wait for the other PR to complete or unlock the project manually.
   ---
   *AI analysis could not be performed due to the above issue. Please check the PR status and try again later.*
```

#### Errore nel Piano
```
🤖 AI Confidence Score Analysis Failed for PR 132 in repo terraform-ops:
   Status: ❌ AI Analysis Failed
   Reason: Plan error detected
   Details: The Terraform plan contains errors that need to be resolved.
   Recommendation: Fix the Terraform configuration issues and re-run the plan.
   ---
   *AI analysis could not be performed due to the above issue. Please check the PR status and try again later.*
```

### Quando usare `disable_pr_comments: true`
- **Testing**: Durante lo sviluppo e test delle funzionalità AI
- **Debugging**: Per analizzare l'output AI senza cluttering le PR
- **Ambienti di sviluppo**: Dove non vuoi commenti permanenti sulle PR
- **Analisi batch**: Quando analizzi molte PR e vuoi solo i risultati sul terminale

### Quando usare `disable_pr_comments: false` (predefinito)
- **Produzione**: Quando vuoi che l'analisi AI sia visibile ai team
- **Collaborazione**: Quando altri sviluppatori devono vedere l'analisi AI
- **Audit**: Quando vuoi tracciare le decisioni AI nelle PR
- **Trasparenza**: Quando vuoi che le decisioni di auto-merge siano documentate

## Usage
### Options
```bash
options:
  -h, --help            show this help message and exit
  --config_file CONFIG_FILE
                        JSON file holding the GitHub access token, default is .config.json
  --approve_all         Approves all PRs that match the filters in the config
  --log_level {DEBUG,INFO,WARNING,ERROR}
                        Set logging level (DEBUG, INFO, WARNING, ERROR)
```

### Python
Create a config file (by default it should be placed in ./config.json)
And run the following:
```bash
# Install dependencies
pip3 install -r requirements.txt
# Run it
python3 main.py
```

### Docker
```bash
docker run -d -v ./config.json:/app/config.json --name automerge alessiocasco/automerge:latest
```

### Helm
Move to `/charts/automerge`, tune your `values.yaml` file and run:
```
helm install -f values.yaml automerge -n <your_namespace> .
```

The Helm chart supports AI features via environment variables:

```yaml
job:
  env:
    - name: ENABLE_AI_CONFIDENCE_SCORE
      value: "false"
    - name: ENABLE_AI_AUTOMERGE_ACTION
      value: "false"
```

## Testing and Development

### Manual Testing Commands
```bash
# Install dependencies (including coverage)
pip install -r requirements.txt

# Run tests only
python -m unittest discover -s ./tests -p 'test_*.py' -v
```
### Manual Coverage Commands
```bash
# Run tests with coverage
coverage run -m unittest discover -s ./tests -p 'test_*.py'

# Generate coverage report
coverage report

# Generate HTML coverage report
coverage html
```
### Manual ruff Commands
```bash
# Run code linting
ruff check .

# Auto-fix linting issues
ruff check . --fix
```

### Running Specific Tests
```bash
# Run tests for a specific module
python -m unittest tests.test_config -v

# Run a specific test class
python -m unittest tests.test_github_client.TestIsApproved -v

# Run a single test method
python -m unittest tests.test_config.TestValidateConfig.test_validate_config_success -v

# Run tests matching a pattern
python -m unittest discover -s ./tests -p 'test_github*' -v

# Run tests with verbose output
python -m unittest discover -s ./tests -p 'test_*.py' -v

# Run tests and stop on first failure
python -m unittest discover -s ./tests -p 'test_*.py' --failfast

# Run AI confidence score tests
python -m unittest tests.test_ai_confidence -v

# Run test PRs tests
python -m unittest tests.test_test_prs -v
```

### Continuous Integration
The project uses GitHub Actions for CI/CD with:
- **Python Coverage Comment Action**: Automatically comments coverage reports on PRs
- **Multi-version testing**: Tests against Python 3.9, 3.10, 3.11, and 3.12
- **Code linting**: Uses Ruff for code quality checks
- **Coverage reporting**: Generates detailed coverage reports

Coverage reports are automatically generated and commented on pull requests, helping maintain code quality standards.

### Coverage Configuration

The project uses a `.coveragerc` file to configure coverage reporting:

```ini
[run]
source = src
relative_files = true
omit = tests/*, .venv/*, venv/*, */site-packages/*

[report]
show_missing = True
precision = 2

[html]
directory = htmlcov

[xml]
output = coverage.xml
```

Key settings:
- **`relative_files = true`**: Required for GitHub Actions integration
- **`source = src`**: Only measure coverage for source code
- **`omit`**: Exclude test files and virtual environments

### Test File Organization

The test suite is organized in the `tests/` directory with the following structure:

```
tests/
├── test_config.py          # Configuration loading and validation tests
├── test_github_client.py   # GitHub API interaction tests
├── test_pr_processor.py    # Pull request processing logic tests
├── test_utils.py           # Utility function tests
├── test_main.py            # Main application tests
├── test_dismissed_prs.py   # Dismissed PR handling tests
├── test_conf.py            # Test utilities and mock objects
├── test_ai_confidence.py   # AI confidence score feature tests
└── test_test_prs.py        # Test PRs feature tests
```

**Test Naming Conventions:**
- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<functionality>_<scenario>`

**Example Test Structure:**
```python
class TestGitHubClient(unittest.TestCase):
    def setUp(self):
        # Test setup code

    def test_is_approved_true(self):
        # Test when PR is approved

    def test_is_approved_false(self):
        # Test when PR is not approved

    def test_is_approved_error_handling(self):
        # Test error scenarios
```

This includes additional tools like:
- **pytest**: Alternative test runner
- **black**: Code formatter
- **mypy**: Type checking
- **pre-commit**: Git hooks
- **sphinx**: Documentation generation

### Development Workflow
1. Make your changes
2. Run tests: `python run_tests.py --full_no_web`
3. Fix any linting issues: `ruff check . --fix`
4. Commit your changes
5. Create a pull request (coverage will be automatically reported)

## Usage
This tool is intended to run as a k8s cronjob during the night; every ~15 minutes for a couple of hours so it can close as many pull requests as possible.
Something like:
```cron
*/20 3-5 * * *
```

## What it does at every run:
* Gets all pull requests from every repo listed in the config
* Filters out the ones that don't have the prefix set in the config
  * If the pull request is new and has no comments:
    * Syncs the branch with master if needed, waits for all the checks to pass and finally writes `atlantis plan` as a comment into the pull request
  * If the pull request is planned and has no diffs:
    * Approves the pull request and merges it
  * If the pull request is planned and has diffs:
    * Writes comment `This PR will be ignored by automerge` into the pull request, unlocks it and sets an `automerge_ignore` label.
    * All future runs of Automerge will ignore this pull request (see option `--force` to override this)
  * If the pull request was planned but had errors:
    * Automerge will try to plan it again
  * If the pull request was planned by no projects were actually planned (Usually happens when the pull request bumps something in a module and Atlantis )
    * Automerge sets the following label `automerge_no_project` and ignores it.

## Ignored pull requests and labels:
Automerge ignores all pull requests having terraform differences or that result in no projects being planned. It marks the first ones with a `automerge_ignore` label and the others with `automerge_no_project`, so you can filter by label with the following GitHub query `is:open label:automerge_ignore ` for example and take action.

## Know issues:
* Automerge does not work really well with repos that have Atlantis set to automatic plan every time there is a change in the code. This conflicts with the syncing from master + the `atlantis plan` comments and may end up with errors shown in the comments.
  * We may add a parameter to the config where we define the behaviour of automerge for specific repos.
    * ie: instead of syncing from master and comment, we can only sync
* Atlantis [doesn't have an API to unlock pull requests](https://github.com/runatlantis/atlantis/issues/733), so we can't unlock everything before starting automerge, this may result in automerge being unable to plan specific pull requests until the lock is manually released. A solution may be to intercept the message, unlock it and plan it on the next run.
