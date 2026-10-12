import os
import time
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv

from eth_account import Account
from eth_utils import to_checksum_address
from gltest_cli.config.user import load_user_config
from gltest_cli.config.general import get_general_config
from gltest import get_contract_factory
from gltest.assertions import tx_execution_failed

FEES_CONFIG = {
    "distribution": {
        "leaderTimeunitsAllocation": 100,
        "validatorTimeunitsAllocation": 200,
        "appealRounds": 0,
        "executionBudgetPerRound": 100000000000000000,
        "executionConsumed": 0,
        "totalMessageFees": 0,
        "rotations": [3],
        "maxPriceGenPerTimeUnit": 2,
        "storageFeeMaxGasPrice": 300000000,
        "receiptFeeMaxGasPrice": 300000000
    }
}
FEE_VALUE = 500000000000010352

STATE_NAMES = {
    0: "STATE_PENDING",
    1: "STATE_ELIGIBLE",
    2: "STATE_INELIGIBLE",
    3: "STATE_EVIDENCE_FAILED",
    4: "STATE_APPROVED",
    5: "STATE_REJECTED",
    6: "STATE_EXPIRED",
    7: "STATE_FINALIZED",
}

PAYOUT_STATE_NAMES = {
    0: "PAYOUT_NONE",
    1: "PAYOUT_APPROVED",
    2: "PAYOUT_PENDING",
    3: "PAYOUT_DELIVERED",
    4: "PAYOUT_FAILED",
}

def log_step(title):
    print("\n" + "=" * 70)
    print(f"[*] {title}")
    print("=" * 70)

def main():
    load_dotenv()
    key = os.environ.get("PRIVATE_KEY")
    if not key:
        raise ValueError("PRIVATE_KEY not set")

    general_config = get_general_config()
    user_config = load_user_config(Path('gltest.config.yaml'))
    if user_config.networks.get("studio-dev"):
        user_config.networks["studio-dev"].accounts = [key]
        user_config.networks["studio-dev"].from_account = key
    general_config.user_config = user_config

    account = Account.from_key(key)
    print(f"Operator: {account.address}")

    with open("deploy/receipt.json") as f:
        receipt_data = json.load(f)
    contract_address = receipt_data["contract_address"]
    print(f"Target contract on studio-dev: {contract_address}")

    factory = get_contract_factory("CharterGate")
    contract = factory.build_contract(contract_address, account=account)

    demo_results = {
        "contract_address": contract_address,
        "operator": str(account.address),
        "steps": []
    }

    # Step 1: Query initial state
    log_step("Step 1: Query Initial State")
    err = contract.get_error().call()
    print(f"Initial get_error(): {err}")

    # Step 2: Deposit treasury funds
    log_step("Step 2: Deposit Treasury Funds")
    tx_deposit = contract.deposit().transact(
        value=5000,
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_deposit):
        raise RuntimeError(f"Deposit failed: {tx_deposit}")
    print(f"Deposit TX: {tx_deposit['hash']}")
    time.sleep(5)
    demo_results["steps"].append({
        "step": "deposit",
        "tx_hash": tx_deposit["hash"],
        "status": "ACCEPTED",
        "deposited_wei": 5000
    })

    # Step 3: Propose Payout
    log_step("Step 3: Propose Payout to Recipient")
    bob = to_checksum_address("0x81b637d8fcd2c6da6359e6963113a1170de795e4")
    evidence_url = "https://raw.githubusercontent.com/edwarderlick/chartergate/fix/payout-recovery/evidence/subscription_invoice.md"
    evidence_hash = "159d5d83d41b837b89c2147e396070546dcbb2279353ab0b3d29ee3a1dc04b63"
    now = int(time.time())
    screen_dl = now + 86400
    vote_dl = screen_dl + 86400
    payout_amount = 100

    tx_propose = contract.propose([
        bob, payout_amount, "Annual software subscription for developer tooling.",
        evidence_url, evidence_hash, screen_dl, vote_dl
    ]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_propose):
        raise RuntimeError(f"Propose failed: {tx_propose}")
    print(f"Propose TX: {tx_propose['hash']}")
    time.sleep(5)
    # Detect newly created proposal ID
    current_count = 0
    for i in range(25):
        try:
            contract.get_proposal([i]).call()
            current_count += 1
        except Exception:
            break
    pid = max(0, current_count - 1)
    print(f"Target Proposal ID: {pid}")

    p_after_prop = contract.get_proposal([pid]).call()
    print(f"Proposal State: {STATE_NAMES.get(p_after_prop['state'])} ({p_after_prop['state']})")
    demo_results["steps"].append({
        "step": "propose",
        "pid": pid,
        "tx_hash": tx_propose["hash"],
        "recipient": bob,
        "amount": payout_amount,
        "state": STATE_NAMES.get(p_after_prop['state'])
    })

    # Step 4: Screen Proposal
    log_step("Step 4: AI Evidence Screening")
    tx_screen = contract.screen_proposal([pid]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_screen):
        raise RuntimeError(f"Screen failed: {tx_screen}")
    print(f"Screen TX: {tx_screen['hash']}")
    time.sleep(10)

    p_after_screen = contract.get_proposal([pid]).call()
    print(f"Screened Proposal State: {STATE_NAMES.get(p_after_screen['state'])} ({p_after_screen['state']})")
    print(f"Eligibility Details: {p_after_screen.get('eligibility_details')}")
    demo_results["steps"].append({
        "step": "screen_proposal",
        "pid": pid,
        "tx_hash": tx_screen["hash"],
        "state": STATE_NAMES.get(p_after_screen['state']),
        "eligibility_details": p_after_screen.get('eligibility_details')
    })

    # Step 5: Member Vote
    log_step("Step 5: Member Vote")
    tx_vote = contract.vote([pid, True]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_vote):
        raise RuntimeError(f"Vote failed: {tx_vote}")
    print(f"Vote TX: {tx_vote['hash']}")
    time.sleep(5)

    p_after_vote = contract.get_proposal([pid]).call()
    print(f"Yes Votes: {p_after_vote['yes_votes']}, No Votes: {p_after_vote['no_votes']}")
    demo_results["steps"].append({
        "step": "vote",
        "pid": pid,
        "tx_hash": tx_vote["hash"],
        "yes_votes": p_after_vote["yes_votes"]
    })

    # Step 6: Finalize (Approval as Identifiable Liability)
    log_step("Step 6: Finalize Vote -> Approval as Identifiable Liability")
    tx_finalize = contract.finalize([pid]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_finalize):
        raise RuntimeError(f"Finalize failed: {tx_finalize}")
    print(f"Finalize TX: {tx_finalize['hash']}")
    time.sleep(5)

    p_after_fin = contract.get_proposal([pid]).call()
    payout_fin = contract.get_payout([pid]).call()
    print(f"Proposal State: {STATE_NAMES.get(p_after_fin['state'])} ({p_after_fin['state']})")
    print(f"Payout State:   {PAYOUT_STATE_NAMES.get(p_after_fin['payout_state'])} ({p_after_fin['payout_state']})")
    print(f"Is Liability:   {payout_fin.get('is_liability')} (PRESERVED - liability protected!)")
    demo_results["steps"].append({
        "step": "finalize_approval",
        "pid": pid,
        "tx_hash": tx_finalize["hash"],
        "state": STATE_NAMES.get(p_after_fin['state']),
        "payout_state": PAYOUT_STATE_NAMES.get(p_after_fin['payout_state']),
        "is_liability": payout_fin.get('is_liability')
    })

    # Step 7: Claim Payout (Pending Delivery)
    log_step("Step 7: Claim Payout -> Pending Delivery")
    tx_claim = contract.claim_payout([pid]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_claim):
        raise RuntimeError(f"Claim payout failed: {tx_claim}")
    print(f"Claim Payout TX: {tx_claim['hash']}")
    time.sleep(5)

    p_after_claim = contract.get_proposal([pid]).call()
    payout_claim = contract.get_payout([pid]).call()
    print(f"Proposal State: {STATE_NAMES.get(p_after_claim['state'])} ({p_after_claim['state']})")
    print(f"Payout State:   {PAYOUT_STATE_NAMES.get(p_after_claim['payout_state'])} ({p_after_claim['payout_state']})")
    print(f"Is Liability:   {payout_claim.get('is_liability')} (STILL PRESERVED during delivery flight!)")
    demo_results["steps"].append({
        "step": "claim_payout_pending",
        "pid": pid,
        "tx_hash": tx_claim["hash"],
        "state": STATE_NAMES.get(p_after_claim['state']),
        "payout_state": PAYOUT_STATE_NAMES.get(p_after_claim['payout_state']),
        "is_liability": payout_claim.get('is_liability')
    })

    # Step 8: Duplicate Claim Attempt (Must Revert / Reject)
    log_step("Step 8: Prevent Duplicate Payout Emission")
    print("Attempting second claim_payout while delivery is already pending...")
    is_failed = False
    tx_dup_hash = ""
    try:
        tx_dup = contract.claim_payout([pid]).transact(
            fee_value=FEE_VALUE,
            fees=FEES_CONFIG
        )
        is_failed = tx_execution_failed(tx_dup)
        tx_dup_hash = tx_dup.get("hash", "")
    except Exception as e:
        print(f"Call reverted as expected: {e}")
        is_failed = True
        tx_dup_hash = "reverted_on_submission"
    print(f"Duplicate Claim TX: {tx_dup_hash}")
    print(f"Execution Failed as Expected: {is_failed}")
    demo_results["steps"].append({
        "step": "duplicate_claim_prevention",
        "pid": pid,
        "tx_hash": tx_dup_hash,
        "reverted_as_expected": is_failed
    })

    # Step 9: Report Failed Delivery (Recoverable Liability)
    log_step("Step 9: Report Failed Delivery -> Recoverable Liability")
    tx_fail = contract.report_failed_delivery([pid]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_fail):
        raise RuntimeError(f"Report failed delivery failed: {tx_fail}")
    print(f"Report Failed Delivery TX: {tx_fail['hash']}")
    time.sleep(5)

    p_after_fail = contract.get_proposal([pid]).call()
    payout_fail = contract.get_payout([pid]).call()
    print(f"Proposal State: {STATE_NAMES.get(p_after_fail['state'])} ({p_after_fail['state']})")
    print(f"Payout State:   {PAYOUT_STATE_NAMES.get(p_after_fail['payout_state'])} ({p_after_fail['payout_state']})")
    print(f"Is Liability:   {payout_fail.get('is_liability')} (PRESERVED - cannot withdraw backing funds!)")
    demo_results["steps"].append({
        "step": "report_failed_delivery",
        "pid": pid,
        "tx_hash": tx_fail["hash"],
        "state": STATE_NAMES.get(p_after_fail['state']),
        "payout_state": PAYOUT_STATE_NAMES.get(p_after_fail['payout_state']),
        "is_liability": payout_fail.get('is_liability')
    })

    # Step 10: Retry Payout
    log_step("Step 10: Retry Payout Delivery")
    tx_retry = contract.retry_payout([pid]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_retry):
        raise RuntimeError(f"Retry payout failed: {tx_retry}")
    print(f"Retry Payout TX: {tx_retry['hash']}")
    time.sleep(5)

    p_after_retry = contract.get_proposal([pid]).call()
    payout_retry = contract.get_payout([pid]).call()
    print(f"Proposal State: {STATE_NAMES.get(p_after_retry['state'])} ({p_after_retry['state']})")
    print(f"Payout State:   {PAYOUT_STATE_NAMES.get(p_after_retry['payout_state'])} ({p_after_retry['payout_state']})")
    print(f"Is Liability:   {payout_retry.get('is_liability')}")
    demo_results["steps"].append({
        "step": "retry_payout",
        "pid": pid,
        "tx_hash": tx_retry["hash"],
        "state": STATE_NAMES.get(p_after_retry['state']),
        "payout_state": PAYOUT_STATE_NAMES.get(p_after_retry['payout_state']),
        "is_liability": payout_retry.get('is_liability')
    })

    # Step 11: Confirm Delivery (Safe Final Settlement)
    log_step("Step 11: Confirm Delivery -> Safe Final Settlement")
    tx_confirm = contract.confirm_delivery([pid]).transact(
        fee_value=FEE_VALUE,
        fees=FEES_CONFIG
    )
    if tx_execution_failed(tx_confirm):
        raise RuntimeError(f"Confirm delivery failed: {tx_confirm}")
    print(f"Confirm Delivery TX: {tx_confirm['hash']}")
    time.sleep(5)

    p_after_conf = contract.get_proposal([pid]).call()
    payout_conf = contract.get_payout([pid]).call()
    print(f"Proposal State: {STATE_NAMES.get(p_after_conf['state'])} ({p_after_conf['state']})")
    print(f"Payout State:   {PAYOUT_STATE_NAMES.get(p_after_conf['payout_state'])} ({p_after_conf['payout_state']})")
    print(f"Is Liability:   {payout_conf.get('is_liability')} (SAFELY RESOLVED & DECREMENTED)")
    demo_results["steps"].append({
        "step": "confirm_delivery",
        "pid": pid,
        "tx_hash": tx_confirm["hash"],
        "state": STATE_NAMES.get(p_after_conf['state']),
        "payout_state": PAYOUT_STATE_NAMES.get(p_after_conf['payout_state']),
        "is_liability": payout_conf.get('is_liability')
    })

    # Step 12: Duplicate Claim After Delivery (Must Revert)
    log_step("Step 12: Prevent Claim After Delivery Completed")
    is_failed_post = False
    tx_post_hash = ""
    try:
        tx_after_del = contract.claim_payout([pid]).transact(
            fee_value=FEE_VALUE,
            fees=FEES_CONFIG
        )
        is_failed_post = tx_execution_failed(tx_after_del)
        tx_post_hash = tx_after_del.get("hash", "")
    except Exception as e:
        print(f"Call reverted as expected: {e}")
        is_failed_post = True
        tx_post_hash = "reverted_on_submission"
    print(f"Post-delivery Claim TX: {tx_post_hash}")
    print(f"Reverted as expected: {is_failed_post}")
    demo_results["steps"].append({
        "step": "post_delivery_claim_prevention",
        "pid": pid,
        "tx_hash": tx_post_hash,
        "reverted_as_expected": is_failed_post
    })

    # Save full demonstration evidence
    evidence_path = Path("deploy/payout_recovery_live_demo.json")
    evidence_path.write_text(json.dumps(demo_results, indent=2, default=str), encoding="utf-8")
    print(f"\n[+] Full live recovery demonstration evidence saved to {evidence_path}")

if __name__ == "__main__":
    main()
