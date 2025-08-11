// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract WeightsetRegistry {
    address public owner;

    modifier onlyOwner() {
        require(msg.sender == owner, "Not the owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }
    // Store tuple keccak hash for on-chain validation (not JSON sha256)
    event Published(uint256 indexed epoch, bytes32 indexed tupleHash, string cid, string signer, address indexed publisher);

    struct Entry {
        uint256 epoch;
        bytes32 tupleHash;
        string cid;
        string signer;
        address publisher;
        uint256 blockNumber;
        uint256 timestamp;
    }

    mapping(uint256 => Entry) public byEpoch;

    function setOwner(address newOwner) external onlyOwner {
        owner = newOwner;
    }

    function publish(uint256 epoch, bytes32 tupleHash, string calldata cid, string calldata signer) external onlyOwner returns (bool) {
        require(epoch > 0, "bad_epoch");
        require(byEpoch[epoch].epoch == 0, "already_published");
        byEpoch[epoch] = Entry({
            epoch: epoch,
            tupleHash: tupleHash,
            cid: cid,
            signer: signer,
            publisher: msg.sender,
            blockNumber: block.number,
            timestamp: block.timestamp
        });
        emit Published(epoch, tupleHash, cid, signer, msg.sender);
        return true;
    }
}


