# THIS FILE IS AUTOMATICALLY GENERATED - DO NOT EDIT

import logging
import platform
import queue

import serial

from acconeer.exptool.flash._xc120._uart_protocol import Packet, UartReader


_LOG = logging.getLogger(__name__)


class CommandFailed(Exception):
    pass


class XcCommandResponsePacket(Packet):
    packet_type = 0xF2

    def __init__(self, payload):
        self.command_id = int.from_bytes(payload[0:2], byteorder="little")
        self.command_payload = payload[2:]
        super().__init__(payload)

    def get_command_packet(self):
        return _command_packets.get(self.command_id)(self.command_payload)


class XcCommandRequestPacket(Packet):
    packet_type = 0xF2

    def __init__(self, command_payload):
        command_payload[0:0] = self.command_id.to_bytes(2, byteorder="little")
        super().__init__(command_payload)


class GetLastErrorRequestPacket(XcCommandRequestPacket):
    command_id = 0x0002

    def __init__(
        self,
    ):
        payload = bytearray()
        super().__init__(payload)


class GetLastErrorResponsePacket:
    command_id = 0x0002

    def __init__(self, payload):
        self.payload = payload

    def get_status(self):
        return self.payload[0]

    def get_response_data(self):
        return self.payload[1:].decode("ascii")


class GetAppSwVersionRequestPacket(XcCommandRequestPacket):
    command_id = 0x010A

    def __init__(
        self,
    ):
        payload = bytearray()
        super().__init__(payload)


class GetAppSwVersionResponsePacket:
    command_id = 0x010A

    def __init__(self, payload):
        self.payload = payload

    def get_status(self):
        return self.payload[0]

    def get_version(self):
        return self.payload[1:].decode("ascii")


class GetAppSwNameRequestPacket(XcCommandRequestPacket):
    command_id = 0x010B

    def __init__(
        self,
    ):
        payload = bytearray()
        super().__init__(payload)


class GetAppSwNameResponsePacket:
    command_id = 0x010B

    def __init__(self, payload):
        self.payload = payload

    def get_status(self):
        return self.payload[0]

    def get_name(self):
        return self.payload[1:].decode("ascii")


class DfuRebootRequestPacket(XcCommandRequestPacket):
    command_id = 0xFFFF

    def __init__(
        self,
    ):
        payload = bytearray()
        super().__init__(payload)


_command_packets = {
    0x0002: GetLastErrorResponsePacket,
    0x010A: GetAppSwVersionResponsePacket,
    0x010B: GetAppSwNameResponsePacket,
}


class XCCommunication:
    def __init__(self, port):
        if platform.system() != "Linux":
            _LOG.error("Unsupported OS: %s", platform.system())
            raise OSError("Module only supports Linux.")

        self._ser = serial.Serial(port, exclusive=True)
        self._reader = UartReader(self._ser, [XcCommandResponsePacket])
        self._reader.start()
        self._timeout = UartReader.DEFAULT_READ_TIMEOUT
        self._reader_started = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def stop(self):
        if self._reader_started:
            self._reader.stop()
            self._reader_started = False

    def close(self):
        self.stop()
        self._ser.close()
        self._ser = None

    def _send_packet(self, packet):
        data = packet.get_byte_array()
        _LOG.debug("Sending packet %s", data)
        self._ser.write(data)

    def _execute_request(self, packet):
        try:
            self._send_packet(packet)
            response = self._reader.wait_packet(XcCommandResponsePacket.packet_type, self._timeout)
            return response.get_command_packet()
        except queue.Empty:
            _LOG.error("read timeout")
            raise TimeoutError("_execute_request timeout")

    def get_last_error(self):
        response = self._execute_request(GetLastErrorRequestPacket())
        status = response.get_status()
        response_data = response.get_response_data()
        if status != 0:
            error_msg = self.get_last_error()
            raise CommandFailed(f"Command failed with code {status} [{error_msg}]")
        return response_data

    def get_app_sw_version(self):
        response = self._execute_request(GetAppSwVersionRequestPacket())
        status = response.get_status()
        version = response.get_version()
        if status != 0:
            error_msg = self.get_last_error()
            raise CommandFailed(f"Command failed with code {status} [{error_msg}]")
        return version

    def get_app_sw_name(self):
        response = self._execute_request(GetAppSwNameRequestPacket())
        status = response.get_status()
        name = response.get_name()
        if status != 0:
            error_msg = self.get_last_error()
            raise CommandFailed(f"Command failed with code {status} [{error_msg}]")
        return name

    def dfu_reboot(self):
        self._send_packet(DfuRebootRequestPacket())