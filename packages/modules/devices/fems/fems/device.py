#!/usr/bin/env python3
import logging
from typing import Iterable, Optional, List, Union

from helpermodules.cli import run_using_positional_cli_args
from modules.common import req
from modules.common.abstract_device import DeviceDescriptor
from modules.common.configurable_device import ConfigurableDevice, ComponentFactoryByType, MultiComponentUpdater
from modules.devices.fems.fems import bat, counter, inverter
from modules.devices.fems.fems.config import Fems, FemsBatSetup, FemsConfiguration, FemsCounterSetup, FemsInverterSetup

log = logging.getLogger(__name__)


def create_device(device_config: Fems):
    session = None

    def create_bat_component(component_config: FemsBatSetup):
        nonlocal session
        return bat.FemsBat(component_config, ip_address=device_config.configuration.ip_address, session=session)

    def create_counter_component(component_config: FemsCounterSetup):
        nonlocal session
        return counter.FemsCounter(component_config, ip_address=device_config.configuration.ip_address, session=session)

    def create_inverter_component(component_config: FemsInverterSetup):
        nonlocal session
        return inverter.FemsInverter(component_config, ip_address=device_config.configuration.ip_address,
                                     session=session)

    def update_components(components: Iterable[Union[bat.FemsBat, counter.FemsCounter, inverter.FemsInverter]]):
        for component in components:
            component.update()

    def initializer():
        nonlocal session
        session = req.get_http_session()
        session.auth = ("x", device_config.configuration.password)

    return ConfigurableDevice(
        device_config=device_config,
        initializer=initializer,
        component_factory=ComponentFactoryByType(
            bat=create_bat_component,
            counter=create_counter_component,
            inverter=create_inverter_component,
        ),
        component_updater=MultiComponentUpdater(update_components)
    )


COMPONENT_TYPE_TO_MODULE = {
    "bat": bat,
    "counter": counter,
    "inverter": inverter,
}


def read_legacy(component_type: str,
                ip_address: str,
                password: str,
                bat_num: Optional[int] = None,
                num: Optional[int] = None) -> None:
    dev = create_device(Fems(configuration=FemsConfiguration(ip_address=ip_address, password=password)))
    if component_type in COMPONENT_TYPE_TO_MODULE:
        component_config = COMPONENT_TYPE_TO_MODULE[component_type].component_descriptor.configuration_factory()
    else:
        raise Exception(
            "illegal component type " + component_type + ". Allowed values: " +
            ','.join(COMPONENT_TYPE_TO_MODULE.keys())
        )
    component_config.id = num
    if component_type == "bat":
        component_config.configuration.num = bat_num + 1
    dev.add_component(component_config)

    log.debug('Fems IP-Adresse: ' + ip_address)
    log.debug('Fems Password: ' + password)

    dev.update()


def main(argv: List[str]) -> None:
    run_using_positional_cli_args(read_legacy, argv)


device_descriptor = DeviceDescriptor(configuration_factory=Fems)
