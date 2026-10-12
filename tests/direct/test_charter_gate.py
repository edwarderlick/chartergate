import json
import hashlib
import time
import pytest

STATE_PENDING = 0
STATE_ELIGIBLE = 1
STATE_INELIGIBLE = 2
STATE_EVIDENCE_FAILED = 3
STATE_APPROVED = 4
STATE_REJECTED = 5
STATE_EXPIRED = 6
STATE_FINALIZED = 7

PAYOUT_NONE = 0
PAYOUT_APPROVED = 1
PAYOUT_PENDING = 2
PAYOUT_DELIVERED = 3
PAYOUT_FAILED = 4

MAX_LIFETIME_PROPOSALS = 25


def _addr_hex(addr) -> str:
    if hasattr(addr, "as_hex"):
        return addr.as_hex
    from eth_utils import to_checksum_address

    return to_checksum_address("0x" + addr.hex())


def test_charter_gate_schema_generation_accepts_public_methods():
    import json
    import os
    import subprocess
    import sys

    code = """
import json
from genvm_linter.validate import validate_contract
result = validate_contract("contracts/charter_gate.py")
payload = result.to_dict()
payload["schema"] = result.schema
print(json.dumps(payload))
raise SystemExit(0 if result.ok else 1)
"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        env=env,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    payload = json.loads(completed.stdout)
    methods = payload["schema"]["methods"]
    assert "__on_errored_message__" not in methods
    assert all(not name.startswith("__") for name in methods)

def _setup_mocks(vm, eligible: bool, rule_results=["rule met"], mismatch=False, fetch_failed=False, malformed=False, custom_llm_raw=None):
    vm.clear_mocks()
    if fetch_failed:
        vm.mock_web(r".*evidence.*", {"status": 404, "body": ""})
    elif mismatch:
        vm.mock_web(r".*evidence.*", {"status": 200, "body": "Modified content"})
    else:
        vm.mock_web(r".*evidence.*", {"status": 200, "body": "Receipt for team dinner."})
        
    if malformed:
        vm.mock_llm(r".*Evaluate.*", json.dumps(json.dumps({"eligible": "false", "rule_results": 123})))
    elif custom_llm_raw is not None:
        vm.mock_llm(r".*Evaluate.*", custom_llm_raw)
    else:
        vm.mock_llm(r".*Evaluate.*", json.dumps(json.dumps({"eligible": eligible, "rule_results": rule_results})))

def test_charter_gate_success_flow(direct_vm, direct_deploy, direct_alice, direct_bob):
    alice_hex = _addr_hex(direct_alice)
    bob_hex = _addr_hex(direct_bob)
    
    direct_vm.deal(direct_alice, 50000)
    direct_vm.deal(direct_bob, 0)
    
    sunset = int(time.time()) + 100000
    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "Funds can be used for team dinners.", f"{alice_hex},{bob_hex}", 2, 1, sunset)
    
    direct_vm.sender = direct_alice
    direct_vm.value = 500
    direct_vm.deal(direct_vm._contract_address, 500)
    contract.deposit()
    direct_vm.value = 0
    
    evidence_url = "https://raw.githubusercontent.com/evidence"
    evidence_text = "Receipt for team dinner."
    evidence_hash = hashlib.sha256(evidence_text.encode('utf-8')).hexdigest()
    
    now = int(time.time())
    screen_dl = now + 1000
    vote_dl = now + 2000
    
    pid = contract.propose(bob_hex, 100, "Team dinner", evidence_url, evidence_hash, screen_dl, vote_dl)
    assert contract.get_proposal(pid)["state"] == STATE_PENDING
    
    _setup_mocks(direct_vm, True)
    contract.screen_proposal(pid)
    assert contract.get_proposal(pid)["eligibility_details"] == "SUCCESS"
    assert contract.get_proposal(pid)["state"] == STATE_ELIGIBLE
    
    # Voting
    direct_vm.sender = direct_alice
    contract.vote(pid, True)
    
    direct_vm.sender = direct_bob
    contract.vote(pid, True)
    
    # Finalize should approve payout liability without prematurely decrementing reserved funds
    contract.finalize(pid)
    prop = contract.get_proposal(pid)
    assert prop["state"] == STATE_APPROVED
    assert prop["payout_state"] == PAYOUT_APPROVED
    assert contract.reserved_funds == 100

    # Claim payout
    contract.claim_payout(pid)
    prop = contract.get_proposal(pid)
    assert prop["state"] == STATE_APPROVED
    assert prop["payout_state"] == PAYOUT_PENDING
    assert contract.reserved_funds == 100

    # Confirm delivery
    contract.confirm_delivery(pid)
    prop = contract.get_proposal(pid)
    assert prop["state"] == STATE_FINALIZED
    assert prop["payout_state"] == PAYOUT_DELIVERED
    assert contract.reserved_funds == 0

def test_constructor_empty_charter(direct_vm, direct_deploy, direct_alice):
    alice_hex = _addr_hex(direct_alice)
    sunset = int(time.time()) + 10000
    with direct_vm.expect_revert("Charter text cannot be empty"):
        direct_deploy("contracts/charter_gate.py", alice_hex, "", f"{alice_hex}", 1, 1, sunset)

def test_constructor_zero_sponsor_rejected(direct_vm, direct_deploy, direct_alice):
    alice_hex = _addr_hex(direct_alice)
    sunset = int(time.time()) + 10000
    with direct_vm.expect_revert("Zero address sponsor not allowed"):
        direct_deploy(
            "contracts/charter_gate.py",
            "0x0000000000000000000000000000000000000000",
            "text",
            f"{alice_hex}",
            1,
            1,
            sunset,
        )

def test_constructor_duplicate_members(direct_vm, direct_deploy, direct_alice):
    alice_hex = _addr_hex(direct_alice)
    sunset = int(time.time()) + 10000
    with direct_vm.expect_revert("Duplicate member"):
        direct_deploy("contracts/charter_gate.py", alice_hex, "text", f"{alice_hex},{alice_hex}", 1, 1, sunset)

def test_constructor_bad_threshold(direct_vm, direct_deploy, direct_alice):
    alice_hex = _addr_hex(direct_alice)
    sunset = int(time.time()) + 10000
    with direct_vm.expect_revert("Quorum and threshold must be > 0 to require a YES vote"):
        direct_deploy("contracts/charter_gate.py", alice_hex, "text", f"{alice_hex}", 1, 0, sunset)

def test_malformed_llm_and_ineligible(direct_vm, direct_deploy, direct_alice):
    alice_hex = _addr_hex(direct_alice)
    sunset = int(time.time()) + 10000
    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "text", f"{alice_hex}", 1, 1, sunset)
    
    direct_vm.deal(direct_alice, 500)
    direct_vm.sender = direct_alice
    direct_vm.value = 500
    direct_vm.deal(direct_vm._contract_address, 500)
    contract.deposit()
    direct_vm.value = 0
    
    evidence_text = "Receipt for team dinner."
    evidence_hash = hashlib.sha256(evidence_text.encode('utf-8')).hexdigest()
    now = int(time.time())
    
    pid1 = contract.propose(alice_hex, 10, "Purpose", "https://raw.githubusercontent.com/evidence1", evidence_hash, now+1000, now+2000)
    _setup_mocks(direct_vm, False, malformed=True)
    contract.screen_proposal(pid1)
    assert contract.get_proposal(pid1)["state"] == STATE_EVIDENCE_FAILED
    
    pid2 = contract.propose(alice_hex, 10, "Purpose", "https://raw.githubusercontent.com/evidence2", evidence_hash, now+1000, now+2000)
    _setup_mocks(direct_vm, False) # Valid LLM output but eligible=false
    contract.screen_proposal(pid2)
    assert contract.get_proposal(pid2)["state"] == STATE_INELIGIBLE
    
def test_sponsor_recovery_before_sunset_reverts(direct_vm, direct_deploy, direct_alice, direct_bob):
    alice_hex = _addr_hex(direct_alice)
    bob_hex = _addr_hex(direct_bob)
    sunset = int(time.time()) + 10000
    
    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "text", f"{alice_hex}", 1, 1, sunset)
    direct_vm.deal(direct_alice, 1000)
    direct_vm.sender = direct_alice
    direct_vm.value = 500
    direct_vm.deal(direct_vm._contract_address, 500)
    contract.deposit()
    direct_vm.value = 0
    
    evidence_text = "Receipt for team dinner."
    evidence_hash = hashlib.sha256(evidence_text.encode('utf-8')).hexdigest()
    now = int(time.time())
    
    # Create proposal that will fail payment (no funds, or contract reverting)
    # EOA transfers shouldn't fail natively unless there is no balance. 
    # But let's mock it failing by making amount > available when finalizing? No, amount is reserved.
    # We can test sunset withdraw
    
    with direct_vm.expect_revert("Cannot withdraw before sunset time"):
        contract.withdraw_treasury(100)
        
    # We mock time for sunset? direct_vm doesn't have time warp, we must rely on other mechanics or accept we can't test sunset directly without it.
    pass

def test_deadline_boundaries(direct_vm, direct_deploy, direct_alice):
    alice_hex = _addr_hex(direct_alice)
    sunset = int(time.time()) + 10000
    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "text", f"{alice_hex}", 1, 1, sunset)
    
    direct_vm.deal(direct_alice, 1000)
    direct_vm.sender = direct_alice
    direct_vm.value = 500
    direct_vm.deal(direct_vm._contract_address, 500)
    contract.deposit()
    direct_vm.value = 0
    
    now = int(time.time())
    evidence_hash = hashlib.sha256(b"").hexdigest()
    
    with direct_vm.expect_revert("Screen deadline must be in the future"):
        contract.propose(alice_hex, 10, "Purpose", "https://raw.githubusercontent.com/1", evidence_hash, now-100, now+2000)
        
    with direct_vm.expect_revert("Vote deadline must be after screen deadline"):
        contract.propose(alice_hex, 10, "Purpose", "https://raw.githubusercontent.com/1", evidence_hash, now+1000, now+500)

def test_lifetime_proposal_cap_rejects_before_state_changes(direct_vm, direct_deploy, direct_alice):
    alice_hex = _addr_hex(direct_alice)
    sunset = int(time.time()) + 100000
    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "text", f"{alice_hex}", 1, 1, sunset)

    direct_vm.deal(direct_alice, 1000)
    direct_vm.sender = direct_alice
    direct_vm.value = 1000
    direct_vm.deal(direct_vm._contract_address, 1000)
    contract.deposit()
    direct_vm.value = 0

    evidence_text = "Receipt for team dinner."
    evidence_hash = hashlib.sha256(evidence_text.encode("utf-8")).hexdigest()
    now = int(time.time())

    for idx in range(MAX_LIFETIME_PROPOSALS):
        pid = contract.propose(
            alice_hex,
            1,
            f"Purpose {idx}",
            f"https://raw.githubusercontent.com/evidence{idx}",
            evidence_hash,
            now + 1000 + idx,
            now + 2000 + idx,
        )
        _setup_mocks(direct_vm, False)
        contract.screen_proposal(pid)
        assert contract.get_proposal(pid)["state"] == STATE_INELIGIBLE
        assert contract.active_proposals == 0
        assert contract.reserved_funds == 0

    assert contract.proposal_count == MAX_LIFETIME_PROPOSALS
    reserved_before = contract.reserved_funds
    active_before = contract.active_proposals
    with direct_vm.expect_revert("Max lifetime proposals reached"):
        contract.propose(
            alice_hex,
            1,
            "Over cap",
            "https://raw.githubusercontent.com/evidence-over-cap",
            evidence_hash,
            now + 5000,
            now + 6000,
        )

    assert contract.proposal_count == MAX_LIFETIME_PROPOSALS
    assert contract.reserved_funds == reserved_before
    assert contract.active_proposals == active_before

def test_charter_gate_malformed_llm_output(direct_vm, direct_deploy, direct_alice, direct_bob):
    alice_hex = _addr_hex(direct_alice)
    bob_hex = _addr_hex(direct_bob)
    
    sunset = int(time.time()) + 100000
    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "Funds can be used for team dinners.", f"{alice_hex},{bob_hex}", 1, 1, sunset)
    
    direct_vm.deal(direct_alice, 50000)
    direct_vm.sender = direct_alice
    direct_vm.value = 50000
    direct_vm.deal(direct_vm._contract_address, 50000)
    contract.deposit()
    direct_vm.value = 0

    evidence_url = "https://raw.githubusercontent.com/evidence"
    evidence_text = "Receipt for team dinner."
    evidence_hash = hashlib.sha256(evidence_text.encode('utf-8')).hexdigest()

    malformed_cases = [
        "not a json at all",
        "{}", # missing 'eligible'
        '{"eligible": "true"}', # string instead of boolean
        '{"eligible": "false"}', # string instead of boolean
        '{"eligible": 1}', # integer
        '{"eligible": null}', # null
    ]

    for i, custom_raw in enumerate(malformed_cases):
        contract.propose(
            bob_hex, 
            100, 
            "Test", 
            evidence_url, 
            evidence_hash, 
            int(time.time()) + 100000, 
            int(time.time()) + 200000
        )
        pid = contract.proposal_count - 1

        
        _setup_mocks(direct_vm, True, custom_llm_raw=custom_raw)
        contract.screen_proposal(pid)
        
        prop = contract.get_proposal(pid)
        assert prop["state"] in [STATE_EVIDENCE_FAILED, STATE_INELIGIBLE]
        if prop["state"] == STATE_INELIGIBLE:
            assert prop["eligibility_details"] == "Rejected by AI"


def test_release_expired_eligible(direct_vm, direct_deploy, direct_alice, direct_bob):
    alice_hex = _addr_hex(direct_alice)
    bob_hex = _addr_hex(direct_bob)

    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "Funds.", f"{alice_hex},{bob_hex}", 1, 1, int(time.time()) + 10000)

    direct_vm.deal(direct_alice, 500)
    direct_vm.sender = direct_alice
    direct_vm.value = 500
    direct_vm.deal(direct_vm._contract_address, 500)
    contract.deposit()
    direct_vm.value = 0

    now = int(time.time())
    
    # Test release_expired paying properly for successful votes
    evidence_hash = hashlib.sha256("Receipt for team dinner.".encode('utf-8')).hexdigest()
    pid1 = contract.propose(alice_hex, 50, "P1", "https://raw.githubusercontent.com/evidence", evidence_hash, now+1000, now+2000)
    _setup_mocks(direct_vm, True)
    contract.screen_proposal(pid1)
    print("PROPOSAL:", contract.get_proposal(pid1))
    contract.vote(pid1, True)
    
    # Fast forward past vote deadline
    from datetime import datetime, timezone
    new_time = datetime.fromtimestamp(now + 3000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
    direct_vm.warp(new_time)
    
    # Patch the SDK's message datetime manually since gltest missed it
    import genlayer
    genlayer.message.datetime = new_time
    
    start_reserved = contract.reserved_funds
    contract.release_expired(pid1)
    
    # Assert proposal is approved liability
    assert contract.get_proposal(pid1)["state"] == STATE_APPROVED
    assert contract.get_proposal(pid1)["payout_state"] == PAYOUT_APPROVED
    assert contract.reserved_funds == start_reserved
    
    # Claim payout
    contract.claim_payout(pid1)
    assert contract.get_proposal(pid1)["payout_state"] == PAYOUT_PENDING
    assert contract.reserved_funds == start_reserved
    
    # Verify exactly one EmitExternalMessage
    emissions = sum(1 for t in direct_vm._traces if "EmitExternalMessage" in str(t))
    assert emissions == 1, f"Expected exactly 1 external message for payment to be emitted, got {emissions}"
    
    # Confirm delivery
    contract.confirm_delivery(pid1)
    assert contract.get_proposal(pid1)["state"] == STATE_FINALIZED
    assert contract.get_proposal(pid1)["payout_state"] == PAYOUT_DELIVERED
    assert contract.reserved_funds == start_reserved - 50
    
    # Test that finalize also fails after release_expired (only one payment)
    with direct_vm.expect_revert():
        contract.finalize(pid1)


def test_payout_approval_preserves_reserved_funds_liability(direct_vm, direct_deploy, direct_alice, direct_bob):
    alice_hex = _addr_hex(direct_alice)
    bob_hex = _addr_hex(direct_bob)
    sunset = int(time.time()) + 100000
    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "Dinners.", f"{alice_hex},{bob_hex}", 1, 1, sunset)

    direct_vm.deal(direct_alice, 500)
    direct_vm.deal(direct_vm._contract_address, 500)
    direct_vm.sender = direct_alice
    direct_vm.value = 500
    contract.deposit()
    direct_vm.value = 0

    now = int(time.time())
    evidence_hash = hashlib.sha256("Receipt for team dinner.".encode('utf-8')).hexdigest()
    pid = contract.propose(bob_hex, 100, "Dinner", "https://raw.githubusercontent.com/evidence", evidence_hash, now+1000, now+2000)
    _setup_mocks(direct_vm, True)
    contract.screen_proposal(pid)
    direct_vm.sender = direct_alice
    contract.vote(pid, True)
    direct_vm.sender = direct_bob
    contract.vote(pid, True)

    assert contract.reserved_funds == 100
    contract.finalize(pid)

    # Approved state: liability must be active and funds reserved
    prop = contract.get_proposal(pid)
    assert prop["state"] == STATE_APPROVED
    assert prop["payout_state"] == PAYOUT_APPROVED
    assert contract.reserved_funds == 100
    payout_info = contract.get_payout(pid)
    assert payout_info["payout_state"] == PAYOUT_APPROVED
    assert payout_info["is_liability"] is True
    assert payout_info["recipient"] == bob_hex
    assert payout_info["amount"] == 100


def test_payout_pending_delivery(direct_vm, direct_deploy, direct_alice, direct_bob):
    alice_hex = _addr_hex(direct_alice)
    bob_hex = _addr_hex(direct_bob)
    sunset = int(time.time()) + 100000
    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "Dinners.", f"{alice_hex},{bob_hex}", 1, 1, sunset)

    direct_vm.deal(direct_alice, 500)
    direct_vm.deal(direct_vm._contract_address, 500)
    direct_vm.sender = direct_alice
    direct_vm.value = 500
    contract.deposit()
    direct_vm.value = 0

    now = int(time.time())
    evidence_hash = hashlib.sha256("Receipt for team dinner.".encode('utf-8')).hexdigest()
    pid = contract.propose(bob_hex, 100, "Dinner", "https://raw.githubusercontent.com/evidence", evidence_hash, now+1000, now+2000)
    _setup_mocks(direct_vm, True)
    contract.screen_proposal(pid)
    direct_vm.sender = direct_alice
    contract.vote(pid, True)
    direct_vm.sender = direct_bob
    contract.vote(pid, True)
    contract.finalize(pid)

    # Claim moves to PAYOUT_PENDING, transfer emitted, reserved_funds protected
    contract.claim_payout(pid)
    prop = contract.get_proposal(pid)
    assert prop["state"] == STATE_APPROVED
    assert prop["payout_state"] == PAYOUT_PENDING
    assert contract.reserved_funds == 100
    payout_info = contract.get_payout(pid)
    assert payout_info["payout_state"] == PAYOUT_PENDING
    assert payout_info["is_liability"] is True


def test_payout_duplicate_attempts_revert(direct_vm, direct_deploy, direct_alice, direct_bob):
    alice_hex = _addr_hex(direct_alice)
    bob_hex = _addr_hex(direct_bob)
    sunset = int(time.time()) + 100000
    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "Dinners.", f"{alice_hex},{bob_hex}", 1, 1, sunset)

    direct_vm.deal(direct_alice, 500)
    direct_vm.deal(direct_vm._contract_address, 500)
    direct_vm.sender = direct_alice
    direct_vm.value = 500
    contract.deposit()
    direct_vm.value = 0

    now = int(time.time())
    evidence_hash = hashlib.sha256("Receipt for team dinner.".encode('utf-8')).hexdigest()
    pid = contract.propose(bob_hex, 100, "Dinner", "https://raw.githubusercontent.com/evidence", evidence_hash, now+1000, now+2000)
    _setup_mocks(direct_vm, True)
    contract.screen_proposal(pid)
    direct_vm.sender = direct_alice
    contract.vote(pid, True)
    direct_vm.sender = direct_bob
    contract.vote(pid, True)
    contract.finalize(pid)

    # Finalize cannot be called again
    with direct_vm.expect_revert("Proposal already approved"):
        contract.finalize(pid)

    # First claim succeeds
    contract.claim_payout(pid)

    # Repeated claim while pending reverts
    with direct_vm.expect_revert("Payout transfer already pending"):
        contract.claim_payout(pid)

    # Retry while pending reverts
    with direct_vm.expect_revert("Payout transfer already pending"):
        contract.retry_payout(pid)

    # Confirm delivery
    contract.confirm_delivery(pid)

    # Cannot claim or retry after delivery
    with direct_vm.expect_revert("Proposal is not approved"):
        contract.claim_payout(pid)


def test_payout_failed_delivery_recovery_and_retry(direct_vm, direct_deploy, direct_alice, direct_bob):
    alice_hex = _addr_hex(direct_alice)
    bob_hex = _addr_hex(direct_bob)
    sunset = int(time.time()) + 100000
    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "Dinners.", f"{alice_hex},{bob_hex}", 1, 1, sunset)

    direct_vm.deal(direct_alice, 500)
    direct_vm.deal(direct_vm._contract_address, 500)
    direct_vm.sender = direct_alice
    direct_vm.value = 500
    contract.deposit()
    direct_vm.value = 0

    now = int(time.time())
    evidence_hash = hashlib.sha256("Receipt for team dinner.".encode('utf-8')).hexdigest()
    pid = contract.propose(bob_hex, 100, "Dinner", "https://raw.githubusercontent.com/evidence", evidence_hash, now+1000, now+2000)
    _setup_mocks(direct_vm, True)
    contract.screen_proposal(pid)
    direct_vm.sender = direct_alice
    contract.vote(pid, True)
    direct_vm.sender = direct_bob
    contract.vote(pid, True)
    contract.finalize(pid)

    # Claim payout puts in pending
    contract.claim_payout(pid)
    assert contract.get_payout(pid)["payout_state"] == PAYOUT_PENDING

    # Report delivery failure
    contract.report_failed_delivery(pid)
    prop = contract.get_proposal(pid)
    assert prop["state"] == STATE_APPROVED
    assert prop["payout_state"] == PAYOUT_FAILED
    assert contract.reserved_funds == 100  # Liability protected!
    assert contract.get_payout(pid)["is_liability"] is True

    # Retry payout puts it back to pending
    contract.retry_payout(pid)
    assert contract.get_payout(pid)["payout_state"] == PAYOUT_PENDING
    assert contract.reserved_funds == 100

    # Finally delivery succeeds and confirms
    contract.confirm_delivery(pid)
    assert contract.get_proposal(pid)["state"] == STATE_FINALIZED
    assert contract.get_payout(pid)["payout_state"] == PAYOUT_DELIVERED
    assert contract.reserved_funds == 0


def test_payout_sponsor_withdrawal_protection_against_liabilities(direct_vm, direct_deploy, direct_alice, direct_bob):
    alice_hex = _addr_hex(direct_alice)
    bob_hex = _addr_hex(direct_bob)
    now = int(time.time())
    sunset = now + 1000
    contract = direct_deploy("contracts/charter_gate.py", alice_hex, "Dinners.", f"{alice_hex},{bob_hex}", 1, 1, sunset)

    direct_vm.deal(direct_alice, 500)
    direct_vm.deal(direct_vm._contract_address, 500)
    direct_vm.sender = direct_alice
    direct_vm.value = 500
    contract.deposit()
    direct_vm.value = 0

    evidence_hash = hashlib.sha256("Receipt for team dinner.".encode('utf-8')).hexdigest()
    pid = contract.propose(bob_hex, 400, "Dinner", "https://raw.githubusercontent.com/evidence", evidence_hash, now+200, now+400)
    _setup_mocks(direct_vm, True)
    contract.screen_proposal(pid)
    direct_vm.sender = direct_alice
    contract.vote(pid, True)
    direct_vm.sender = direct_bob
    contract.vote(pid, True)
    contract.finalize(pid)

    # Warp past sunset
    from datetime import datetime, timezone
    new_time = datetime.fromtimestamp(now + 2000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
    direct_vm.warp(new_time)
    import genlayer
    genlayer.message.datetime = new_time

    # Treasury balance: 500, Reserved: 400 (liability for approved payout)
    # Sponsor attempts to withdraw 200 (which would infringe on the 400 liability) -> must revert!
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Insufficient balance (accounting for reserved funds)"):
        contract.withdraw_treasury(200)

    # Sponsor attempts to withdraw 101 (surplus is only 100) -> must revert!
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("Insufficient balance (accounting for reserved funds)"):
        contract.withdraw_treasury(101)

    # Sponsor CAN withdraw unreserved surplus (100)
    contract.withdraw_treasury(100)

    # After surplus is withdrawn, contract balance matches reserved liability (400)
    direct_vm.deal(direct_vm._contract_address, 400)
    with direct_vm.expect_revert("Insufficient balance (accounting for reserved funds)"):
        contract.withdraw_treasury(1)


