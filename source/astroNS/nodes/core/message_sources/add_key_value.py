""" Add Key Value node adds keys to the message dictionary.

With each message containing a dictionary of keys, a new key can be added for
use later on in the simulation.

"""
from simpy.core import Environment
from typing import List, Dict, Tuple, Any, Optional, Callable

from nodes.core.base import BaseNode


class AddKeyValue(BaseNode):
    """AddKeyValueNode class"""

    def __init__(self, env: Environment, name: str, configuration: Dict[str, Any]):
        """Initialize AddKeyValueNode class"""
        super().__init__(env, name, configuration, self.execute())
        self._key: self.configuration.get("key", None)
        self._value: self.configuration.get("value", None)
        self._time_delay: Callable[[], Optional[float]] = self.setFloatFromConfig(
            "time_delay", 0.0
        )
        self.required_imports: str = "import math; import datetime;" #configuration.get('imports', "")
        self.result_key: str       = configuration.get('result_key', name) 
        value_fn_string: str       = "def value_fn(sim_time,msg):  " + configuration.get('def value_fn(sim_time,msg)', 'msg')
        self.fns: Dict[str, Any] = {}
        exec(self.required_imports, self.fns)
        exec( value_fn_string, self.fns) 

        #import pudb; pu.db

        self.env.process(self.run())

    @property
    def time_delay(self) -> Optional[float]:
        """
        Sample
        ::
            Collect_Take:
                type: AddKeyValue
                time_delay: 30

        In this case the AddKeyValue node does nothing except delay the node.
        This should be done with :func:`~astroNS.nodes.network.delaytime`, but
        it can be combined with the other properties.
        """
        return self._time_delay()

    @property
    def key(self):
        """
        Sample
        ::
            Collect_Take:
                type: AddKeyValue
                key: collected
                value: 200

        This sets the key "collected" to what's in the property value.
        """
        return self._key

    @property
    def value(self):
        """
        Sample
        ::
            Collect_Take:
                type: AddKeyValue
                key: collected
                value: 200

        This sets the value of the key set by the key property to 200.
        """
        return self._value

    def execute(self):
        """Simpy execution code"""
        delay: float = 0.0
        processing_time: float = delay
        data_out_list: List[Tuple] = []
        #import pudb; pu.db
        while True:
            data_in = yield (delay, processing_time, data_out_list)

            #print(data_in)

            if data_in:
                msg = data_in #.copy()
                if (
                        ("key" not in self.configuration)
                    and ("value" not in self.configuration)
                ): 
                    #import pudb;pu.db
                    result = (self.fns['value_fn'])( self.env.now, data_in )
                    #print(self.log_prefix(data_in['ID']) + "Data ID |{}| arrived, set msg key |{}| to |{}|".format( data_in["ID"], self.result_key, result))
            
                    data_out = data_in.copy()
                    if self.result_key != 'delay':
                        data_out[self.result_key] = result
                        delay = self.time_delay
                        print(self.log_prefix(data_in['ID']) + "value:|{}| set to key: |{}|".format(result, self.result_key))
                    else:
                        delay = result
                        print(self.log_prefix(data_in['ID']) + "value: |{}| set as msg delay".format(result))
                    processing_time = delay
                    data_out_list = [data_out]

                elif (
                    self.configuration["key"] is None
                    and self.configuration["value"] is not None
                ):
                    processing_time = delay
                    data_out_list = [msg]
                    print(
                        self.log_prefix(data_in["ID"])
                        + "Data ID {} arrived at {}. Failed configuration as key is None".format(
                            data_in["ID"],
                            self.env.now,
                            self.configuration["key"],
                            msg[self.configuration["key"]],
                        )
                    )
                else:
                    # Key is not None or Value is also None
                    msg[self.configuration["key"]] = self.configuration["value"]
                    processing_time = delay
                    data_out_list = [msg]

                    print(
                        self.log_prefix(data_in["ID"])
                        + "Data ID {} arrived at {}. Adding new key-value pair: {}={}".format(
                            data_in["ID"],
                            self.env.now,
                            self.configuration["key"],
                            msg[self.configuration["key"]],
                        )
                    )

            else:
                # There was no data
                data_out_list = []
