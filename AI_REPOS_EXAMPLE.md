# Esempio di utilizzo della gestione separata dei repo AI

## Configurazione

### Configurazione completa con repo AI separati
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
    "terraform-aws"
  ],
  "enable_ai_confidence_score": true,
  "enable_ai_automerge_action": true,
  "disable_pr_comments": false,
  "ai_repos": [
    "terraform-ops",
    "terraform-k8s"
  ],
  "ai_wait_time_seconds": 300,
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

## Flusso di Esecuzione

### 1. Processing Standard (repo principali)
```
📊 Processing standard repositories: terraform-vault, terraform-aws

🔍 Analyzing PRs in terraform-vault...
   - PR 123: No changes detected → Ready for merge
   - PR 124: Has diffs → Triggering plan

🔍 Analyzing PRs in terraform-aws...
   - PR 125: No comments → Triggering plan
   - PR 126: Error in plan → Triggering plan

✅ Standard processing completed
```

### 2. Attesa per i Piani Atlantis
```
⏳ Waiting 300 seconds for Atlantis plans to complete before AI analysis...
```

### 3. Processing AI (repo AI)
```
🤖 Processing AI repositories: terraform-ops, terraform-k8s

📊 Analyzing PRs in repository: terraform-ops
   - PR 127: Valid plan found → AI analysis completed (85% confidence)
   - PR 128: No plan found → AI failure comment posted
   - PR 129: Plan in progress → AI failure comment posted

📊 Analyzing PRs in repository: terraform-k8s
   - PR 130: Lock conflict → AI failure comment posted
   - PR 131: Valid plan found → AI analysis completed (100% confidence) → Auto-merged
```

## Messaggi di Errore AI

### Nessun Piano Trovato
```
🤖 AI Confidence Score Analysis Failed for PR 128 in repo terraform-ops:
   Status: ❌ AI Analysis Failed
   Reason: No Terraform plan found
   Details: Atlantis has not yet generated a plan for this PR, or the plan has been deleted.
   Recommendation: Wait for Atlantis to complete the plan or trigger a new plan manually.
   ---
   *AI analysis could not be performed due to the above issue. Please check the PR status and try again later.*
```

### Piano in Corso
```
🤖 AI Confidence Score Analysis Failed for PR 129 in repo terraform-ops:
   Status: ❌ AI Analysis Failed
   Reason: Plan still in progress
   Details: Atlantis is still running the plan for this PR.
   Recommendation: Wait for the plan to complete before AI analysis can be performed.
   ---
   *AI analysis could not be performed due to the above issue. Please check the PR status and try again later.*
```

### Conflitto di Lock
```
🤖 AI Confidence Score Analysis Failed for PR 130 in repo terraform-k8s:
   Status: ❌ AI Analysis Failed
   Reason: Lock conflict detected
   Details: Another PR has acquired the lock for this project.
   Recommendation: Wait for the other PR to complete or unlock the project manually.
   ---
   *AI analysis could not be performed due to the above issue. Please check the PR status and try again later.*
```

### Errore nel Piano
```
🤖 AI Confidence Score Analysis Failed for PR 132 in repo terraform-ops:
   Status: ❌ AI Analysis Failed
   Reason: Plan error detected
   Details: The Terraform plan contains errors that need to be resolved.
   Recommendation: Fix the Terraform configuration issues and re-run the plan.
   ---
   *AI analysis could not be performed due to the above issue. Please check the PR status and try again later.*
```

## Vantaggi della Nuova Architettura

### 1. **Separazione delle Responsabilità**
- **Repo principali**: Processing standard con merge immediato
- **Repo AI**: Processing avanzato con analisi AI e auto-merge intelligente

### 2. **Gestione del Timing**
- Attesa configurabile per permettere ad Atlantis di completare i piani
- Evita analisi AI su piani incompleti o in corso

### 3. **Robustezza**
- Gestione dettagliata degli errori con messaggi informativi
- Fallback graceful quando l'AI non può essere utilizzato
- Continuità del servizio anche in caso di problemi AI

### 4. **Flessibilità**
- Configurazione separata per repo diversi
- Tempo di attesa personalizzabile per ambienti diversi
- Possibilità di disabilitare commenti per testing

## Casi d'Uso

### Ambiente di Sviluppo
```json
{
  "ai_wait_time_seconds": 180,  // Attesa più breve
  "enable_ai_automerge_action": true,
  "disable_pr_comments": true   // Solo output terminale
}
```

### Ambiente di Produzione
```json
{
  "ai_wait_time_seconds": 600,  // Attesa più lunga
  "enable_ai_automerge_action": false,  // Solo analisi, no auto-merge
  "disable_pr_comments": false  // Commenti sulle PR
}
```

### Testing
```json
{
  "ai_wait_time_seconds": 30,   // Attesa minima per test
  "test_prs": [
    {"repo": "terraform-ops", "pr_number": 23680}
  ]
}
```
