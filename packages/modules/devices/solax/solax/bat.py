#!/usr/bin/env python3
from typing import Any, TypedDict

from modules.common import modbus
from modules.common.abstract_device import AbstractBat
from modules.common.component_state import BatState
from modules.common.component_type import ComponentDescriptor
from modules.common.fault_state import ComponentInfo, FaultState
from modules.common.modbus import ModbusDataType
from modules.common.simcount import SimCounter
from modules.common.store import get_bat_value_store
from modules.devices.solax.solax.config import SolaxBatSetup, Solax


class KwargsDict(TypedDict):
    client: modbus.ModbusTcpClient_
    device_config: Solax


class SolaxBat(AbstractBat):
    def __init__(self, component_config: SolaxBatSetup, **kwargs: Any) -> None:
        self.component_config = component_config
        self.kwargs: KwargsDict = kwargs

    def initialize(self) -> None:
        self.__tcp_client = self.kwargs['client']
        self.device_config = self.kwargs['device_config']
        self.sim_counter = SimCounter(self.device_config.id, self.component_config.id, prefix="speicher")
        self.store = get_bat_value_store(self.component_config.id)
        self.fault_state = FaultState(ComponentInfo.from_component_config(self.component_config))

    def update(self) -> None:
        unit = self.device_config.configuration.modbus_id

        # kein Speicher für Versionen G2 und G4
        power = self.__tcp_client.read_input_registers(0x0016, ModbusDataType.INT_16, unit=unit)
        soc = self.__tcp_client.read_input_registers(0x001C, ModbusDataType.UINT_16, unit=unit)

        imported, exported = self.sim_counter.sim_count(power)
        bat_state = BatState(
            power=power,
            soc=soc,
            imported=imported,
            exported=exported
        )
        self.store.set(bat_state)


component_descriptor = ComponentDescriptor(configuration_factory=SolaxBatSetup)
