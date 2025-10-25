import json
import solcx as solc_x
from web3 import Web3

# --- Configuration ---
GANACHE_URL = "http://127.0.0.1:7545"
CONTRACT_FILE = "AuditTrail.sol"
CONTRACT_NAME = "AuditTrail"
SOLC_VERSION = "0.8.19"
# --- End Configuration ---

print(f"Installing and setting up solc version {SOLC_VERSION}...")
solc_x.install_solc(SOLC_VERSION)
solc_x.set_solc_version(SOLC_VERSION)
print("Compiler is ready.")

# 1. Read the Solidity file
with open(CONTRACT_FILE, 'r') as f:
    contract_source_code = f.read()

# 2. Compile the contract
print(f"Compiling {CONTRACT_FILE}...")
compiled_sol = solc_x.compile_source(
    contract_source_code,
    output_values=['abi', 'bin']
)

# Get the bytecode (bin) and ABI
contract_id, contract_interface = compiled_sol.popitem()
bytecode = contract_interface['bin']
abi = contract_interface['abi']

print("Contract compiled successfully.")

# 3. Connect to Ganache
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))
if not web3.is_connected():
    raise ConnectionError("Failed to connect to Ganache. Is it running?")

# Use the first account from Ganache as the deployer
web3.eth.default_account = web3.eth.accounts[0]
print(f"Connected to Ganache. Using account: {web3.eth.default_account}")

# 4. Deploy the contract
Contract = web3.eth.contract(abi=abi, bytecode=bytecode)

print("Deploying contract...")
tx_hash = Contract.constructor().transact()

print("Waiting for transaction to be mined...")
tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

contract_address = tx_receipt.contractAddress

print("\n" + "="*50)
print("✅ CONTRACT DEPLOYED SUCCESSFULLY! ✅")
print(f"Contract Address: {contract_address}")
print("\n" + "="*50)
print("Paste this address into your 'app.py':")
print(f'contract_address = "{contract_address}"')
print("\n" + "="*50)
print("Paste this ABI into your 'app.py':")
print(f"contract_abi = '''{json.dumps(abi)}'''")
print("="*50)