import json
from pathlib import Path
from gltest import get_contract_factory
from gltest.assertions import tx_execution_failed
from eth_utils import to_checksum_address
import os
import time
from eth_account import Account
from dotenv import load_dotenv

from gltest_cli.config.user import load_user_config
from gltest_cli.config.general import get_general_config

RECEIPT_FILE = Path(__file__).parent.parent / "deploy" / "receipt.json"

def deploy():
    general_config = get_general_config()
    user_config = load_user_config(Path('gltest.config.yaml'))
    general_config.user_config = user_config
    
    load_dotenv()
    key = os.environ.get("PRIVATE_KEY")
    if not key:
        raise ValueError("PRIVATE_KEY environment variable is not set")
        
    if user_config.networks.get("studio-dev"):
        user_config.networks["studio-dev"].accounts = [key]
        user_config.networks["studio-dev"].from_account = key
        
    account = Account.from_key(key)
    factory = get_contract_factory("CharterGate")

    print(f"[deploy] Operator / deployer: {account.address}")
    print(f"[deploy] Sending deploy tx to Studio-Devnet ...")
    
    alice = to_checksum_address("0xbb4e0fd1ceac9f8db17242cf86decdcdd45fa48a")
    bob = to_checksum_address("0x81b637d8fcd2c6da6359e6963113a1170de795e4")

    now = int(time.time())
    receipt = factory.deploy_contract_tx(
        args=[
            str(account.address),
            "Only software subscriptions.",
            f"{alice},{bob}",
            2,
            2,
            now + 86400 * 365
        ],
        account=account,
        fees={
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
        },
        fee_value=500000000000010352,
    )

    if tx_execution_failed(receipt):
        payload = (receipt.get("consensus_data") or {}).get("leader_receipt") or receipt
        raise RuntimeError(f"[deploy] Deploy tx failed:\n{json.dumps(payload, indent=2, default=str)}")

    contract_address = receipt["data"]["contract_address"]
    tx_hash = receipt["hash"]
    print(f"[deploy] Deploy tx:       {tx_hash}")
    print(f"[deploy] Contract address: {contract_address}")
    print(f"[deploy] Status: ACCEPTED")
    
    time.sleep(15)

    RECEIPT_FILE.parent.mkdir(parents=True, exist_ok=True)
    output = {
        "contract_address": contract_address,
        "deploy_tx": tx_hash,
        "operator": str(account.address),
        "network": "studio_devnet",
        "chain_id": 61997,
        "explorer": f"https://explorer-studio-dev.genlayer.com/address/{contract_address}?chain=studio-devnet"
    }
    RECEIPT_FILE.write_text(json.dumps(output, indent=2))
    print(f"[deploy] Receipt saved at {RECEIPT_FILE}")
    print(f"[deploy] Explorer: {output['explorer']}")
    return contract_address, tx_hash

if __name__ == '__main__':
    deploy()
