"""
In-memory Data Store for Elexon BMRS Wind Data.
Loads Parquet (or JSON fallback) into pandas DataFrames at application startup.
"""

import os
import logging
from typing import Optional
import pandas as pd

logger = logging.getLogger("fastapi_datastore")

class DataStore:
    def __init__(self):
        self.fuelhh_df: Optional[pd.DataFrame] = None
        self.windfor_df: Optional[pd.DataFrame] = None
        self.is_loaded: bool = False
        self.fuelhh_count: int = 0
        self.windfor_count: int = 0
        self.data_dir: str = ""

    def load(self, data_dir: str):
        self.data_dir = data_dir
        logger.info("Initializing in-memory data store from %s...", data_dir)

        fuelhh_parquet = os.path.join(data_dir, "fuelhh_jan2026.parquet")
        fuelhh_json = os.path.join(data_dir, "fuelhh_jan2026.json")
        windfor_parquet = os.path.join(data_dir, "windfor_jan2026.parquet")
        windfor_json = os.path.join(data_dir, "windfor_jan2026.json")

        # Load FUELHH
        if os.path.exists(fuelhh_parquet):
            logger.info("Loading FUELHH from Parquet: %s", fuelhh_parquet)
            self.fuelhh_df = pd.read_parquet(fuelhh_parquet)
        elif os.path.exists(fuelhh_json):
            logger.info("Loading FUELHH from JSON: %s", fuelhh_json)
            self.fuelhh_df = pd.read_json(fuelhh_json)
        else:
            logger.warning("No FUELHH dataset found in %s", data_dir)
            self.fuelhh_df = pd.DataFrame()

        # Load WINDFOR
        if os.path.exists(windfor_parquet):
            logger.info("Loading WINDFOR from Parquet: %s", windfor_parquet)
            self.windfor_df = pd.read_parquet(windfor_parquet)
        elif os.path.exists(windfor_json):
            logger.info("Loading WINDFOR from JSON: %s", windfor_json)
            self.windfor_df = pd.read_json(windfor_json)
        else:
            logger.warning("No WINDFOR dataset found in %s", data_dir)
            self.windfor_df = pd.DataFrame()

        # Ensure datetime types
        if not self.fuelhh_df.empty:
            if not pd.api.types.is_datetime64_any_dtype(self.fuelhh_df["startTime"]):
                self.fuelhh_df["startTime"] = pd.to_datetime(self.fuelhh_df["startTime"], utc=True)
            self.fuelhh_count = len(self.fuelhh_df)

        if not self.windfor_df.empty:
            if not pd.api.types.is_datetime64_any_dtype(self.windfor_df["publishTime"]):
                self.windfor_df["publishTime"] = pd.to_datetime(self.windfor_df["publishTime"], utc=True)
            if not pd.api.types.is_datetime64_any_dtype(self.windfor_df["startTime"]):
                self.windfor_df["startTime"] = pd.to_datetime(self.windfor_df["startTime"], utc=True)
            self.windfor_count = len(self.windfor_df)

        self.is_loaded = True
        logger.info(
            "DataStore successfully loaded: %d FUELHH rows, %d WINDFOR rows",
            self.fuelhh_count,
            self.windfor_count
        )

data_store = DataStore()

