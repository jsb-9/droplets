import asyncio
import datetime as dt
from typing import Any, Literal

import motor.motor_asyncio as motor
import polars as pl

from core import settings
# from ..core import settings

from .enums import AssetClass, Index

client = motor.AsyncIOMotorClient('mongodb://localhost', 27017)

db = client["historical_api"]
spot_collection = db["spot"]
options_collection = db["options"]


async def _fetch_batch(
    index: Index,
    start_date: dt.date,
    end_date: dt.date,
    start_time: dt.time = dt.time(9, 15),
    end_time: dt.time = dt.time(15, 30),
    expiry: dt.date | None = None,
    strike: int | None = None,
    asset_class: AssetClass | None = None,
) -> list[Any] | None:
    if (end_date - start_date).days > 7:
        raise ValueError("Time period must not exceed 7 days.")

    if expiry or strike or asset_class:
        if not (expiry and strike and asset_class):
            raise ValueError(
                "To fetch options data all three: expiry, strike and asset class are required."
            )

    documents = []

    if asset_class and expiry:
        async for document in options_collection.find(
            {
                "index": index,
                "datetime": {
                    "$gte": dt.datetime.combine(start_date, start_time),
                    "$lte": dt.datetime.combine(end_date, end_time),
                },
                "expiry": dt.datetime.combine(expiry, dt.time(0, 0)),
                "strike": strike,
                "asset_class": asset_class,
            }
        ):
            documents.append(document)
    else:
        async for document in spot_collection.find(
            {
                "instrument": index,
                "datetime": {
                    "$gte": dt.datetime.combine(start_date, start_time),
                    "$lte": dt.datetime.combine(end_date, end_time),
                },
            }
        ):
            documents.append(document)

    if documents:
        return documents

    return None


async def fetch_data(
    index: Index,
    start_date: dt.date,
    end_date: dt.date,
    start_time: dt.time = dt.time(9, 15),
    end_time: dt.time = dt.time(15, 30),
    expiry: dt.date | None = None,
    strike: int | None = None,
    asset_class: AssetClass | None = None,
    ffill: bool = False,
) -> pl.DataFrame | None:
    # all_documents = []
    batches = []
    batch_start_date = start_date
    while batch_start_date <= end_date:
        batch_end_date = min(batch_start_date + dt.timedelta(days=7), end_date)

        if batch_start_date == batch_end_date:
            batches.append((batch_start_date, batch_end_date))
        else:
            batches.append((batch_start_date, batch_end_date))

        batch_start_date = batch_end_date + dt.timedelta(days=1)

    results = await asyncio.gather(
        *(
            _fetch_batch(
                index=index,
                start_date=batch_start,
                end_date=batch_end,
                start_time=start_time,
                end_time=end_time,
                expiry=expiry,
                strike=strike,
                asset_class=asset_class,
            )
            for batch_start, batch_end in batches
        )
    )

    if results:
        all_documents = [doc for batch in results if batch for doc in batch if doc]
    else:
        return None

    if all_documents:
        data = (
            pl.DataFrame(all_documents)
            .drop(columns="_id")
            .sort(by="datetime")
            .with_columns(datetime=pl.col("datetime").dt.truncate(every="1m"))
        )

        if ffill:
            data = (
                data.with_columns(pl.col("datetime").dt.date().alias("_date"))
                .group_by("_date")
                .map_groups(
                    lambda day: pl.DataFrame()
                    .with_columns(
                        pl.date_range(
                            dt.datetime.combine(
                                day[0]["datetime"][0].date(), dt.time(9, 15)
                            ),
                            dt.datetime.combine(
                                day[0]["datetime"][0].date(), dt.time(15, 29)
                            ),
                            dt.timedelta(minutes=1),
                        ).alias("datetime")
                    )
                    .join(other=day, on="datetime", how="left")
                    .drop("_date")
                    .with_columns(
                        pl.col("o").forward_fill(),
                        pl.col("h").forward_fill(),
                        pl.col("l").forward_fill(),
                        pl.col("c").forward_fill(),
                        pl.col("v").forward_fill(),
                        pl.col("oi").forward_fill(),
                        pl.col("index").forward_fill(),
                        pl.col("expiry").forward_fill(),
                        pl.col("strike").forward_fill(),
                        pl.col("asset_class").forward_fill(),
                    )
                )
            )
        return data
    return None


async def fetch_spot_data(
    instrument: str,
    exchange: str,
    tf: Literal["1m", "1d"],
    start_date: dt.date,
    end_date: dt.date,
    start_time: dt.time = dt.time(9, 15),
    end_time: dt.time = dt.time(15, 30),
) -> pl.DataFrame | None:
    documents = []

    async for document in spot_collection.find(
        {
            "instrument": instrument,
            "exchange": exchange,
            "tf": tf,
            "datetime": {
                "$gte": dt.datetime.combine(start_date, start_time),
                "$lte": dt.datetime.combine(end_date, end_time),
            },
        }
    ):
        documents.append(document)

    if documents:
        if tf == "1m":
            return (
                pl.DataFrame(documents)
                .drop(columns="_id")
                .sort(by="datetime")
                .with_columns(datetime=pl.col("datetime").dt.truncate(every="1m"))
            )
        else:
            return (
                pl.DataFrame(documents)
                .drop(columns="_id")
                .sort(by="datetime")
                .with_columns(
                    datetime=pl.col("datetime").dt.truncate(every="1d").cast(pl.Date)
                )
            )

    return None
