"""
CSV Data Source Node -- Get messages from a spacelynx ops csv to pulse through the system.
"""

import pandas as pd
from simpy.core import Environment

from nodes.core.base import BaseNode

from typing import (
    List,
    Dict,
    Tuple,
    Any,
    Iterator,
    Optional,
    Type,
    Callable,
    Generator,
    Iterable,
    Union as typeUnion,
)


class FileDataSource(BaseNode):
    """A message source that gets messages from a CSV or excel file of spacelynx ops.
    Required columns:
        "Collect_ID",
        "Collect_Start_Seconds_After_Sim_Epoch",
        "File_Size_Gbits"

    Note: Ensure that the default msg_size_key is size_gbits, NOT size_mbits. This can be changed in the .yml file

    """

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialization"""
        super().__init__(env, name, configuration, self.execute())
        self.file_name: str = configuration.get("file_name", "NOT_PROVIDED")
        self.delimiter: str = configuration.get("delimiter", ",")
        self.keys: list = configuration.get("file_keys", [])

        if self.file_name == "NOT_PROVIDED":
            print(self.log_prefix() + "ERROR. FileDataSource file_name not provided")

        if len(self.keys) == 0:
            self.keys = [
                "Collect_ID",
                "Collect_Start_Seconds_After_Sim_Epoch",
                "File_Size_Gbits",
            ]
            print(
                self.log_prefix()
                + "No keys provided to index input data, using SpaceLynx defaults."
            )

        self.env.process(self.run())

    def execute(self):
        """Execute function, part of simpy functionality"""
        yield 0.0, 0.0, []

        with open(self.file_name, "r") as in_file:
            if ".csv" in self.file_name:
                messages = pd.read_csv(in_file)
                # messages = csv.DictReader(in_file,delimiter=self.delimiter,quoting=csv.QUOTE_MINIMAL)
            elif ".xlsx" in self.file_name:
                messages = pd.read_excel(in_file)
            else:
                print(
                    self.log_prefix()
                    + f"ERROR. {self.file_name} is not either a CSV or Excel file."
                )
                print("Please change input to be CSV or Excel.")

            # old columns names to pull out SL data
            # sl_cols = [
            #     "ID",
            #     "time_delay",
            #     "size_mbits"]
            #     "SSDR_Data_Post_Op_Gbits",
            #     "Target_Name",
            #     "Asset_ID",
            #     "Phenomenology",
            #     "Target_ID",
            # ]
            messages = messages[self.keys]

            # Rename columns to astroNS format? Maybe later
            astroNS_cols = ["ID", "time_delay", self.msg_size_key]

            delay = float(0)
            for i, m in messages.iterrows():
                ID: str = m[self.keys[0]]
                sim_time: float = float(m[self.keys[1]])
                message_size: float = float(m[self.keys[2]])
                row_dict = {
                    astroNS_cols[0]: ID,
                    astroNS_cols[1]: sim_time,
                    astroNS_cols[2]: message_size,
                }
                print(
                    self.log_prefix()
                    + "Processed Line # |{}|{}| Delay:|{}|".format(i, row_dict, delay)
                )
                yield delay, delay, [row_dict]

            yield BaseNode.stop_signal, BaseNode.stop_signal, {}
