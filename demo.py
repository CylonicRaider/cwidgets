#!/usr/bin/env python3

"""
cwidgets demo script, as taken from the module docstring.
"""

import sys, curses

from cwidgets import *

def demo(window):
    # Create the root of the widget hierarchy.
    root = WidgetRoot(window)
    # Make the display less monochrome.
    root.styler = ClassStyler(do_colors=True)
    root.styler.add_style(Widget, background=('white', 'blue'),
                          default=('black', 'white'))
    root.styler.add_style(Focusable, default=('red', 'white'),
                          highlight=('black', 'red'), focus=('white', 'red'))
    root.styler.add_style(EntryBox, default=('white', 'black'),
                          focus=('black', 'white'))
    # Wrap the UI in a Viewport to avoid crashes at small resolutions.
    vp = root.add(Viewport())
    # Push the UI together to avoid spreading everyting over the screen.
    cont = vp.add(AlignContainer())
    # The user-visible "window"; with a border and the bottom line pushed
    # inside by one line height.
    win = cont.add(MarginContainer(border=True, insets=(0, 0, 1, 0)))
    # Decoratively enclose the title
    title_wrapper = win.add(TeeContainer(), slot=MarginContainer.POS_TOP)
    # Add the title
    title = title_wrapper.add(Label('cwidgets demo'))
    # Add the content. This could also be a nested Viewport containing
    # a more complex UI.
    # When text is typed into the entry box, it will increase smoothly (along
    # with the remaining UI) until it's 70 columns or 20 rows (because of the
    # multiline setting, it can have multiple lines) large, then, it will not
    # grow further (along the corresponding axis), and scroll instead.
    content = win.add(EntryBox('Lorem ipsum dolor sit amet', multiline=True,
                               cmaxsize=(70, 20)))
    # Bind a vertical scrollbar to the content
    sbv = win.add(content.bind(Scrollbar(Scrollbar.DIR_VERTICAL)),
                  slot=MarginContainer.POS_RIGHT)
    # The bottom contains a line of buttons stacked below a scrollbar.
    bottom = win.add(VerticalContainer(), slot=MarginContainer.POS_BOTTOM)
    # Add the horizontal scrollbar.
    sbh = bottom.add(content.bind(Scrollbar(Scrollbar.DIR_HORIZONTAL)))
    # The buttons are laid out horizontally.
    buttons = bottom.add(HorizontalContainer())
    # A bare Widget as "glue" to fill the space. An AlignContainer would
    # have been possible as well.
    buttons.add(Widget(), weight=1)
    # The first button
    buttons.add(Button('OK', sys.exit))
    # A little spacer between the buttons
    buttons.add(Widget(cminsize=(1, 1)))
    # The second button
    buttons.add(Button('Cancel', lambda: sys.exit(1)))
    # Another glue
    buttons.add(Widget(), weight=1)
    # Run it.
    root.main()

def main():
    init()
    curses.wrapper(demo)

if __name__ == '__main__': main()
