#!/usr/bin/python

from common import *
from deploy import *
from auth import *
import os
import argparse


class Subcommands(object):
    def __init__(self):
        pass

    @arg('--advertise-address', default=None, help="Node advertise ip address.Override env if this is set")
    @cmd_help('Initialize wharf cluster')
    def init(self, args, **cluster_data):

        if not args.advertise_address:
            try:
                os.environ["ADVERTISE_ADDRESS"]
            except Exception:
                print("Please specify the advertise address before initializing")
                return
        else:
            os.environ["ADVERTISE_ADDRESS"] = args.advertise_address

        deploy_etcd_metadata()
        deploy_etcd_cluster()
        deploy_apiserver()
        deploy_cmanager()
        deploy_scheduler()

    @arg('--filepath', default="/etc/wharf/auth/")
    @cmd_help("Generate authentication files")
    def generate_auth(self, args):
        print("Generating authentication files.Caution!Cluster should be re-init after this")
        generate_auth(args.filepath)

    # @common.arg('--config', default=constants.cluster_cfg_path, help="Default config file path")
    def test(self, args):
        print(args.config)


def _get_funcs(obj):
    result = []
    for i in dir(obj):
        if callable(getattr(obj, i)) and not i.startswith('_'):
            result.append((i, getattr(obj, i)))
    return result


def main():
    # Arguments
    top_parser = argparse.ArgumentParser()
    top_parser.add_argument('--test', dest='test_unit', type=str, default='')

    # Subcommands
    subparsers = top_parser.add_subparsers(help='Commands')
    subcommands_obj = Subcommands()
    subcommands = _get_funcs(subcommands_obj)

    for (func_name, func) in subcommands:
        try:
            func_help = getattr(func, 'help')
        except AttributeError as e:
            func_help = ""

        func_parser = subparsers.add_parser(func_name.replace("_", "-"), help=func_help)
        func_parser.set_defaults(func=func)

        for args, kwargs in getattr(func, 'arguments', []):
            func_parser.add_argument(*args, **kwargs)

    top_args = top_parser.parse_args()

    top_args.func(top_args)


if __name__ == "__main__":
    main()
