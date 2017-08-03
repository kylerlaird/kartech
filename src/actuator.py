#!/usr/bin/python
import os
from array import array

import can4python as can


class Actuator:

    """
    default Command Identifier is 0xFF0000.
    """
    @property
    def DCI(self):
        return 0xFF0000
 
    """
    default Report Identifier is 0xFF0001.
    """
    @property
    def DRI(self):
        return 0xFF0001


    def __init__(self, interface, cfg = None):
        self.can_interface = interface

        if cfg is None:
            self.cfg = can.Configuration()
            self.cfg.ego_node_ids="1"

        self.bus_snd = None
        self.bus_rcv = None
        
        self.device_id = self.DCI
        self.report_id = self.DRI 

    def __reg_frame_desc(self, frame_id, name, frame_data):
        frame_def = can.CanFrameDefinition(frame_id, name=name, dlc = len(frame_data))
        frame_def.producer_ids = ["1"]
        sig = can.CanSignalDefinition(name, 0, 8*len(frame_data))
        frame_def.signaldefinitions.append(sig)
        self.cfg.add_framedefinition(frame_def)


    def __startSendBus(self, timeout):
        if self.bus_snd is None:
            self.bus_snd = can.CanBus(self.cfg, self.can_interface, timeout = timeout)

    def __stopSendBus(self):
        if self.bus_snd is not None:
            self.bus_snd.stop()
            self.bus_snd.caninterface.close()
            self.bus_snd = None

    def __startRcvBus(self):
        if self.bus_rcv is None:
            self.bus_rcv = can.CanBus(self.cfg, self.can_interface, timeout = timeout)

    def __stopRcvBus(self):
        if self.bus_rcv is not None:
            self.bus_rcv.stop()
            self.bus_rcv.caninterface.close()
            self.bus_rcv = None


    def __sendFrame(self, frame_id, cmd):
        if self.bus_snd is not None:
            print("Frame id:", frame_id)
            frame = can.canframe.CanFrame(frame_id, cmd.tobytes(), can.constants.CAN_FRAMEFORMAT_EXTENDED)
            self.bus_snd.send_frame(frame)


    def _recvFrame(self):
        received_signalvalues = None
        if self.bus_rcv is not None:
            received_signalvalues = self.bus_rcv.recv_next_signals()

        return received_signalvalues

    def __createCommand(self, cmd, data_type, confirmation, auto_reply):
        cmd = array('B', [cmd, data_type, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0])
        if confirmation:
            cmd[1] |= 0x1
        if auto_reply:
            cmd[1] |= 0x2

        return cmd

    def IsRcvBus(self):
        return self.bus_rcv is not None;

    def IsSndBus(self):
        return self.bus_snd is not None;

    def SoftwareVersionData(self, confirmation = True):
        cmd = self.__createCommand(0x7f, 0x41, confirmation, False)
        self.__sendFrame(self.device_id, cmd)
