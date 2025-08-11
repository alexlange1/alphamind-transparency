// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

contract TAO20 {
    string public name = "TAO20 Index";
    string public symbol = "TAO20";
    uint8 public immutable decimals = 18;
    uint256 public totalSupply;

    address public minter;

    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event MinterChanged(address indexed newMinter);

    modifier onlyMinter() { require(msg.sender == minter, "not minter"); _; }

    constructor(address _minter) { minter = _minter; emit MinterChanged(_minter); }

    function setMinter(address _minter) external onlyMinter { minter = _minter; emit MinterChanged(_minter); }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 a = allowance[from][msg.sender];
        require(a >= amount, "insufficient allowance");
        unchecked { allowance[from][msg.sender] = a - amount; }
        _transfer(from, to, amount);
        return true;
    }

    function _transfer(address from, address to, uint256 amount) internal {
        require(balanceOf[from] >= amount, "insufficient balance");
        unchecked { balanceOf[from] -= amount; }
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
    }

    function mint(address to, uint256 amount) external onlyMinter {
        require(to != address(0), "mint to zero address");
        totalSupply += amount;
        balanceOf[to] += amount;
        emit Transfer(address(0), to, amount);
    }

    function burn(address from, uint256 amount) external onlyMinter {
        require(balanceOf[from] >= amount, "insufficient");
        unchecked { balanceOf[from] -= amount; }
        totalSupply -= amount;
        emit Transfer(from, address(0), amount);
    }
}


