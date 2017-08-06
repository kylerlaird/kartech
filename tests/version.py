import actuator
import binascii
import threading


def OnFrameSending(frame):
    print("-> [%s]: %s" % (hex(frame.frame_id), binascii.hexlify(frame.frame_data).decode()))


def OnFrameReceiving(frame):
    print("<- [%s]: %s" % (hex(frame.frame_id), binascii.hexlify(frame.frame_data).decode()))


act = actuator.Actuator("can0")
act.Ignore(0x00FF0000)
try:
    act.StartSendingBus(3, OnFrameSending)
    act.StartReceivingBus(3, OnFrameReceiving)
    msg = act.SoftwareVersionData(False, True)
    if msg is None:
        print ("Wrong response received")
    print ("Version %s" % msg.SoftwareVersion())
    print ("Date (DD/MM/YYYY): %s/%s/%s" % (msg.SwDay(), msg.SwMonth(), msg.SwYear()))

finally:
    act.StopSendingBus()
    act.StopSendingBus()

print("Execution DONE.")
