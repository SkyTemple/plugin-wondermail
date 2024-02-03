from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from gi.repository import Gtk

from skytemple_plugin_wondermail.util import data_dir

if TYPE_CHECKING:
    from skytemple_plugin_wondermail.module import WonderMailPluginModule


logger = logging.getLogger(__name__)


@Gtk.Template(filename=os.path.join(data_dir(), "widget", "wonder_mail.ui"))
class StWonderMailPluginView(Gtk.Box):
    __gtype_name__ = "StWonderMailPluginView"

    module: WonderMailPluginModule

    # tree_spawn_list = cast(Gtk.TreeView, Gtk.Template.Child())

    def __init__(self, module: WonderMailPluginModule, _item_data):
        super().__init__()
        self.module = module
