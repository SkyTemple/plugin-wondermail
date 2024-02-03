import os


# The "open request" type we use. See "handle_request". This can be anything,
# but you should prefix it with the package name or the module's entry point name
# or something, so there are no conflicts.
REQUEST_OPEN_TYPE = "skytemple_example_plugin:Monster"


def data_dir():
    return os.path.join(os.path.dirname(__file__), "data")
