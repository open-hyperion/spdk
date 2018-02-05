#!/usr/bin/env python
import io
import sys
import random
import signal
import subprocess
import pprint
import socket

from errno import ESRCH
from os import kill, path, unlink, path, listdir, remove
from rpc_commands_lib import Commands_Rpc
from time import sleep
from uuid import uuid4


def test_counter():
    '''
    :return: the number of tests
    '''
    return 24


def header(num):
    test_name = {
        1: 'construct_lvs_positive',
        50: 'construct_logical_volume_positive',
        51: 'construct_multi_logical_volumes_positive',
        52: 'construct_lvol_bdev_using_name_positive',
        53: 'construct_lvol_bdev_duplicate_names_positive',
        100: 'construct_logical_volume_nonexistent_lvs_uuid',
        101: 'construct_lvol_bdev_on_full_lvol_store',
        102: 'construct_lvol_bdev_name_twice',
        150: 'resize_lvol_bdev_positive',
        200: 'resize_logical_volume_nonexistent_logical_volume',
        201: 'resize_logical_volume_with_size_out_of_range',
        250: 'destroy_lvol_store_positive',
        251: 'destroy_lvol_store_use_name_positive',
        252: 'destroy_lvol_store_with_lvol_bdev_positive',
        253: 'destroy_multi_logical_volumes_positive',
        254: 'destroy_after_resize_lvol_bdev_positive',
        255: 'delete_lvol_store_persistent_positive',
        300: 'destroy_lvol_store_nonexistent_lvs_uuid',
        301: 'delete_lvol_store_underlying_bdev',
        350: 'nested_destroy_logical_volume_negative',
        400: 'nested_construct_logical_volume_positive',
        450: 'construct_lvs_nonexistent_bdev',
        451: 'construct_lvs_on_bdev_twice',
        452: 'construct_lvs_name_twice',
        500: 'nested_construct_lvol_bdev_on_full_lvol_store',
        550: 'delete_bdev_positive',
        600: 'construct_lvol_store_with_cluster_size_max',
        601: 'construct_lvol_store_with_cluster_size_min',
        650: 'tasting_positive',
        651: 'tasting_lvol_store_positive',
        700: 'SIGTERM',
    }
    print("========================================================")
    print("Test Case {num}: Start".format(num=num))
    print("Test Name: {name}".format(name=test_name[num]))
    print("========================================================")

def footer(num):
    print("Test Case {num}: END\n".format(num=num))
    print("========================================================")

class TestCases(object):

    def __init__(self, rpc_py, total_size, block_size, cluster_size, base_dir_path, app_path):
        self.c = Commands_Rpc(rpc_py)
        self.total_size = total_size
        self.block_size = block_size
        self.cluster_size = cluster_size
        self.path = base_dir_path
        self.app_path = app_path
        self.lvs_name = "lvs_test"
        self.lbd_name = "lbd_test"
        self.vhost_config_path = path.join(path.dirname(sys.argv[0]), 'vhost.conf')

    def _gen_lvs_uudi(self):
        return str(uuid4())

    def _gen_lvb_uudi(self):
        return "_".join([str(uuid4()), str(random.randrange(9999999999))])

    def _stop_vhost(self, pid_path):
        with io.open(pid_path, 'r') as vhost_pid:
            pid = int(vhost_pid.readline())
            if pid:
                try:
                    kill(pid, signal.SIGTERM)
                    for count in range(30):
                        sleep(1)
                        kill(pid, 0)
                except OSError, err:
                    if err.errno == ESRCH:
                        pass
                    else:
                        return 1
                else:
                    return 1
            else:
                return 1
        return 0

    def _start_vhost(self, vhost_path, config_path, pid_path):
        subprocess.call("{app} -c {config} -f "
                        "{pid} &".format(app=vhost_path,
                                         config=config_path,
                                         pid=pid_path), shell=True)
        for timeo in range(10):
            if timeo == 9:
                print("ERROR: Timeout on waiting for app start")
                return 1
            if not path.exists(pid_path):
                print("Info: Waiting for PID file...")
                sleep(1)
                continue
            else:
                break

        # Wait for RPC to open
        sock = socket.socket(socket.AF_UNIX)
        for timeo in range(30):
            if timeo == 29:
                print("ERROR: Timeout on waiting for RPC start")
                return 1
            try:
                sock.connect("/var/tmp/spdk.sock")
                break
            except socket.error as e:
                print("Info: Waiting for RPC Unix socket...")
                sleep(1)
                continue
            else:
                sock.close()
                break

        with io.open(pid_path, 'r') as vhost_pid:
            pid = int(vhost_pid.readline())
            if not pid:
                return 1
        return 0

    def _find_traddress_for_nvme(self, nvme_name):
        with open(self.vhost_config_path) as file:
            for line in file:
                if nvme_name in line and "TransportID" in line:
                    for word in line.split(" "):
                        if word.startswith("traddr"):
                            return word.split(":", 1)[1].replace("\"", "")

        print("INFO: Traddr not found for Nvme {nvme}".format(nvme=nvme_name))
        return -1

    # positive tests
    def test_case1(self):
        header(1)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        self.c.destroy_lvol_store(uuid_store)
        self.c.delete_bdev(base_name)
        if self.c.check_get_lvol_stores("", "", "") == 1:
            fail_count += 1
        footer(1)
        return fail_count

    def test_case50(self):
        header(50)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                               self.lbd_name,
                                               self.total_size - 1)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev,
                                                     self.total_size - 1)
        self.c.delete_bdev(uuid_bdev)
        self.c.destroy_lvol_store(uuid_store)
        self.c.delete_bdev(base_name)
        footer(50)
        return fail_count

    def test_case51(self):
        header(51)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        size = ((self.total_size - 1) / 4)

        for j in range(2):
            uuid_bdevs = []
            for i in range(4):
                uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                                       self.lbd_name + str(i),
                                                       size)
                uuid_bdevs.append(uuid_bdev)
                fail_count += self.c.check_get_bdevs_methods(uuid_bdev, size)

            for uuid_bdev in uuid_bdevs:
                self.c.delete_bdev(uuid_bdev)

        self.c.destroy_lvol_store(uuid_store)
        self.c.delete_bdev(base_name)
        footer(51)
        return fail_count

    def test_case52(self):
        header(52)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)

        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)

        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)

        uuid_bdev = self.c.construct_lvol_bdev(self.lvs_name,
                                               self.lbd_name,
                                               self.total_size - 1)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev,
                                                     self.total_size - 1)

        fail_count += self.c.delete_bdev(uuid_bdev)
        fail_count += self.c.destroy_lvol_store(uuid_store)
        fail_count += self.c.delete_bdev(base_name)
        footer(52)
        return fail_count

    def test_case53(self):
        header(53)
        base_name_1 = self.c.construct_malloc_bdev(self.total_size,
                                                   self.block_size)
        base_name_2 = self.c.construct_malloc_bdev(self.total_size,
                                                   self.block_size)

        uuid_store_1 = self.c.construct_lvol_store(base_name_1,
                                                   self.lvs_name + "1",
                                                   self.cluster_size)
        uuid_store_2 = self.c.construct_lvol_store(base_name_2,
                                                   self.lvs_name + "2",
                                                   self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name_1, uuid_store_1,
                                                  self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name_2, uuid_store_2,
                                                  self.cluster_size)

        uuid_bdev_1 = self.c.construct_lvol_bdev(uuid_store_1,
                                                 self.lbd_name,
                                                 self.total_size - 1)
        uuid_bdev_2 = self.c.construct_lvol_bdev(uuid_store_2,
                                                 self.lbd_name,
                                                 self.total_size - 1)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev_1, self.total_size - 1)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev_2, self.total_size - 1)

        fail_count += self.c.delete_bdev(uuid_bdev_1)
        fail_count += self.c.delete_bdev(uuid_bdev_2)
        fail_count += self.c.destroy_lvol_store(uuid_store_1)
        fail_count += self.c.destroy_lvol_store(uuid_store_2)
        fail_count += self.c.delete_bdev(base_name_1)
        fail_count += self.c.delete_bdev(base_name_2)
        footer(53)
        return fail_count

    def test_case100(self):
        header(100)
        fail_count = 0
        if self.c.construct_lvol_bdev(self._gen_lvs_uudi(),
                                      self.lbd_name,
                                      32) == 0:
            fail_count += 1
        footer(100)
        return fail_count

    def test_case101(self):
        header(101)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                               self.lbd_name,
                                               self.total_size - 1)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev,
                                                     self.total_size - 1)
        if self.c.construct_lvol_bdev(uuid_store,
                                      self.lbd_name + "_1",
                                      self.total_size - 1) == 0:
            fail_count += 1

        self.c.delete_bdev(uuid_bdev)
        self.c.destroy_lvol_store(uuid_store)
        self.c.delete_bdev(base_name)
        footer(101)
        return fail_count

    def test_case102(self):
        header(102)
        size = (self.total_size / 2) - 1
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                               self.lbd_name,
                                               size)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev,
                                                     size)
        if self.c.construct_lvol_bdev(uuid_store,
                                      self.lbd_name,
                                      size) == 0:
            fail_count += 1

        self.c.delete_bdev(uuid_bdev)
        self.c.destroy_lvol_store(uuid_store)
        self.c.delete_bdev(base_name)
        footer(102)
        return fail_count

    def test_case150(self):
        header(150)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        # size is equal to one quarter of size malloc bdev
        uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                               self.lbd_name,
                                               self.total_size / 4)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev,
                                                     self.total_size / 4)
        # size is equal to half  of size malloc bdev
        self.c.resize_lvol_bdev(uuid_bdev, self.total_size / 2)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev,
                                                     self.total_size / 2)
        # size is smaller by 1 MB
        self.c.resize_lvol_bdev(uuid_bdev, self.total_size - 1)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev,
                                                     self.total_size - 1)
        # size is equal 0 MiB
        self.c.resize_lvol_bdev(uuid_bdev, 0)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev, 0)

        self.c.delete_bdev(uuid_bdev)
        self.c.destroy_lvol_store(uuid_store)
        self.c.delete_bdev(base_name)
        footer(150)
        return fail_count

    def test_case200(self):
        header(200)
        fail_count = 0
        if self.c.resize_lvol_bdev(self._gen_lvb_uudi(), 16) == 0:
            fail_count += 1
        footer(200)
        return fail_count

    def test_case201(self):
        header(201)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                               self.lbd_name,
                                               self.total_size - 1)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev,
                                                     self.total_size - 1)
        if self.c.resize_lvol_bdev(uuid_bdev, self.total_size + 1) == 0:
            fail_count += 1

        self.c.delete_bdev(uuid_bdev)
        self.c.destroy_lvol_store(uuid_store)
        self.c.delete_bdev(base_name)
        footer(201)
        return fail_count

    def test_case250(self):
        header(250)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        self.c.destroy_lvol_store(uuid_store)
        if self.c.check_get_lvol_stores("", "", "") == 1:
            fail_count += 1
        self.c.delete_bdev(base_name)
        footer(250)
        return fail_count

    def test_case251(self):
        header(251)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        fail_count += self.c.destroy_lvol_store(self.lvs_name)
        if self.c.check_get_lvol_stores("", "", "") == 1:
            fail_count += 1
        fail_count += self.c.delete_bdev(base_name)
        footer(251)
        return fail_count

    def test_case252(self):
        header(252)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                               self.lbd_name,
                                               self.total_size - 1)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev,
                                                     self.total_size - 1)
        if self.c.destroy_lvol_store(uuid_store) != 0:
            fail_count += 1

        if self.c.check_get_lvol_stores("", "", "") == 1:
            fail_count += 1
        self.c.delete_bdev(base_name)
        footer(252)
        return fail_count

    def test_case253(self):
        header(253)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        size = ((self.total_size - 1) / 4)

        for i in range(4):
            uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                                   self.lbd_name + str(i),
                                                   size)
            fail_count += self.c.check_get_bdevs_methods(uuid_bdev, size)

        self.c.destroy_lvol_store(uuid_store)
        if self.c.check_get_lvol_stores("", "", "") == 1:
            fail_count += 1
        self.c.delete_bdev(base_name)
        footer(253)
        return fail_count

    def test_case254(self):
        header(254)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        size = ((self.total_size - 1) / 4)
        uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                               self.lbd_name,
                                               size)
        fail_count += self.c.check_get_bdevs_methods(uuid_bdev,
                                                     size)

        # TODO: Improve resize_lvol_bdev tests to verify if bdev was actually
        # correctly resized
        fail_count += self.c.resize_lvol_bdev(uuid_bdev, size + 1)
        fail_count += self.c.resize_lvol_bdev(uuid_bdev, size * 2)
        fail_count += self.c.resize_lvol_bdev(uuid_bdev, size * 3)
        fail_count += self.c.resize_lvol_bdev(uuid_bdev, (size * 4) - 1)
        fail_count += self.c.resize_lvol_bdev(uuid_bdev, 0)

        self.c.destroy_lvol_store(uuid_store)
        if self.c.check_get_lvol_stores("", "", "") == 1:
            fail_count += 1
        self.c.delete_bdev(base_name)
        footer(254)
        return fail_count

    def test_case255(self):
        header(255)
        base_path = path.dirname(sys.argv[0])
        base_name = "Nvme0n1"
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        if self.c.destroy_lvol_store(self.lvs_name) != 0:
            fail_count += 1
        traddr = self._find_traddress_for_nvme("Nvme0")
        if traddr != -1:
            self.c.delete_bdev(base_name)
            self.c.construct_nvme_bdev("Nvme0", "PCIe", traddr)
            # wait 1 second to allow time for lvolstore tasting
            sleep(1)
        else:
            fail_count += 1
        ret_value = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                 self.cluster_size)
        if ret_value == 0:
            fail_count += 1
        footer(255)
        return fail_count

    def test_case300(self):
        header(300)
        fail_count = 0
        if self.c.destroy_lvol_store(self._gen_lvs_uudi()) == 0:
            fail_count += 1
        footer(300)
        return fail_count

    def test_case301(self):
        header(301)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)

        if self.c.delete_bdev(base_name) != 0:
            fail_count += 1

        if self.c.destroy_lvol_store(uuid_store) == 0:
            fail_count += 1

        footer(301)
        return fail_count

    def test_case350(self):
        print("Test of this feature not yet implemented.")
        pass
        return 0

    def test_case400(self):
        print("Test of this feature not yet implemented.")
        pass
        return 0

    # negative tests
    def test_case450(self):
        header(450)
        fail_count = 0
        bad_bdev_id = random.randrange(999999999)
        if self.c.construct_lvol_store(bad_bdev_id,
                                       self.lvs_name,
                                       self.cluster_size) == 0:
            fail_count += 1
        footer(450)
        return fail_count

    def test_case451(self):
        header(451)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        if self.c.construct_lvol_store(base_name,
                                       self.lvs_name,
                                       self.cluster_size) == 0:
            fail_count += 1
        self.c.destroy_lvol_store(uuid_store)
        self.c.delete_bdev(base_name)
        footer(451)
        return fail_count

    def test_case452(self):
        header(452)
        fail_count = 0
        base_name_1 = self.c.construct_malloc_bdev(self.total_size,
                                                   self.block_size)
        base_name_2 = self.c.construct_malloc_bdev(self.total_size,
                                                   self.block_size)
        uuid_store_1 = self.c.construct_lvol_store(base_name_1,
                                                   self.lvs_name,
                                                   self.cluster_size)
        fail_count += self.c.check_get_lvol_stores(base_name_1,
                                                   uuid_store_1,
                                                   self.cluster_size)
        if self.c.construct_lvol_store(base_name_2,
                                       self.lvs_name,
                                       self.cluster_size) == 0:
            fail_count += 1

        fail_count += self.c.destroy_lvol_store(uuid_store_1)
        fail_count += self.c.delete_bdev(base_name_1)
        fail_count += self.c.delete_bdev(base_name_2)

        footer(452)
        return fail_count

    def test_case500(self):
        print("Test of this feature not yet implemented.")
        pass
        return 0

    def test_case550(self):
        header(550)
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        self.c.delete_bdev(base_name)
        if self.c.check_get_lvol_stores("", "", "") == 1:
            fail_count += 1
        footer(550)
        return fail_count

    def test_case600(self):
        header(600)
        fail_count = 0
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        lvol_uuid = self.c.construct_lvol_store(base_name,
                                                self.lvs_name,
                                                (self.total_size * 1024 * 1024) + 1) == 0
        if self.c.check_get_lvol_stores(base_name, lvol_uuid) == 0:
            fail_count += 1
        fail_count += self.c.delete_bdev(base_name)
        footer(600)
        return fail_count

    def test_case601(self):
        header(601)
        fail_count = 0
        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        lvol_uuid = self.c.construct_lvol_store(base_name, self.lvs_name, 8191)
        if self.c.check_get_lvol_stores(base_name, lvol_uuid) == 0:
            fail_count += 1
        fail_count += self.c.delete_bdev(base_name)
        footer(601)
        return fail_count

    def test_case650(self):
        header(650)
        fail_count = 0
        uuid_bdevs = []
        base_name = "Nvme0n1"

        base_path = path.dirname(sys.argv[0])
        vhost_path = path.join(self.app_path, 'vhost')
        config_path = path.join(base_path, 'vhost.conf')
        pid_path = path.join(base_path, 'vhost.pid')

        # Create initial configuration on running vhost instance
        # create lvol store, create 5 bdevs
        # save info of all lvs and lvol bdevs
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count += self.c.check_get_lvol_stores(base_name,
                                                   uuid_store,
                                                   self.cluster_size)

        # size = approx 10% of total NVMe disk size
        _ = self.c.get_lvol_stores()[0]
        size = int(_["free_clusters"] / 10)

        for i in range(5):
            uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                                   self.lbd_name + str(i),
                                                   size)
            uuid_bdevs.append(uuid_bdev)
            fail_count += self.c.check_get_bdevs_methods(uuid_bdev, size)

        old_bdevs = sorted(self.c.get_lvol_bdevs(), key=lambda x: x["name"])
        old_stores = self.c.get_lvol_stores()

        # Shut down vhost instance and restart with new instance
        fail_count += self._stop_vhost(pid_path)
        remove(pid_path)
        if self._start_vhost(vhost_path, config_path, pid_path) != 0:
            fail_count += 1
            footer(650)
            return fail_count

        # Check if configuration was properly loaded after tasting
        # get all info all lvs and lvol bdevs, compare with previous info
        new_bdevs = sorted(self.c.get_lvol_bdevs(), key=lambda x: x["name"])
        new_stores = self.c.get_lvol_stores()

        if old_stores != new_stores:
            fail_count += 1
            print("ERROR: old and loaded lvol store is not the same")
            print("DIFF:")
            print(old_stores)
            print(new_stores)

        if len(old_bdevs) != len(new_bdevs):
            fail_count += 1
            print("ERROR: old and loaded lvol bdev list count is not equal")

        for o, n in zip(old_bdevs, new_bdevs):
            if o != n:
                fail_count += 1
                print("ERROR: old and loaded lvol bdev is not the same")
                print("DIFF:")
                pprint.pprint([o, n])

        if fail_count != 0:
            footer(650)
            return fail_count

        # Try modifying loaded configuration
        # Add some lvol bdevs to existing lvol store then
        # remove all lvol configuration and re-create it again
        for i in range(5, 10):
            uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                                   self.lbd_name + str(i),
                                                   size)
            uuid_bdevs.append(uuid_bdev)
            fail_count += self.c.check_get_bdevs_methods(uuid_bdev, size)

        for uuid_bdev in uuid_bdevs:
            self.c.delete_bdev(uuid_bdev)

        if self.c.destroy_lvol_store(uuid_store) != 0:
            fail_count += 1

        uuid_bdevs = []

        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count += self.c.check_get_lvol_stores(base_name,
                                                   uuid_store,
                                                   self.cluster_size)

        for i in range(10):
            uuid_bdev = self.c.construct_lvol_bdev(uuid_store,
                                                   self.lbd_name + str(i),
                                                   size)
            uuid_bdevs.append(uuid_bdev)
            fail_count += self.c.check_get_bdevs_methods(uuid_bdev, size)

        if self.c.destroy_lvol_store(uuid_store) != 0:
            fail_count += 1

        footer(650)
        return fail_count

    def test_case651(self):
        header(651)
        base_name = "Nvme0n1"
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)
        traddr = self._find_traddress_for_nvme("Nvme0")
        if traddr != -1:
            self.c.delete_bdev(base_name)
            self.c.construct_nvme_bdev("Nvme0", "PCIe", traddr)
            # wait 1 second to allow time for lvolstore tasting
            sleep(1)
        else:
            fail_count += 1
        if self.c.check_get_lvol_stores(base_name, uuid_store,
                                        self.cluster_size) != 0:
            fail_count += 1
        if self.c.destroy_lvol_store(uuid_store) != 0:
            fail_count += 1
        footer(651)
        return fail_count

    def test_case700(self):
        header(700)
        pid_path = path.join(self.path, 'vhost.pid')

        base_name = self.c.construct_malloc_bdev(self.total_size,
                                                 self.block_size)
        uuid_store = self.c.construct_lvol_store(base_name,
                                                 self.lvs_name,
                                                 self.cluster_size)
        fail_count = self.c.check_get_lvol_stores(base_name, uuid_store,
                                                  self.cluster_size)

        fail_count += self._stop_vhost(pid_path)
        footer(700)
        return fail_count
