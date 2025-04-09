import datetime as dt
from typing import Literal

import numpy as np
import numpy.typing as npt
import polars as pl
from pydantic import validate_call

from .enums import AssetClass, Index, StrikeSpread
from .fetch import fetch_option_data, fetch_spot_data


async def find_atm(
    index: Index,
    date: dt.date,
    time: dt.time,
    based_on: Literal["o", "h", "l", "c"] = "c",
    strike_spread: StrikeSpread = StrikeSpread.BNF,
) -> int:
    data = await fetch_spot_data(
        instrument=index,  # type:ignore[arg-type]
        start_date=date,
        end_date=date,
        start_time=time,
        end_time=time,
    )

    if isinstance(data, str):
        raise ValueError(f"Expected dataframe. Something went wrong: {data}")

    value = data[based_on][0]
    if (value % strike_spread) >= int(strike_spread / 2):
        return int(value - (value % strike_spread) + strike_spread)
    return int(value - (value % strike_spread))


async def calc_strike_either_side(
    strike: int, strike_spread: int, to_generate: int = 10
) -> npt.NDArray[np.int64]:
    return np.arange(
        strike - (to_generate * strike_spread),
        strike + (to_generate * strike_spread) + 1,
        strike_spread,
        dtype=int,
    )


@validate_call(config=dict(arbitrary_types_allowed=True))
async def option_tool(
    index: Index,
    expiry: dt.date,
    asset_class: AssetClass,
    start_date: dt.date,
    end_date: dt.date,
    start_time: dt.time = dt.time(9, 15),
    end_time: dt.time = dt.time(15, 30),
    strike: int | None = None,
    atm_date: dt.date | None = None,
    atm_time: dt.time | None = None,
    premium: float | None = None,
    range_lookup_num: int = 10,
    spread: str = "+0",
) -> pl.DataFrame:
    if strike:
        data = await fetch_option_data(
            index=index,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            expiry=expiry,
            strike=strike,
            asset_class=asset_class,
        )

        if isinstance(data, str):
            raise ValueError(f"Expected dataframe. Something went wrong: {data}")
    elif premium:
        # Find ATM
        atm = await find_atm(
            index=index,
            date=atm_date if atm_date else start_date,
            time=atm_time if atm_time else start_time,
            based_on="c",
            strike_spread=StrikeSpread[index.name],
        )

        range_lookup = await calc_strike_either_side(
            strike=atm,
            strike_spread=StrikeSpread[index.name],
            to_generate=range_lookup_num,
        )

        multi_strike_data_ls = [
            {
                "strike": strike_l,
                "price": (
                    await fetch_option_data(
                        index=index,
                        start_date=atm_date if atm_date else start_date,
                        end_date=atm_date if atm_date else start_date,
                        start_time=atm_time if atm_time else start_time,
                        end_time=atm_time if atm_time else start_time,
                        expiry=expiry,
                        strike=strike_l,
                        asset_class=asset_class,
                    )
                ),
            }
            for strike_l in range_lookup
        ]

        multi_strike_data_ls = [
            d for d in multi_strike_data_ls if not isinstance(d.get("price"), str)
        ]

        multi_strike_data_ls = [
            {
                "strike": d.get("strike"),
                "price": d.get("price")["c"][0],  # type:ignore[index]
            }
            for d in multi_strike_data_ls
        ]

        multi_strike_data = pl.from_dicts(multi_strike_data_ls)

        nearest_strike = multi_strike_data.with_columns(
            diff=pl.col("price") - premium
        ).sort("diff", descending=False)["strike"][0]

        data = await fetch_option_data(
            index=index,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            expiry=expiry,
            strike=nearest_strike,
            asset_class=asset_class,
        )

    else:
        # Find ATM
        atm = await find_atm(
            index=index,
            date=atm_date if atm_date else start_date,
            time=atm_time if atm_time else start_time,
            based_on="c",
            strike_spread=StrikeSpread[index.name],
        )

        new_strike: int | None = None

        if spread:
            if spread[0] not in ["+", "-"]:
                raise ValueError("Spread must start with either + or -")

            try:
                spread_int = int(spread[1:])
            except ValueError:
                raise TypeError("Spread must contain an integer/number after + or -")

            if spread_int % StrikeSpread[index.name] != 0:
                raise ValueError(
                    f"Spread must be a multiple of {StrikeSpread[index.name]} for {index.name}"
                )

            if spread[0] == "+":
                new_strike = atm + spread_int
            else:
                new_strike = atm - spread_int

        data = await fetch_option_data(
            index=index,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            expiry=expiry,
            strike=new_strike if new_strike else atm,
            asset_class=asset_class,
        )

    if isinstance(data, str):
        raise ValueError(f"Expected dataframe. Something went wrong: {data}")

    data_filtered: pl.DataFrame = pl.concat(
        [
            data.filter(
                pl.col("datetime") == dt.datetime.combine(start_date, start_time)
            ).with_columns(candle=pl.lit("entry_candle")),
            data.filter(pl.col("h") == pl.col("h").max()).with_columns(
                candle=pl.lit("max_value_candle")
            ),
            data.filter(pl.col("l") == pl.col("l").min()).with_columns(
                candle=pl.lit("min_value_candle")
            ),
            data[-1].with_columns(candle=pl.lit("exit_price_candle")),
        ]
    )

    return data_filtered
