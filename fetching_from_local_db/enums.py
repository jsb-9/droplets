from enum import IntEnum, StrEnum

class Index(StrEnum):
    BNF = 'bnf'
    NIFTY = 'nifty'
    FINNIFTY = 'finnifty'
    MIDCPNIFTY = 'midcpnifty'
    SENSEX = 'sensex'
    BANKEX = 'bankex'

class AssetClass(StrEnum):
    CALL = 'C'
    PUT = 'P'

class StrikeSpread(IntEnum):
    BNF = 100
    NIFTY = 50
    FINNIFTY = 50
    MIDCPNIFTY = 25
    SENSEX = 100
    BANKEX = 100