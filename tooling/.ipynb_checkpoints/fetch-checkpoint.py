import datetime as dt

import httpx
import polars as pl
from pydantic import validate_call

from .enums import AssetClass, Index, Spot
from .globals import API_URL


@validate_call(config=dict(arbitrary_types_allowed=True))
async def fetch_option_data(
    index: Index,
    expiry: dt.date,
    strike: int,
    asset_class: AssetClass,
    start_date: dt.date,
    end_date: dt.date,
    start_time: dt.time = dt.time(9, 15),
    end_time: dt.time = dt.time(15, 30),
) -> str | pl.DataFrame:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            API_URL + "/options/get",
            params={
                "index": index,
                "expiry": expiry,  # type:ignore[dict-item]
                "strike": strike,
                "asset_class": asset_class,
                "start_date": dt.datetime.combine(
                    date=start_date, time=start_time
                ),  # type:ignore[dict-item]
                "end_date": dt.datetime.combine(
                    date=end_date, time=end_time
                ),  # type:ignore[dict-item]
            },
        )

    if resp.status_code != 200:
        msg: str = resp.json()["msg"]["error"]
        return msg

    if resp.status_code == 200:
        data = resp.json()["data"]

        return pl.DataFrame(data).with_columns(
            pl.col("datetime").str.strptime(pl.Datetime, format="%Y-%m-%dT%H:%M:%S"),
            pl.col("expiry")
            .str.strptime(pl.Datetime, format="%Y-%m-%dT%H:%M:%S")
            .dt.date(),
        )

    raise Exception(f"Something went wrong: {resp.json()}")


@validate_call(config=dict(arbitrary_types_allowed=True))
async def fetch_spot_data(
    instrument: Spot,
    start_date: dt.date,
    end_date: dt.date,
    start_time: dt.time = dt.time(9, 15),
    end_time: dt.time = dt.time(15, 30),
) -> str | pl.DataFrame:
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            f"{API_URL}/spot/get/{instrument}",
            params={
                "start_date": dt.datetime.combine(
                    date=start_date, time=start_time
                ),  # type:ignore[dict-item]
                "end_date": dt.datetime.combine(
                    date=end_date, time=end_time
                ),  # type:ignore[dict-item]
            },
        )

    if resp.status_code != 200:
        msg: str = resp.json()["msg"]["error"]
        return msg

    if resp.status_code == 200:
        data = resp.json()["data"]

        return pl.DataFrame(data).with_columns(
            pl.col("datetime").str.strptime(pl.Datetime, format="%Y-%m-%dT%H:%M:%S"),
        )

    raise Exception(f"Something went wrong: {resp.json()}")
