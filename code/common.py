import subprocess
import os


class FileNotFoundException(Exception):
    def __init__(self, text=None):
        if text is not None:
            super(FileNotFoundException, self).__init__()
            self.message = "File not found: {text}".format(text=text)


def check_filepath(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundException(filepath)


def shell_exec(cmd, shell=True):
    try:
        ret = subprocess.check_output(cmd, shell=shell)
    except subprocess.CalledProcessError as e:
        return e

    return ret


def get_host_ip():
    pass


def cmd_help(text):
    """
    Help decorator for CLI commands.

    :param text:
    :return:
    """

    def _decorator(func):
        if not hasattr(func, 'help'):
            func.help = text
        return func

    return _decorator


def arg(*args, **kwargs):
    """
    Arguments decorator for CLI args.

    :param args:
    :param kwargs:
    :return:
    """

    def _decorator(func):
        if not hasattr(func, 'arguments'):
            func.arguments = []
        if (args, kwargs) not in func.arguments:
            func.arguments.insert(0, (args, kwargs))

        return func

    return _decorator
