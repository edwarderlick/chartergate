# CharterGate Implementation Checklist

## 1. Runtime and Network Configuration
- [x] Pinned GenVM runtime magic comment to the first line (py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng).
- [x] Verified pin against the referenced working `txtlock.py`.
- [x] Updated `requirements.txt` to `genlayer-py==0.19.0rc2` and `genlayer-test==0.30.0rc2`.
- [x] Deployed successfully to `studio-dev` endpoint.

## 2. Constructor Validations & Documented Rules
- [x] Added checks for empty charter, malformed/zero member addresses, and duplicate members.
- [x] Added checks for empty/oversized member lists.
- [x] Added checks for impossible quorum/threshold values (e.g. threshold > member count).
- [x] Documented the exact voting rule ensuring AI eligibility alone NEVER pays anyone.

## 3. Strict AI Output Parsing (JSON Boolean)
- [x] Modified `screen_proposal` to require strict boolean (`is_eligible is True`).
- [x] Added regression tests for `"false"`, `"true"`, integers, missing fields, null, and malformed JSON.
- [x] Ensured malformed outputs transition the proposal to `STATE_EVIDENCE_FAILED` or `STATE_INELIGIBLE`.
- [x] Include frozen proposal amount and recipient in AI evaluation.
- [x] Treat purpose/evidence explicitly as untrusted data in the prompt.

## 4. Test Suite and Runtime Resolution
- [x] Replaced nonexistent `create_proposal` in tests with actual `propose` method.
- [x] Expired `ELIGIBLE` proposals delegate to `finalize` to ensure consistent resolution (preventing cancellation of successful proposals).
- [x] Fixed `PermissionError` blockages in `gltest` deployment tests by extracting working deployment scripts.

## 5. Storage Types and Deployment Source Verification
- [x] Removed bootloader substitution (`try...except ImportError`).
- [x] Swapped `DynArray` and `TreeMap` for `str` state variables with JSON serialization for members, proposals, and liabilities (following the primitive-storage pattern from `TxtLock`).
- [x] Redeployed `CharterGate` using the new completely unmocked script.
- [x] Verified actual on-chain deployment bytes using `gen_getContractCode` exactly matched local source file SHA-256 hash.

## 6. Final Agent Verification (Completed)
- [x] Fixed time warping test logic (patched `_get_now_ts` to use `datetime.now(timezone.utc)` for SDK compatibility with wasi_mock).
- [x] All 9/9 regression tests pass successfully, including `test_release_expired_eligible`.
- [x] Exactly one payout message was emitted in the direct test; recipient delivery was not verified.
- [x] Verified successful live deployment and transaction lifecycle (Finalized) on `studio-devnet` at `0xf175D6ED3fA0a5d416CAd7440EDFdB27e327FB0F`.
- [x] **Live Payout Unverified:** Live payout execution flow blocked by SDK `ValueError: Failed to get schema from all clients` when querying `studio-dev.genlayer.com/api` via `gen_getContractSchemaForCode`.
- [ ] **Unverified Features:** Live payout delivery, sponsor recovery after sunset, and failed-payment recovery remain unverified on the live network.
