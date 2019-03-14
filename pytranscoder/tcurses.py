import curses
import random
import time
from queue import Queue, Empty
from threading import Thread

stdscr = None


def _main(scr):
    global stdscr

    ui = CursesUI.get()
    stdscr = scr
    ui.start()
    #ui.join()


class StatusItem(object):
    host: str
    name: str
    runtime: int
    done: int
    line: int

    def __init__(self, host: str, name: str, runtime: int, done: int = 0):
        self.host = host
        self.name = name
        self.runtime = runtime
        self.done = done


_work: [StatusItem] = []


class CursesUI(Thread):
    __me: object = None
    events: Queue
    width: int
    height: int

    def __init__(self):
        super().__init__(name='curses', daemon=True, group=None)
        self.events = Queue()

    @staticmethod
    def get():
        if CursesUI.__me is None:
            CursesUI.__me = CursesUI()
        return CursesUI.__me

    def draw_items(self):

        # first get the width of the longest name, for table spacing
        max_name = 0
        for item in _work:
            max_name = max(len(item.name), max_name)

        if max_name + 20 >= self.width:
            # can't fit on screen, just go blank and let user resize
            return
        max_name = max(max_name, self.width - 30)

        line = 2
        for item in _work:
            if item.host is not None:
                stdscr.addstr(line, 1, item.host)
            if 0 < item.done < item.runtime:
                pct = (item.done / item.runtime)
                pct_whole = int(pct * 100)
                name = item.name.ljust(max_name)
                done_of_name = int(pct * len(name))
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(line, 15, name[0:done_of_name])
                stdscr.attroff(curses.A_REVERSE)
                stdscr.addstr(line, 15 + done_of_name, name[done_of_name:])
                stdscr.addstr(line, 15 + max_name + 1, f'[{pct_whole:2}%]')
            elif item.done >= item.runtime:
                stdscr.attron(curses.A_DIM)
                stdscr.addstr(line, 15, item.name)
                stdscr.addstr(line, 15 + max_name + 1, '[done]')
                stdscr.attroff(curses.A_DIM)
            else:
                stdscr.addstr(line, 15, item.name)
            line += 1
            if line >= self.height - 2:
                break
        if line >= self.height - 2:
            # more lines to show that we have screen space, so remove completed items
            for i in range(len(_work)):
                if _work[i].done >= _work[i].runtime:
                    del _work[i]


    def run(self):

        stdscr.erase()
        stdscr.refresh()
        stdscr.nodelay(True)

        # Start colors in curses
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_WHITE)

        while True:

            while True:
                try:
                    status = self.events.get_nowait()
                    if status is not None:
                        for item in _work:
                            if status.name == item.name:
                                item.host = status.host
                                item.done = status.done
                                break
                        self.events.task_done()
                except Empty as e:
                    break

            stdscr.erase()
            self.height, self.width = stdscr.getmaxyx()

            statusbarstr = "Press 'q' to exit |"

            # Render status bar
            stdscr.attron(curses.color_pair(3))
            stdscr.addstr(self.height-1, 0, statusbarstr)
            stdscr.addstr(self.height-1, len(statusbarstr), " " * (self.width - len(statusbarstr) - 1))
            stdscr.attroff(curses.color_pair(3))

            self.draw_items()
            stdscr.refresh()
            time.sleep(1)
            ch = stdscr.getch()
            if ch != curses.ERR and ch == ord('q'):
                break
        stdscr.clear()
        stdscr.refresh()
        curses.endwin()
        _work.clear()


def start_curses(work: [StatusItem]):
    global _work

    _work = work
    curses.wrapper(_main)


if __name__ == '__main__':

    children = [
        {'host': None, 'name': '/some/long/directory/name/test file 1', 'runtime': 120, 'done': 0},
        {'host': None, 'name': '/some/long/directory/name/test file 2', 'runtime': 57, 'done': 0},
        {'host': None, 'name': '/some/long/directory/name/test file 3', 'runtime': 165, 'done': 0},
    ]
    work = list()
    for child in children:
        work.append(StatusItem(**child))

    start_curses(work)

    while True:
        time.sleep(1)
        i = random.randint(1, len(children)) - 1
        child = children[i]
        if child['done'] >= child['runtime']:
            del children[i]
            continue
        if child['host'] is None:
            child['host'] = f'host_{i}'
        child['done'] += random.randint(1, 10)
        CursesUI.get().events.put(StatusItem(**child))
