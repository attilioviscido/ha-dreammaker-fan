"""Test helpers: load the integration modules without Home Assistant.

The parser has no Home Assistant dependencies. server.py only needs
HomeAssistant (type hints) and async_dispatcher_send, which are stubbed here
so the TCP handshake can be tested end to end with a simulated fan.
"""
import importlib
import os
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG_DIR = os.path.join(ROOT, "custom_components", "dreammaker_fan")

DISPATCHED = []


def _stub_homeassistant():
    if "homeassistant" in sys.modules:
        return
    ha = types.ModuleType("homeassistant")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    dispatcher = types.ModuleType("homeassistant.helpers.dispatcher")

    class HomeAssistant:  # noqa: D401 - minimal stand-in
        pass

    def async_dispatcher_send(hass, signal, *args):
        DISPATCHED.append((signal, args))

    core.HomeAssistant = HomeAssistant
    dispatcher.async_dispatcher_send = async_dispatcher_send
    sys.modules.update(
        {
            "homeassistant": ha,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.dispatcher": dispatcher,
        }
    )


def _load_package():
    # Register the package without running __init__.py (it needs HA).
    if "dreammaker_fan" not in sys.modules:
        pkg = types.ModuleType("dreammaker_fan")
        pkg.__path__ = [PKG_DIR]
        sys.modules["dreammaker_fan"] = pkg


_stub_homeassistant()
_load_package()
parser = importlib.import_module("dreammaker_fan.parser")
server = importlib.import_module("dreammaker_fan.server")
