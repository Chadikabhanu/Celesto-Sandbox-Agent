# Celesto Sandbox Code Verification Agent — Demo Video Script & Storyboard

This document provides a **complete, scene-by-scene script, screen action cues, and word-for-word voiceover narration** to record a 2 to 2.5 minute video demonstration of the project.

---

## Recording Setup & Tips

- **Recommended Resolution**: 1080p (1920x1080) or 1440p
- **Screen Layout**:
  - **Option A (Split Screen)**: Terminal on the Left (60%), VS Code / GitHub README on the Right (40%).
  - **Option B (Full Terminal Focus)**: Terminal maximized with high-contrast colored font, switching to VS Code / Browser when referencing architecture and reports.
- **Hands-Free Demo Command**:
  ```bash
  python scripts/demo_walkthrough.py --auto --delay 1.8
  ```
  *(Runs through all 5 scenes automatically with realistic pacing so you can focus entirely on speaking or syncing audio).*
- **Interactive Step-by-Step Command**:
  ```bash
  python scripts/demo_walkthrough.py
  ```
  *(Pauses at each scene and waits for you to press Enter).*

---

## Scene-by-Scene Storyboard & Voiceover Script

### Scene 1: The Problem & Architecture Boundary (0:00 – 0:30)

| Time | On-Screen Visual | Action | Spoken Voiceover (Word-for-Word) |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:15** | [README.md](README.md) showing the Mermaid Architecture Diagram or GitHub Repo | Highlight the Host Control Plane vs. Celesto MicroVM Isolation Boundary | *"Autonomous coding agents generate, modify, and test untrusted code. Running that code directly on the host or inside standard containers risks host corruption, secret exfiltration, and cascading step failures. Today, I'm presenting the Celesto Sandbox Code Verification Agent—a secure, microVM-isolated execution plane coupled with a trusted host ledger."* |
| **0:15 – 0:30** | Terminal running `python scripts/demo_walkthrough.py` | Run **Scene 1** in terminal | *"Here, the agent requests an execution environment. The control plane provisions an isolated Celesto microVM with a unique cryptographic identifier, enforcing zero host subprocess fallback. In just 58 milliseconds, the microVM boots into a ready state with zero host contamination."* |

---

### Scene 2: Pre-Execution Safety Callbacks & Containment (0:30 – 1:00)

| Time | On-Screen Visual | Action | Spoken Voiceover (Word-for-Word) |
| :--- | :--- | :--- | :--- |
| **0:30 – 0:45** | Terminal showing **Scene 2** | Watch destructive & exfiltration payloads get blocked | *"Standard containers only inspect exit codes after destructive commands have already executed. With Celesto's class-based safety callbacks, we hook directly into the VM lifecycle before execution. Watch what happens when adversarial code attempts to wipe the filesystem or exfiltrate our host canary secret via external sockets."* |
| **0:45 – 1:00** | Terminal output showing `[VETOED / BLOCKED]` in red & `Host Fixture Integrity Check: PASS` | Point cursor at the policy reasons and SHA-256 match | *"The pre-run callback intercepts and vetoes every malicious command before it ever touches the guest kernel. Our host fixture SHA-256 hash remains completely intact, and our canary secret was never disclosed to the network."* |

---

### Scene 3: Step 7 Snapshot Checkpointing & Transient Recovery (1:00 – 1:35)

| Time | On-Screen Visual | Action | Spoken Voiceover (Word-for-Word) |
| :--- | :--- | :--- | :--- |
| **1:00 – 1:18** | Terminal running **Scene 3** (10 Canonical Steps) | Watch the visual pipeline execute Steps 1 through 10 | *"In autonomous multi-step pipelines, test verification steps frequently experience transient timeouts or network blips. Without point-in-time recovery, the agent either fails completely or has to restart from scratch, wasting compute and API tokens."* |
| **1:18 – 1:35** | Terminal highlights `[STEP 07]` failure, `[STEP 08]` rollback to Step 6, and `[STEP 07]` attempt 2 success | Highlight the recovery transition | *"Here, transient failure is injected at Step 7. Instead of discarding the prior work, our recovery engine applies the `checkpoint_rollback_retry` policy. It restores the guest `/workspace` from the clean Step 6 snapshot, immediately re-executes the test on Attempt 2, and successfully finishes the pipeline."* |

---

### Scene 4: High-Throughput Concurrency & Zero State Collisions (1:35 – 2:05)

| Time | On-Screen Visual | Action | Spoken Voiceover (Word-for-Word) |
| :--- | :--- | :--- | :--- |
| **1:35 – 1:50** | Terminal running **Scene 4** (5 parallel jobs) | Watch 5 parallel jobs launch with `asyncio.gather` | *"When scaling AI evaluations across benchmark suites, running concurrent jobs often causes file collisions and shared-state leaks. We evaluated simultaneous parallel verification workloads across independent Celesto microVMs."* |
| **1:50 – 2:05** | Terminal showing 5 jobs completed, `Collisions: 0`, `Shared-State Leaks: 0` | Point out the execution metrics | *"All five jobs ran concurrently with strictly isolated filesystems. We observed zero namespace collisions, zero cross-job leaks, and guaranteed terminal teardown to the `deleted` state upon completion."* |

---

### Scene 5: Cryptographic Audit Ledger & Production Readiness (2:05 – 2:30)

| Time | On-Screen Visual | Action | Spoken Voiceover (Word-for-Word) |
| :--- | :--- | :--- | :--- |
| **2:05 – 2:18** | Terminal showing **Scene 5** & `logs/commands.jsonl` | Briefly display recent audit log entries | *"Every command attempt, safety decision, and lifecycle event is logged immutably in our host ledger and `commands.jsonl` audit trail for complete post-execution provenance."* |
| **2:18 – 2:30** | VS Code terminal showing `pytest tests/test_reports.py` passing 100% | Run `pytest tests/test_reports.py` or highlight test suite | *"With 108 automated tests passing, 100% reliability across 20 fresh sequential runs, and strict hardware virtualization boundaries, the Celesto Sandbox Code Verification Agent makes autonomous code execution safe, auditable, and resilient. Thank you!"* |

---

## Quick Reference Commands for Recording

```bash
# 1. Run the animated demo in terminal (Hands-free mode)
python scripts/demo_walkthrough.py --auto --delay 1.8

# 2. Show the test contract checks passing (Optional live validation)
pytest tests/test_reports.py -v

# 3. View the audit trail
cat logs/commands.jsonl | head -n 5
```
