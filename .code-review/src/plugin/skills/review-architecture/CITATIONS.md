# CITATIONS: review-architecture

Everything in `SKILL.md` was cut by line range from the files under `AGENTS/PLUGINS/` (paths below are relative to that folder), except the lines marked "own" and the frontmatter, `## Working method` and `## Output contract`, which were kept byte for byte from the earlier `SKILL.md`. Blank lines at the edges of each cut were trimmed and one blank line was put between cuts; nothing else inside a cut was changed unless the row says so.

The frontmatter had to stay on the first lines of the file, so it is not last. The `## Working method` and `## Output contract` sections are the last two sections, in that order.

## Part 1: Passages

| SKILL.md lines | Part heading | Source folder | File | Source lines | Status |
|---|---|---|---|---|---|
| 1-4 | frontmatter | (earlier SKILL.md) | SKILL.md | 1-4 | verbatim, kept byte for byte |
| 6-6 | heading | - | - | - | own text, not from any source |
| 8-8 | severity mapping and scope note (my joining text) | - | - | - | own text, not from any source |
| 10-10 | heading | - | - | - | own text, not from any source |
| 12-14 | Scope of an architecture review | brooks-lint-marketplace | skills/brooks-review/pr-review-guide.md | 10-12 | changed: removed `Note in the report which files were skipped and why.` |
| 16-18 | Scope of an architecture review | brooks-lint-marketplace | skills/brooks-review/pr-review-guide.md | 35-37 | verbatim |
| 20-20 | Scope of an architecture review | ce-code-review | SKILL.md | 9-9 | verbatim |
| 22-22 | heading | - | - | - | own text, not from any source |
| 24-26 | Whole-system structure | brooks-lint-marketplace | skills/brooks-audit/architecture-guide.md | 7-9 | verbatim |
| 28-34 | Whole-system structure | brooks-lint-marketplace | skills/brooks-audit/architecture-guide.md | 41-47 | verbatim |
| 36-45 | Whole-system structure | brooks-lint-marketplace | skills/brooks-audit/architecture-guide.md | 97-106 | changed: removed `(any `-.->|circular|` edge in the map above)` |
| 47-68 | Whole-system structure | brooks-lint-marketplace | skills/brooks-audit/architecture-guide.md | 108-129 | verbatim |
| 70-72 | Whole-system structure | brooks-lint-marketplace | skills/brooks-audit/architecture-guide.md | 132-135 | verbatim |
| 74-95 | Whole-system structure | brooks-lint-marketplace | skills/brooks-audit/architecture-guide.md | 137-158 | verbatim |
| 97-114 | Whole-system structure | brooks-lint-marketplace | skills/brooks-audit/architecture-guide.md | 160-177 | verbatim |
| 116-118 | Whole-system structure | brooks-lint-marketplace | skills/brooks-sweep/sweep-guide.md | 148-153 | changed: replaced `Scan the full scope for architecture-level issues. The dependency-direction\nsymptoms (inverted dependencies, circular imports, cross-domain coupling) are\ndefined in `../_shared/decay-risks.md` Risk 5 — use that checklist. Step 5\nadditionally covers architecture-only concerns that R5 does not: missing` with `Architecture-level concerns beyond dependency direction: missing` |
| 120-120 | heading | - | - | - | own text, not from any source |
| 122-168 | Coupling and change propagation | brooks-lint-marketplace | skills/_shared/decay-risks.md | 54-100 | verbatim |
| 170-204 | Coupling and change propagation | brooks-lint-marketplace | skills/_shared/decay-risks.md | 104-138 | verbatim |
| 206-215 | Coupling and change propagation | brooks-lint-marketplace | skills/brooks-review/pr-review-guide.md | 39-48 | verbatim |
| 217-222 | Coupling and change propagation | brooks-lint-marketplace | skills/brooks-review/pr-review-guide.md | 60-65 | verbatim |
| 224-224 | heading | - | - | - | own text, not from any source |
| 226-268 | Dependency direction and cycles | brooks-lint-marketplace | skills/_shared/decay-risks.md | 186-228 | verbatim |
| 270-277 | Dependency direction and cycles | brooks-lint-marketplace | skills/brooks-review/pr-review-guide.md | 74-81 | verbatim |
| 279-280 | Dependency direction and cycles | codebase-audit-suite | skills-catalog/ln-644-dependency-graph-auditor/SKILL.md | 21-22 | verbatim |
| 282-282 | Dependency direction and cycles | codebase-audit-suite | skills-catalog/ln-644-dependency-graph-auditor/SKILL.md | 24-24 | verbatim |
| 284-287 | Dependency direction and cycles | codebase-audit-suite | skills-catalog/ln-644-dependency-graph-auditor/SKILL.md | 208-211 | verbatim |
| 289-296 | Dependency direction and cycles | codebase-audit-suite | skills-catalog/ln-644-dependency-graph-auditor/SKILL.md | 390-397 | verbatim |
| 298-318 | Dependency direction and cycles | codebase-audit-suite | skills-catalog/ln-644-dependency-graph-auditor/references/dependency_rules.md | 14-34 | verbatim |
| 320-448 | Dependency direction and cycles | codebase-audit-suite | skills-catalog/ln-644-dependency-graph-auditor/references/dependency_rules.md | 36-164 | verbatim |
| 450-521 | Dependency direction and cycles | codebase-audit-suite | skills-catalog/ln-644-dependency-graph-auditor/references/graph_metrics.md | 6-77 | verbatim |
| 523-532 | Dependency direction and cycles | codebase-audit-suite | skills-catalog/ln-644-dependency-graph-auditor/references/import_patterns.md | 118-127 | verbatim |
| 534-534 | heading | - | - | - | own text, not from any source |
| 536-580 | Layers, module boundaries and design patterns | architecture-patterns | SKILL.md | 24-68 | verbatim |
| 582-606 | Layers, module boundaries and design patterns | architecture-patterns | SKILL.md | 127-151 | changed: removed ` (see Testing section above)` |
| 608-612 | Layers, module boundaries and design patterns | architecture-patterns | references/advanced-patterns.md | 222-226 | verbatim |
| 614-622 | Layers, module boundaries and design patterns | architecture-patterns | references/advanced-patterns.md | 265-273 | verbatim |
| 624-644 | Layers, module boundaries and design patterns | architecture-patterns | references/advanced-patterns.md | 363-383 | verbatim |
| 646-654 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-640-pattern-evolution-auditor/references/layer_rules.md | 9-17 | verbatim |
| 656-667 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-640-pattern-evolution-auditor/references/layer_rules.md | 19-30 | verbatim |
| 669-674 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-640-pattern-evolution-auditor/references/layer_rules.md | 32-37 | verbatim |
| 676-684 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-640-pattern-evolution-auditor/references/layer_rules.md | 39-47 | verbatim |
| 686-696 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-640-pattern-evolution-auditor/references/layer_rules.md | 56-66 | verbatim |
| 698-700 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-642-layer-boundary-auditor/SKILL.md | 108-110 | verbatim |
| 702-718 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-642-layer-boundary-auditor/SKILL.md | 121-137 | verbatim |
| 720-722 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-642-layer-boundary-auditor/SKILL.md | 141-143 | verbatim |
| 724-731 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-642-layer-boundary-auditor/SKILL.md | 152-159 | verbatim |
| 733-735 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-642-layer-boundary-auditor/SKILL.md | 163-166 | verbatim |
| 737-744 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-642-layer-boundary-auditor/SKILL.md | 169-176 | verbatim |
| 746-747 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-642-layer-boundary-auditor/SKILL.md | 248-249 | verbatim |
| 749-749 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-642-layer-boundary-auditor/SKILL.md | 252-252 | verbatim |
| 751-1021 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-640-pattern-evolution-auditor/references/pattern_library.md | 41-311 | changed: removed ` (per `shared/references/ai_ready_architecture.md`)` |
| 1023-1034 | Layers, module boundaries and design patterns | codebase-audit-suite | skills-catalog/ln-640-pattern-evolution-auditor/references/pattern_library.md | 352-365 | changed: removed `Used by ln-640 Phase 1c to suggest patterns that COULD improve architecture.\n\n` |
| 1036-1036 | heading | - | - | - | own text, not from any source |
| 1038-1043 | API and data contracts | ce-code-review | references/personas/api-contract-reviewer.md | 7-12 | verbatim |
| 1045-1060 | API and data contracts | ce-code-review | references/personas/api-contract-reviewer.md | 14-31 | changed: removed `Use the anchored confidence rubric in the subagent template. Persona-specific guidance:\n\n`; removed `, or when synthesis moves it to a soft bucket (`testing_gaps`, `residual_risks`, or advisory)` |
| 1062-1062 | API and data contracts | ce-code-review | references/personas/data-migration-reviewer.md | 9-9 | verbatim |
| 1064-1064 | API and data contracts | ce-code-review | references/personas/data-migration-reviewer.md | 52-52 | verbatim |
| 1066-1066 | API and data contracts | ce-code-review | references/personas/data-migration-reviewer.md | 54-54 | verbatim |
| 1068-1068 | API and data contracts | ce-code-review | references/personas/data-migration-reviewer.md | 56-56 | verbatim |
| 1070-1077 | API and data contracts | codebase-audit-suite | skills-catalog/ln-643-api-contract-auditor/SKILL.md | 63-71 | changed: removed ` Exclusions per `shared/references/ai_ready_architecture.md`` |
| 1079-1080 | API and data contracts | codebase-audit-suite | skills-catalog/ln-652-transaction-correctness-auditor/SKILL.md | 151-152 | verbatim |
| 1082-1091 | API and data contracts | codebase-audit-suite | skills-catalog/ln-652-transaction-correctness-auditor/SKILL.md | 164-173 | verbatim |
| 1093-1101 | API and data contracts | codebase-audit-suite | skills-catalog/ln-652-transaction-correctness-auditor/SKILL.md | 175-183 | verbatim |
| 1103-1103 | heading | - | - | - | own text, not from any source |
| 1105-1144 | Domain model and type design | brooks-lint-marketplace | skills/_shared/decay-risks.md | 232-271 | verbatim |
| 1146-1150 | Domain model and type design | brooks-lint-marketplace | skills/brooks-review/pr-review-guide.md | 83-87 | verbatim |
| 1152-1157 | Domain model and type design | pr-review-toolkit | agents/type-design-analyzer.md | 17-22 | verbatim |
| 1159-1159 | own text | - | - | - | own text, not from any source |
| 1161-1164 | Domain model and type design | pr-review-toolkit | agents/type-design-analyzer.md | 25-28 | verbatim |
| 1166-1166 | own text | - | - | - | own text, not from any source |
| 1168-1171 | Domain model and type design | pr-review-toolkit | agents/type-design-analyzer.md | 31-34 | verbatim |
| 1173-1173 | own text | - | - | - | own text, not from any source |
| 1175-1178 | Domain model and type design | pr-review-toolkit | agents/type-design-analyzer.md | 37-40 | verbatim |
| 1180-1180 | own text | - | - | - | own text, not from any source |
| 1182-1185 | Domain model and type design | pr-review-toolkit | agents/type-design-analyzer.md | 43-46 | verbatim |
| 1187-1216 | Domain model and type design | pr-review-toolkit | agents/type-design-analyzer.md | 81-110 | verbatim |
| 1218-1218 | heading | - | - | - | own text, not from any source |
| 1220-1228 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/SKILL.md | 66-74 | verbatim |
| 1230-1236 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/SKILL.md | 82-88 | verbatim |
| 1238-1241 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/SKILL.md | 90-93 | verbatim |
| 1243-1254 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/references/detection_patterns.md | 5-16 | verbatim |
| 1256-1263 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/references/detection_patterns.md | 86-93 | verbatim |
| 1265-1315 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/references/refactoring_decision_tree.md | 5-55 | verbatim |
| 1317-1332 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-624-code-quality-auditor/SKILL.md | 111-126 | verbatim |
| 1334-1334 | Duplication, size, complexity and unneeded abstraction | agent-skills-code-review-and-quality | SKILL.md | 113-113 | verbatim |
| 1336-1350 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-624-code-quality-auditor/SKILL.md | 128-142 | verbatim |
| 1352-1374 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-624-code-quality-auditor/SKILL.md | 206-228 | verbatim |
| 1376-1383 | Duplication, size, complexity and unneeded abstraction | brooks-lint-marketplace | skills/_shared/decay-risks.md | 22-29 | verbatim |
| 1385-1386 | Duplication, size, complexity and unneeded abstraction | brooks-lint-marketplace | skills/_shared/decay-risks.md | 48-49 | verbatim |
| 1388-1428 | Duplication, size, complexity and unneeded abstraction | brooks-lint-marketplace | skills/_shared/decay-risks.md | 142-182 | verbatim |
| 1430-1435 | Duplication, size, complexity and unneeded abstraction | brooks-lint-marketplace | skills/brooks-review/pr-review-guide.md | 67-72 | verbatim |
| 1437-1455 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/SKILL.md | 97-115 | verbatim |
| 1457-1462 | Duplication, size, complexity and unneeded abstraction | agent-skills-code-simplification | SKILL.md | 149-154 | verbatim |
| 1464-1465 | Duplication, size, complexity and unneeded abstraction | ce-simplify-code | ce-simplify-code/references/personas/code-quality-reviewer.md | 3-4 | verbatim |
| 1467-1468 | Duplication, size, complexity and unneeded abstraction | ce-simplify-code | ce-simplify-code/references/personas/code-quality-reviewer.md | 6-7 | verbatim |
| 1470-1470 | Duplication, size, complexity and unneeded abstraction | ce-simplify-code | ce-simplify-code/references/personas/code-quality-reviewer.md | 13-13 | verbatim |
| 1472-1472 | Duplication, size, complexity and unneeded abstraction | ce-simplify-code | ce-simplify-code/references/personas/code-quality-reviewer.md | 15-15 | verbatim |
| 1474-1474 | Duplication, size, complexity and unneeded abstraction | ce-simplify-code | ce-simplify-code/references/personas/code-reuse-reviewer.md | 3-3 | verbatim |
| 1476-1476 | own text | - | - | - | own text, not from any source |
| 1478-1491 | Duplication, size, complexity and unneeded abstraction | mattpocock-code-review | code-review/SKILL.md | 43-56 | verbatim |
| 1493-1503 | Duplication, size, complexity and unneeded abstraction | ce-code-review | references/personas/maintainability-reviewer.md | 9-19 | verbatim |
| 1505-1508 | Duplication, size, complexity and unneeded abstraction | ce-code-review | references/personas/maintainability-reviewer.md | 23-26 | verbatim |
| 1510-1517 | Duplication, size, complexity and unneeded abstraction | ce-code-review | references/personas/maintainability-reviewer.md | 29-36 | verbatim |
| 1519-1522 | Duplication, size, complexity and unneeded abstraction | ce-code-review | references/personas/maintainability-reviewer.md | 38-41 | verbatim |
| 1524-1530 | Duplication, size, complexity and unneeded abstraction | ce-code-review | references/personas/maintainability-reviewer.md | 43-49 | verbatim |
| 1532-1540 | Duplication, size, complexity and unneeded abstraction | ce-code-review | references/personas/maintainability-reviewer.md | 51-61 | changed: removed `Use the anchored confidence rubric in the subagent template. Persona-specific guidance:\n\n`; removed ` (the synthesis rules still report a critical structural regression you could not fully verify as P0 at anchor 50)` |
| 1542-1549 | Duplication, size, complexity and unneeded abstraction | ce-code-review | references/personas/maintainability-reviewer.md | 63-70 | verbatim |
| 1551-1566 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/SKILL.md | 131-146 | verbatim |
| 1568-1580 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/SKILL.md | 150-162 | verbatim |
| 1582-1612 | Duplication, size, complexity and unneeded abstraction | codebase-audit-suite | skills-catalog/shared/references/clean_code_checklist.md | 27-57 | verbatim |
| 1614-1614 | heading | - | - | - | own text, not from any source |
| 1616-1619 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-646-project-structure-auditor/SKILL.md | 298-301 | verbatim |
| 1621-1622 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-646-project-structure-auditor/SKILL.md | 307-308 | verbatim |
| 1624-1624 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-646-project-structure-auditor/SKILL.md | 313-313 | verbatim |
| 1626-1668 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-646-project-structure-auditor/references/structure_rules.md | 7-49 | verbatim |
| 1670-1684 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-646-project-structure-auditor/references/structure_rules.md | 53-67 | verbatim |
| 1686-1688 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-646-project-structure-auditor/references/structure_rules.md | 92-95 | verbatim |
| 1690-1708 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-646-project-structure-auditor/references/structure_rules.md | 97-117 | verbatim |
| 1710-1776 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-646-project-structure-auditor/references/structure_rules.md | 119-186 | verbatim |
| 1778-1813 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-646-project-structure-auditor/references/structure_rules.md | 190-225 | verbatim |
| 1815-1817 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-647-env-config-auditor/SKILL.md | 19-21 | verbatim |
| 1819-1822 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-647-env-config-auditor/SKILL.md | 48-51 | verbatim |
| 1824-1828 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-647-env-config-auditor/SKILL.md | 319-323 | changed: removed ` per config_rules.md` |
| 1830-1842 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-647-env-config-auditor/references/config_rules.md | 37-49 | verbatim |
| 1844-1874 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-647-env-config-auditor/references/config_rules.md | 62-92 | verbatim |
| 1876-1877 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-645-open-source-replacer/SKILL.md | 18-19 | verbatim |
| 1879-1883 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-645-open-source-replacer/SKILL.md | 293-297 | verbatim |
| 1885-1885 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-645-open-source-replacer/SKILL.md | 303-303 | verbatim |
| 1887-1888 | Project structure, configuration and build versus buy | codebase-audit-suite | skills-catalog/ln-645-open-source-replacer/SKILL.md | 307-308 | verbatim |
| 1890-1890 | heading | - | - | - | own text, not from any source |
| 1892-1913 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/shared/references/ai_ready_architecture.md | 9-30 | verbatim |
| 1915-1929 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/shared/references/ai_ready_architecture.md | 32-46 | verbatim |
| 1931-1953 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/shared/references/ai_ready_architecture.md | 50-72 | verbatim |
| 1955-1972 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/shared/references/ai_ready_architecture.md | 76-93 | verbatim |
| 1974-1974 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/shared/references/ai_ready_architecture.md | 117-117 | verbatim |
| 1976-1985 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/shared/references/ai_ready_architecture.md | 121-130 | verbatim |
| 1987-2008 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/ln-624-code-quality-auditor/SKILL.md | 230-251 | changed: removed `**MANDATORY READ:** `shared/references/ai_ready_architecture.md` for side-effect markers, false positive exclusions, and opaque sink rules.` |
| 2010-2070 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/ln-629-lifecycle-auditor/SKILL.md | 48-108 | verbatim |
| 2072-2075 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/ln-629-lifecycle-auditor/SKILL.md | 139-142 | verbatim |
| 2077-2092 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/ln-652-transaction-correctness-auditor/SKILL.md | 84-99 | verbatim |
| 2094-2108 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/ln-652-transaction-correctness-auditor/SKILL.md | 101-115 | verbatim |
| 2110-2112 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/ln-654-resource-lifecycle-auditor/SKILL.md | 64-67 | verbatim |
| 2114-2119 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/ln-654-resource-lifecycle-auditor/SKILL.md | 91-96 | verbatim |
| 2121-2123 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/ln-654-resource-lifecycle-auditor/SKILL.md | 100-103 | verbatim |
| 2125-2129 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/ln-654-resource-lifecycle-auditor/SKILL.md | 126-130 | verbatim |
| 2131-2133 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/ln-654-resource-lifecycle-auditor/SKILL.md | 247-250 | verbatim |
| 2135-2139 | Side effects, lifecycle, resources and transactions | codebase-audit-suite | skills-catalog/ln-654-resource-lifecycle-auditor/SKILL.md | 272-276 | verbatim |
| 2141-2141 | heading | - | - | - | own text, not from any source |
| 2143-2149 | Agent-facing surfaces and composition | ce-code-review | references/personas/agent-native-reviewer.md | 5-11 | verbatim |
| 2151-2159 | Agent-facing surfaces and composition | ce-code-review | references/personas/agent-native-reviewer.md | 23-31 | verbatim |
| 2161-2169 | Agent-facing surfaces and composition | ce-code-review | references/personas/agent-native-reviewer.md | 34-42 | verbatim |
| 2171-2183 | Agent-facing surfaces and composition | ce-code-review | references/personas/agent-native-reviewer.md | 44-56 | verbatim |
| 2185-2193 | Agent-facing surfaces and composition | ce-code-review | references/personas/agent-native-reviewer.md | 58-66 | verbatim |
| 2195-2216 | Agent-facing surfaces and composition | ce-code-review | references/personas/agent-native-reviewer.md | 68-89 | verbatim |
| 2218-2226 | Agent-facing surfaces and composition | ce-code-review | references/personas/agent-native-reviewer.md | 91-99 | verbatim |
| 2228-2235 | Agent-facing surfaces and composition | ce-code-review | references/personas/agent-native-reviewer.md | 101-108 | verbatim |
| 2237-2244 | Agent-facing surfaces and composition | ce-code-review | references/personas/agent-native-reviewer.md | 110-117 | verbatim |
| 2246-2256 | Agent-facing surfaces and composition | ce-code-review | references/personas/agent-native-reviewer.md | 119-129 | verbatim |
| 2258-2266 | Agent-facing surfaces and composition | ce-code-review | references/personas/agent-native-reviewer.md | 131-141 | changed: removed `Use the anchored confidence rubric in the subagent template. Persona-specific guidance:\n\n`; removed `, or when synthesis moves it to a soft bucket (`testing_gaps`, `residual_risks`, or advisory)` |
| 2268-2275 | Agent-facing surfaces and composition | ce-code-review | references/personas/adversarial-reviewer.md | 36-43 | verbatim |
| 2277-2277 | heading | - | - | - | own text, not from any source |
| 2279-2285 | Design review, debt and checklists | comprehensive-review | commands/full-review.md | 153-159 | verbatim |
| 2287-2287 | Design review, debt and checklists | comprehensive-review | commands/full-review.md | 254-254 | verbatim |
| 2289-2298 | Design review, debt and checklists | code-review-excellence | SKILL.md | 102-111 | verbatim |
| 2300-2301 | Design review, debt and checklists | agent-skills-code-review-and-quality | SKILL.md | 48-49 | verbatim |
| 2303-2312 | Design review, debt and checklists | agent-skills-code-review-and-quality | SKILL.md | 53-62 | verbatim |
| 2314-2327 | Design review, debt and checklists | agent-skills-code-review-and-quality | SKILL.md | 88-101 | verbatim |
| 2329-2329 | Design review, debt and checklists | agent-skills-code-review-and-quality | SKILL.md | 396-396 | verbatim |
| 2331-2366 | Design review, debt and checklists | thermos | skills/thermo-nuclear-code-quality-review/SKILL.md | 34-69 | verbatim |
| 2368-2382 | Design review, debt and checklists | thermos | skills/thermo-nuclear-code-quality-review/SKILL.md | 73-87 | verbatim |
| 2384-2391 | Design review, debt and checklists | thermos | skills/thermo-nuclear-code-quality-review/SKILL.md | 183-190 | verbatim |
| 2393-2395 | Design review, debt and checklists | codebase-audit-suite | skills-catalog/shared/agents/prompt_templates/modes/code.md | 38-40 | verbatim |
| 2397-2400 | Design review, debt and checklists | codebase-audit-suite | skills-catalog/shared/agents/prompt_templates/modes/code.md | 44-47 | verbatim |
| 2402-2415 | Design review, debt and checklists | brooks-lint-marketplace | skills/brooks-debt/debt-guide.md | 38-51 | verbatim |
| 2417-2429 | Design review, debt and checklists | brooks-lint-marketplace | skills/brooks-debt/debt-guide.md | 83-96 | changed: removed `Mark each finding with `[intentional]` or `[accidental]` in the Debt Summary Table.\n` |
| 2431-2452 | Design review, debt and checklists | multi-reviewer-patterns | references/review-dimensions.md | 60-81 | verbatim |
| 2454-2454 | heading | - | - | - | own text, not from any source |
| 2456-2462 | Judging and calibrating a finding | brooks-lint-marketplace | skills/_shared/source-coverage.md | 22-28 | verbatim |
| 2464-2477 | Judging and calibrating a finding | brooks-lint-marketplace | skills/_shared/source-coverage.md | 32-45 | verbatim |
| 2479-2494 | Judging and calibrating a finding | brooks-lint-marketplace | skills/_shared/source-coverage.md | 67-82 | verbatim |
| 2496-2511 | Judging and calibrating a finding | brooks-lint-marketplace | skills/_shared/source-coverage.md | 86-101 | verbatim |
| 2513-2526 | Judging and calibrating a finding | brooks-lint-marketplace | skills/_shared/source-coverage.md | 105-118 | verbatim |
| 2528-2544 | Judging and calibrating a finding | brooks-lint-marketplace | skills/_shared/source-coverage.md | 122-138 | verbatim |
| 2546-2561 | Judging and calibrating a finding | brooks-lint-marketplace | skills/_shared/source-coverage.md | 142-157 | verbatim |
| 2563-2580 | Judging and calibrating a finding | brooks-lint-marketplace | skills/_shared/source-coverage.md | 161-178 | verbatim |
| 2582-2587 | Judging and calibrating a finding | codebase-audit-suite | skills-catalog/shared/references/context_validation.md | 12-17 | verbatim |
| 2589-2589 | Judging and calibrating a finding | codebase-audit-suite | skills-catalog/shared/references/context_validation.md | 19-19 | verbatim |
| 2591-2596 | Judging and calibrating a finding | codebase-audit-suite | skills-catalog/shared/references/context_validation.md | 21-26 | verbatim |
| 2598-2609 | Judging and calibrating a finding | codebase-audit-suite | skills-catalog/shared/references/context_validation.md | 28-39 | verbatim |
| 2611-2620 | Judging and calibrating a finding | codebase-audit-suite | skills-catalog/shared/references/context_validation.md | 50-59 | verbatim |
| 2622-2653 | Judging and calibrating a finding | codebase-audit-suite | skills-catalog/shared/references/two_layer_detection.md | 40-71 | verbatim |
| 2655-2659 | Judging and calibrating a finding | brooks-lint-marketplace | skills/brooks-review/pr-review-guide.md | 146-150 | verbatim |
| 2661-2661 | heading | - | - | - | own text, not from any source |
| 2663-2663 | pointer intro (my joining text) | - | - | - | own text, not from any source |
| 2665-2670 | pointer list (my joining text) | - | - | - | own text, not from any source |
| 2672-2729 | Working method, Output contract | (earlier SKILL.md) | SKILL.md | 1046-1104 | verbatim, kept byte for byte |

Lines marked "own text" are headings and joining lines I wrote: the part headings, the severity-mapping note under "How to read the passages below", the lead-in line of the Fowler smell list, the fence lines (three backticks) that close and reopen code blocks cut from `ln-647`, the `#### ` headings between the four type-design questions, and the reference-file pointer list.

## Part 2: Supporting files

Each file in `references/` is a new file made by copy and paste from the source files named below, by line range. Blank lines at the edges of a block were trimmed. Blocks are in the order they appear in the new file, with one blank line between them. "verbatim" means the lines are as in the source; a block that skips lines names them. Lines marked "own" are a heading or a fence line I wrote.

### references/architecture-pattern-examples.md

| New file lines | Source folder | File | Source lines | Status |
|---|---|---|---|---|
| 1-1 | - | - | - | own text, not from any source |
| 3-335 | architecture-patterns | references/details.md | 3-336 | verbatim |
| 337-550 | architecture-patterns | references/advanced-patterns.md | 7-220 | verbatim |
| 551-551 | - | - | - | own text, not from any source |
| 553-587 | architecture-patterns | references/advanced-patterns.md | 228-264 | verbatim |
| 589-673 | architecture-patterns | references/advanced-patterns.md | 275-360 | verbatim |

### references/api-contract-checks.md

| New file lines | Source folder | File | Source lines | Status |
|---|---|---|---|---|
| 1-1 | - | - | - | own text, not from any source |
| 3-119 | codebase-audit-suite | skills-catalog/ln-643-api-contract-auditor/references/detection_patterns.md | 5-122 | verbatim |
| 121-132 | codebase-audit-suite | skills-catalog/ln-643-api-contract-auditor/references/detection_patterns.md | 125-137 | verbatim |
| 134-134 | - | - | - | own text, not from any source |
| 136-156 | codebase-audit-suite | skills-catalog/shared/references/ai_ready_architecture.md | 95-115 | verbatim |

### references/pattern-detection-catalog.md

| New file lines | Source folder | File | Source lines | Status |
|---|---|---|---|---|
| 1-1 | - | - | - | own text, not from any source |
| 3-33 | codebase-audit-suite | skills-catalog/ln-640-pattern-evolution-auditor/references/pattern_library.md | 7-37 | verbatim |
| 35-35 | codebase-audit-suite | skills-catalog/ln-640-pattern-evolution-auditor/references/pattern_library.md | 315-316 | verbatim |
| 37-49 | codebase-audit-suite | skills-catalog/ln-640-pattern-evolution-auditor/references/pattern_library.md | 319-331 | verbatim |

### references/layer-and-dependency-detection.md

| New file lines | Source folder | File | Source lines | Status |
|---|---|---|---|---|
| 1-1 | - | - | - | own text, not from any source |
| 3-8 | codebase-audit-suite | skills-catalog/ln-640-pattern-evolution-auditor/references/layer_rules.md | 49-54 | verbatim |
| 10-121 | codebase-audit-suite | skills-catalog/ln-644-dependency-graph-auditor/references/import_patterns.md | 5-117 | verbatim |

### references/duplication-and-overengineering-checks.md

| New file lines | Source folder | File | Source lines | Status |
|---|---|---|---|---|
| 1-1 | - | - | - | own text, not from any source |
| 3-57 | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/references/detection_patterns.md | 18-85 | verbatim, except source lines 22,23,24,39,56,71,75,76,77 left out (their own output field or a pointer to a file or tool that is not carried) |
| 59-71 | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/references/detection_patterns.md | 96-112 | verbatim, except source lines 111 left out (their own output field or a pointer to a file or tool that is not carried) |
| 73-129 | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/references/detection_patterns.md | 128-193 | verbatim, except source lines 141,158,175,192 left out (their own output field or a pointer to a file or tool that is not carried) |
| 131-149 | codebase-audit-suite | skills-catalog/ln-623-code-principles-auditor/references/detection_patterns.md | 194-212 | verbatim |

### references/env-config-patterns.md

| New file lines | Source folder | File | Source lines | Status |
|---|---|---|---|---|
| 1-1 | - | - | - | own text, not from any source |
| 3-31 | codebase-audit-suite | skills-catalog/ln-647-env-config-auditor/references/config_rules.md | 7-35 | verbatim |
| 33-42 | codebase-audit-suite | skills-catalog/ln-647-env-config-auditor/references/config_rules.md | 51-61 | verbatim |

Source files read in full and left out of `references/` because their useful text is already in `SKILL.md` or belongs to another reviewer are listed in Part 3 with the reason.

## Part 3: Reading record

Files under `AGENTS/PLUGINS/`: 485. Read in full: 455. Not read in full: 30. "Read in full" means the last line of the file came back to me from a read of that file. The files marked "no" are: the licence texts and empty marker files and the image, which I was told to leave, and two files that hold attack samples, which a safety check stopped; the note on each says which. Files marked "yes" in the first run that I printed several at a time were read again one at a time; their notes begin "re-read alone with the Read tool".

| Path | Lines | Read in full | Used | Reason |
|---|---|---|---|---|
| agent-skills-agents/LICENSE | 21 | no | not used | licence text, skipped as allowed |
| agent-skills-agents/code-reviewer.md | 102 | yes | not used | architecture bullets (lines 26-31) repeat the same passage already taken from code-review-and-quality; rest is own output format |
| agent-skills-agents/security-auditor.md | 112 | yes | not used | security checklist: security reviewer's |
| agent-skills-agents/test-engineer.md | 95 | yes | not used | testing patterns and test-engineer persona: tests reviewer's |
| agent-skills-code-review-and-quality/LICENSE | 21 | no | not used | licence text, skipped as allowed |
| agent-skills-code-review-and-quality/SKILL.md | 396 | yes | used | lines 48-49, 53-62, 88-101, 113, 396 (architecture axis, structural remedies, file-size signal, presumptive structural blockers); left out other four axes, change sizing/description, process, etiquette, dependency discipline, checklist |
| agent-skills-code-simplification/LICENSE | 21 | no | not used | licence text, skipped as allowed |
| agent-skills-code-simplification/SKILL.md | 331 | yes | used | lines 149-154 (redundancy table: duplication, dead code, wrapper abstractions, over-engineered patterns); rest is simplification process, language examples, naming (code quality) |
| agent-skills-references/LICENSE | 21 | no | not used | licence text, skipped as allowed |
| agent-skills-references/accessibility-checklist.md | 160 | yes | not used | re-read alone with the Read tool to its last line: front-end accessibility checklist, the UI reviewer's |
| agent-skills-references/definition-of-done.md | 67 | yes | not used | definition of done checklist and orchestration pattern catalog: not architecture review criteria |
| agent-skills-references/observability-checklist.md | 91 | yes | not used | re-read alone with the Read tool to its last line: telemetry checklist, the observability reviewer's |
| agent-skills-references/orchestration-patterns.md | 370 | yes | not used | definition of done checklist and orchestration pattern catalog: not architecture review criteria |
| agent-skills-references/performance-checklist.md | 153 | yes | not used | re-read alone with the Read tool to its last line: web and database performance checklist, the performance reviewer's |
| agent-skills-references/security-checklist.md | 205 | yes | not used | security checklist: security reviewer's |
| agent-skills-references/testing-patterns.md | 235 | yes | not used | testing patterns and test-engineer persona: tests reviewer's |
| agent-skills-test-driven-development/LICENSE | 21 | no | not used | licence text, skipped as allowed |
| agent-skills-test-driven-development/SKILL.md | 398 | yes | not used | TDD workflow: tests reviewer's |
| architecture-patterns/LICENSE | 20 | no | not used | licence text, skipped as allowed |
| architecture-patterns/SKILL.md | 164 | yes | used | core concepts 24-68; troubleshooting symptoms/fixes 127-151; left out worked in-memory test example, when-to-use, related skills |
| architecture-patterns/references/advanced-patterns.md | 391 | yes | used | relationship types 222-226, aggregate heuristics 265-273 and cycle symptoms/fixes 363-383 are in SKILL.md; lines 7-220, 228-264 and 275-360 (project structure, onion versus clean, anti-corruption layer, context map, wiring, aggregates, domain events) are in references/architecture-pattern-examples.md; left out: lines 1-6 (names its plugin), 361-362 and 384-392 (heading and a visualisation tool command) |
| architecture-patterns/references/details.md | 335 | yes | not used | lines 3-336 (clean architecture layout and implementation, hexagonal ports and adapters, value objects and aggregates) are in references/architecture-pattern-examples.md; line 1-2 (title naming its plugin) left out |
| backend-security-coder/LICENSE | 20 | no | not used | licence text, skipped as allowed |
| backend-security-coder/backend-security-coder.md | 153 | yes | not used | backend security capability list: security reviewer's |
| brooks-lint-marketplace/.brooks-lint.example.yaml | 99 | yes | not used | re-read alone with the Read tool to its last line: example config file of that plugin (its own risk codes, scoring and sweep settings), not architecture content |
| brooks-lint-marketplace/.gitignore | 39 | yes | not used | gitignore patterns |
| brooks-lint-marketplace/AGENTS.md | 36 | yes | not used | re-read alone with the Read tool to its last line: that repository's own agent notes (skill names, scoring table, layout); its own report scoring, not architecture content |
| brooks-lint-marketplace/CLAUDE.md | 90 | yes | not used | its full text was shown to me in the session context and the Read tool answered that it was unchanged (it did not print the file a second time); about maintaining that repository (release steps, evals, installs), not architecture content |
| brooks-lint-marketplace/SECURITY.md | 31 | yes | not used | re-read alone with the Read tool to its last line: security policy of that repository, the security reviewer's |
| brooks-lint-marketplace/skills/_shared/common.md | 268 | yes | not used | own report template/Iron Law format/config/health score (own output format); R1-R6 index table only |
| brooks-lint-marketplace/skills/_shared/custom-risks-guide.md | 47 | yes | not used | config loading for its own custom risk codes and report |
| brooks-lint-marketplace/skills/_shared/decay-risks.md | 271 | yes | used | decay-risks R2-R6 + parts of R1 (shallow module, chains, flag arg, primitive obsession): lines 22-29,48-49,54-271 |
| brooks-lint-marketplace/skills/_shared/remedy-guide.md | 43 | yes | not used | own fix-mode/report format (Remedy enhancement, fix summary) |
| brooks-lint-marketplace/skills/_shared/source-coverage.md | 248 | yes | used | Do-not-ignore/over-flag notes for architecture books: lines 22-28,32-45,67-82,86-101,105-118,122-138,142-157,161-178; test/other books (McConnell, Meszaros, Osherove, Feathers, Google tests) not for architecture |
| brooks-lint-marketplace/skills/_shared/test-decay-risks.md | 239 | yes | not used | test-suite quality risks: the tests reviewer's (seam/legacy points already carried from architecture-guide) |
| brooks-lint-marketplace/skills/brooks-audit/SKILL.md | 43 | yes | not used | skill wrapper: trigger text and pointers to the plugin's own shared files/report; guidance is in its guide files |
| brooks-lint-marketplace/skills/brooks-audit/architecture-guide.md | 187 | yes | used | Steps 2-6 (dependency disorder, domain distortion, blast radius, seams, Conway) lines 7-9,41-47,97-177; left out Step 0 tool commands (Glob/Grep) and Step 1 mermaid graph and Output (own report format) |
| brooks-lint-marketplace/skills/brooks-audit/onboarding-guide.md | 89 | yes | not used | newcomer onboarding tour, not a review of a change (own output) |
| brooks-lint-marketplace/skills/brooks-debt/SKILL.md | 36 | yes | not used | skill wrapper: trigger text and pointers to the plugin's own shared files/report; guidance is in its guide files |
| brooks-lint-marketplace/skills/brooks-debt/debt-guide.md | 125 | yes | used | per-risk questions 38-51; intentional vs accidental debt 83-96; left out pain x spread scoring (own scale) and debt summary table (own output format) |
| brooks-lint-marketplace/skills/brooks-health/SKILL.md | 38 | yes | not used | skill wrapper: trigger text and pointers to the plugin's own shared files/report; guidance is in its guide files |
| brooks-lint-marketplace/skills/brooks-health/health-guide.md | 99 | yes | not used | own dashboard/scoring template; its architecture scan repeats decay-risks R5 |
| brooks-lint-marketplace/skills/brooks-review/SKILL.md | 38 | yes | not used | skill wrapper: trigger text and pointers to the plugin's own shared files/report; guidance is in its guide files |
| brooks-lint-marketplace/skills/brooks-review/pr-review-guide.md | 161 | yes | used | scope/generated-file skip (10-12), >10 files (35-37), Steps 2,4,5,6a,6b (39-87), severity tiebreaker (146-150); left out Step 3 cognitive overload (code_quality), Step 7 tests (tests reviewer), own report template |
| brooks-lint-marketplace/skills/brooks-sweep/SKILL.md | 40 | yes | not used | skill wrapper: trigger text and pointers to the plugin's own shared files/report; guidance is in its guide files |
| brooks-lint-marketplace/skills/brooks-sweep/sweep-guide.md | 264 | yes | used | only lines 148-153 (architecture-only concerns: missing abstraction layers, god modules, leaked infrastructure, seam violations); rest is an auto-fix pipeline and own report format |
| brooks-lint-marketplace/skills/brooks-test/SKILL.md | 37 | yes | not used | skill wrapper: trigger text and pointers to the plugin's own shared files/report; guidance is in its guide files |
| brooks-lint-marketplace/skills/brooks-test/test-guide.md | 149 | yes | not used | test-suite quality risks: the tests reviewer's (seam/legacy points already carried from architecture-guide) |
| ce-code-review/SKILL.md | 40 | yes | not used | re-read alone with the Read tool to its last line: that plugin's own orchestration steps (stages, dispatch, report), no architecture content beyond what SKILL.md already carries from its persona files |
| ce-code-review/references/action-class-rubric.md | 67 | yes | not used | review orchestration: action classes, severity scale of its own, peer-model pass, dispatch (left out: its own output format and fields) |
| ce-code-review/references/cross-model-recovery.md | 32 | yes | not used | review orchestration: action classes, severity scale of its own, peer-model pass, dispatch (left out: its own output format and fields) |
| ce-code-review/references/cross-model-review.md | 184 | yes | not used | review orchestration: action classes, severity scale of its own, peer-model pass, dispatch (left out: its own output format and fields) |
| ce-code-review/references/depth-paths.md | 30 | yes | not used | review orchestration: action classes, severity scale of its own, peer-model pass, dispatch (left out: its own output format and fields) |
| ce-code-review/references/diff-scope.md | 53 | yes | not used | scope tiers (primary/secondary/pre-existing) and evidence tools; tied to its own output fields |
| ce-code-review/references/dispatch-reviewers.md | 129 | yes | not used | review orchestration: action classes, severity scale of its own, peer-model pass, dispatch (left out: its own output format and fields) |
| ce-code-review/references/findings-schema.json | 125 | yes | not used | review orchestration, finish handoff, merge/validation stages, output modes and its own JSON schema (left out: its own output format) |
| ce-code-review/references/finish-input.md | 116 | yes | not used | review orchestration, finish handoff, merge/validation stages, output modes and its own JSON schema (left out: its own output format) |
| ce-code-review/references/finish-review.md | 202 | yes | not used | review orchestration, finish handoff, merge/validation stages, output modes and its own JSON schema (left out: its own output format) |
| ce-code-review/references/intent-and-plan.md | 73 | yes | not used | review orchestration, finish handoff, merge/validation stages, output modes and its own JSON schema (left out: its own output format) |
| ce-code-review/references/modes-and-output.md | 144 | yes | not used | review orchestration, finish handoff, merge/validation stages, output modes and its own JSON schema (left out: its own output format) |
| ce-code-review/references/persona-catalog.md | 66 | yes | not used | re-read alone with the Read tool to its last line: that plugin's own reviewer selection, scope resolution and run-directory steps (orchestration), not architecture content |
| ce-code-review/references/personas/adversarial-reviewer.md | 110 | yes | used | re-read alone with the Read tool to its last line; only lines 36-43 (composition failures across component boundaries) are architecture; the rest is failure-scenario hunting (the logic reviewer's), known vulnerability patterns and its own output format |
| ce-code-review/references/personas/agent-native-reviewer.md | 173 | yes | used | re-read alone with the Read tool to its last line; nothing new: lines 5-11,23-31,34-42,44-56,58-66,68-89,91-99,101-108,110-117,119-129,131-141 are in SKILL.md; left out lines 1-4 and 12-22 (persona statement, triage workflow) and 143-173 (its own report layout) |
| ce-code-review/references/personas/api-contract-reviewer.md | 44 | yes | used | lines 7-12 hunting, 14-31 confidence + do-not-flag; left out intro persona and output block |
| ce-code-review/references/personas/correctness-reviewer.md | 47 | yes | not used | re-read alone with the Read tool to its last line: logic bugs, null handling, races, state errors; the correctness reviewer's |
| ce-code-review/references/personas/data-migration-reviewer.md | 111 | yes | not used | re-read alone with the Read tool to its last line: schema drift, backfills, rollback and deploy checks for data migrations; the data-migration reviewer's |
| ce-code-review/references/personas/deployment-verification-agent.md | 157 | yes | not used | re-read alone with the Read tool to its last line: go/no-go deployment checklist with queries and rollback; operations, and its own output layout |
| ce-code-review/references/personas/julik-frontend-races-reviewer.md | 45 | yes | not used | re-read alone with the Read tool to its last line: front-end timing and cleanup races; the logic and front-end reviewer's |
| ce-code-review/references/personas/learnings-researcher.md | 260 | yes | not used | institutional-knowledge search agent: search workflow and own output format |
| ce-code-review/references/personas/maintainability-reviewer.md | 83 | yes | used | persona text lines 9-19,23-26,29-36,38-41,43-49,51-61,63-70; left out name/dead-code/naming (code_quality) and output block (own format) |
| ce-code-review/references/personas/performance-reviewer.md | 45 | yes | not used | re-read alone with the Read tool to its last line: N+1, unbounded memory, pagination, blocking I/O; the performance reviewer's |
| ce-code-review/references/personas/previous-comments-reviewer.md | 59 | yes | not used | re-read alone with the Read tool to its last line: checks that earlier PR comments were addressed; review process, not architecture |
| ce-code-review/references/personas/project-standards-reviewer.md | 77 | yes | not used | compliance reviewer's: audits against the project's written rules |
| ce-code-review/references/personas/reliability-reviewer.md | 49 | yes | not used | re-read alone with the Read tool to its last line: timeouts, retries, error swallowing, resource leaks, cascading failure; the reliability reviewer's |
| ce-code-review/references/personas/security-reviewer.md | 50 | yes | not used | re-read alone with the Read tool to its last line: injection, auth, secrets, crypto, SSRF; the security reviewer's |
| ce-code-review/references/personas/swift-ios-reviewer.md | 99 | yes | not used | re-read alone with the Read tool to its last line: SwiftUI state wrappers, retain cycles, Swift concurrency, accessibility, money types; language-specific defects, other reviewers' |
| ce-code-review/references/personas/testing-reviewer.md | 51 | yes | not used | re-read alone with the Read tool to its last line: untested branches, vacuous assertions, brittle and flaky tests, test-only seams; the tests reviewer's |
| ce-code-review/references/review-output-template.md | 172 | yes | not used | report layout, per-reviewer prompt template with own confidence/severity/schema rules, validator prompt (left out: its own output format) |
| ce-code-review/references/scope.md | 172 | yes | not used | re-read alone with the Read tool to its last line: that plugin's own reviewer selection, scope resolution and run-directory steps (orchestration), not architecture content |
| ce-code-review/references/select-and-route.md | 93 | yes | not used | re-read alone with the Read tool to its last line: that plugin's own reviewer selection, scope resolution and run-directory steps (orchestration), not architecture content |
| ce-code-review/references/subagent-template.md | 206 | yes | not used | report layout, per-reviewer prompt template with own confidence/severity/schema rules, validator prompt (left out: its own output format) |
| ce-code-review/references/validator-batch-template.md | 67 | yes | not used | report layout, per-reviewer prompt template with own confidence/severity/schema rules, validator prompt (left out: its own output format) |
| ce-code-review/scripts/cross-model-adversarial-review.sh | 1304 | yes | not used | script code (pack resolution, peer-model launcher); no architecture review criteria |
| ce-code-review/scripts/findings-mechanics.py | 274 | yes | not used | script code for finding merge, scope counting and cost logging; no architecture review criteria |
| ce-code-review/scripts/packs-resolve.py | 737 | yes | not used | script code (pack resolution, peer-model launcher); no architecture review criteria |
| ce-code-review/scripts/peer-job-runner.py | 2465 | yes | not used | detached job supervisor script (process control, Windows and POSIX); no architecture review criteria |
| ce-code-review/scripts/review-scope.py | 390 | yes | not used | script code for finding merge, scope counting and cost logging; no architecture review criteria |
| ce-code-review/scripts/run-log.py | 271 | yes | not used | script code for finding merge, scope counting and cost logging; no architecture review criteria |
| ce-simplify-code/LICENSE | 21 | no | not used | licence text, skipped as allowed |
| ce-simplify-code/ce-simplify-code/SKILL.md | 66 | yes | not used | simplification workflow, scope, dispatch, verification |
| ce-simplify-code/ce-simplify-code/references/personas/code-quality-reviewer.md | 17 | yes | used | lines 3-4,6-7,13,15 (redundant state, parameter sprawl, leaky abstractions, stringly-typed, compat scaffolding, balance); left out nesting, comments, dead code, naming (code quality) |
| ce-simplify-code/ce-simplify-code/references/personas/code-reuse-reviewer.md | 7 | yes | used | line 3 (existing helper instead of new duplicate); rest are reuse/built-in swaps |
| ce-simplify-code/ce-simplify-code/references/personas/efficiency-reviewer.md | 11 | yes | not used | efficiency/performance reviewer's |
| code-review-excellence/LICENSE | 20 | no | not used | licence text, skipped as allowed |
| code-review-excellence/SKILL.md | 529 | yes | used | lines 102-111 (architecture/design and file-organization questions); rest is feedback etiquette, language examples, checklists and templates |
| code-simplifier/.claude-plugin/plugin.json | 9 | yes | not used | plugin manifest |
| code-simplifier/.in_use/14964 | 0 | no | not used | empty marker file |
| code-simplifier/.in_use/15821 | 0 | no | not used | empty marker file |
| code-simplifier/.in_use/27289 | 0 | no | not used | empty marker file |
| code-simplifier/.in_use/44306 | 0 | no | not used | empty marker file |
| code-simplifier/.in_use/47413 | 0 | no | not used | empty marker file |
| code-simplifier/.in_use/59166 | 0 | no | not used | empty marker file |
| code-simplifier/.in_use/6646 | 0 | no | not used | empty marker file |
| code-simplifier/.in_use/81901 | 0 | no | not used | empty marker file |
| code-simplifier/LICENSE | 202 | no | not used | licence text, skipped as allowed |
| code-simplifier/agents/code-simplifier.md | 52 | yes | not used | simplifier persona (same text as pr-review-toolkit simplifier) |
| codebase-audit-suite/LICENSE | 21 | yes | not used | documentation audit coordinator/worker (hierarchy, SSOT, compression, freshness): documentation reviewer's |
| codebase-audit-suite/skills-catalog/ln-610-docs-auditor/SKILL.md | 350 | yes | not used | documentation audit coordinator/worker (hierarchy, SSOT, compression, freshness): documentation reviewer's |
| codebase-audit-suite/skills-catalog/ln-611-docs-structure-auditor/SKILL.md | 119 | yes | not used | documentation audit coordinator/worker (hierarchy, SSOT, compression, freshness): documentation reviewer's |
| codebase-audit-suite/skills-catalog/ln-611-docs-structure-auditor/references/audit_checklist.md | 253 | yes | not used | documentation audit coordinator/worker (hierarchy, SSOT, compression, freshness): documentation reviewer's |
| codebase-audit-suite/skills-catalog/ln-611-docs-structure-auditor/references/size_limits.md | 121 | yes | not used | documentation audit coordinator/worker (hierarchy, SSOT, compression, freshness): documentation reviewer's |
| codebase-audit-suite/skills-catalog/ln-612-semantic-content-auditor/SKILL.md | 169 | yes | not used | documentation semantic-content/comments/fact-checker auditors: documentation reviewer's |
| codebase-audit-suite/skills-catalog/ln-613-code-comments-auditor/SKILL.md | 116 | yes | not used | documentation semantic-content/comments/fact-checker auditors: documentation reviewer's |
| codebase-audit-suite/skills-catalog/ln-613-code-comments-auditor/references/comments_rules.md | 223 | yes | not used | documentation semantic-content/comments/fact-checker auditors: documentation reviewer's |
| codebase-audit-suite/skills-catalog/ln-614-docs-fact-checker/SKILL.md | 217 | yes | not used | documentation semantic-content/comments/fact-checker auditors: documentation reviewer's |
| codebase-audit-suite/skills-catalog/ln-614-docs-fact-checker/references/claim_extraction_rules.md | 307 | yes | not used | documentation semantic-content/comments/fact-checker auditors: documentation reviewer's |
| codebase-audit-suite/skills-catalog/ln-620-codebase-auditor/SKILL.md | 413 | yes | not used | L2 coordinator: delegates to worker skills, runtime phases, aggregation, own report template |
| codebase-audit-suite/skills-catalog/ln-621-security-auditor/SKILL.md | 180 | yes | not used | security auditor (secrets/SQLi/XSS/deps/validation): security reviewer's |
| codebase-audit-suite/skills-catalog/ln-621-security-auditor/references/security_rules.md | 248 | yes | not used | security auditor (secrets/SQLi/XSS/deps/validation): security reviewer's |
| codebase-audit-suite/skills-catalog/ln-622-build-auditor/SKILL.md | 183 | yes | not used | build-health auditor (compiler/linter/type/test/config): a build/CI-health reviewer's, not architecture |
| codebase-audit-suite/skills-catalog/ln-622-build-auditor/references/build_rules.md | 289 | yes | not used | build-health auditor (compiler/linter/type/test/config): a build/CI-health reviewer's, not architecture |
| codebase-audit-suite/skills-catalog/ln-623-code-principles-auditor/SKILL.md | 238 | yes | used | layer-2 downgrades 66-74, DRY rows 82-88,90-93, KISS/YAGNI tables 97-115, central error handler 131-146, DI 150-162; left out copy-pasted tests row (tests), missing error handling (correctness), best-practices-guide check, scoring/report text |
| codebase-audit-suite/skills-catalog/ln-623-code-principles-auditor/references/detection_patterns.md | 216 | yes | used | exclusions 5-16 and similarity indicators 86-93 are in SKILL.md; the per-type recipes (lines 18-85, 96-112, 128-212) are in references/duplication-and-overengineering-checks.md; left out: copy-pasted tests 113-127 (tests reviewer), the clone-finder tool lines 22-24 and 75-77, and each type's pattern_signature line (its own output field) |
| codebase-audit-suite/skills-catalog/ln-623-code-principles-auditor/references/refactoring_decision_tree.md | 59 | yes | used | decision tree 5-55 (where the shared piece should live) |
| codebase-audit-suite/skills-catalog/ln-624-code-quality-auditor/SKILL.md | 308 | yes | used | god class sizes 111-126, parameters 128-142, signature quality 206-228, cascade depth 230-251 (path adjusted); left out complexity/nesting/length/O(n2)/N+1/constants (code_quality, performance), pipe/sink table output, scoring/report |
| codebase-audit-suite/skills-catalog/ln-625-dependencies-auditor/SKILL.md | 202 | yes | not used | re-read alone with the Read tool to its last line: dependency hygiene, outdated packages, CVE scan (the dependencies reviewer's); its custom-implementation check is covered by the build-versus-buy passage already carried |
| codebase-audit-suite/skills-catalog/ln-625-dependencies-auditor/references/ci_integration_guide.md | 120 | yes | not used | dependency-vulnerability CI/audit commands: security/dependency reviewer's |
| codebase-audit-suite/skills-catalog/ln-625-dependencies-auditor/references/vulnerability_commands.md | 99 | yes | not used | dependency-vulnerability CI/audit commands: security/dependency reviewer's |
| codebase-audit-suite/skills-catalog/ln-626-dead-code-auditor/SKILL.md | 160 | yes | not used | dead-code auditor: code-quality/simplification reviewer's |
| codebase-audit-suite/skills-catalog/ln-627-observability-auditor/SKILL.md | 155 | yes | not used | observability auditor (logging/health/metrics/tracing): an observability reviewer's, not architecture |
| codebase-audit-suite/skills-catalog/ln-628-concurrency-auditor/SKILL.md | 292 | yes | not used | concurrency/thread-safety auditor (races, deadlocks, TOCTOU): a concurrency-bug reviewer's, not architecture |
| codebase-audit-suite/skills-catalog/ln-629-lifecycle-auditor/SKILL.md | 157 | yes | used | lifecycle rules 48-108 and critical rules 139-142; left out Layer-1/2 workflow, scoring, report |
| codebase-audit-suite/skills-catalog/ln-630-test-auditor/SKILL.md | 445 | yes | not used | test-suite audit coordinator and business-logic/E2E-priority/value workers: a test reviewer's |
| codebase-audit-suite/skills-catalog/ln-631-test-business-logic-auditor/SKILL.md | 177 | yes | not used | test-suite audit coordinator and business-logic/E2E-priority/value workers: a test reviewer's |
| codebase-audit-suite/skills-catalog/ln-632-test-e2e-priority-auditor/SKILL.md | 174 | yes | not used | test-suite audit coordinator and business-logic/E2E-priority/value workers: a test reviewer's |
| codebase-audit-suite/skills-catalog/ln-633-test-value-auditor/SKILL.md | 206 | yes | not used | test-suite audit coordinator and business-logic/E2E-priority/value workers: a test reviewer's |
| codebase-audit-suite/skills-catalog/ln-634-test-coverage-auditor/SKILL.md | 214 | yes | not used | test coverage-gaps/isolation/manual-test/structure auditors: a test reviewer's |
| codebase-audit-suite/skills-catalog/ln-635-test-isolation-auditor/SKILL.md | 357 | yes | not used | test coverage-gaps/isolation/manual-test/structure auditors: a test reviewer's |
| codebase-audit-suite/skills-catalog/ln-636-manual-test-auditor/SKILL.md | 222 | yes | not used | test coverage-gaps/isolation/manual-test/structure auditors: a test reviewer's |
| codebase-audit-suite/skills-catalog/ln-637-test-structure-auditor/SKILL.md | 226 | yes | not used | test coverage-gaps/isolation/manual-test/structure auditors: a test reviewer's |
| codebase-audit-suite/skills-catalog/ln-640-pattern-evolution-auditor/SKILL.md | 617 | yes | not used | L2 coordinator: orchestrates worker skills, runtime phases, catalog files and score aggregation (own scoring); guidance for individual checks lives in the worker files |
| codebase-audit-suite/skills-catalog/ln-640-pattern-evolution-auditor/references/layer_rules.md | 91 | yes | used | layer presets, I/O boundary rules, coverage checks, transaction rules (lines 9-47, 56-66) are in SKILL.md; lines 49-54 (commit and rollback detection by layer) are in references/layer-and-dependency-detection.md; left out: async consistency and fire-and-forget rules 68-88 (concurrency reviewer) and lines 1-8 (names its plugin and a project doc) |
| codebase-audit-suite/skills-catalog/ln-640-pattern-evolution-auditor/references/pattern_library.md | 421 | yes | used | best-practice parts per pattern (41-311) and pattern recommendations (352-365) are in SKILL.md; the detection keyword table 7-37 and structural discovery heuristics 315-331 are in references/pattern-detection-catalog.md; left out: lines 3 and 317 (name its plugin), document-based heuristics and discovery output 333-348, MCP search queries and library lists 369-419 (cataloguing tools) |
| codebase-audit-suite/skills-catalog/ln-640-pattern-evolution-auditor/references/scoring_rules.md | 281 | yes | not used | own 0-100 scoring model with detection greps, effort estimates and thresholds (own scoring scale) |
| codebase-audit-suite/skills-catalog/ln-641-pattern-analyzer/SKILL.md | 172 | yes | not used | worker for one pattern: scoring workflow and report writing; the context check (deviation documented -> lower) is stated better elsewhere |
| codebase-audit-suite/skills-catalog/ln-642-layer-boundary-auditor/SKILL.md | 277 | yes | used | lines 108-110,121-137 transaction boundary; 141-143,152-159 session ownership; 163-176 flat orchestration; 248-252 critical rules; left out grep pseudo-code, scoring, report writing, coordinator I/O |
| codebase-audit-suite/skills-catalog/ln-643-api-contract-auditor/SKILL.md | 184 | yes | used | six rules table lines 63-71 (path to ai_ready_architecture adjusted); left out 4-score scoring, report writing, duplication boundary line |
| codebase-audit-suite/skills-catalog/ln-643-api-contract-auditor/references/detection_patterns.md | 139 | yes | used | lines 5-122 and 125-137 are in references/api-contract-checks.md; left out: line 3 (names its plugin), line 123 (pointer), version lines |
| codebase-audit-suite/skills-catalog/ln-644-dependency-graph-auditor/SKILL.md | 425 | yes | used | lines 21-22,24 purposes; 208-211 cycle-breaking; 390-397 critical rules; left out graph-building pseudo-code, baseline file, scoring and report writing |
| codebase-audit-suite/skills-catalog/ln-644-dependency-graph-auditor/references/dependency_rules.md | 169 | yes | used | lines 14-34 and 36-164 are in SKILL.md; left out lines 1-13 (its own source-priority table naming project docs) and the version lines |
| codebase-audit-suite/skills-catalog/ln-644-dependency-graph-auditor/references/graph_metrics.md | 91 | yes | used | metrics, SDP, thresholds, Lakos aggregate (6-77); left out deferred metrics |
| codebase-audit-suite/skills-catalog/ln-644-dependency-graph-auditor/references/import_patterns.md | 132 | yes | used | lines 118-127 are in SKILL.md; lines 5-117 (import patterns, module resolution, exclusion lists) are in references/layer-and-dependency-detection.md |
| codebase-audit-suite/skills-catalog/ln-645-open-source-replacer/SKILL.md | 337 | yes | used | lines 18-19, 293-297, 303, 307-308 (module discovery, severity, goal-based, ecosystem, classification gate); left out web/MCP research workflow, report format, migration plan |
| codebase-audit-suite/skills-catalog/ln-646-project-structure-auditor/SKILL.md | 341 | yes | used | lines 298-301, 307-308, 313; left out phases as pseudo-code greps, report writing |
| codebase-audit-suite/skills-catalog/ln-646-project-structure-auditor/references/structure_rules.md | 230 | yes | used | lines 7-49, 53-67, 92-95, 97-117, 119-186, 190-225 are in SKILL.md; left out: secrets and dockerignore baselines 69-89 (security, build), the two pointers to files that are not present (96, 118), header lines 1-6 naming its plugin |
| codebase-audit-suite/skills-catalog/ln-647-env-config-auditor/SKILL.md | 336 | yes | used | lines 19-21,48-51,319-323 (purpose, scope, rules); left out C1.2/C4.2 (security) and the grep pseudo-code of checks C2-C4, because it names tools not in this folder; scoring/report |
| codebase-audit-suite/skills-catalog/ln-647-env-config-auditor/references/config_rules.md | 119 | yes | used | lines 37-49, 62-92 (env files, validation frameworks, framework-managed vars) are in SKILL.md; lines 7-35 and 51-61 (how each language reads env vars, deployment files that declare them) are in references/env-config-patterns.md; left out: sensitive names (security) and the severity table with unexplained codes |
| codebase-audit-suite/skills-catalog/ln-650-persistence-performance-auditor/SKILL.md | 353 | yes | not used | persistence/query-efficiency/runtime-performance auditors: a performance reviewer's |
| codebase-audit-suite/skills-catalog/ln-651-query-efficiency-auditor/SKILL.md | 212 | yes | not used | persistence/query-efficiency/runtime-performance auditors: a performance reviewer's |
| codebase-audit-suite/skills-catalog/ln-652-transaction-correctness-auditor/SKILL.md | 237 | yes | used | lines 84-115 (scope too wide / too narrow), 151-152,164-173,175-183 (event channel name consistency); left out trigger-commit, rollback, long-held checks (correctness), grep steps, scoring, report |
| codebase-audit-suite/skills-catalog/ln-653-runtime-performance-auditor/SKILL.md | 212 | yes | not used | persistence/query-efficiency/runtime-performance auditors: a performance reviewer's |
| codebase-audit-suite/skills-catalog/ln-654-resource-lifecycle-auditor/SKILL.md | 335 | yes | used | scope mismatch, streaming holding, factory vs injection (64-67,91-96,100-103,126-130,247-250,272-276); left out cleanup, pool config, error-path leaks (correctness/performance), per-language greps, scoring, report |
| codebase-audit-suite/skills-catalog/shared/agents/agent_registry.json | 58 | yes | not used | multi-model agent runner infra (Codex/Gemini CLI orchestration) for an unrelated planning/debate skill family |
| codebase-audit-suite/skills-catalog/shared/agents/agent_runner.mjs | 1027 | yes | not used | multi-model agent runner infra (Codex/Gemini CLI orchestration) for an unrelated planning/debate skill family |
| codebase-audit-suite/skills-catalog/shared/agents/prompt_templates/general_analysis.md | 14 | yes | not used | prompt skeleton with own report and JSON format |
| codebase-audit-suite/skills-catalog/shared/agents/prompt_templates/iterative_refinement.md | 66 | yes | not used | generic review-prompt templates (iterative refinement, context/plan review) for planning skills, not code architecture |
| codebase-audit-suite/skills-catalog/shared/agents/prompt_templates/modes/code.md | 81 | yes | used | lines 38-40 and 44-47 (duplication, pattern compliance, layering); rest is own output schema and orchestration |
| codebase-audit-suite/skills-catalog/shared/agents/prompt_templates/modes/context.md | 52 | yes | not used | generic review-prompt templates (iterative refinement, context/plan review) for planning skills, not code architecture |
| codebase-audit-suite/skills-catalog/shared/agents/prompt_templates/modes/plan_review.md | 74 | yes | not used | generic review-prompt templates (iterative refinement, context/plan review) for planning skills, not code architecture |
| codebase-audit-suite/skills-catalog/shared/agents/prompt_templates/modes/story.md | 69 | yes | not used | epic/story/task planning review prompt templates and perspectives: a planning skill's, not code architecture review |
| codebase-audit-suite/skills-catalog/shared/agents/prompt_templates/refinement_perspectives.md | 80 | yes | not used | epic/story/task planning review prompt templates and perspectives: a planning skill's, not code architecture review |
| codebase-audit-suite/skills-catalog/shared/agents/prompt_templates/review_base.md | 99 | yes | not used | prompt skeleton with own report and JSON format |
| codebase-audit-suite/skills-catalog/shared/agents/prompt_templates/scope_analysis.md | 35 | yes | not used | epic/story/task planning review prompt templates and perspectives: a planning skill's, not code architecture review |
| codebase-audit-suite/skills-catalog/shared/agents/prompt_templates/task_decomposition.md | 42 | yes | not used | epic/story/task planning review prompt templates and perspectives: a planning skill's, not code architecture review |
| codebase-audit-suite/skills-catalog/shared/agents/schemas/code_review_schema.json | 37 | yes | not used | review-verdict JSON schemas for code/context/story review (other skills' output contracts) |
| codebase-audit-suite/skills-catalog/shared/agents/schemas/context_review_schema.json | 37 | yes | not used | review-verdict JSON schemas for code/context/story review (other skills' output contracts) |
| codebase-audit-suite/skills-catalog/shared/agents/schemas/story_review_schema.json | 37 | yes | not used | review-verdict JSON schemas for code/context/story review (other skills' output contracts) |
| codebase-audit-suite/skills-catalog/shared/concise_terms.md | 119 | yes | not used | verbose-to-concise phrase dictionary for authoring SKILL.md files: not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/ac_validation_rules.md | 161 | yes | not used | AC/INVEST story-validation criteria for a planning skill, not architecture review |
| codebase-audit-suite/skills-catalog/shared/references/agent_delegation_pattern.md | 343 | yes | not used | agent-delegation pattern for external Codex/Gemini CLI orchestration: generic review infra, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/agent_review_memory.md | 29 | yes | not used | write-only review_history.md log format: generic audit infra |
| codebase-audit-suite/skills-catalog/shared/references/agent_review_workflow.md | 376 | yes | not used | shared agent-review workflow mechanics (health checks, background execution, verification loop): generic orchestration, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/ai_ready_architecture.md | 146 | yes | used | re-read alone with the Read tool to its last line; nothing new beyond the passages already in SKILL.md (lines 9-30, 32-46, 50-72, 76-93, 117, 121-130) and lines 95-115 now in the reference file api-contract-checks.md; left out: its article citation and the external tools table (tools) |
| codebase-audit-suite/skills-catalog/shared/references/audit_coordinator_aggregation.md | 97 | yes | not used | generic audit-coordinator aggregation mechanics (parsing worker JSON, score rollups): orchestration plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/audit_coordinator_domain_mode.md | 82 | yes | not used | generic audit-runtime plumbing (domain-mode discovery, output schema, runtime contract, summary envelope, worker core contract): defines its own output format/transport, not architecture review content |
| codebase-audit-suite/skills-catalog/shared/references/audit_output_schema.md | 126 | yes | not used | generic audit-runtime plumbing (domain-mode discovery, output schema, runtime contract, summary envelope, worker core contract): defines its own output format/transport, not architecture review content |
| codebase-audit-suite/skills-catalog/shared/references/audit_runtime_contract.md | 107 | yes | not used | generic audit-runtime plumbing (domain-mode discovery, output schema, runtime contract, summary envelope, worker core contract): defines its own output format/transport, not architecture review content |
| codebase-audit-suite/skills-catalog/shared/references/audit_scoring.md | 61 | yes | not used | re-read alone with the Read tool to its last line: its own penalty scoring formula (own scoring scale) |
| codebase-audit-suite/skills-catalog/shared/references/audit_summary_contract.md | 89 | yes | not used | generic audit-runtime plumbing (domain-mode discovery, output schema, runtime contract, summary envelope, worker core contract): defines its own output format/transport, not architecture review content |
| codebase-audit-suite/skills-catalog/shared/references/audit_worker_core_contract.md | 89 | yes | not used | generic audit-runtime plumbing (domain-mode discovery, output schema, runtime contract, summary envelope, worker core contract): defines its own output format/transport, not architecture review content |
| codebase-audit-suite/skills-catalog/shared/references/auto_discovery_pattern.md | 92 | yes | not used | data-discovery fallback chains for task/kanban/team metadata: project-management plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/benchmark_generation.md | 153 | yes | not used | benchmark-generation code templates per language: performance-tooling, not architecture review content |
| codebase-audit-suite/skills-catalog/shared/references/ci_tool_detection.md | 112 | yes | not used | CI tool detection/execution command registry (lint/test/build per stack): build/CI tooling, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/clean_code_checklist.md | 73 | yes | used | re-read alone with the Read tool to its last line; only lines 27-57 (backward-compat shims, replacement rule, exceptions) are used; dead-code categories 5-26 and the checklist 59-69 are the dead-code reviewer's |
| codebase-audit-suite/skills-catalog/shared/references/code_efficiency_criterion.md | 36 | yes | not used | re-read alone with the Read tool to its last line: a writer's brevity self-check for code being written, not a review criterion for a change |
| codebase-audit-suite/skills-catalog/shared/references/community_discussion_formatting.md | 102 | yes | not used | GitHub Discussions formatting rules for community-engagement skills: unrelated domain |
| codebase-audit-suite/skills-catalog/shared/references/community_github_discovery.md | 65 | yes | not used | GitHub repo/discussion discovery protocol for community-engagement skills: unrelated domain |
| codebase-audit-suite/skills-catalog/shared/references/community_strategy_template.md | 131 | yes | not used | community-engagement strategy template: unrelated domain |
| codebase-audit-suite/skills-catalog/shared/references/context_validation.md | 90 | yes | used | re-read alone with the Read tool to its last line; rules 1, 2, 3 and 5 (lines 12-39, 50-59) are used; rule 4 (dependency versions) and rule 6 (performance findings) are other reviewers', and the exempt list, advisory section and coordinator table are its own workflow |
| codebase-audit-suite/skills-catalog/shared/references/coordinator_runtime_contract.md | 140 | yes | not used | generic coordinator runtime contract (manifest/state/checkpoint model): own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/coordinator_summary_contract.md | 177 | yes | not used | generic worker-summary envelope/payload shapes for unrelated skill families (story/task/epic/docs/quality/test planning): own output format |
| codebase-audit-suite/skills-catalog/shared/references/creation_quality_checklist.md | 64 | yes | not used | story/task creation checklist (INVEST/AC/story-size penalties): a planning skill's |
| codebase-audit-suite/skills-catalog/shared/references/cvss_severity_mapping.md | 83 | yes | not used | CVSS severity mapping for dependency vulnerabilities: the dependency/security reviewer's |
| codebase-audit-suite/skills-catalog/shared/references/decompose_first_pattern.md | 67 | yes | not used | decompose-first planning pattern for Epic/Story/Task coordinators: a planning skill's |
| codebase-audit-suite/skills-catalog/shared/references/destructive_operation_safety.md | 105 | yes | not used | destructive-operation detection/safety guard rules for task review and settings.json permissions: security/ops reviewer's domain |
| codebase-audit-suite/skills-catalog/shared/references/detection_efficacy_audit.md | 105 | yes | not used | post-incident detection-efficacy meta-audit of the review pipeline's own coverage gaps: process-improvement tool, not an architecture check |
| codebase-audit-suite/skills-catalog/shared/references/docs_generation_summary_contract.md | 20 | yes | not used | docs-generation worker summary contract: own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/docs_pipeline_runtime_contract.md | 38 | yes | not used | docs-pipeline coordinator runtime contract (ln-100 phases/state): own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/docs_quality_contract.md | 278 | yes | not used | docs-quality acceptance contract (header markers, doc kinds, placeholder/link rules) for a documentation-generation pipeline: own output format |
| codebase-audit-suite/skills-catalog/shared/references/docs_quality_rules.json | 341 | yes | not used | docs-quality acceptance contract (header markers, doc kinds, placeholder/link rules) for a documentation-generation pipeline: own output format |
| codebase-audit-suite/skills-catalog/shared/references/docs_runtime_contract.md | 41 | yes | not used | docs-pipeline (ln-110) runtime contract: own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/documentation_creation.md | 124 | yes | not used | documentation-creation workflow (guide/manual/adr/research templates): a documentation skill's |
| codebase-audit-suite/skills-catalog/shared/references/environment_setup_runtime_contract.md | 54 | yes | not used | environment-setup (ln-010) coordinator runtime contract: own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/environment_state_contract.md | 32 | yes | not used | environment-state (.hex-skills/environment_state.json) contract and schema: own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/environment_state_schema.json | 76 | yes | not used | environment-state (.hex-skills/environment_state.json) contract and schema: own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/epic_plan_summary_contract.md | 21 | yes | not used | epic-planning (ln-210) summary contract and runtime: own output format, a planning skill's |
| codebase-audit-suite/skills-catalog/shared/references/epic_planning_runtime_contract.md | 41 | yes | not used | epic-planning (ln-210) summary contract and runtime: own output format, a planning skill's |
| codebase-audit-suite/skills-catalog/shared/references/epistemic_protocol.md | 68 | yes | not used | source-attribution/anti-hallucination protocol for research outputs: generic research methodology, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/frontend_design_guide.md | 99 | yes | not used | frontend/UI design and accessibility guide: the frontend/UI reviewer's domain |
| codebase-audit-suite/skills-catalog/shared/references/frontmatter_reference.md | 114 | yes | not used | Claude Code frontmatter field reference for commands/agents/skills: unrelated to architecture review content |
| codebase-audit-suite/skills-catalog/shared/references/git_scope_detection.md | 47 | yes | not used | git changed-files scope-detection algorithm: generic plumbing utility, not architecture review content |
| codebase-audit-suite/skills-catalog/shared/references/git_worktree_fallback.md | 56 | yes | not used | git worktree isolation lifecycle for code-writing skills: generic plumbing, not architecture review content |
| codebase-audit-suite/skills-catalog/shared/references/goal_articulation_gate.md | 62 | yes | not used | generic goal-articulation meta-cognitive gate used before any task: not architecture-specific content |
| codebase-audit-suite/skills-catalog/shared/references/hook_health_check.md | 82 | yes | not used | Claude Code hook health-check validation steps and hooks event reference: tooling infra, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/hooks_reference.md | 94 | yes | not used | Claude Code hook health-check validation steps and hooks event reference: tooling infra, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/humanizer_checklist.md | 75 | yes | not used | anti-AI-slop writing/humanizer checklist for published text: writing-style content, not architecture review |
| codebase-audit-suite/skills-catalog/shared/references/input_resolution_pattern.md | 132 | yes | not used | Story/Task/Epic identifier auto-resolution chain (git/kanban lookups): a planning skill's plumbing |
| codebase-audit-suite/skills-catalog/shared/references/kanban_update_algorithm.md | 87 | yes | not used | kanban_board.md update/formatting algorithm: a planning skill's plumbing |
| codebase-audit-suite/skills-catalog/shared/references/linear_creation_workflow.md | 117 | yes | not used | Linear/file-mode issue-creation workflow for Epic/Story/Task: a planning skill's plumbing |
| codebase-audit-suite/skills-catalog/shared/references/markdown_read_protocol.md | 57 | yes | not used | progressive markdown-reading protocol for documentation skills/audits: generic reading discipline, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/mcp_integration_patterns.md | 66 | yes | not used | hex-line MCP tool-usage patterns (outline/edit/verify/bulk_replace): tooling preference, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/mcp_tool_preferences.md | 47 | yes | not used | hex-line MCP tool-usage patterns (outline/edit/verify/bulk_replace): tooling preference, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/meta_analysis_protocol.md | 183 | yes | not used | universal post-completion meta-analysis/self-audit protocol for coordinators: process-improvement tool, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/numbering_conventions.md | 129 | yes | not used | Epic/Story/Task numbering conventions: a planning skill's |
| codebase-audit-suite/skills-catalog/shared/references/optimization_runtime_contract.md | 82 | yes | not used | performance-optimizer (ln-810) runtime contract: a performance skill's own output format |
| codebase-audit-suite/skills-catalog/shared/references/orchestrator_pattern.md | 147 | yes | not used | generic L2 coordinator-to-L3-worker orchestration lifecycle: plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/output_normalization.md | 97 | yes | not used | CLI output normalization/dedup/truncation rules for test and build logs: generic tooling, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/plan_mode_pattern.md | 200 | yes | not used | Plan Mode preview/confirmation behavior pattern for coordinators and validators: generic UX plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/problem_solving.md | 66 | yes | not used | generic root-cause-first/5-Whys problem-solving checklist: cross-cutting debugging methodology, not an architecture-specific check |
| codebase-audit-suite/skills-catalog/shared/references/procedural_extraction_rules.md | 79 | yes | not used | procedural-vs-declarative scoring rules for extracting doc sections into slash commands: a documentation skill's |
| codebase-audit-suite/skills-catalog/shared/references/quality_runtime_contract.md | 49 | yes | not used | quality coordinator (ln-510) runtime/summary contract: own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/quality_summary_contract.md | 24 | yes | not used | quality coordinator (ln-510) runtime/summary contract: own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/questions_format.md | 48 | yes | not used | questions.md format spec for document validation questions: a documentation skill's |
| codebase-audit-suite/skills-catalog/shared/references/replan_algorithm.md | 158 | yes | not used | replan KEEP/UPDATE/OBSOLETE/CREATE comparison algorithm for Epic/Story/Task: a planning skill's |
| codebase-audit-suite/skills-catalog/shared/references/research_methodology.md | 148 | yes | not used | MCP Ref/Context7 research methodology and source-credibility hierarchy for library/standards research: generic research plumbing |
| codebase-audit-suite/skills-catalog/shared/references/research_tool_fallback.md | 47 | yes | not used | research tool fallback chain (Ref/Context7/WebSearch): generic plumbing |
| codebase-audit-suite/skills-catalog/shared/references/results_log_pattern.md | 67 | yes | not used | append-only audit results_log.md trend-tracking schema: generic plumbing |
| codebase-audit-suite/skills-catalog/shared/references/review_runtime_contract.md | 140 | yes | not used | review-coordinator (ln-310) deterministic runtime contract: own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/risk_based_testing_guide.md | 329 | yes | not used | risk-based testing/test-usefulness criteria guide: the test reviewer's domain |
| codebase-audit-suite/skills-catalog/shared/references/runtime_status_catalog.md | 107 | yes | not used | canonical runtime status/verdict enum catalog: own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/scope_decomposition_runtime_contract.md | 37 | yes | not used | scope-decomposition (ln-200) runtime/summary contract: a planning skill's own output format |
| codebase-audit-suite/skills-catalog/shared/references/scope_decomposition_summary_contract.md | 18 | yes | not used | scope-decomposition (ln-200) runtime/summary contract: a planning skill's own output format |
| codebase-audit-suite/skills-catalog/shared/references/skill_contract.md | 142 | yes | not used | SKILL.md authoring contract for this skills repository itself (structure/delegation/context-economy rules for writing Claude skills): meta content about the skill framework, not about reviewing a target codebase's architecture |
| codebase-audit-suite/skills-catalog/shared/references/storage_mode_detection.md | 132 | yes | not used | Linear-vs-File storage mode operation lookup tables for Epic/Story/Task: a planning skill's plumbing |
| codebase-audit-suite/skills-catalog/shared/references/story_execution_runtime_contract.md | 66 | yes | not used | story-execution (ln-400) runtime contract: a planning/execution skill's own output format |
| codebase-audit-suite/skills-catalog/shared/references/story_gate_runtime_contract.md | 76 | yes | not used | story quality-gate (ln-500) runtime contract: own output format, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/story_planning_runtime_contract.md | 61 | yes | not used | story-planning (ln-220) runtime contract: a planning skill's own output format |
| codebase-audit-suite/skills-catalog/shared/references/task_delegation_pattern.md | 74 | yes | not used | generic Agent-tool delegation pattern for coordinators: orchestration plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/references/task_planning_runtime_contract.md | 58 | yes | not used | task-planning (ln-300) runtime contract: a planning skill's own output format |
| codebase-audit-suite/skills-catalog/shared/references/template_loading_pattern.md | 94 | yes | not used | template-loading-and-copy-to-project pattern for Epic/Story/Task templates: a planning skill's plumbing |
| codebase-audit-suite/skills-catalog/shared/references/test_planning_runtime_contract.md | 44 | yes | not used | test-planning (ln-520) runtime/summary contract: the test reviewer's own output format |
| codebase-audit-suite/skills-catalog/shared/references/test_planning_summary_contract.md | 26 | yes | not used | test-planning (ln-520) runtime/summary contract: the test reviewer's own output format |
| codebase-audit-suite/skills-catalog/shared/references/tools_config_guide.md | 72 | yes | not used | tools_config.md bootstrap/detection guide for external tool providers (Linear, MCP, agents, git): generic plumbing |
| codebase-audit-suite/skills-catalog/shared/references/two_layer_detection.md | 98 | yes | used | re-read alone with the Read tool to its last line; only the Layer 2 steps (lines 40-71) are used; Layer 1 tool steps, the clone-finder tool, the clipboard example and the usage note are workflow of that plugin |
| codebase-audit-suite/skills-catalog/shared/scripts/audit-runtime/cli.mjs | 241 | yes | not used | audit-runtime CLI/guards/store implementation + its test harness: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/audit-runtime/lib/guards.mjs | 133 | yes | not used | audit-runtime CLI/guards/store implementation + its test harness: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/audit-runtime/lib/store.mjs | 229 | yes | not used | audit-runtime CLI/guards/store implementation + its test harness: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/audit-runtime/test/guards.mjs | 129 | yes | not used | audit-runtime CLI/guards/store implementation + its test harness: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/audit-runtime/test/negative.mjs | 108 | yes | not used | audit-runtime CLI/guards/store implementation + its test harness: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/audit-runtime/test/smoke.mjs | 146 | yes | not used | audit-runtime CLI/guards/store implementation + its test harness: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/coordinator-runtime/lib/artifacts.mjs | 24 | yes | not used | coordinator-runtime shared library (artifacts/cli-helpers/core/environment-state/runtime-constants/schemas/validate) + its tests: pure JS plumbing shared by all runtime families, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/coordinator-runtime/lib/cli-helpers.mjs | 94 | yes | not used | coordinator-runtime shared library (artifacts/cli-helpers/core/environment-state/runtime-constants/schemas/validate) + its tests: pure JS plumbing shared by all runtime families, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/coordinator-runtime/lib/core.mjs | 532 | yes | not used | coordinator-runtime shared library (artifacts/cli-helpers/core/environment-state/runtime-constants/schemas/validate) + its tests: pure JS plumbing shared by all runtime families, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/coordinator-runtime/lib/environment-state.mjs | 55 | yes | not used | coordinator-runtime shared library (artifacts/cli-helpers/core/environment-state/runtime-constants/schemas/validate) + its tests: pure JS plumbing shared by all runtime families, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/coordinator-runtime/lib/runtime-constants.mjs | 126 | yes | not used | coordinator-runtime shared library (artifacts/cli-helpers/core/environment-state/runtime-constants/schemas/validate) + its tests: pure JS plumbing shared by all runtime families, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/coordinator-runtime/lib/schemas.mjs | 580 | yes | not used | coordinator-runtime shared library (artifacts/cli-helpers/core/environment-state/runtime-constants/schemas/validate) + its tests: pure JS plumbing shared by all runtime families, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/coordinator-runtime/lib/validate.mjs | 150 | yes | not used | coordinator-runtime shared library (artifacts/cli-helpers/core/environment-state/runtime-constants/schemas/validate) + its tests: pure JS plumbing shared by all runtime families, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/coordinator-runtime/test/cli-test-helpers.mjs | 31 | yes | not used | coordinator-runtime shared library (artifacts/cli-helpers/core/environment-state/runtime-constants/schemas/validate) + its tests: pure JS plumbing shared by all runtime families, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/coordinator-runtime/test/consistency-scan.mjs | 179 | yes | not used | coordinator-runtime shared library (artifacts/cli-helpers/core/environment-state/runtime-constants/schemas/validate) + its tests: pure JS plumbing shared by all runtime families, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/coordinator-runtime/test/platform-regression.mjs | 251 | yes | not used | coordinator-runtime shared library (artifacts/cli-helpers/core/environment-state/runtime-constants/schemas/validate) + its tests: pure JS plumbing shared by all runtime families, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-pipeline-runtime/cli.mjs | 189 | yes | not used | docs-pipeline-runtime CLI/guards/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-pipeline-runtime/lib/guards.mjs | 62 | yes | not used | docs-pipeline-runtime CLI/guards/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-pipeline-runtime/lib/phases.mjs | 13 | yes | not used | docs-pipeline-runtime phases constant + docs-quality CLI/manifest/rules/verify implementation: JS plumbing implementing the docs-quality contract, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-pipeline-runtime/lib/store.mjs | 71 | yes | not used | docs-pipeline-runtime CLI/guards/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-pipeline-runtime/test/guards.mjs | 108 | yes | not used | docs-pipeline-runtime CLI/guards/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-pipeline-runtime/test/negative.mjs | 51 | yes | not used | docs-pipeline-runtime CLI/guards/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-pipeline-runtime/test/smoke.mjs | 70 | yes | not used | docs-pipeline-runtime CLI/guards/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-quality/cli.mjs | 84 | yes | not used | docs-pipeline-runtime phases constant + docs-quality CLI/manifest/rules/verify implementation: JS plumbing implementing the docs-quality contract, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-quality/lib/manifest.mjs | 103 | yes | not used | docs-pipeline-runtime phases constant + docs-quality CLI/manifest/rules/verify implementation: JS plumbing implementing the docs-quality contract, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-quality/lib/rules.mjs | 54 | yes | not used | docs-pipeline-runtime phases constant + docs-quality CLI/manifest/rules/verify implementation: JS plumbing implementing the docs-quality contract, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-quality/lib/verify.mjs | 331 | yes | not used | docs-pipeline-runtime phases constant + docs-quality CLI/manifest/rules/verify implementation: JS plumbing implementing the docs-quality contract, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-quality/test/smoke.mjs | 129 | yes | not used | docs-quality CLI test suite: pure JS plumbing testing own output format rules |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-runtime/cli.mjs | 214 | yes | not used | docs-runtime (ln-110) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-runtime/lib/guards.mjs | 72 | yes | not used | docs-runtime (ln-110) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-runtime/lib/phases.mjs | 12 | yes | not used | docs-runtime (ln-110) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-runtime/lib/store.mjs | 97 | yes | not used | docs-runtime (ln-110) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-runtime/test/guards.mjs | 98 | yes | not used | docs-runtime (ln-110) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-runtime/test/negative.mjs | 51 | yes | not used | docs-runtime (ln-110) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/docs-runtime/test/smoke.mjs | 71 | yes | not used | docs-runtime (ln-110) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/environment-setup-runtime/cli.mjs | 221 | yes | not used | environment-setup-runtime (ln-010) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/environment-setup-runtime/lib/guards.mjs | 98 | yes | not used | environment-setup-runtime (ln-010) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/environment-setup-runtime/lib/phases.mjs | 13 | yes | not used | environment-setup-runtime (ln-010) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/environment-setup-runtime/lib/store.mjs | 154 | yes | not used | environment-setup-runtime (ln-010) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/environment-setup-runtime/test/guards.mjs | 87 | yes | not used | environment-setup-runtime (ln-010) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/environment-setup-runtime/test/negative.mjs | 71 | yes | not used | environment-setup-runtime (ln-010) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/environment-setup-runtime/test/smoke.mjs | 58 | yes | not used | environment-setup-runtime (ln-010) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/epic-planning-runtime/cli.mjs | 175 | yes | not used | epic-planning-runtime (ln-210) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/epic-planning-runtime/lib/guards.mjs | 61 | yes | not used | epic-planning-runtime (ln-210) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/epic-planning-runtime/lib/phases.mjs | 15 | yes | not used | epic-planning-runtime (ln-210) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/epic-planning-runtime/lib/store.mjs | 52 | yes | not used | epic-planning-runtime (ln-210) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/epic-planning-runtime/test/guards.mjs | 105 | yes | not used | epic-planning-runtime (ln-210) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/epic-planning-runtime/test/negative.mjs | 48 | yes | not used | epic-planning-runtime (ln-210) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/epic-planning-runtime/test/smoke.mjs | 53 | yes | not used | epic-planning-runtime (ln-210) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/optimization-runtime/cli.mjs | 275 | yes | not used | optimization-runtime (ln-810) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/optimization-runtime/lib/guards.mjs | 138 | yes | not used | optimization-runtime (ln-810) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/optimization-runtime/lib/phases.mjs | 18 | yes | not used | optimization-runtime (ln-810) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/optimization-runtime/lib/store.mjs | 147 | yes | not used | optimization-runtime (ln-810) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/optimization-runtime/test/guards.mjs | 173 | yes | not used | optimization-runtime (ln-810) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/optimization-runtime/test/negative.mjs | 101 | yes | not used | optimization-runtime (ln-810) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/optimization-runtime/test/smoke.mjs | 78 | yes | not used | optimization-runtime (ln-810) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/planning-runtime/lib/cli.mjs | 116 | yes | not used | planning-runtime shared library (CLI helpers, guards, store, story/task template-section compliance checker): pure JS plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/planning-runtime/lib/guards.mjs | 42 | yes | not used | planning-runtime shared library (CLI helpers, guards, store, story/task template-section compliance checker): pure JS plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/planning-runtime/lib/store.mjs | 129 | yes | not used | planning-runtime shared library (CLI helpers, guards, store, story/task template-section compliance checker): pure JS plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/planning-runtime/lib/template-compliance.mjs | 85 | yes | not used | planning-runtime shared library (CLI helpers, guards, store, story/task template-section compliance checker): pure JS plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/quality-runtime/cli.mjs | 218 | yes | not used | quality-runtime (ln-510) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/quality-runtime/lib/guards.mjs | 85 | yes | not used | quality-runtime (ln-510) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/quality-runtime/lib/phases.mjs | 17 | yes | not used | quality-runtime (ln-510) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/quality-runtime/lib/store.mjs | 102 | yes | not used | quality-runtime (ln-510) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/quality-runtime/test/guards.mjs | 130 | yes | not used | quality-runtime (ln-510) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/quality-runtime/test/negative.mjs | 42 | yes | not used | quality-runtime (ln-510) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/quality-runtime/test/smoke.mjs | 79 | yes | not used | quality-runtime (ln-510) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/review-runtime/cli.mjs | 318 | yes | not used | review-runtime (ln-310) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/review-runtime/lib/guards.mjs | 134 | yes | not used | review-runtime (ln-310) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/review-runtime/lib/phases.mjs | 15 | yes | not used | review-runtime (ln-310) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/review-runtime/lib/store.mjs | 129 | yes | not used | review-runtime (ln-310) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/review-runtime/test/guards.mjs | 219 | yes | not used | review-runtime (ln-310) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/review-runtime/test/negative.mjs | 86 | yes | not used | review-runtime (ln-310) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/review-runtime/test/smoke.mjs | 139 | yes | not used | review-runtime (ln-310) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/scope-decomposition-runtime/cli.mjs | 193 | yes | not used | scope-decomposition-runtime (ln-200) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/scope-decomposition-runtime/lib/guards.mjs | 58 | yes | not used | scope-decomposition-runtime (ln-200) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/scope-decomposition-runtime/lib/phases.mjs | 13 | yes | not used | scope-decomposition-runtime (ln-200) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/scope-decomposition-runtime/lib/store.mjs | 87 | yes | not used | scope-decomposition-runtime (ln-200) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/scope-decomposition-runtime/test/guards.mjs | 80 | yes | not used | scope-decomposition-runtime (ln-200) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/scope-decomposition-runtime/test/negative.mjs | 47 | yes | not used | scope-decomposition-runtime (ln-200) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/scope-decomposition-runtime/test/smoke.mjs | 51 | yes | not used | scope-decomposition-runtime (ln-200) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-execution-runtime/cli.mjs | 270 | yes | not used | story-execution-runtime (ln-400) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-execution-runtime/lib/guards.mjs | 118 | yes | not used | story-execution-runtime (ln-400) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-execution-runtime/lib/phases.mjs | 15 | yes | not used | story-execution-runtime (ln-400) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-execution-runtime/lib/store.mjs | 172 | yes | not used | story-execution-runtime (ln-400) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-execution-runtime/test/guards.mjs | 112 | yes | not used | story-execution-runtime (ln-400) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-execution-runtime/test/negative.mjs | 107 | yes | not used | story-execution-runtime (ln-400) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-execution-runtime/test/smoke.mjs | 118 | yes | not used | story-execution-runtime (ln-400) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-gate-runtime/cli.mjs | 252 | yes | not used | story-gate-runtime (ln-500) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-gate-runtime/lib/guards.mjs | 97 | yes | not used | story-gate-runtime (ln-500) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-gate-runtime/lib/phases.mjs | 15 | yes | not used | story-gate-runtime (ln-500) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-gate-runtime/lib/store.mjs | 132 | yes | not used | story-gate-runtime (ln-500) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-gate-runtime/test/guards.mjs | 107 | yes | not used | story-gate-runtime (ln-500) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-gate-runtime/test/negative.mjs | 90 | yes | not used | story-gate-runtime (ln-500) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-gate-runtime/test/smoke.mjs | 90 | yes | not used | story-gate-runtime (ln-500) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-planning-runtime/cli.mjs | 198 | yes | not used | story-planning-runtime (ln-220) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-planning-runtime/lib/guards.mjs | 87 | yes | not used | story-planning-runtime (ln-220) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-planning-runtime/lib/phases.mjs | 15 | yes | not used | story-planning-runtime (ln-220) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-planning-runtime/lib/store.mjs | 74 | yes | not used | story-planning-runtime (ln-220) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-planning-runtime/test/negative.mjs | 73 | yes | not used | story-planning-runtime (ln-220) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/story-planning-runtime/test/smoke.mjs | 59 | yes | not used | story-planning-runtime (ln-220) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/task-planning-runtime/cli.mjs | 195 | yes | not used | task-planning-runtime (ln-300) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/task-planning-runtime/lib/guards.mjs | 83 | yes | not used | task-planning-runtime (ln-300) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/task-planning-runtime/lib/phases.mjs | 14 | yes | not used | task-planning-runtime (ln-300) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/task-planning-runtime/lib/store.mjs | 71 | yes | not used | task-planning-runtime (ln-300) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/task-planning-runtime/test/negative.mjs | 73 | yes | not used | task-planning-runtime (ln-300) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/task-planning-runtime/test/smoke.mjs | 54 | yes | not used | task-planning-runtime (ln-300) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/test-planning-runtime/cli.mjs | 215 | yes | not used | test-planning-runtime (ln-520) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/test-planning-runtime/lib/guards.mjs | 75 | yes | not used | test-planning-runtime (ln-520) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/test-planning-runtime/lib/phases.mjs | 13 | yes | not used | test-planning-runtime (ln-520) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/test-planning-runtime/lib/store.mjs | 106 | yes | not used | test-planning-runtime (ln-520) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/test-planning-runtime/test/guards.mjs | 92 | yes | not used | test-planning-runtime (ln-520) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/test-planning-runtime/test/negative.mjs | 42 | yes | not used | test-planning-runtime (ln-520) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/scripts/test-planning-runtime/test/smoke.mjs | 70 | yes | not used | test-planning-runtime (ln-520) CLI/guards/phases/store implementation + tests: pure JS state-machine plumbing, not architecture content |
| codebase-audit-suite/skills-catalog/shared/templates/adr_template.md | 99 | yes | not used | ADR document template: a documentation skill's own output format |
| codebase-audit-suite/skills-catalog/shared/templates/audit_worker_report_template.md | 202 | yes | not used | audit worker report template: defines its own output format |
| codebase-audit-suite/skills-catalog/shared/templates/codebase_audit_template.md | 122 | yes | not used | codebase audit report template: defines its own output format |
| codebase-audit-suite/skills-catalog/shared/templates/guide_template.md | 83 | yes | not used | pattern-guide/manual/research/story document templates: documentation and planning skills' own output formats |
| codebase-audit-suite/skills-catalog/shared/templates/linear_integration.md | 375 | yes | not used | Linear API integration guide (Team ID discovery, create_project/create_issue): a planning skill's plumbing |
| codebase-audit-suite/skills-catalog/shared/templates/manual_template.md | 149 | yes | not used | pattern-guide/manual/research/story document templates: documentation and planning skills' own output formats |
| codebase-audit-suite/skills-catalog/shared/templates/patterns_template.md | 198 | yes | not used | architecture patterns catalog template with its own scoring legend: defines its own output format/scoring scale |
| codebase-audit-suite/skills-catalog/shared/templates/refactoring_task_template.md | 527 | yes | not used | refactoring-task template with its own DRY/KISS/YAGNI checklist: a code-quality/task-planning skill's own output format |
| codebase-audit-suite/skills-catalog/shared/templates/research_template.md | 115 | yes | not used | pattern-guide/manual/research/story document templates: documentation and planning skills' own output formats |
| codebase-audit-suite/skills-catalog/shared/templates/story_template.md | 238 | yes | not used | pattern-guide/manual/research/story document templates: documentation and planning skills' own output formats |
| codebase-audit-suite/skills-catalog/shared/templates/task_template_implementation.md | 208 | yes | not used | implementation task template with its own fields (technical approach, logging, error-handling): a task-planning skill's own output format |
| codebase-audit-suite/skills-catalog/shared/templates/test_task_template.md | 536 | yes | not used | test task template with risk-based test-planning fields: the test reviewer's/planning skill's own output format |
| comprehensive-review/.claude-plugin/plugin.json | 10 | yes | not used | plugin manifest |
| comprehensive-review/.codex-plugin/plugin.json | 16 | yes | not used | plugin manifest |
| comprehensive-review/LICENSE | 20 | no | not used | licence text, skipped as allowed |
| comprehensive-review/agents/architect-review.md | 162 | yes | not used | persona and capability lists (patterns, cloud, tooling); no concrete detection conditions beyond other sources |
| comprehensive-review/agents/code-reviewer.md | 171 | yes | not used | persona and capability lists for code review generally (tools, languages); no concrete architecture conditions |
| comprehensive-review/agents/security-auditor.md | 156 | yes | not used | re-read alone with the Read tool to its last line: security auditor agent profile (DevSecOps, compliance, cloud, incident response); the security reviewer's |
| comprehensive-review/commands/full-review.md | 597 | yes | used | lines 153-159 (architecture and design review checklist) and 254 (scalability barriers); rest is the multi-phase orchestrator, state files and own report format |
| comprehensive-review/commands/pr-enhance.md | 709 | yes | not used | writing PR descriptions, checklists and splitting advice for authors (code samples), not review of a change's structure |
| feature-dev-code-reviewer/LICENSE | 202 | no | not used | licence text, skipped as allowed |
| feature-dev-code-reviewer/code-reviewer.md | 46 | yes | not used | bugs/guidelines persona with own confidence scale |
| mattpocock-code-review/LICENSE | 21 | no | not used | licence text, skipped as allowed |
| mattpocock-code-review/code-review/SKILL.md | 87 | yes | used | lines 43-56 (smell baseline from Fowler); left out spec/standards two-axis flow, sub-agent prompts, issue tracker |
| mattpocock-code-review/code-review/agents/openai.yaml | 3 | yes | not used | interface display metadata |
| multi-agent-review/SKILL.md | 213 | yes | not used | orchestration pseudo-code for a multi-agent coordinator, no review criteria |
| multi-reviewer-patterns/LICENSE | 20 | no | not used | licence text, skipped as allowed |
| multi-reviewer-patterns/SKILL.md | 127 | yes | not used | dimension allocation, dedup, calibration and consolidated report: coordinator work and own scale/format |
| multi-reviewer-patterns/references/review-dimensions.md | 127 | yes | used | lines 60-81 (architecture review checklist); other dimensions are other reviewers' |
| official-code-review/.claude-plugin/plugin.json | 9 | yes | not used | plugin manifest |
| official-code-review/.orphaned_at | 0 | no | not used | empty marker file |
| official-code-review/LICENSE | 202 | no | not used | licence text, skipped as allowed |
| official-code-review/README.md | 246 | yes | not used | plugin docs for PR commenting command |
| official-code-review/commands/code-review.md | 92 | yes | not used | left out: its own output format; GitHub PR commenting orchestration |
| pr-review-toolkit/.claude-plugin/plugin.json | 9 | yes | not used | plugin manifest |
| pr-review-toolkit/README.md | 313 | yes | not used | re-read alone with the Read tool to its last line: usage guide for that plugin's six agents (triggers, workflows, install); its type-design material is already carried from the agent file itself |
| pr-review-toolkit/agents/code-reviewer.md | 47 | yes | not used | compliance/bug review against CLAUDE.md with own 0-100 confidence scale |
| pr-review-toolkit/agents/code-simplifier.md | 83 | yes | not used | simplifies code for clarity (code quality) and applies project style |
| pr-review-toolkit/agents/comment-analyzer.md | 70 | yes | not used | comment accuracy: code_quality/compliance |
| pr-review-toolkit/agents/pr-test-analyzer.md | 69 | yes | not used | tests reviewer's (own 1-10 criticality scale) |
| pr-review-toolkit/agents/silent-failure-hunter.md | 130 | yes | not used | error handling and silent failures: correctness reviewer's (project logging specifics) |
| pr-review-toolkit/agents/type-design-analyzer.md | 110 | yes | used | lines 17-22,25-28,31-34,37-40,43-46,81-110 (invariants, four questions, principles, anti-patterns, how to weigh improvements); left out the 1-10 ratings and own output block (contradict the fixed contract) |
| pr-review-toolkit/commands/review-pr.md | 189 | yes | not used | re-read alone with the Read tool to its last line: that plugin's own review command (aspects, agent launch, summary layout) |
| secrets-management/SKILL.md | 47 | yes | not used | secrets handling checklist: security reviewer's |
| secrets-management/references/github-secrets.md | 13 | yes | not used | secrets handling checklist: security reviewer's |
| secrets-management/references/vault-setup.md | 13 | yes | not used | secrets handling checklist: security reviewer's |
| security-guidance/.claude-plugin/plugin.json | 10 | yes | not used | security-guidance plugin overview/readme: security reviewer's |
| security-guidance/.in_use/15821 | 0 | yes | not used | empty marker file |
| security-guidance/.in_use/47413 | 0 | yes | not used | empty marker file |
| security-guidance/LICENSE | 202 | no | not used | licence text, skipped as allowed |
| security-guidance/README.md | 123 | yes | not used | security-guidance plugin overview/readme: security reviewer's |
| security-guidance/hooks/_base.py | 234 | yes | not used | hook infra (debug log, usage/cost accounting): security reviewer's own tool code |
| security-guidance/hooks/diffstate.py | 493 | yes | not used | git baseline/diff-state tracking for the Stop-hook reviewer: security reviewer's own tool code |
| security-guidance/hooks/ensure_agent_sdk.py | 862 | yes | not used | SessionStart bootstrap for agent SDK venv: security reviewer's own tool code |
| security-guidance/hooks/extensibility.py | 289 | yes | not used | org-specific security guidance/pattern extensibility loader: security reviewer's own tool code |
| security-guidance/hooks/gitutil.py | 917 | yes | not used | git/diff subprocess helpers for the commit/stop reviewer: security reviewer's own tool code |
| security-guidance/hooks/hooks.json | 124 | yes | not used | security-guidance plugin overview/readme: security reviewer's |
| security-guidance/hooks/llm.py | 1935 | yes | not used | LLM diff-review and agentic commit-reviewer implementation (vuln categories, model selection, SDK plumbing): security reviewer's |
| security-guidance/hooks/patterns.py | 360 | yes | not used | regex security pattern definitions (XSS, injection, deserialization, crypto): security reviewer's |
| security-guidance/hooks/reporesolve.py | 306 | yes | not used | repo-root resolution from command/cwd/touched-paths: security reviewer's own tool code |
| security-guidance/hooks/review_api.py | 398 | yes | not used | agentic investigate/self-refute prompts and schemas for the commit reviewer: security reviewer's |
| security-guidance/hooks/security_reminder_hook.py | 2426 | yes | not used | main hook orchestrator (commit/push/stop handlers, pattern checks): security reviewer's own tool code |
| security-guidance/hooks/session_state.py | 161 | yes | not used | per-session state file locking: security reviewer's own tool code |
| security-guidance/hooks/sg-python.sh | 122 | yes | not used | python interpreter shim for hook launch (Windows/venv compat): security reviewer's own tool code |
| security-guidance/tests/conftest.py | 214 | yes | not used | pytest fixtures/test harness for the security hook: security reviewer's own test code |
| security-guidance/tests/test_git_index_locks.py | 288 | yes | not used | test: git index locking/temp-index behavior of the hook: security reviewer's own test code |
| security-guidance/tests/test_repo_resolution.py | 619 | yes | not used | test: repo-root resolution, commit/push/stop handler integration: security reviewer's own test code |
| security-guidance/tests/test_review_model.py | 404 | yes | not used | test: model-selection cache, SDK path, pricing: security reviewer's own test code |
| security-guidance/tests/test_temp_index_cleanup.py | 166 | yes | not used | test: git index locking/temp-index behavior of the hook: security reviewer's own test code |
| security/007/SKILL.md | 47 | yes | not used | security reviewer's / workflow bundles for security testing (left out: another reviewer's) |
| security/007/references/ai-agent-security.md | 470 | yes | not used | threat modeling, OWASP, API security and AI-agent security guides: security reviewer's |
| security/007/references/api-security-patterns.md | 479 | yes | not used | threat modeling, OWASP, API security and AI-agent security guides: security reviewer's |
| security/007/references/detailed-guide.md | 647 | yes | not used | security auditor persona and workflow (red/blue team, incident playbooks): security reviewer's |
| security/007/references/incident-playbooks.md | 394 | yes | not used | threat modeling, OWASP, API security and AI-agent security guides: security reviewer's |
| security/007/references/owasp-checklists.md | 76 | yes | not used | threat modeling, OWASP, API security and AI-agent security guides: security reviewer's |
| security/007/references/stride-pasta-guide.md | 395 | yes | not used | threat modeling, OWASP, API security and AI-agent security guides: security reviewer's |
| security/007/scripts/config.py | 472 | yes | not used | scanner config and scoring engine: security reviewer's own CLI tool |
| security/007/scripts/full_audit.py | 1327 | yes | not used | scanner/audit CLI orchestrator scripts: security reviewer's own tool code |
| security/007/scripts/quick_scan.py | 490 | yes | not used | scanner/audit CLI orchestrator scripts: security reviewer's own tool code |
| security/007/scripts/requirements.txt | 26 | yes | not used | scanner config and scoring engine: security reviewer's own CLI tool |
| security/007/scripts/scanners/__init__.py | 0 | yes | not used | empty package marker |
| security/007/scripts/scanners/dependency_scanner.py | 1317 | yes | not used | supply-chain/dependency scanner: security reviewer's own tool code |
| security/007/scripts/scanners/injection_scanner.py | 1114 | yes | not used | injection vulnerability scanner: security reviewer's own tool code |
| security/007/scripts/scanners/secrets_scanner.py | 1018 | yes | not used | deep secrets scanner: security reviewer's own tool code |
| security/007/scripts/score_calculator.py | 765 | yes | not used | scanner config and scoring engine: security reviewer's own CLI tool |
| security/security-and-hardening/SKILL.md | 476 | yes | not used | security hardening guidance: security reviewer's |
| security/security-and-hardening/references/security-checklist.md | 13 | yes | not used | security reviewer's / workflow bundles for security testing (left out: another reviewer's) |
| security/security-arsenal/SKILL.md | 446 | no | not used | offensive security payload library; stopped reading per safety policy |
| security/security-arsenal/references/details.md | 540 | no | not used | offensive security payload library; stopped reading per safety policy |
| security/security-audit/SKILL.md | 222 | yes | not used | security reviewer's / workflow bundles for security testing (left out: another reviewer's) |
| security/security-lens-reviewer/SKILL.md | 35 | yes | not used | security reviewer's / workflow bundles for security testing (left out: another reviewer's) |
| security/security-reviewer/SKILL.md | 46 | yes | not used | security reviewer's / workflow bundles for security testing (left out: another reviewer's) |
| security/security-scanning-security-hardening/SKILL.md | 161 | yes | not used | security reviewer's / workflow bundles for security testing (left out: another reviewer's) |
| superpowers-code-review/LICENSE | 21 | no | not used | licence text, skipped as allowed |
| superpowers-code-review/receiving-code-review/SKILL.md | 205 | yes | not used | how to respond to review feedback; not a review criterion |
| superpowers-code-review/requesting-code-review/SKILL.md | 95 | yes | not used | how to request a review and dispatch subagents |
| superpowers-code-review/requesting-code-review/code-reviewer.md | 198 | yes | not used | reviewer prompt: generic checklist lines (separation of concerns, sound design) already covered by fuller passages; own output format and subagent rules |
| thermos/.cursor-plugin/plugin.json | 32 | yes | not used | plugin docs, changelog, manifest |
| thermos/CHANGELOG.md | 8 | yes | not used | plugin docs, changelog, manifest |
| thermos/LICENSE | 21 | no | not used | licence text, skipped as allowed |
| thermos/README.md | 70 | yes | not used | plugin docs, changelog, manifest |
| thermos/agents/thermo-nuclear-code-quality-review-subagent.md | 23 | yes | not used | orchestration of two subagents |
| thermos/agents/thermo-nuclear-review-subagent.md | 28 | yes | not used | orchestration of two subagents |
| thermos/assets/logo.png | 240 | no | not used | binary image |
| thermos/skills/thermo-nuclear-code-quality-review/SKILL.md | 192 | yes | used | lines 34-69, 73-87, 183-190 (file-size rule, spaghetti growth, thin abstractions, type boundaries, canonical layer, atomic updates, questions, presumptive blockers); left out tone, ambition prompt, flag/remedy lists that repeat the same points, output ordering |
| thermos/skills/thermo-nuclear-review/SKILL.md | 51 | yes | not used | bug/security/devex/feature-gate audit: other reviewers' |
| thermos/skills/thermos/SKILL.md | 21 | yes | not used | orchestration of two subagents |
