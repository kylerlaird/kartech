#!/usr/bin/python
# Do not forget to set:
# export PYTHONPATH=$PYTHONPATH:../src/ 
# if it is required

import os
import hashlib
import unittest
import logging
import subprocess
import threading
import time

import actuator

class CANActuatorTests(unittest.TestCase):
    """
    Actuator test cases
    """

    @classmethod
    def setUpClass(cls):
        cls.can_dev = "vcan0"
        print("START" )

    @classmethod
    def tearDownClass(cls):
        print("DONE")

    def setUp(self):
        self.act = actuator.Actuator(self.can_dev)

    def tearDown(self):
        pass

    def testRcvBus(self):

        self.assertIsNotNone(self.act)

        self.assertFalse(self.act.IsRcvBus())

        self.act.StartReceivingBus(5)
        self.assertTrue(self.act.IsRcvBus())

        self.act.StopReceivingBus()
        self.assertFalse(self.act.IsRcvBus())


    def testSndBus(self):
        self.assertIsNotNone(self.act)

        self.assertFalse(self.act.IsSndBus())

        self.act.StartSendingBus(5)
        self.assertTrue(self.act.IsSndBus())

        self.act.StopSendingBus()
        self.assertFalse(self.act.IsSndBus())


    def testReceiver(self):

        class DataReceiver(actuator.DataReceiver):
            def OnFrameRecieved(self, frame):
                return True # continue receiving

            def OnFrameTimeout(self, error):
                return False

            def OnFrameError(self, error):
                return False

        def startRecv(act):
            rcv = DataReceiver()
            act.RunReceiver(rcv, 5)

        self.assertIsNotNone(self.act)

        self.assertFalse(self.act.IsRcvWorking())

        rcv = threading.Thread(target = startRecv, args=[self.act])
        rcv.start()
        
        time.sleep(1)
        self.assertTrue(self.act.IsRcvWorking())

        rcv.join()

        self.assertFalse(self.act.IsRcvWorking())
        

if __name__ == '__main__':
    logLevel = int(os.environ.get('LOG_LEVEL', logging.INFO))

    testVerbosity = int(os.environ.get('TEST_VERBOSITY', 2))

    logging.basicConfig(filename='tests.log',
                        level=logLevel,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%m-%d %H:%M')
    unittest.main(verbosity=testVerbosity)
