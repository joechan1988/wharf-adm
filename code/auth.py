#!/usr/bin/python

import json, subprocess, os
from common import *

ca_csr = {
    "CN": "wharf",
    "key": {
        "algo": "rsa",
        "size": 2048
    },
    "names": [
        {
            "C": "CN",
            "ST": "BeiJing",
            "L": "BeiJing",
            "O": "wharf",
            "OU": "System"
        }
    ]
}

ca_config = {
    "signing": {
        "default": {
            "expiry": "87600h"
        },
        "profiles": {
            "wharf": {
                "usages": [
                    "signing",
                    "key encipherment",
                    "server auth",
                    "client auth"
                ],
                "expiry": "87600h"
            }
        }
    }
}

etcd_csr = {
    "CN": "etcd",
    "hosts": [],
    "key": {
        "algo": "rsa",
        "size": 2048
    },
    "names": [
        {
            "C": "CN",
            "ST": "BeiJing",
            "L": "BeiJing",
            "O": "k8s",
            "OU": "System"
        }
    ]
}

kubernetes_csr = {
    "CN": "wharf",
    "hosts": [],
    "key": {
        "algo": "rsa",
        "size": 2048
    },
    "names": [
        {
            "C": "CN",
            "ST": "BeiJing",
            "L": "BeiJing",
            "O": "wharf",
            "OU": "System"
        }
    ]
}


def gen_json_file(dest=None, json_obj=None):
    json_file = open(dest, 'wb')
    json_file.write(json.dumps(json_obj))
    json_file.close()


def gen_ca_cert(path):
    gen_json_file(path + "ca-config.json", ca_config)
    gen_json_file(path + "ca-csr.json", ca_csr)
    print("---Generating CA Cert Files---")
    gen_cmd = 'cfssl gencert -initca ' + path + '/ca-csr.json | cfssljson -bare ca'
    mv_cmd = 'mv -f ca.csr ca-key.pem ca.pem ' + path
    shell_exec(gen_cmd)
    shell_exec(mv_cmd)


def gen_etcd_cert(path):
    cert_hosts = [
        "127.0.0.1",
        os.environ["ADVERTISE_ADDRESS"]
    ]

    etcd_csr["hosts"] = cert_hosts

    gen_json_file(path + "etcd-csr.json", etcd_csr)
    print("Generating etcd Cert Files...")

    gen_cmd = 'cfssl gencert -ca=' + path + 'ca.pem \
                    -ca-key=' + path + '/ca-key.pem \
                    -config=' + path + '/ca-config.json \
                    -profile=wharf ' + path + 'etcd-csr.json' + ' \
                        | cfssljson -bare etcd'
    mv_cmd = 'mv -f etcd.csr etcd-key.pem etcd.pem ' + path
    shell_exec(gen_cmd)
    shell_exec(mv_cmd)


def gen_api_cert(path):
    # TODO: Load Balancer address
    cert_hosts = [
        "127.0.0.1",
        "10.254.0.1",
        os.environ["ADVERTISE_ADDRESS"],
        "kubernetes",
        "kubernetes.default",
        "kubernetes.default.svc",
        "kubernetes.default.svc.cluster",
        "kubernetes.default.svc.cluster.local"]

    kubernetes_csr["hosts"] = cert_hosts
    gen_json_file(path + "kubernetes-csr.json", kubernetes_csr)
    print("Generating kubernetes Cert Files...")
    gen_cmd = 'cfssl gencert -ca=' + path + 'ca.pem \
                    -ca-key=' + path + '/ca-key.pem \
                    -config=' + path + '/ca-config.json \
                    -profile=wharf ' + path + 'kubernetes-csr.json' + ' \
                        | cfssljson -bare kubernetes'
    mv_cmd = 'mv -f kubernetes.csr kubernetes-key.pem kubernetes.pem ' + path
    shell_exec(gen_cmd)
    shell_exec(mv_cmd)


def generate_auth(auth_path):
    # auth_path = "/etc/wharf/auth/"
    gen_ca_cert(auth_path)
    gen_etcd_cert(auth_path)
    gen_api_cert(auth_path)
