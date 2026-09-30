# CharterGate

CharterGate is a standalone GenLayer Intelligent Contract designed to function as a small group treasury. It enables a group to deposit funds under a fixed, frozen charter, and securely manage payouts. The lifecycle depends strictly on **hash-checked web evidence**, **AI eligibility screening**, and a **mandatory member vote** for every payout.

## Contract Design
- **Frozen Charter**: The treasury's purpose (charter) is frozen at creation and acts as the sole rubric for funding decisions.
- **AI Eligibility Screening**: Evaluates a proposal against the charter based on public web evidence fetched dynamically.
- **Hash-Checked Evidence**: Evidence fetched from the web is rigorously checked against a proposer-provided SHA-256 hash. If the evidence changes, is too large, or produces a 404 error, the contract fails-closed, immediately terminating the proposal.
- **Mandatory Member Vote**: AI eligibility alone is never sufficient for a payout. Once a proposal passes the AI screen, members must vote on it. It must achieve the required quorum and YES vote threshold.
- **Reservations & Payout**: During the proposal lifecycle, funds are reserved so that eligible proposals are guaranteed funding if finalized. After deadlines pass and votes succeed, a single payout is emitted. 
- **Deadlines**: The contract uses strict screen and vote deadlines.
- **Sponsor Recovery**: The sponsor may recover the unreserved treasury funds only after a predetermined sunset timestamp, ensuring safety from permanent lockup without circumventing active proposal guarantees.

## Why GenLayer?
CharterGate is only possible due to GenLayer's unique Intelligent Contract capabilities:
1. **Web Access**: The contract dynamically fetches off-chain receipts, invoices, or project milestones to verify claims. Standard smart contracts cannot perform native HTTP requests.
2. **LLM Evaluation**: Natural language rules (the charter) are evaluated against unstructured web evidence using LLM-based reasoning, allowing subjective intent-matching that code cannot do.
3. **`strict_eq` Consensus**: GenLayer's equivalence principle (`strict_eq`) requires validator consensus on exactly formatted boolean LLM outputs, preventing hallucinated payouts.

## Links and Evidence
- **Source Code**: [charter_gate.py](contracts/charter_gate.py)
- **Focused Tests**: [test_charter_gate.py](tests/direct/test_charter_gate.py)
- **Test Summary**: [pytest_summary.txt](pytest_summary.txt)
- **Deployment Receipt**: [receipt.json](deploy/receipt.json)
- **Source Hash Evidence**: [deployment_verification.txt](deployment_verification.txt)
- **Explorer Address**: [0xf175D6ED3fA0a5d416CAd7440EDFdB27e327FB0F](https://explorer-studio-dev.genlayer.com/address/0xf175D6ED3fA0a5d416CAd7440EDFdB27e327FB0F?chain=studio-devnet)
- **Explorer Transaction**: [0xbc69f25a92b86da345bb5d45370372ebb8dfb31523b9f3a4a07a2716bfc897ed](https://explorer-studio-dev.genlayer.com/transactions/0xbc69f25a92b86da345bb5d45370372ebb8dfb31523b9f3a4a07a2716bfc897ed?chain=studio-devnet)

## Verification Status
- **Tests**: 9 direct tests passed.
- **Payout Verification**: Precisely one payout message was emitted in the direct test. 
- **Unverified Features**: Live recipient delivery, sponsor recovery after sunset, and failed-payment recovery remain unverified on the live network.

## Final Deployment Details
- **Address**: `0xf175D6ED3fA0a5d416CAd7440EDFdB27e327FB0F`
- **TX**: `0xbc69f25a92b86da345bb5d45370372ebb8dfb31523b9f3a4a07a2716bfc897ed`
- **Source SHA-256**: `bdb9c0e7ca27a435deb618f9242a2e8d09afb3f3b3dc7665a07455cd63c4ab92`
