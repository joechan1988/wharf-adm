import unittest
import common
from common import *
from deploy import *


# class TestCommon(unittest.TestCase):
#     def test_get_idle_port(self):
#         port = common.get_idle_port("192.168.1.199")
#         print port
#
#
# def suite():
#     suite = unittest.TestSuite()
#     suite.addTest(TestCommon("test_get_idle_port"))
#     return suite
#
#
# if __name__ == "__main__":
#     unittest.main(defaultTest="suite")


class TestCommon(object):
    @staticmethod
    def test_get_idle_port():
        port = common.get_idle_port("192.168.1.199")
        print port


class TestDeploy(object):
    @staticmethod
    def test_deploy_etcd_cluster():
        advertise_address = "192.168.1.199"
        deploy_etcd_metadata()
        init_etcd_metadata(advertise_address)


def main():
    # TestCommon.test()
    TestDeploy.test_deploy_etcd_cluster()


if __name__ == "__main__":
    main()
