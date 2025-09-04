# Esempio di utilizzo del parametro `disable_pr_comments`

## Configurazione

### Con commenti abilitati (comportamento predefinito)
```json
{
  "enable_ai_confidence_score": true,
  "disable_pr_comments": false,
  "ai_provider": "claude-code",
  "ai_config": {
    "claude-code": {
      "api_base": "https://api.anthropic.com",
      "api_key": "your_api_key",
      "model": "claude-sonnet-4"
    }
  }
}
```

**Risultato**: L'analisi AI viene postata come commento sulla PR e stampata sul terminale.

### Con commenti disabilitati
```json
{
  "enable_ai_confidence_score": true,
  "disable_pr_comments": true,
  "ai_provider": "claude-code",
  "ai_config": {
    "claude-code": {
      "api_base": "https://api.anthropic.com",
      "api_key": "your_api_key",
      "model": "claude-sonnet-4"
    }
  }
}
```

**Risultato**: L'analisi AI viene stampata solo sul terminale, nessun commento viene aggiunto alla PR.

## Output del Terminale

Quando `disable_pr_comments` è abilitato, vedrai un output come questo:

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

## Casi d'Uso

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

## Note

- L'analisi AI viene sempre eseguita, indipendentemente dal valore di `disable_pr_comments`
- Il parametro influenza solo dove viene mostrato il risultato (PR vs terminale)
- Utile per evitare di riempire le PR con commenti durante i test
- Non influisce sulla logica di auto-merge o altre funzionalità
