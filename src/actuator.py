#!/usr/bin/python
import os
import socket
from array import array

import can4python as can

class UnexpectedResponse(Exception):
    pass

class DataReceiver:
    def OnFrameRecieved(self, frame):
        print("-> %s"% str(frame))
        return True # continue receiving

    def OnFrameTimeout(self, error):
        return True # continue

    def OnFrameError(self, error):
        print("Error: %s" % str(error))
        return False # stop 

class ActuatorCommand:
    def __init__(self, cmd, data_type, confirmation, auto_reply):
        self.__cmd = array('B', [cmd, data_type, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0])
        if confirmation:
            self.__cmd[1] |= 0x1
        if auto_reply:
            self.__cmd[1] |= 0x2

    @classmethod
    def CreateCommand(cmd, data_type, confirmation, auto_reply):
        return ActuatorCommand(cmd, data_type, confirmation, auto_reply)  

    @property
    def rawFrame(self):
        return self.__cmd.tobytes()
    
    def FrameData(self, position):
        if position >= len(self.__cmd):
            raise IndexError("Position out of length")

        return self.__cmd[position]

    def SetFrameByte(self, position, value):
        if position >= len(self.__cmd):
            raise IndexError("Position out of length")

        if value > 0xff:
            raise ValueError("Value too big")

        self.__cmd[position] = value
        return self.__cmd[position]


class SoftwareRevisionReport(ActuatorCommand):
    """
    Byte1: DT - Data Type - will be set to 65 (0x41).
    Bytes 2 thru 4: SW VER – These bytes show the software version.
    Byte 5: SW DAY – This is the day the software was written.
    Bytes 6 & 7: SW YEAR/MONTH - This is the month and year the software was written.
    """

    def __init__(self, frame):
        super(SoftwareRevisionReport, self).__init__(frame.frame_data[0], frame.frame_data[1], False, False)
        if self.FrameData(0) != 0xEF:
            raise ValueError("Wrong frame byte 0")
        if self.FrameData(1) != 0x41:
            raise ValueError("Wrong frame byte 1")

        self.SetFrameByte(2, frame.frame_data[2])
        self.SetFrameByte(3, frame.frame_data[3])
        self.SetFrameByte(4, frame.frame_data[4])
        self.SetFrameByte(5, frame.frame_data[5])
        self.SetFrameByte(6, frame.frame_data[6])
        self.SetFrameByte(7, frame.frame_data[7])
        
    def SoftwareVersion(self):
        a = 0

        a <<= 8
        a += self.FrameData(3)
        a <<= 8
        a += self.FrameData(4)
        return "%s.%s" % (str(self.FrameData(2)), str(a))

    
    def SwDay(self):
        return self.FrameData(5)

    def SwYear(self):
        return self.FrameData(6)

    def SwYear(self):
        return self.FrameData(7)
    

class UniqueDeviceIDReport(ActuatorCommand):
    """
    Byte 1: A – Auto Reply Flag. If this is the response from an Auto Reply, this bit
    will be set. Otherwise it will be cleared.
    DT - Data Type - will be set to 0.
    Bytes 2 thru 7:
    ACTUATOR ID PART 1– These bytes show the first 6 bytes of the
    Unique ID Number.
    """

    def __init__(self, frame):
        super(UniqueDeviceIDReport, self).__init__(frame.frame_data[0], frame.frame_data[1], False, False)
        if self.FrameData(0) != 0xA8:
            raise ValueError("Wrong frame byte 0")

        self.SetFrameByte(2, frame.frame_data[2])
        self.SetFrameByte(3, frame.frame_data[3])
        self.SetFrameByte(4, frame.frame_data[4])
        self.SetFrameByte(5, frame.frame_data[5])
        self.SetFrameByte(6, frame.frame_data[6])
        self.SetFrameByte(7, frame.frame_data[7])
        
    def ActuatorIDPart(self):
        a = 0
        a += self.FrameData(2)
        a <<= 8
        a += self.FrameData(3)
        a <<= 8
        a += self.FrameData(4)
        a <<= 8
        a += self.FrameData(5)
        a <<= 8
        a += self.FrameData(6)
        a <<= 8
        a += self.FrameData(7)
        return a


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
#            self.cfg.ego_node_ids="1"

        self.bus_snd = None
        self.bus_rcv = None
        
        self.device_id = self.DCI
        self.report_id = self.DRI 

        self.working = False

        self.OnFrameReceiving = None
        self.OnFrameSending = None

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

    def __startRcvBus(self, timeout):
        if self.bus_rcv is None:
            self.bus_rcv = can.CanBus(self.cfg, self.can_interface, timeout = timeout)

    def __stopRcvBus(self):
        if self.bus_rcv is not None:
            self.bus_rcv.stop()
            self.bus_rcv.caninterface.close()
            self.bus_rcv = None


    def __sendFrame(self, frame_id, cmd):
        if self.bus_snd is not None:
            frame = can.canframe.CanFrame(frame_id, cmd.rawFrame, can.constants.CAN_FRAMEFORMAT_EXTENDED)

            if self.OnFrameSending is not None: self.OnFrameSending(frame)

            self.bus_snd.send_frame(frame)


    def __recvFrame(self):
        received = None
        if self.bus_rcv is not None:
            received = self.bus_rcv.recv_next_frame()

        if self.OnFrameReceiving is not None: self.OnFrameReceiving(received)

        return received

#    def __createCommand(self, cmd, data_type, confirmation, auto_reply):
#        cmd = array('B', [cmd, data_type, 0x0, 0x0, 0x0, 0x0, 0x0, 0x0])
#        if confirmation:
#            cmd[1] |= 0x1
#        if auto_reply:
#            cmd[1] |= 0x2
#
#        return cmd

    def __ReadResp(self, orig, shouldBeConfirmed):
        frame = self.__recvFrame()
        if shouldBeConfirmed:
            # check that data is the same as request
            if frame.frame_data[0] != orig.FrameData(0):
                # wrong frame
                raise UnexpectedResponse("Expecting %s but received %s command" % (str(orig.FrameData(0)), str(frame.frame_data[0])))

            frame = self.__recvFrame()
        return frame

    def __ReadConfirm(self, orig):
        frame = self.__recvFrame()
        # check that data is the same as request
        if frame.frame_data[0] != orig.FrameData(0):
            # wrong frame
            raise UnexpectedResponse("Expecting %s but received %s command" % (str(orig.FrameData(0)), str(frame.frame_data[0])))

    def IsRcvBus(self):
        return self.bus_rcv is not None;

    def IsSndBus(self):
        return self.bus_snd is not None;

    def IsRcvWorking(self):
        return self.working

    def RunReceiver(self, dataReceiver, recvTimeout):
        self.__startRcvBus(recvTimeout)
        self.working = True
        while self.working:
            try:
                frame = self.__recvFrame()
                if frame is None:
                    print("Lost connection...")
                    break
                self.working = dataReceiver.OnFrameRecieved(frame)
            except can.exceptions.CanTimeoutException as t:
#                print("Got timeout: %s" % str(t))
                self.working  = dataReceiver.OnFrameTimeout(t)
            except Exception as e:
#                print("Receiving: Got error, %s" % str(e))
                self.working = dataReceiver.OnFrameError(e)
            
        self.__stopRcvBus()
            
    def StartSendingBus(self, timeout, OnFrameSending = None):
        self.OnFrameSending = OnFrameSending
        self.__startSendBus(timeout)

    def StopSendingBus(self):
        self.__stopSendBus()
        self.OnFrameSending = None

    def StartReceivingBus(self, timeout, OnFrameReceiving = None):
        self.OnFrameReceiving = OnFrameReceiving
        self.__startRcvBus(timeout)

    def StopReceivingBus(self):
        self.__stopRcvBus()
        self.OnFrameReceiving = None

    def SoftwareVersionData(self, confirmation = True, waitResponse = False):
        cmd = ActuatorCommand(0x7f, 0x41, confirmation, False)
        cmd.SetFrameByte(2, 0x01)

        self.__sendFrame(self.device_id, cmd)
        ret = None
        if waitResponse:
            frame = self.__ReadResp(cmd, confirmation)
            if frame is not None:
                ret = SoftwareRevisionReport(frame)

        return ret

    def UniqueDeviceID(self, confirmation = True, waitResponse = False):
        cmd = ActuatorCommand(0x28, 0x40, confirmation, False)

        self.__sendFrame(self.device_id, cmd)
        ret = None
        if waitResponse:
            frame = self.__ReadResp(cmd, confirmation)
            if frame is not None:
                ret = UniqueDeviceIDReport(frame)

        return ret

    def Reset(self, resetType, resetTypeExt, confirmation = True, waitResponse = False):
        """
        RESET TYPE - This value determines which type of reset is to be done.
        0x0001 = Reset Outputs. All outputs are turned off.
        0x0002 = Reset User Defined IDs.
        0x0004 = Reset Report Rates.
        0x0008 = Reset Hardware Configurations.
        0x0010 = Reset User Configurations (KP, KI, KD, ...).
        0xFFFF = Reset everything.
        RESET TYPE EXTENTION 1 – This parameter further defines some
        resets. Setting the bit to 1, activates the specific Reset. Clearing the
        bit leaves that parameter untouched.
        Bit 0: Reset User Defined Report ID
        Bit 1: Reset User Defined Command ID #1
        Bit 2: Reset User Defined Command ID #2
        Bit 3: Reset User Defined Command ID #3
        Bit 4: Reset User Defined Command ID #4
        Bit 13: Reset RPSEL.
        Bit 14: Reset DISDEF.

        all data for this command are in host order
        """

        cmd = ActuatorCommand(0xF9, 0x0, confirmation, False)

        if resetType is None and resetTypeExt is None:
            raise ValueError("resetType and resetTypeExt cannot be None")

        if resetType is not None:
            netorder = socket.htons(resetType)

            lo = netorder & 0xff
            hi = (netorder >> 8 ) & 0xff

            cmd.SetFrameByte(2, hi)
            cmd.SetFrameByte(3, lo)

        if resetTypeExt is not None:
            netorder = socket.htons(resetTypeExt)

            lo = netorder & 0xff
            hi = (netorder >> 8 ) & 0xff

            cmd.SetFrameByte(4, hi)
            cmd.SetFrameByte(5, lo)

        self.__sendFrame(self.device_id, cmd)

        if waitResponse and confirmation:
            self.__ReadConfirm(cmd)

        return None

    def PWMFrequency(self, pwmMin, pwmMax, pwmFreq, confirmation = True, waitResponse = False):
        cmd = ActuatorCommand(0xF5, 0x01, confirmation, False)

        cmd.SetFrameByte(3, 0x2)

        if pwmMin is None:
            pwmMin = 0

        if pwmMin > 100:
            raise ValueError("pwmMin too big")

        cmd.SetFrameByte(4, pwmMin)

        if pwmMax is None:
            pwmMax = 100

        if pwmMax > 100:
            raise ValueError("pwmMan too big")

        cmd.SetFrameByte(5, pwmMax)

        if pwmFreq is not None:
            netorder = socket.htons(pwmFreq)

            lo = netorder & 0xff
            hi = (netorder >> 8 ) & 0xff

            cmd.SetFrameByte(6, hi)
            cmd.SetFrameByte(7, lo)

        self.__sendFrame(self.device_id, cmd)

        if waitResponse and confirmation:
            self.__ReadConfirm(cmd)

        return None
