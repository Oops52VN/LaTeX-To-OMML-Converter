---
trigger: always_on
description: Mandatory project context, walkthrough logging, implementation plan archival, prompt history rules, project tree sync, single-line purpose format, and English language standard for the .agent directory.
---

# `.agent` Governance & Documentation Rules

You **MUST** strictly adhere to the following 6 rules in every session and task within this workspace:

## 1. Pre-Execution Context Analysis (`.agent/`)
- **Mandatory Pre-Flight Check**: Before executing any task, modifying code, or running commands, you **MUST** inspect, read, and analyze all orientation and context documents inside the `.agent/` directory (`rules/`, `walkthroughes/` or `walkthroughs/`, `implementation_plans_done/`, and `prompt_history/`).
- Ensure all architectural decisions and changes align with the historical context recorded in `.agent/`.

## 2. Session Walkthrough Logging (`walkthroughes/` / `walkthroughs/`)
- **Per-Session / Per-Task Separation (CRITICAL)**: Each distinct working session or conversation must be recorded in its own separate walkthrough file. **DO NOT** merge walkthroughs from different sessions/conversations that occurred on the same date into a single file.
- **File Naming Convention**: `<DD>_<MM>_<YYYY>_W<No>.md`, where `<No>` is the sequential ascending number (`1, 2, 3...`) for each separate session/walkthrough on that date (e.g., `02_11_2026_W1.md`, `02_11_2026_W2.md`).
- **Language**: **100% English**.
- **Content**: Summarize the objectives completed, architectural changes, files added/modified/deleted, verification results, and key technical notes for that specific session.

## 3. Completed Implementation Plans (`.agent/implementation_plans_done/`)
- **Per-Plan Separation**: Always save and archive each deployed and completed implementation plan as an individual file in `.agent/implementation_plans_done/`.
- **File Naming Convention**: `<DD>_<MM>_<YYYY>_P<No>.md`, where `<No>` is the sequential ascending plan number (`1, 2, 3...`) for that date (e.g., `02_11_2026_P1.md`, `02_11_2026_P2.md`, `02_11_2026_P3.md`).
- **Language**: **100% English**.
- **Content**: Include goal description, scope, step-by-step execution details, file changes, and verification outcomes.

## 4. User Prompt History Logging (`.agent/prompt_history/`)
- **Per-Conversation Separation (CRITICAL)**: Each distinct conversation session must be saved into its own separate prompt history file. **DO NOT** combine prompts from multiple different conversations initiated on the same date into a single file.
- **File Naming Convention**: `<DD>_<MM>_<YYYY>_C<No>.txt`, using the date when the conversation was initiated and the sequential ascending conversation number (`1, 2, 3...`) for that date (e.g., `02_11_2026_C1.txt`, `02_11_2026_C2.txt`).
- **Format**: Plaintext (`.txt`).
- **Required Metadata per Prompt**:
  - **UTC+0 Timestamp**: Exact timestamp of the prompt in `YYYY-MM-DD HH:MM:SS UTC+0` format.
  - **AI Model**: The active AI model selected for that turn.
  - **Execution Duration**: Total execution wall-clock time for the turn (in seconds).
  - **Token Consumption**: Estimated/converted total tokens consumed during the turn (input + tool I/O + output).
- **Data Processing & Transformation (CRITICAL)**:
  - **DO NOT** save the raw/original user text verbatim.
  - You **MUST** normalize, fix spelling/typographical errors, expand abbreviated or implicit context into a clear and detailed technical specification while keeping it concise, upgrade the phrasing to professional engineering standards, and translate the entire prompt into **accurate, idiomatic English** before saving.

## 5. Project Tree Synchronization (`tree.txt`)
- **Mandatory Synchronization**: You **MUST** update `tree.txt` whenever any change occurs in the repository's filesystem hierarchy (including adding new files/folders, modifying structural contents, moving, or deleting files/directories).
- **Format Consistency & Symmetry**: Maintain strict columnar alignment, symmetry, and formatting consistency across the tree diagram and the core component linkage table.
- **Single-Line PURPOSE Requirement (STRICT)**: Descriptions in the `PURPOSE` column **MUST NEVER** break or wrap into multiple lines; each entry must fit entirely onto a single line to preserve horizontal structure and symmetry.
- **Exception for `.agent/`**: In `tree.txt`, only display the `.agent/` directory itself as a single entry. **DO NOT** expand or list individual walkthroughs, implementation plans, rules, or prompt history files inside `.agent/`.

## 6. Language Standard (100% English)
- All source code, commit messages, documentation, walkthroughs, implementation plans, prompt history records, code comments, and technical notes **MUST** be written in **100% English**, unless the user explicitly requests another specific language.
