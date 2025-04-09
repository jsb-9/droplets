from enum import IntEnum, StrEnum

class Index(StrEnum):
    BNF = "bnf"
    NIFTY = "nifty"
    FINNIFTY = "finnifty"
    MIDCP = "midcpnifty"
    

class Spot(StrEnum):
    BNF = "bnf"
    NIFTY = "nifty"
    FINNIFTY = "finnifty"
    VIX = "vix"
    MIDCP = "midcpnifty"


class AssetClass(StrEnum):
    CALL = "C"
    PUT = "P"


class StrikeSpread(IntEnum):
    BNF = 100
    NIFTY = 50
    FINNIFTY = 50
    MIDCP = 25
