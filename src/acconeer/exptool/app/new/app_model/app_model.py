from __future__ import annotations

import abc
import logging
import queue
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple, Type

import attrs

from PySide6.QtCore import QDeadlineTimer, QObject, QThread, Signal
from PySide6.QtWidgets import QWidget

import pyqtgraph as pg

from acconeer.exptool import a121
from acconeer.exptool.app.new.backend import (
    Backend,
    BackendPlugin,
    BusyMessage,
    Command,
    IdleMessage,
    Message,
    Task,
)

from .serial_port_updater import SerialPortUpdater
from .state_enums import ConnectionInterface, ConnectionState, PluginState


log = logging.getLogger(__name__)


class AppModelAware(abc.ABC):
    def __init__(self, app_model: AppModel) -> None:
        app_model.sig_notify.connect(self.on_app_model_update)
        app_model.sig_error.connect(self.on_app_model_error)

    @abc.abstractmethod
    def on_app_model_update(self, app_model: AppModel) -> None:
        pass

    @abc.abstractmethod
    def on_app_model_error(self, exception: Exception) -> None:
        pass


class PlotPlugin(AppModelAware):
    def __init__(self, app_model: AppModel, plot_layout: pg.GraphicsLayout) -> None:
        super().__init__(app_model=app_model)
        self.plot_layout = plot_layout

    @abc.abstractmethod
    def handle_message(self, message: Message) -> None:
        pass

    @abc.abstractmethod
    def draw(self) -> None:
        pass


class ViewPlugin(AppModelAware):
    def __init__(self, app_model: AppModel, view_widget: QWidget) -> None:
        super().__init__(app_model=app_model)
        self.app_model = app_model
        self.view_widget = view_widget

    def send_backend_command(self, command: Command) -> None:
        self.app_model._backend._send(command)

    def send_backend_task(self, task: Task) -> None:
        self.send_backend_command(("task", task))


class PluginFamily(Enum):
    SERVICE = "Services"
    DETECTOR = "Detectors"


class PluginGeneration(Enum):
    A111 = "a111"
    A121 = "a121"


@attrs.frozen(kw_only=True)
class Plugin:
    generation: PluginGeneration = attrs.field()
    key: str = attrs.field()
    title: str = attrs.field()
    description: Optional[str] = attrs.field(default=None)
    family: PluginFamily = attrs.field()
    backend_plugin: Type[BackendPlugin] = attrs.field()
    plot_plugin: Type[PlotPlugin] = attrs.field()
    view_plugin: Type[ViewPlugin] = attrs.field()


class _BackendListeningThread(QThread):
    sig_received_from_backend = Signal(Message)

    def __init__(self, backend: Backend, parent: QObject) -> None:
        super().__init__(parent)
        self.backend = backend

    def run(self) -> None:
        log.debug("Backend listening thread starting...")

        while not self.isInterruptionRequested():
            try:
                message = self.backend.recv(timeout=0.1)
            except queue.Empty:
                continue
            else:
                self.sig_received_from_backend.emit(message)

        log.debug("Backend listening thread stopping...")


class AppModel(QObject):
    sig_notify = Signal(object)
    sig_error = Signal(Exception)
    sig_load_plugin = Signal(object)
    sig_message_plot_plugin = Signal(object)
    sig_message_view_plugin = Signal(object)

    plugins: list[Plugin]
    plugin: Optional[Plugin]

    connection_state: ConnectionState
    connection_interface: ConnectionInterface
    plugin_state: PluginState
    socket_connection_ip: str
    serial_connection_port: Optional[str]
    available_tagged_ports: list[Tuple[str, Optional[str]]]
    saveable_file: Optional[Path]

    def __init__(self, backend: Backend, plugins: list[Plugin]) -> None:
        super().__init__()
        self._backend = backend
        self._listener = _BackendListeningThread(self._backend, self)
        self._listener.sig_received_from_backend.connect(self._handle_backend_message)
        self._serial_port_updater = SerialPortUpdater(self)
        self._serial_port_updater.sig_update.connect(self._handle_serial_port_update)

        self._a121_server_info: Optional[a121.ServerInfo] = None

        self.plugins = plugins
        self.plugin = None

        self.connection_state = ConnectionState.DISCONNECTED
        self.connection_interface = ConnectionInterface.SERIAL
        self.plugin_state = PluginState.UNLOADED
        self.socket_connection_ip = ""
        self.serial_connection_port = None
        self.available_tagged_ports = []
        self.saveable_file = None

    def start(self) -> None:
        self._listener.start()
        self._serial_port_updater.start()

    def stop(self) -> None:
        self._listener.requestInterruption()
        status = self._listener.wait(QDeadlineTimer(500))

        if not status:
            log.debug("Backend listening thread did not stop when requested, terminating...")
            self._listener.terminate()

        self._serial_port_updater.stop()

    def broadcast(self) -> None:
        self.sig_notify.emit(self)

    def _handle_backend_message(self, message: Message) -> None:
        if message.status == "error":
            self.sig_error.emit(message.exception)

        if message.recipient is not None:
            if message.recipient == "plot_plugin":
                self.sig_message_plot_plugin.emit(message)
            elif message.recipient == "view_plugin":
                self.sig_message_view_plugin.emit(message)
            else:
                raise RuntimeError(
                    f"AppModel cannot handle messages with recipient {message.recipient!r}"
                )

            return

        if message.command_name == "connect_client":
            if message.status == "ok":
                self.connection_state = ConnectionState.CONNECTED
            else:
                self.connection_state = ConnectionState.DISCONNECTED
        elif message.command_name == "disconnect_client":
            if message.status == "ok":
                self.connection_state = ConnectionState.DISCONNECTED
                self._a121_server_info = None
            else:
                self.connection_state = ConnectionState.CONNECTED
        elif message.command_name == "server_info":
            self._a121_server_info = message.data
        elif message.command_name == "load_plugin":
            if message.status == "ok":
                self.plugin_state = PluginState.LOADED_IDLE
            else:
                self.plugin_state = PluginState.UNLOADED
        elif message.command_name == "unload_plugin":
            if message.status == "ok":
                self.plugin_state = PluginState.UNLOADED
            else:
                self.plugin_state = PluginState.LOADED_IDLE
        elif message == BusyMessage():
            self.plugin_state = PluginState.LOADED_BUSY
        elif message == IdleMessage():
            self.plugin_state = PluginState.LOADED_IDLE

        self.broadcast()

    def _handle_serial_port_update(self, tagged_ports: list[Tuple[str, Optional[str]]]) -> None:
        self.serial_connection_port = self._select_new_serial_port(
            dict(self.available_tagged_ports),
            dict(tagged_ports),
            self.serial_connection_port,
        )
        self.available_tagged_ports = tagged_ports

        self.broadcast()

    def _select_new_serial_port(
        self,
        old_ports: dict[str, Optional[str]],
        new_ports: dict[str, Optional[str]],
        current_port: Optional[str],
    ) -> Optional[str]:
        if self.connection_state != ConnectionState.DISCONNECTED:
            return current_port

        if current_port not in new_ports:  # Then find a new suitable port
            port = None

            for port, tag in new_ports.items():
                if tag:
                    return port

            return port

        # If we already have a tagged port, keep it
        if new_ports[current_port]:
            return current_port

        # If a tagged port was added, select it
        added_ports = {k: v for k, v in new_ports.items() if k not in old_ports}
        for port, tag in added_ports.items():
            if tag:
                return port

        return current_port

    def connect_client(self) -> None:
        if self.connection_interface == ConnectionInterface.SOCKET:
            client_info = a121.ClientInfo(ip_address=self.socket_connection_ip)
        elif self.connection_interface == ConnectionInterface.SERIAL:
            client_info = a121.ClientInfo(serial_port=self.serial_connection_port)
        else:
            raise RuntimeError

        log.debug(f"Connecting client with {client_info}")

        self._backend.put_task(
            task=(
                "connect_client",
                {"client_info": client_info},
            )
        )
        self.connection_state = ConnectionState.CONNECTING
        self.broadcast()

    def disconnect_client(self) -> None:
        self._backend.put_task(task=("disconnect_client", {}))
        self.connection_state = ConnectionState.DISCONNECTING
        self.broadcast()

    def set_connection_interface(self, connection_interface: ConnectionInterface) -> None:
        self.connection_interface = connection_interface
        self.broadcast()

    def set_socket_connection_ip(self, ip: str) -> None:
        self.socket_connection_ip = ip
        self.broadcast()

    def set_serial_connection_port(self, port: Optional[str]) -> None:
        self.serial_connection_port = port
        self.broadcast()

    def set_plugin_state(self, state: PluginState) -> None:
        self.plugin_state = state
        self.broadcast()

    def load_plugin(self, plugin: Optional[Plugin]) -> None:
        if plugin == self.plugin:
            return

        if plugin is None:
            self._backend.unload_plugin()
            if self.plugin is not None:
                self.plugin_state = PluginState.UNLOADING
        else:
            self._backend.load_plugin(plugin.backend_plugin)
            if self.plugin is not None:
                self.plugin_state = PluginState.LOADING

        self.sig_load_plugin.emit(plugin)
        self.plugin = plugin
        self.broadcast()

    def save_to_file(self, path: Path) -> None:
        log.debug(f"{self.__class__.__name__} saving to file '{path}'")

        if self.saveable_file is None:
            raise RuntimeError

        self.saveable_file.rename(path)
        self.saveable_file = None
        self.broadcast()

    def load_from_file(self, path: Path) -> None:
        log.debug(f"{self.__class__.__name__} loading from file '{path}'")
        # TODO

    @property
    def rss_version(self) -> Optional[str]:
        if self._a121_server_info is None:
            return None

        return self._a121_server_info.rss_version