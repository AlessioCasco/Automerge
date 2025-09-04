# Esempio di utilizzo della logica AI integrata

## Configurazione

### Configurazione con AI integrato nel ciclo standard
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

## Flusso di Esecuzione Integrato

### Processing Standard con AI Integrato
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

## Logica di Integrazione

### 1. **Categorizzazione Standard**
- Tutte le PR vengono categorizzate normalmente
- `pr_with_diffs`: PR con cambiamenti che necessitano review

### 2. **AI Analysis per Repo Configurati**
- Solo per repo in `ai_repos` e quando `enable_ai_confidence_score: true`
- Controllo se AI comment già esistente (evita duplicati)
- Recupero piano Terraform dai commenti

### 3. **Validazione Piano**
- **Nessun piano**: Commento di errore AI
- **Piano in corso**: Commento di errore AI
- **Lock conflict**: Commento di errore AI
- **Errori piano**: Commento di errore AI
- **Piano valido**: Analisi AI

### 4. **Auto-Merge Decision**
- **100% confidence + ambiente dev**: Auto-merge immediato
- **Altri casi**: Standard unlock process

## Vantaggi della Nuova Architettura

### 1. **Integrazione Seamless**
- Nessun ciclo separato
- Nessun tempo di attesa aggiuntivo
- Mantiene comportamento esistente per repo non-AI

### 2. **Efficienza**
- Processing singolo per tutte le PR
- AI analysis solo quando necessario
- Evita duplicazione di analisi

### 3. **Flessibilità**
- Configurazione per repo specifici
- Attivazione/disattivazione per ambiente
- Fallback graceful su errori

### 4. **Robustezza**
- Gestione errori dettagliata
- Continuità servizio anche con problemi AI
- Logging completo per debugging

## Messaggi di Output

### AI Analysis Avviata
```
🤖 Processing AI analysis for PR 127 in repo terraform-ops (AI-enabled repo)
```

### Auto-Merge Eseguito
```
🚀 Auto-merging PR 128 (100% confidence, dev environment)
```

### Manual Merge Richiesto
```
📋 Manual merge required for PR 127 (confidence: 85%, dev: false)
```

### Errore AI
```
❌ Error during AI analysis for PR 127: Network timeout
```

## Casi d'Uso

### Ambiente di Sviluppo
```json
{
  "enable_ai_automerge_action": true,
  "ai_repos": ["terraform-ops", "terraform-k8s"],
  "disable_pr_comments": true
}
```

### Ambiente di Produzione
```json
{
  "enable_ai_automerge_action": false,
  "ai_repos": ["terraform-ops"],
  "disable_pr_comments": false
}
```

### Testing
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

## Note Importanti

- **Duplicazione**: Il sistema evita commenti AI duplicati controllando se già esistono
- **Fallback**: In caso di errori AI, il sistema continua con il processing standard
- **Performance**: Nessun impatto su repo non configurati per AI
- **Compatibilità**: Mantiene piena compatibilità con configurazioni esistenti
