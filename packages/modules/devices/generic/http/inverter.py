#!/usr/bin/env python3
from typing import TypedDict, Any

from requests import Session

from helpermodules import compatibility
from modules.common.abstract_device import AbstractInverter
from modules.common.component_state import InverterState
from modules.common.component_type import ComponentDescriptor
from modules.common.fault_state import ComponentInfo, FaultState
from modules.common.simcount import SimCounter
from modules.common.store import get_inverter_value_store
from modules.devices.generic.http.api import create_request_function
from modules.devices.generic.http.config import HttpInverterSetup


class KwargsDict(TypedDict):
    device_id: int
    url: str


class HttpInverter(AbstractInverter):
    def __init__(self, component_config: HttpInverterSetup, **kwargs: Any) -> None:
        self.component_config = component_config
        self.kwargs: KwargsDict = kwargs

    def initialize(self) -> None:
        self.__device_id: int = self.kwargs['device_id']
        self.url: str = self.kwargs['url']
        self.sim_counter = SimCounter(self.__device_id, self.component_config.id, prefix="pv")
        self.store = get_inverter_value_store(self.component_config.id)
        self.fault_state = FaultState(ComponentInfo.from_component_config(self.component_config))

        self.__get_power = create_request_function(self.url, self.component_config.configuration.power_path)
        self.__get_exported = create_request_function(self.url, self.component_config.configuration.exported_path)

    def update(self, session: Session) -> None:
        power = self.__get_power(session)
        if compatibility.is_ramdisk_in_use():
            # for compatibility: in 1.x power URL values are positive!
            power *= -1
        exported = self.__get_exported(session)
        if exported is None:
            _, exported = self.sim_counter.sim_count(power)

        inverter_state = InverterState(
            power=power,
            exported=exported
        )
        self.store.set(inverter_state)


component_descriptor = ComponentDescriptor(configuration_factory=HttpInverterSetup)
