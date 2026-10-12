# CharterGate

CharterGate is a standalone GenLayer Intelligent Contract designed to function as a small group treasury. It enables a group to deposit funds under a fixed, frozen charter, and securely manage payouts. The lifecycle depends strictly on **hash-checked web evidence**, **AI eligibility screening**, a **mandatory member vote** for every payout, and an **identifiable, protected payout liability recovery mechanism**.

## Contract Design
- **Frozen Charter**: The treasury's purpose (charter) is frozen at creation and acts as the sole rubric for funding decisions.
- **AI Eligibility Screening**: Evaluates a proposal against the charter based on public web evidence fetched dynamically.
- **Hash-Checked Evidence**: Evidence fetched from the web is rigorously checked against a proposer-provided SHA-256 hash. If the evidence changes, is too large, or produces a 404 error, the contract fails-closed, immediately terminating the proposal.
- **Mandatory Member Vote**: AI eligibility alone is never sufficient for a payout. Once a proposal passes the AI screen, members must vote on it. It must achieve the required quorum and YES vote threshold.
- **Identifiable, Protected Payout Liability**: When member voting succeeds, `finalize(pid)` approves the payout as an active liability (`STATE_APPROVED`, `PAYOUT_APPROVED`). The proposal's funds remain fully reserved in `reserved_funds`.
- **Security Finding Regarding Deployment 0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0**:
  - The previous implementation added `report_failed_delivery(pid)` and `confirm_delivery(pid)` which accepted unverified caller assertions.
  - **Attack 1 (Duplicate Payment / Double Spend)**: A caller can claim a payout, receive the transfer, falsely invoke `report_failed_delivery(pid)`, and invoke `retry_payout(pid)` to receive duplicate payments.
  - **Attack 2 (False Delivery Confirmation / Liability Erasure)**: A sponsor can invoke `confirm_delivery(pid)` without payment delivery, wiping the liability and prematurely decrementing `reserved_funds`, allowing the sponsor to withdraw backing funds after sunset.
  - **Attack Reproduction Tests**: Both vulnerabilities are reproduced in focused tests `test_attack_false_failure_causes_duplicate_payment` and `test_attack_false_delivery_confirmation_releases_unpaid_liability` in [test_charter_gate.py](tests/direct/test_charter_gate.py).
  - Both `0x71D888072B123C61E553d82a3ffbAceD8B690410` and `0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0` are **SUPERSEDED** and not suitable for resubmission.
- **Sponsor Withdrawal Protection**: The sponsor cannot withdraw treasury funds backing any active or pending payout liability (`self.balance < self.reserved_funds + amount` reverts), even after the sunset timestamp.
- **Deadlines**: Strict screen and vote deadlines enforce bounded decision windows.
- **Lifetime Proposal Cap**: Each deployment accepts at most 25 lifetime proposals, bounding internal storage.

## Why GenLayer?
CharterGate is only possible due to GenLayer's unique Intelligent Contract capabilities:
1. **Web Access**: The contract dynamically fetches off-chain receipts, invoices, or project milestones to verify claims. Standard smart contracts cannot perform native HTTP requests.
2. **LLM Evaluation**: Natural language rules (the charter) are evaluated against unstructured web evidence using LLM-based reasoning, allowing subjective intent-matching that code cannot do.
3. **`strict_eq` Consensus**: GenLayer's equivalence principle (`strict_eq`) requires validators to agree on the normalized eligibility result (`outcome` and boolean `eligible`) before a proposal can enter member voting. A successful member vote is still required before any payout path runs.

## Links and Evidence
- **Source Code**: [charter_gate.py](contracts/charter_gate.py)
- **Focused Tests**: [test_charter_gate.py](tests/direct/test_charter_gate.py)
- **Test Summary**: [pytest_summary.txt](pytest_summary.txt)
- **Deployment Receipt (Superseded)**: [receipt.json](deploy/receipt.json)
- **Schema Validation Evidence**: [chartergate_validation.json](deploy/chartergate_validation.json)
- **Source Hash Evidence**: [deployment_verification.txt](deployment_verification.txt)
- **Live Demo Analysis Proof**: [payout_recovery_live_demo.json](deploy/payout_recovery_live_demo.json)
- **Superseded Deployment Address**: [0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0](https://explorer-studio-dev.genlayer.com/address/0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0?chain=studio-devnet)
- **Prior Superseded Address**: [0x71D888072B123C61E553d82a3ffbAceD8B690410](https://explorer-studio-dev.genlayer.com/address/0x71D888072B123C61E553d82a3ffbAceD8B690410?chain=studio-devnet)

## Live Demonstration Analysis & Settlement Findings
- **Analysis of Existing Live Demo (`payout_recovery_live_demo.json`)**:
  - Step 7: `claim_payout(0)` emitted 100 wei to recipient `0x81b637d8fCD2C6da6359E6963113a1170de795e4` in TX `0xe4a763d664837ae9e56208ea93dd5d1771c4dca39afeab45319b44cb3e906f5d`. The transfer successfully delivered 100 wei to the recipient.
  - Step 9: The operator manually called `report_failed_delivery(0)` in TX `0x0a8673267bf5df4323be39da72ec1c57d2e10412cf5f19b4b50b04fd9afad0df` despite the transfer having succeeded.
  - Step 10: `retry_payout(0)` was invoked in TX `0x247a732da6a6f6062c675ea176e9885a19327147070a2b1b62d601247fc7112c`, emitting another 100 wei transfer.
  - On-chain verification via studio-dev RPC confirmed the recipient received **200 wei** and the contract balance dropped from 5000 to **4800 wei**.
  - This proves that manually triggered state transitions do not demonstrate safe recovery, but rather demonstrate vulnerability to duplicate payments. Claims that this demonstrated safe recovery have been retracted.
- **Exact Runtime & Settlement Capabilities on Studio-Dev**:
  - Runner: `py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng`
  - SDK: `py-lib-genlayer-std:kzr02ndm9et4qkmbqpq5djjt5sme2yt76n7sz1qbzax0knt6mam0`
  - In GenVM, `@gl.evm.contract_interface` `emit_transfer()` emits an asynchronous external message scheduled for finalization.
  - Value is immediately deducted from the sender contract balance upon emission and held in the emitted message.
  - If a child transaction fails, value is not automatically returned to the contract balance.
  - The runtime does not provide any WASI syscall or SDK method for querying transaction receipts or message delivery status.
  - GenVM schema validation rejects error callbacks (`__on_errored_message__`), and EVM contract callbacks are not functional on Studio/studio-dev.
  - Without a runtime-level delivery confirmation or failure dispatch hook, contracts cannot verify external transfer outcomes on-chain without relying on unverified caller attestations, timeouts, balance polling, or raw transaction IDs.

## Deployment Status
- **0x71D888072B123C61E553d82a3ffbAceD8B690410**: SUPERSEDED (rejected: no payout liability retention after finalize).
- **0x7F58edF6431aE89251Ef4DB555DD817743FaA7E0**: SUPERSEDED (rejected: unverified caller assertions allow duplicate payment and liability erasure).
- **Tests**: 19 focused direct tests passed, including both vulnerability reproduction tests.

