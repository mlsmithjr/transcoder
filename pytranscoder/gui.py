from typing import Dict

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk


class FileManager:

    def __init__(self, builder):
        self.builder = builder
        self.appwindow = builder.get_object("appwindow")
        self.file_list: Gtk.TreeView = builder.get_object("tree_files")
        self.file_list.append_column(Gtk.TreeViewColumn("File", Gtk.CellRendererText(), text=0))
        self.file_list.append_column(Gtk.TreeViewColumn("Profile", Gtk.CellRendererText(), text=1))
        self.file_list.append_column(Gtk.TreeViewColumn("Size", Gtk.CellRendererText(), text=2))

        self.store = Gtk.ListStore(str, str, int)
        self.file_list.set_model(self.store)
        self.setup_filelist_samples()

    def handlers(self) -> Dict:
        return {
            "onAddFileButtonPressed": self.on_add_button,
            "onRemoveFileButtonPressed": self.on_remove_button,
        }

    def setup_filelist_samples(self):
        for i in range(1, 100):
            self.store.append([f"file {i}", "hevc", i * 1000])

    def on_add_button(self, button):
        fcd = Gtk.FileChooserDialog(title="Open...",
                                         parent=self.appwindow,
                                         action=Gtk.FileChooserAction.OPEN,
                                         buttons=(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
        response = fcd.run()
        if response == Gtk.ResponseType.OK:
            print('add clicked')
        fcd.destroy()


    def on_remove_button(self, button):
        print('del clicked')


class AppWindow:

    def __init__(self):
        builder = Gtk.Builder()
        builder.add_from_file("../appwindow.glade")
        self.appwindow = builder.get_object("appwindow")

        self.files_manager = FileManager(builder)

        handlers = {
            "onDestroy": self.on_destroy,
            **self.files_manager.handlers(),
        }
        builder.connect_signals(handlers)

    def show_all(self):
        self.appwindow.show_all()

    def on_destroy(self, *args):
        Gtk.main_quit()


def start_gui():

    win = AppWindow()
    win.show_all()
    Gtk.main()


if __name__ == '__main__':
    start_gui()
