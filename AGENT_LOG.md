# Agent Log

## Fixes Applied
1. **GenVM Storage Types (`DynArray`, `TreeMap`) to Primitives**
   - **Problem:** Using standard Python collections crashed GenVM, but using `DynArray` locally raised `NameError` blocking local `gltest`. The user's external review identified the `try...except ImportError` mock as a defect and requested reusing the `TxtLock` proven pattern of string primitives.
   - **Fix:** Refactored `charter_gate.py` to remove `DynArray` and `TreeMap` entirely. Modified `members`, `proposals`, `has_voted`, and `payment_liabilities` to be `str` JSON representations (`self.members_json`, etc.). State is parsed and dumped using `json.loads` and `json.dumps` at the point of access in writes.

2. **Strict Boolean Validation and Prompt Formatting**
   - **Problem:** The AI prompt missed critical parameters (frozen amount/recipient) and was vulnerable to prompt injection via unescaped purpose/evidence.
   - **Fix:** Expanded the prompt in `screen_proposal` to include `amount` (wei) and `recipient`. Wrapped user input as `Untrusted User Input (Proposed Purpose)` and `Untrusted Evidence (Fetched from URL)` explicitly.

3. **Consistent Release of Expired Eligible Proposals**
   - **Problem:** If a proposal met voting threshold requirements, calling `release_expired` after the voting deadline would set the state to `EXPIRED` instead of properly approving and finalizing the payout.
   - **Fix:** In `release_expired`, for proposals in `STATE_ELIGIBLE` where `now > deadline_vote`, it now explicitly calls `self.finalize(pid)` to properly assess the vote outcome rather than automatically cancelling.

4. **Test Suite `create_proposal` Defect**
   - **Problem:** The regression test called `contract.create_proposal` which did not exist on the contract.
   - **Fix:** Swapped it to `contract.propose` and resolved `PermissionError` local environment limitations on Windows by building custom deployment scripts instead of relying on `gltest` loader hooks that fail file locking.

5. **Network Deployment & Cryptographic Verification**
   - **Action:** Fixed the `scripts/deploy_studio.py` configuration loader so it properly connected to `studio-dev`. Deployed the final refactored `CharterGate` contract successfully to address `0xf175D6ED3fA0a5d416CAd7440EDFdB27e327FB0F`.
   - **Action:** Created `verify_hash.py` to make a `gen_getContractCode` JSON-RPC call.
   - **Result:** Successfully downloaded the Base64 representation of the on-chain executed payload. Hash `bdb9c0e7ca27a435deb618f9242a2e8d09afb3f3b3dc7665a07455cd63c4ab92` matched exactly with local source `charter_gate.py`.

6. **Unverified Features Note**
   - Live payout delivery, sponsor recovery after sunset, and failed-payment recovery remain unverified on the live network.
