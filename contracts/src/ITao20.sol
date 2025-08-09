// SPDX-License-Identifier: MIT
pragma solidity ^0.8.21;

interface ITao20 {
    event Minted(address indexed account, uint256 amountTao20, uint256 navBefore, uint256 navAfter);
    event Redeemed(address indexed account, uint256 amountTao20, uint256 navBefore, uint256 navAfter);

    function mintInKind(uint256[] calldata netuids, uint256[] calldata quantities) external returns (uint256 minted);
    function redeemInKind(uint256 amountTao20) external returns (uint256[] memory netuids, uint256[] memory quantities);
}


