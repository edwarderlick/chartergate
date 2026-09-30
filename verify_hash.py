import requests, json, base64, hashlib

with open('deploy/receipt.json') as f:
    receipt = json.load(f)
address = receipt['contract_address']
deploy_tx = receipt['deploy_tx']

payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'gen_getContractCode', 'params': [address]}
resp = requests.post('https://studio-dev.genlayer.com/api', json=payload).json()
code_b64 = resp['result']
remote_source = base64.b64decode(code_b64)
remote_hash = hashlib.sha256(remote_source).hexdigest()

with open('contracts/charter_gate.py', 'rb') as f:
    local_source = f.read()
local_hash = hashlib.sha256(local_source).hexdigest()

res = 'MATCH' if remote_hash == local_hash else 'MISMATCH'
out = f"""Address: {address}
Deploy TX: {deploy_tx}
Remote Hash: {remote_hash}
Local Hash:  {local_hash}
Result: {res}
"""
with open('deployment_verification.txt', 'w') as f:
    f.write(out)
print(out)
