from eth_utils import event_abi_to_log_topic


UINT256_MAX = (1 << 256) - 1


USER_OPERATION_EVENT_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "bytes32", "name": "userOpHash", "type": "bytes32"},
        {"indexed": True, "internalType": "address", "name": "sender", "type": "address"},
        {"indexed": True, "internalType": "address", "name": "paymaster", "type": "address"},
        {"indexed": False, "internalType": "uint256", "name": "nonce", "type": "uint256"},
        {"indexed": False, "internalType": "bool", "name": "success", "type": "bool"},
        {"indexed": False, "internalType": "uint256", "name": "actualGasCost", "type": "uint256"},
        {"indexed": False, "internalType": "uint256", "name": "actualGasUsed", "type": "uint256"}
    ],
    "name": "UserOperationEvent",
    "type": "event"
}


ERC20_APPROVAL_EVENT_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "address", "name": "owner", "type": "address"},
        {"indexed": True, "internalType": "address", "name": "spender", "type": "address"},
        {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"}
    ],
    "name": "Approval",
    "type": "event"
}

ERC20_TRANSFER_EVENT_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "address", "name": "from", "type": "address"},
        {"indexed": True, "internalType": "address", "name": "to", "type": "address"},
        {"indexed": False, "internalType": "uint256", "name": "value", "type": "uint256"}
    ],
    "name": "Transfer",
    "type": "event"
}

UPGRADED_EVENT_ABI = {
    "anonymous": False,
    "inputs": [
        {"indexed": True, "internalType": "address", "name": "implementation", "type": "address"}
    ],
    "name": "Upgraded",
    "type": "event"
}


TOPIC_USER_OPERATION_EVENT = "0x" + event_abi_to_log_topic(USER_OPERATION_EVENT_ABI).hex()
TOPIC_ERC20_APPROVAL = "0x" + event_abi_to_log_topic(ERC20_APPROVAL_EVENT_ABI).hex()
TOPIC_ERC20_TRANSFER = "0x" + event_abi_to_log_topic(ERC20_TRANSFER_EVENT_ABI).hex()
TOPIC_UPGRADED = "0x" + event_abi_to_log_topic(UPGRADED_EVENT_ABI).hex()
