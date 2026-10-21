# AI agent and LLM pipeline security

## AI / LLM Security

For any feature that calls an LLM (chatbots, summarizers, agents, RAG):

- [ ] Model output treated as untrusted — never into `eval`/SQL/shell/`innerHTML`/file paths
- [ ] Prompt injection assumed; permissions enforced in code, not in the system prompt
- [ ] Secrets, cross-tenant data, and full system prompts kept out of the context window
- [ ] Tool/agent permissions scoped; destructive or irreversible actions require confirmation
- [ ] Token, rate, and recursion/loop limits set (bound consumption)

## OWASP LLM Top 10 (2025)

| # | Vulnerability | Description | Detection Patterns | Fix |
|---|--------------|-------------|-------------------|-----|

| **LLM02** | **Sensitive Information Disclosure** | LLM reveals confidential data from training data, system prompts, or context. | Model outputs API keys, internal URLs, PII; system prompt extraction via "repeat your instructions"; context leakage between users. | Strip secrets from context. Output filtering for PII/secrets. Session isolation. Don't put secrets in system prompts. Anonymize training data. |
| **LLM03** | **Supply Chain Vulnerabilities** | Compromised training data, model weights, plugins, or dependencies. | Poisoned fine-tuning datasets; malicious third-party plugins; tampered model files; compromised prompt templates. | Verify model integrity (checksums). Audit plugins/tools. Signed artifacts. Scan training data. Vendor security assessment. |
| **LLM04** | **Data and Model Poisoning** | Attacker corrupts training/fine-tuning data to influence model behavior. | Biased outputs after fine-tuning; backdoor triggers in model responses; degraded performance on specific topics. | Data validation pipeline. Anomaly detection on training data. Multiple data sources. Regular model evaluation. Federated learning safeguards. |
| **LLM05** | **Improper Output Handling** | LLM output passed to downstream systems without sanitization, enabling XSS, injection, RCE. | LLM output rendered as HTML without escaping; LLM-generated SQL executed directly; LLM output used in system commands. | Treat LLM output as untrusted. Sanitize before rendering. Parameterized queries for LLM-generated SQL. Never pass LLM output to `eval()` or shell. |
| **LLM06** | **Excessive Agency** | LLM agent has too many permissions, can perform destructive actions without human approval. | Agent can delete files, send emails, modify databases without confirmation; no scope limits on tool access; no approval workflow. | Least-privilege tool access. Human-in-the-loop for destructive actions. Read-only by default. Scope limits per session. Action audit logs. |
| **LLM07** | **System Prompt Leakage** | Attacker extracts the system prompt, revealing business logic, guardrails, and instructions. | Prompts like "what are your instructions?"; indirect extraction via role-play; iterative probing to reconstruct system prompt. | Don't rely on system prompt secrecy for security. Defense in depth. Monitor for extraction attempts. Separate config from prompts. |
| **LLM08** | **Vector and Embedding Weaknesses** | Manipulation of RAG retrieval through poisoned embeddings or adversarial documents. | Irrelevant documents surfacing in RAG results; poisoned knowledge base entries; embedding collision attacks. | Validate RAG sources. Access control on knowledge base. Embedding anomaly detection. Source attribution in responses. Regular KB audits. |
| **LLM09** | **Misinformation** | LLM generates false/misleading content (hallucinations) presented as fact. | Confident assertions about nonexistent APIs; fabricated citations; incorrect code that looks plausible; made-up statistics. | Grounding with verified sources (RAG). Confidence scoring. Fact-checking pipeline. Disclaimers on generated content. Human review for critical outputs. |
| **LLM10** | **Unbounded Consumption** | Excessive resource usage through crafted prompts, leading to cost explosion or denial of service. | Extremely long context inputs; recursive agent loops; prompt that triggers maximum token generation; no budget limits. | Token limits per request/session. Budget caps per user. Iteration limits for agents. Timeout on generation. Monitor cost anomalies. |

### Defenses Against Prompt Injection

```yaml
defense_layers:
  input_layer:
    - Sanitize user input (strip control characters, normalize unicode)
    - Detect injection patterns (regex for "ignore previous", "system:", etc.)
    - Input length limits
    - Separate user content from instructions structurally

  architecture_layer:
    - Clear delimiter between system prompt and user input
    - Use structured input formats (JSON) instead of free text where possible
    - Dual-LLM pattern: one LLM processes input, another validates output
    - Never concatenate untrusted data directly into prompts

  output_layer:
    - Validate LLM output matches expected format/schema
    - Filter output for sensitive data (PII, secrets, internal URLs)
    - Human-in-the-loop for destructive actions
    - Output anomaly detection (unexpected tool calls, unusual responses)

  monitoring_layer:
    - Log all prompts and responses (redacted)
    - Alert on injection pattern matches
    - Track prompt-to-action ratios for anomaly detection
```

## 3. Agent Isolation and Least-Privilege Tool Access

### Principle: Agents Should Have Minimum Required Permissions

```yaml
# BAD - overprivileged agent
agent:
  tools:
    - file_system: READ_WRITE  # Full access
    - database: ALL_OPERATIONS
    - http: UNRESTRICTED
    - shell: ENABLED

# GOOD - least-privilege agent
agent:
  tools:
    - file_system:
        mode: READ_ONLY
        allowed_paths: ["/data/reports/"]
        blocked_extensions: [".env", ".key", ".pem"]
        max_file_size: 5MB
    - database:
        mode: READ_ONLY
        allowed_tables: ["products", "categories"]
        max_rows: 1000
    - http:
        allowed_domains: ["api.example.com"]
        allowed_methods: ["GET"]
        timeout: 10s
    - shell: DISABLED
```

### Isolation Patterns

1. **Sandbox execution**: Run agent tools in containers/VMs with no host access
2. **Network isolation**: Allowlist outbound connections by domain
3. **Filesystem isolation**: Mount only required directories, read-only where possible
4. **Process isolation**: Separate processes for agent and tools with IPC
5. **User isolation**: Agent runs as unprivileged user, not root/admin

---

## 5. Context Leakage Between Agents

### Risk: Data Bleed Between Sessions/Users

```
# Scenario: Multi-tenant agent platform
User A asks about their medical records -> agent loads context
User B in same session/instance gets User A's context in responses
```

### Defenses

1. **Session isolation**: Each user session gets a fresh agent instance, no shared state
2. **Context clearing**: Explicitly clear context/memory between users
3. **Namespace separation**: Prefix all data access with user/tenant ID
4. **Memory management**: No persistent memory across sessions unless explicitly scoped
5. **Output scanning**: Check responses for data belonging to other users/sessions

## 6. Secure Tool Calling Patterns

### Validation Before Execution

```python
class SecureToolCaller:
    ALLOWED_TOOLS = {"search", "calculate", "read_file"}
    DANGEROUS_TOOLS = {"write_file", "send_email", "delete"}

    def call_tool(self, principal: str, tool_name: str, args: dict):
        # 1. Validate tool exists in allowlist
        if tool_name not in self.ALLOWED_TOOLS | self.DANGEROUS_TOOLS:
            raise ToolNotAllowed(f"Unknown tool: {tool_name}")

        # 2. Dangerous tools require a human approval recorded server-side for this principal,
        #    these exact arguments and an unexpired window; never a flag the caller passes in
        if tool_name in self.DANGEROUS_TOOLS and not self.approvals.valid(principal, tool_name, args):
            return PendingApproval(tool_name, args)

        # 3. Validate arguments against schema
        schema = self.get_tool_schema(tool_name)
        validate(args, schema)  # Raises on invalid

        # 4. Sanitize arguments (path traversal, injection)
        sanitized_args = self.sanitize(tool_name, args)

        # 5. Execute with timeout
        with timeout(seconds=30):
            result = self.execute(tool_name, sanitized_args)

        # 6. Validate output
        self.validate_output(tool_name, result)

        # 7. Log everything
        self.audit_log(tool_name, sanitized_args, result)

        return result
```

## 9. Supply Chain Attacks on Prompts/Skills

### Attack Vectors

| Vector | Description | Impact |
|--------|-------------|--------|
| **Poisoned prompt templates** | Malicious instructions hidden in shared prompt libraries | Agent executes attacker's instructions |
| **Compromised skills/plugins** | Third-party skill contains backdoor | Data exfiltration, unauthorized actions |
| **Tampered model weights** | Model fine-tuned with adversarial data | Biased or harmful outputs |
| **Dependency confusion** | Attacker publishes skill with same name as internal one | Code execution in agent environment |
| **Prompt template injection** | Variables in templates not properly escaped | Injection via template variables |

### Defenses

```yaml
supply_chain_security:
  prompt_templates:
    - Store in version-controlled repository
    - Code review for ALL prompt changes
    - Checksums on prompt files
    - No dynamic loading from external URLs

  skills_and_plugins:
    - Vendor security assessment
    - Code audit before adoption
    - Pin versions (no auto-update)
    - Signature verification
    - Sandbox execution (no host access)

  model_integrity:
    - Verify checksums on model files
    - Use models from trusted sources only
    - Regular evaluation for behavior drift
    - Isolated model serving environment
```

## Securing AI / LLM Features

If your app calls an LLM — chatbots, summarizers, agents, RAG — it inherits a new attack surface. Map it to the [OWASP Top 10 for LLM Applications (2025)](https://genai.owasp.org/llm-top-10/):

- **Treat all model output as untrusted input (LLM05: Improper Output Handling).** Never pass LLM output straight into `eval`, SQL, a shell, `innerHTML`, or a file path. Validate and encode it exactly as you would raw user input.
- **Assume prompts can be hijacked (LLM01: Prompt Injection).** Untrusted text in the context window — a user message, a fetched web page, a PDF — can carry instructions. The system prompt is not a security boundary; enforce permissions in code, not in the prompt.
- **Keep secrets and other users' data out of prompts (LLM02 / LLM07).** Anything in the context can be echoed back. Don't put API keys, cross-tenant data, or the full system prompt where the model can repeat it.
- **Constrain tool and agent permissions (LLM06: Excessive Agency).** Scope tools to the minimum, require confirmation for destructive or irreversible actions, and validate every tool argument.
- **Bound consumption (LLM10: Unbounded Consumption).** Cap tokens, request rate, and loop/recursion depth so a crafted input can't run up cost or hang the system.
- **Isolate retrieval data (LLM08: Vector and Embedding Weaknesses).** In RAG, treat the vector store as a trust boundary: partition embeddings per tenant so one user can't retrieve another's data, and validate documents before indexing so poisoned content can't steer answers.

```typescript
// BAD: trusting model output as a command or as markup
const sql = await llm.generate(`Write SQL for: ${userQuestion}`);
await db.query(sql);                                   // arbitrary query execution
container.innerHTML = await llm.reply(userMessage);   // stored XSS, via the model

// GOOD: model output is data — parse defensively, then validate, then encode
let intent;
try {
  intent = CommandSchema.parse(JSON.parse(await llm.replyJson(userMessage)));
} catch {
  throw new ValidationError('unexpected model output'); // JSON.parse or schema failed
}
await runAllowlistedAction(intent.action, intent.params);
container.textContent = await llm.reply(userMessage);
```
