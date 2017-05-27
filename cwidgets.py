#!/usr/bin/env python3
# -*- coding: ascii -*-

"""
A simple curses-based TUI library for Python

cwidgets implements an array of classes that can be composed into an
interactive text user interface. The UI can be interacted with using
standard key bindings (Tab, Space, Return, ...), and adapts to different
screen resolutions (if written accordingly).

A typical use (demonstrated on a dialog window would look like this:
>>> # window is a curses window obtained from, for example, initscr().
... root = WidgetRoot(window)
>>> # Wrap the UI in a Viewport to avoid crashes at small resolutions.
... vp = root.add(Viewport())
>>> # Push the UI together to avoid spreading everyting over the screen.
... cont = vp.add(AlignContainer())
>>> # The user-visible "window"; with a border and the bottom line pushed
... # inside by one line height.
... win = cont.add(MarginContainer(border=True, insets=(0, 0, 1, 0)))
>>> # Decoratively enclose the title
... title_wrapper = win.add(TeeContainer(), slot=MarginContainer.POS_TOP)
>>> # Add the title
... title = title_wrapper.add(Label('cwidgets demo'))
>>> # Add the content. This could also be a nested Viewport containing
... # a more complex UI.
... content = win.add(Label('Lorem ipsum dolor sit amet'))
>>> # Bind a vertical scrollbar to the content
... sbv = win.add(content.bind(Scrollbar(Scrollbar.DIR_VERTICAL)),
...               slot=MarginContainer.POS_RIGHT)
>>> # The bottom contains a line of buttons stacked below a scrollbar.
... bottom = win.add(VerticalContainer(), slot=MarginContainer.POS_BOTTOM)
>>> # Add the horizontal scrollbar.
... sbh = bottom.add(content.bind(Scrollbar(Scrollbar.DIR_HORIZONTAL)))
>>> # The buttons are laid out horizontally.
... buttons = bottom.add(HorizontalContainer())
>>> # A bare Widget as "glue" to fill the space. An AlignContainer would
... # have been possible as well.
... buttons.add(Widget(), weight=1)
>>> # The first button
... buttons.add(Button('OK', sys.exit))
>>> # A little spacer between the buttons
... buttons.add(Widget(cminsize=(1, 1)))
>>> # The second button
... buttons.add(Button('Cancel', lambda: sys.exit(1)))
>>> # Another glue
... buttons.add(Widget(), weight=1)
>>> # Run it.
... root.main()
"""

import sys as _sys
import time as _time
import curses as _curses
import codecs as _codecs
import locale as _locale

_ENCODING = None
_KEY_RETURN = ord('\n')
_KEY_TAB = ord('\t')

_LOG = []

if _sys.version_info[0] <= 2:
    _bchr = chr
    _unicode = unicode
else:
    _bchr = lambda x: bytes([x])
    _unicode = str

def zbound(v, m):
    "Return x such that 0 <= x <= m"
    return max(0, min(v, m))
def addpos(p1, p2):
    "Return the sum of the 2-vectors p1 and p2"
    return (p1[0] + p2[0], p1[1] + p2[1])
def subpos(p1, p2):
    "Return the difference of the 2-vectors p1 and p2"
    return (p1[0] - p2[0], p1[1] - p2[1])
def minpos(p1, p2):
    "Return the component-by-component minimum of p1 and p2"
    return (min(p1[0], p2[0]), min(p1[1], p2[1]))
def maxpos(p1, p2):
    "Return the component-by-component maximum of p1 and p2"
    return (max(p1[0], p2[0]), max(p1[1], p2[1]))
def shiftrect(r, p):
    "Return r with the position increased by p"
    return (r[0] + p[0], r[1] + p[1], r[2], r[3])
def unshiftrect(r, p):
    "Return r with the position decreased by p"
    return (r[0] - p[0], r[1] - p[1], r[2], r[3])
def boundrect(r, b):
    "Return r shifted and possibly scaled such that it is entirely in b"
    if r[0] < b[0]: r = (b[0], r[1], r[2] - b[0] + r[0], r[3])
    if r[1] < b[1]: r = (r[0], b[1], r[2], r[3] - b[1] + r[1])
    return (r[0], r[1], zbound(r[2], b[2]), zbound(r[3], b[3]))

def linear_distrib(full, amnt):
    "Return a list of amnt approximately equal integers summing up to full"
    if full == 0:
        return [0] * amnt
    elif amnt == 0:
        return []
    base, rem = divmod(full, amnt)
    if rem == 0:
        return [base] * amnt
    crem, ret = rem, []
    for i in range(amnt):
        inc, crem = divmod(crem + rem, amnt)
        ret.append(base + inc)
    assert sum(ret) == full, 'linear_distrib() failed'
    assert crem == rem, 'linear_distrib() failed'
    return ret
def weight_distrib(full, weights):
    """
    Return a list of integers summing up to full weighted by weights

    The items are approximately proportional to the corresponding weights.
    """
    if full == 0:
        return [0] * len(weights)
    elif not weights:
        return []
    sw = float(sum(weights))
    fr = [full * w / sw for w in weights]
    r, rem = [], 0.0
    for i in fr:
        i, lrem = divmod(i, 1.0)
        inc, rem = divmod(rem + lrem, 1.0)
        r.append(int(i + inc))
    # Rounding errors.
    if 0 < rem <= 1 and sum(r) + 1 == full:
        r[-1] += 1
    assert sum(r) == full, 'weight_distrib() failed'
    return r

def parse_pair(v, default=(None, None)):
    """
    Expand a scalar or 2-tuple into a 2-tuple

    If any element of that is None, the corresponding value from default
    is substituted.
    """
    try:
        v = tuple(v)
    except TypeError:
        v = (v, v)
    return (default[0] if v[0] is None else v[0],
            default[1] if v[1] is None else v[1])
def parse_quad(v, default=(None, None, None, None)):
    """
    Expand a scalar or tuple into a 4-tuple

    If v is a tuple with less than four elements, it is expanded similarly to
    a CSS margin value. Elements of the result that are None are substituted
    by corresponding values from default.
    """
    try:
        v = tuple(v)
    except TypeError:
        v = (v, v, v, v)
    if len(v) == 0:
        raise ValueError('Too few values to parse_quad()!')
    elif len(v) == 1:
        v *= 4
    elif len(v) == 2:
        v *= 2
    elif len(v) == 3:
        return (v[0], v[1], v[2], v[1])
    elif len(v) == 4:
        pass
    else:
        raise ValueError('Too many values to parse_quad()!')
    return (default[0] if v[0] is None else v[0],
            default[1] if v[1] is None else v[1],
            default[2] if v[2] is None else v[2],
            default[3] if v[3] is None else v[3])

def inflate(size, margin, mul=1):
    """
    Increase size (a size or rect) by mul multiples of margin

    margin's items are interpreted as those of a CSS margin. If size is a
    4-tuple, its "sides" are moved outwards by the corresponding items of
    margin; if it is a 2-tuple, it is treated as if it were a rect with a
    nondescript position that is discarded again and the given size.
    """
    if len(size) == 2:
        return (margin[3] * mul + size[0] + margin[1] * mul,
                margin[0] * mul + size[1] + margin[2] * mul)
    elif len(size) == 4:
        return (size[0] - margin[3] * mul,
                size[1] - margin[0] * mul,
                margin[3] * mul + size[2] + margin[1] * mul,
                margin[0] * mul + size[3] + margin[2] * mul)
    else:
        raise TypeError('Must be size or rect')
def deflate(rect, margin, mul=1):
    """
    Decrease size (a size or rect) by mul multiples of margin

    This is equivalent to inflate(rect, margin, -mul).
    """
    return inflate(rect, margin, -mul)

class Constant:
    "A named constant with a meaningful string representation"
    def __init__(self, __name__, **__dict__):
        self.__dict__ = __dict__
        self.__name__ = __name__
    def __repr__(self):
        return '<%s>' % (self.__name__,)
    def __str__(self):
        return str(self.__name__)

class Event(Constant):
    "A singleton for differentiating special events from keystrokes"
FocusEvent = Event('FocusEvent')

class NumericConstant(Constant, float):
    "A constant with a floating-point value"
    def __new__(cls, __value__, __name__, **__dict__):
        return float.__new__(cls, __value__)
    def __init__(self, __value__, __name__, **__dict__):
        Constant.__init__(self, __name__, **__dict__)

class Alignment(NumericConstant):
    "A numerical alignment value"
ALIGN_TOP = Alignment(0.0, 'ALIGN_TOP')
ALIGN_LEFT = Alignment(0.0, 'ALIGN_LEFT')
ALIGN_CENTER = Alignment(0.5, 'ALIGN_CENTER')
ALIGN_RIGHT = Alignment(1.0, 'ALIGN_RIGHT')
ALIGN_BOTTOM = Alignment(1.0, 'ALIGN_BOTTOM')

class Scaling(NumericConstant):
    "A numerical scaling value"
SCALE_COMPRESS = Scaling(0.0, 'SCALE_COMPRESS')
SCALE_STRETCH = Scaling(1.0, 'SCALE_STRETCH')

class Scrollable:
    """
    A mixin class denoting widgets whose contents can be scrolled

    Scrollable implements the management of the scrolling position and the
    binding of scroll bars; the widget class remains responsible for
    rendering the widget. The scroll bars are laid out and rendered
    independently from the scrolling widget.

    The usage/calling direction provided in the documentation serve as
    suggestions and do not prohibit use not mentioned by them (although care
    should be exercised in that case).

    Attributes:
    scrollpos   : The current scrolling position. Modified by the widget
                  class and/or Scrollable, and interpreted by both.
    maxscrollpos: The maximal scrolling position (with the lower bound
                  impliticly being zero). Set by the widget class and
                  consumed by Scrollable.
    contentsize : The size of the content being scrolled. Used in
                  conjunction with maxscrollpos to determine the size of the
                  scroll bar handles. Set by the widget class and read by
                  Scrollable.
    focusable   : Whether the widget can scroll itself appropriately. If
                  true, the scrollbars cannot be focused and serve merely as
                  visual hints of the current scrolling position. If false,
                  the scrollbars can be focused and scroll the widget "on
                  their own". Set by the widget class and interpreted by
                  Scrollable.
    scrollbars  : The currently bound scroll bars. Modified and used by
                  Scrollable.
    """
    def __init__(self):
        """
        Initializer
        """
        self.scrollpos = [0, 0]
        self.maxscrollpos = (0, 0)
        self.contentsize = (0, 0)
        self.focusable = True
        self.scrollbars = {'vert': None, 'horiz': None}
    def bind(self, scrollbar):
        """
        Bind the given scrollbar to self and return it

        If another scrollbar with the same direction is already bound, it is
        unbound first.

        Called externally when creating the UI.
        """
        if scrollbar.dir.vert:
            osb = self.scrollbars['vert']
            if osb is scrollbar: return scrollbar
            if osb: self.unbind(osb)
            self.scrollbars['vert'] = scrollbar
            scrollbar.bind(self)
        else:
            osb = self.scrollbars['horiz']
            if osb is scrollbar: return scrollbar
            if osb: self.unbind(osb)
            self.scrollbars['horiz'] = scrollbar
            scrollbar.bind(self)
        return scrollbar
    def unbind(self, scrollbar):
        """
        Undo the binding of the given scrollbar to self and return it

        Called by Scrollable as part of the binding procedure.
        """
        if self.scrollbars['vert'] is scrollbar:
            self.scrollbars['vert'] = None
            scrollbar.unbind(self)
        elif self.scrollbars['horiz'] is scrollbar:
            self.scrollbars['horiz'] = None
            scrollbar.unbind(self)
        return scrollbar
    def scroll(self, newpos, rel=False):
        """
        Scroll by/to the given coordinates

        If rel is true, the scrolling position is incremented by newpos;
        otherwise, it is set to that. Returns whether the scrolling position
        actually changed (and, hence, on_scroll() has been called).

        Called by the widget class, Scrollable, and/or externally. The widget
        class should override on_scroll() instead of this method.
        """
        if rel: newpos = addpos(self.scrollpos, newpos)
        newpos = maxpos((0, 0), minpos(newpos, self.maxscrollpos))
        oldpos = tuple(self.scrollpos)
        update = (newpos[0] != oldpos[0] or newpos[1] != oldpos[1])
        self.scrollpos[:] = newpos
        if update: self.on_scroll(oldpos)
        return update
    def on_scroll(self, oldpos):
        """
        Event handler for scrolling

        oldpos is the old scrolling position; the current one can be
        determined by inspecting the scrollpos attribute of self.

        Called by Scrollable from scroll(); handled by the widget class and
        Scrollable.
        """
        if self.scrollbars['vert']:
            self.scrollbars['vert'].update()
        if self.scrollbars['horiz']:
            self.scrollbars['horiz'].update()
    def on_highlight(self, active):
        """
        Event handler for highlighting a scrollbar

        If two scroll bars are bound to a widget and one of them is focused,
        the other one is "highlighted" in a subordinate manner as well.

        Called by the scroll bars and handled by Scrollable.
        """
        if self.scrollbars['vert']:
            self.scrollbars['vert'].highlight(active)
        if self.scrollbars['horiz']:
            self.scrollbars['horiz'].highlight(active)
    def scroll_event(self, event):
        """
        Handle the given event as a scrolling action, if applicable

        The semantics of this method are identical to those of the general
        event().
        As a guideline, this method *should* be called after other ways of
        consume the event by children and/or this widget have been
        considered.

        Called (potentially) by the widget, *and* bound scroll bars (when
        those are focused); handled by Scrollable (and the widget if it
        wants to capture events from the scroll bars).
        """
        if event[0] == _curses.KEY_UP:
            return self.scroll((0, -1), True)
        elif event[0] == _curses.KEY_DOWN:
            return self.scroll((0, 1), True)
        elif event[0] == _curses.KEY_LEFT:
            return self.scroll((-1, 0), True)
        elif event[0] == _curses.KEY_RIGHT:
            return self.scroll((1, 0), True)
        return False

class WidgetRoot(object):
    """
    A container for a widget hierarchy directly interfacing curses

    This class implements the methods expected by a widget to be present on
    its parent (and some others, as applicable) as well as an event loop
    translating curses events into cwidgets ones.

    A typical use pattern would be:
    >>> root = WidgetRoot(window)
    >>> root.add(widget)
    >>> root.main()

    Attributes are:
    window       : The curses window to access.
    widget       : The (only) widget to host.
    valid_display: Whether any part of self needs to be redrawn.
    valid_layout : Whether the layout of self needs to be remade.
    """
    def __init__(self, window):
        """
        Initializer

        window is the curses window to draw to and to receive events from.
        """
        self.window = window
        self.widget = None
        self.valid_display = False
        self.valid_layout = False
        self._cursorpos = None
        self._init_decoder()
    def _init_decoder(self):
        "Initialize the input decoder"
        if _ENCODING:
            f = _codecs.getincrementaldecoder(_ENCODING)
            self._decoder = f(errors='replace')
        else:
            self._decoder = None
    def make(self):
        """
        Perform layout

        This lets the widget (if any) make itself.
        The widget is forcefully fitted to the size of the window; if that is
        below the widget's minimum size, trying to draw it can (and will)
        crash. To avoid this scenario, wrap the widget into a Viewport if
        necessary.
        """
        if self.widget is not None:
            hw = self.window.getmaxyx()
            self.widget.pos = (0, 0)
            self.widget.size = (hw[1], hw[0])
            self.widget.make()
        self.valid_layout = True
        self.invalidate()
    def redraw(self):
        """
        Redraw the widget and adjust the cursor position as necessary
        """
        if self.widget is not None:
            self.widget.draw(self.window)
            if self._cursorpos is None:
                _curses.curs_set(0)
                self.window.refresh()
            else:
                self.window.noutrefresh()
                _curses.curs_set(1)
                _curses.setsyx(self._cursorpos[1], self._cursorpos[0])
                _curses.doupdate()
        self.valid_display = True
    def grab_input(self, rect, pos=None, child=None, full=False):
        """
        Bring focus to the specified area

        Of the arguments, only pos is interpreted, and used to set the cursor
        position (or to hide the cursor) on the next redraw.
        """
        # TODO: Respect full.
        self._cursorpos = pos
    def event(self, event):
        """
        Handle an input event

        Returns whether the event was consumed.
        Tab and back tab key presses are translated into calls of focus(); if
        those do not succeed or the key was not a TAB, the event is passed on
        to the widget.
        """
        if event[0] == _KEY_TAB:
            if self.focus(): return True
        elif event[0] == _curses.KEY_BTAB:
            if self.focus(True): return True
        if self.widget is not None:
            return self.widget.event(event)
        return False
    def focus(self, rev=False):
        """
        Cycle focus between widgets

        rev specifies the direction of the focus movement. Returns whether
        the focus switch succeeded.
        If no widget is focused, the first (or last) one is focused. If the
        last (or first) widget is reached, focus wraps around.
        """
        if self.widget is None:
            return False
        # When a widget is fully traversed, it de-focuses itself and returns
        # false; since there is nothing outside us, we "wrap around" and ask
        # the widget to focus itself.
        if not self.widget.focus(rev) and not self.widget.focus(rev):
            return False
        return True
    def invalidate(self, rec=False, child=None):
        """
        Mark the widget root as "damaged", i.e. in need of a redraw

        If rec is true, the entire widget tree is marked recursively
        regardless of topology and state (see Viewport for a notable
        exception), otherwise, subtrees are marked selectively. child
        indicates which widget the redraw request originates from.
        """
        if rec:
            self.valid_display = False
            self.widget.invalidate(rec)
            return
        if not self.valid_display: return
        self.valid_display = False
        self.widget.invalidate()
    def invalidate_layout(self):
        """
        Mark the widget root as in need of a layout refresh

        The action is (unless valid_layout is already false) propagated to
        the nested widget.
        """
        if not self.valid_layout: return
        self.valid_layout = False
        self.widget.invalidate_layout()
    def add(self, widget):
        """
        Add the given widget to the root

        Since a WidgetRoot can only manage one descendant, this previous
        child (if any) is removed.
        """
        if widget is self.widget: return widget
        widget.delete()
        self.widget = widget
        widget.parent = self
        return widget
    def remove(self, widget):
        """
        Remove the given widget from self
        """
        if widget is self.widget:
            self.widget = None
            widget.parent = None
    def _process_input(self, ch):
        "Handle an input character from curses"
        if ch == _curses.KEY_RESIZE:
            self.invalidate_layout()
        elif ch == _curses.KEY_MOUSE:
            self.event((ch, _curses.getmouse()))
        elif isinstance(ch, int) and ch >= 32 and ch < 256:
            if self._decoder:
                res = self._decoder.decode(_bchr(ch))
                if res: self.event((res,))
            else:
                self.event((ch,))
        else:
            self.event((ch,))
    def main(self):
        """
        Main loop

        Revalidates and redraws the widget as necessary, and processes
        events, all that ad infinitum (or until an exception is thrown).
        """
        while 1:
            if not self.valid_layout:
                self.make()
            if not self.valid_display:
                self.redraw()
            last_update = _time.time()
            ch = self.window.getch()
            self._process_input(ch)
            self.window.nodelay(1)
            while _time.time() - last_update < 0.1:
                ch = self.window.getch()
                if ch == -1: break
                self._process_input(ch)
            self.window.nodelay(0)

class Widget(object):
    """
    Base class for all UI widgets

    This provides default implementations for all methods.

    Attributes:
    cminsize     : The (custom) minimal size below which the widget must not
                   shrink. Can be used for creating rigid spacers of custom
                   sizes.
    parent       : The parent of this widget in the hierarchy.
    pos          : The position of the widget in the layout.
    size         : The size of the widget in the layout.
    valid_display: Whether the widget has *not* to be redrawn. Implies
                   valid_self (so that a false valid_self implies a false
                   valid_display).
    valid_self   : Whether the widget itself (i.e. excluding children) needs
                   *not* to be redrawn.
    valid_layout : Whether the widget's layout has *not* to be remade.
    grabbing     : If the widget is currently in charge of the cursor, a
                   rectangle indicating the area to display.
    grabbing_full: Whether the widget is grabbing (in the proper sense) all
                   input.
    cursor_pos   : When grabbing is true, the (absolute) position of the
                   cursor as set by the widget.

    See also:
    Container: for specific notes on widgets "containing" other ones.
    """
    def __init__(self, **kwds):
        """
        Initializer

        Accepts configuration via keyword arguments:
        minsize: The minsize attribute.
        """
        self.cminsize = kwds.get('cminsize', (0, 0))
        self.parent = None
        self.pos = None
        self.size = None
        self.valid_display = False
        self.valid_self = False
        self.valid_layout = False
        self.grabbing = None
        self.grabbing_full = False
        self.cursor_pos = None
        self._minsize = None
        self._prefsize = None
    @property
    def minsize(self):
        "The minimal layout size of this widget"
        if self._minsize is None: self._minsize = self.getminsize()
        return maxpos(self._minsize, self.cminsize)
    @property
    def prefsize(self):
        "The preferred layout size of this widget"
        if self._prefsize is None: self._prefsize = self.getprefsize()
        return maxpos(self._prefsize, self.cminsize)
    @property
    def rect(self):
        "The position concatenated with the size"
        return (self.pos[0], self.pos[1], self.size[0], self.size[1])
    def getminsize(self):
        """
        Compute the minimal layout size of this widget

        The default implementation is to return the preferred size.
        """
        return self.prefsize
    def getprefsize(self):
        """
        Compute the preferred layout size of this widget

        The default implementation merely returns the value of the minsize
        attribute.
        """
        return self.cminsize
    def make(self):
        """
        Recompute the layout of this widget

        The default implementation reestablishes the input cursor position
        (for example, after terminal resizes), removes "needs re-layout"
        mark, and marks the widget for redrawing.
        """
        self.valid_layout = True
        if self.grabbing:
            gr = list(self.grabbing)
            if gr[2] > self.size[0]: gr[2] = self.size[0]
            if gr[3] > self.size[1]: gr[3] = self.size[1]
            rect = shiftrect(gr, self.pos)
            if self.cursor_pos is None:
                pos = None
            else:
                pos = addpos(self.cursor_pos, self.pos)
            self.grab_input(rect, pos, None, self.grabbing_full)
        self.invalidate()
    def draw(self, win):
        """
        Redraw this widget and its children

        win is the curses window to draw to.
        The default implementation does nothing beyond marking the widget as
        (fully) as redrawn  and calling draw_self() if necessary. Containers
        may override this to draw children, but any drawing tasks directly
        related to this widget should go into draw_self().
        Well-behaved implementations should return immediately if they are
        still valid.
        """
        if self.valid_display: return
        self.valid_display = True
        if not self.valid_self:
            self.valid_self = True
            self.draw_self(win)
    def draw_self(self, win):
        """
        Redraw this widget only

        win is the window to draw to.
        The default implementation does nothing.
        """
        pass
    def grab_input(self, rect, pos=None, child=None, full=False):
        """
        Render this widget in charge of input

        rect is the rectangle that should be visible with respect to that
        (for example, the active input area); pos is where to place the
        cursor (or None to hide it); child is the child widget the request
        originated from (if any); full is whether *all* input should be
        grabbed.
        The default implementation stores the specified values in the
        corresponding instance attributes and propagates the request to
        the parent.
        """
        if rect is None or child is not None:
            self.grabbing = None
            self.grabbing_full = False
            self.cursor_pos = None
        else:
            self.grabbing = unshiftrect(rect, self.pos)
            self.grabbing_full = full
            if pos is None:
                self.cursor_pos = None
            else:
                self.cursor_pos = subpos(pos, self.pos)
        self.parent.grab_input(rect, pos, self, full)
    def event(self, event):
        """
        Handle an input event

        Events are tuples, with the first item denoting the event "type" and
        subsequent elements containing additional information. The first
        element of the event can be:
        a string   : The user pressed the key denoted by the string.
        an integer : The user pressed the (special) key denoted by the
                     integer; uses curses' means to determine which it is.
                     Can in particular be KEY_MOUSE (if the mouse is
                     enabled; the second element of the event contains the
                     result of curses.getmouse()), but not KEY_RESIZE (that
                     is handled by WidgetRoot).
        a singleton: If the event does not correspond to either of above,
                     an instance of the Event class can be used for further
                     event types, notably FocusEvent (the second item of the
                     event then contains whether the widget is now focused or
                     not).
        The method returns whether the event has been "consumed" by the
        widget; some containers handle events on their own if the children do
        not, so set this carefully.

        The default implementation reset the grabbing state if focus is lost.
        """
        if event[0] == FocusEvent and not event[1]:
            self.grabbing = None
            self.grabbing_full = False
            self.cursor_pos = None
        return False
    def focus(self, rev=False):
        """
        Perform focus traversal

        rev tells whether the traversal should be "forward" (rev is false) or
        "backward" (rev is true). Returns whether the traversal has stopped
        "inside" the widget and should not continue at parents.
        Widgets that are not focusable should return False unconditionally;
        widgets that only have two focus states should toggle their focus
        status and return whether they are focused now; widgets that have
        multiple focusable parts should advance focus amongst those and
        return correspondingly as well.

        The default implementation assumes an unfocusable widget and behaves
        accordingly (i.e. returns False).
        """
        return False
    def invalidate(self, rec=False, child=None):
        """
        Mark this widget as in need of a redraw

        rec is whether the entire widget tree should be invalidated; child
        is the child the invalidation request originated from (if any).
        A widget can be invalidated in multiple ways:
        - Recursive invalidation: If rec is true, the entire widget tree
          below and including self is invalidated unconditionally. child
          should be None. valid_display and valid_self (if child is None as
          specified above) are cleared.
        - Pinpoint invalidation: If rec is false and child is None, the
          invalidation is aimed at exactly this widget. Both valid_display
          and valid_self are reset, and the request is propagated to the
          parent.
        - Pass-through invalidation: If rec is false and child is not None,
          a child was invalidated and is propagating the request to its
          parent. valid_display is reset (valid_self not), and the request
          is propagated further.
        If a widget (such as a container with multiple children) optimizes
        its rendering, it should flush state related to that on the Python
        condition (rec or child is None).
        """
        ovd = self.valid_display
        self.valid_display = False
        if child is None: self.valid_self = False
        if ovd and not rec: self.parent.invalidate(child=self)
    def invalidate_layout(self):
        """
        Mark this widget as in need of a re-layout

        The standard implementation sets the valid_layout attribute to False
        and propagates the request to the parent.
        """
        ov, self.valid_layout = self.valid_layout, False
        if ov: self.parent.invalidate_layout()
        self._minsize = None
        self._prefsize = None
    def _delete_layout(self):
        "Remove the widget from its container"
        if self.parent is not None:
            self.parent.remove(self)
    def delete(self):
        """
        Remove this widget from the hierarchy

        The standard implementation removes the widget from its container.
        """
        self._delete_layout()

class Container(Widget):
    """
    A widget "containing" others

    A container is responsible for the management, layout, and rendering of
    its children. Children may expect to be laid out at (unconditionally) no
    less than their minimum size, and preferably at their preferred size.
    The minimum and preferred sizes of the container should be chosen such
    that this is possible.

    This class provides default implementations for all methods expected on
    "container" widgets. In particular, the children are "stacked" on top of
    each other, assuming the position and size of the container and being
    rendered (and tab-traversed) in the order of insertion. Specific
    subclasses of Container are available with more sophisticated layout
    algorithms.

    Attributes:
    children: The list of children held by this widget. May be read
              externally, but should only be modified using the corresponding
              methods.
    """
    def __init__(self, **kwds):
        """
        Initializer

        See Widget.__init__() for more detail.
        """
        Widget.__init__(self, **kwds)
        self.children = []
        self._focused = None
        self._oldrect = None
    def getminsize(self):
        """
        Calculate the absolute minimum size of the container

        This method should be overridden as part of the concrete class'
        layout algorithm.
        """
        wh = (0, 0)
        for i in self.children: wh = maxpos(wh, i.minsize)
        return wh
    def getprefsize(self):
        """
        Calculate the preferred size of the container

        This method should be overridden as part of the concrete class'
        layout algorithm.
        """
        wh = (0, 0)
        for i in self.children: wh = maxpos(wh, i.prefsize)
        return wh
    def make(self):
        """
        Perform layout

        The standard implementation aborts if the container is (already)
        valid; otherwise, if the container's position or size have changed,
        it invalidates all children, calls the relayout() method, and
        invokes all children's make() methods. In any case, the container
        is valid after the procedure.
        """
        if self.valid_layout: return
        if self._oldrect != self.rect:
            for i in self.children:
                i.invalidate_layout()
            self.relayout()
            for i in self.children:
                i.make()
            self._oldrect = self.rect
        Widget.make(self)
    def relayout(self):
        """
        Perform the actual layout of children

        This method should be overridden as part of the concrete class'
        layout algorithm.
        """
        for i in self.children:
            i.pos = self.pos
            i.size = minpos(self.size, i.prefsize)
    def draw(self, win):
        """
        Draw this container to the given window

        The standard implementation aborts if already valid, draws all
        children recursively, and marks the container as valid.
        Subclasses should hook draw_self() (which is implicitly called
        if necessary) to display own UI elements.
        """
        if self.valid_display: return
        Widget.draw(self, win)
        for i in self.children:
            i.draw(win)
    def event(self, event):
        """
        Process input events directed to this widget

        The standard implementation initiates focus traversal (if this did
        not happen at a higher level in the hierarchy), handles focus
        events, and forwards events to the currently focused child otherwise.
        """
        ret = Widget.event(self, event)
        if event[0] == FocusEvent:
            if not event[1]:
                self._refocus(None)
            return True
        elif event[0] == _KEY_TAB:
            return (self.focus() or ret)
        elif event[0] == _curses.KEY_BTAB:
            return (self.focus(True) or ret)
        elif self._focused is not None:
            return (self._focused.event(event) or ret)
        else:
            return ret
    def focus(self, rev=False):
        """
        Perform focus traversal

        rev indicates whether the traversal should be reversed or no.
        The standard implementation first relays traversal to the focused
        child (if any), then attempts successive children (preceding /
        following it in insertion order) until one is found that takes the
        focus, or reports failure to the caller.
        """
        if not self.children:
            return False
        elif self._focused is not None:
            idx = self.children.index(self._focused)
        elif rev:
            idx = len(self.children) - 1
        else:
            idx = 0
        incr = (-1 if rev else 1)
        while 1:
            ch = self.children[idx]
            if ch.focus(rev):
                self._refocus(ch)
                return True
            idx += incr
            if idx in (-1, len(self.children)): break
        self._refocus(None)
        return False
    def invalidate(self, rec=False, child=None):
        """
        Mark this widget as in need of a redraw

        rec tells whether the invalidation should propagate to all children
        of the container; child tells which (direct) child of the container
        the invalidation originated at.
        The standard implementation actually marks the container itself and
        propagates the event to the children if rec is true.
        Subclasses may need to override this to reset drawing state; see
        Widget.invalidate() for details.
        """
        Widget.invalidate(self, rec, child)
        if rec:
            for i in self.children:
                i.invalidate(rec)
    def invalidate_layout(self):
        """
        Mark this widget as in need of a layout refresh

        The standard implementation actually marks the container as such,
        propagates the request to the parent (if that has not happened yet),
        clears cached values, and propagates the invalidation to all
        children.
        Subclasses may need to hook this to reset cached state.
        """
        Widget.invalidate_layout(self)
        # Force layout recalculation.
        self._oldrect = None
    def _refocus(self, new):
        "Helper method to properly switch focus between two children"
        if new is self._focused: return
        if self._focused is not None:
            self._focused.event((FocusEvent, False))
        self._focused = new
        if self._focused is not None:
            self._focused.event((FocusEvent, True))
    def add(self, widget, **config):
        """
        Add the given widget to the container

        config may contain further detail on the role of the widget in
        this container.
        The default implementation ignores config, removes the widget
        from its previous parent (if any), installs it as a child of
        the container, and invalidates the latter.
        """
        widget._delete_layout()
        self.children.append(widget)
        widget.parent = self
        self.invalidate_layout()
        return widget
    def remove(self, widget):
        """
        Remove the widget from the container

        The standard implementation removes the widget from the container,
        resets the focus if it had previously beed at the widget, and
        invalidates the container.
        The invalidation of layout-related state should be handled at
        invalidate_layout() (unless positive reasons exist to do so here).
        """
        self.children.remove(widget)
        if self._focused is widget:
            self._focused = None
        widget.parent = None
        self.invalidate_layout()
    def clear(self):
        """
        Remove all children from this container

        The standard implementation calls remove() for each child.
        """
        for i in self.children[:]:
            self.remove(i)

class SingleContainer(Container):
    """
    A container holding no more than one child

    Adding a child when one is already present removes the former one.
    """
    def __init__(self, **kwds):
        "Initializer"
        Container.__init__(self, **kwds)
        self._chms = None
        self._chps = None
    def _child_minsize(self, **kwds):
        """
        Get the minimum size of the child, or (0, 0) if none

        This is a helper method aimed at subclasses.
        """
        if self._chms is not None:
            pass
        elif not self.children:
            self._chms = (0, 0)
        else:
            self._chms = self.children[0].minsize
        return self._chms
    def _child_prefsize(self):
        """
        Get the preferred size of the child, or (0, 0) if none

        This is a helper method aimed at subclasses.
        """
        if self._chps is not None:
            pass
        elif not self.children:
            self._chps = (0, 0)
        else:
            self._chps = self.children[0].prefsize
        return self._chps
    def invalidate_layout(self):
        "Signal the need of a relayout"
        Container.invalidate_layout(self)
        self._chms = None
        self._chps = None
    def add(self, widget, **config):
        "Add a child"
        while self.children:
            self.remove(self.children[0])
        return Container.add(self, widget, **config)

class VisibilityContainer(SingleContainer):
    """
    A container that can disappear (partially or fully)

    The container (including the child) can be in one of the three
    visibility states:
    VIS_VISIBLE : Normally visible.
    VIS_HIDDEN  : Not visibile but still taking up space.
    VIS_COLLAPSE: Not visible and not consuming any space.
    """
    class Visibility(Constant):
        "A mode of widget visibility"
    VIS_VISIBLE = Visibility('VIS_VISIBLE')
    VIS_HIDDEN = Visibility('VIS_HIDDEN')
    VIS_COLLAPSE = Visibility('VIS_COLLAPSE')
    def __init__(self, **kwds):
        "Initializer"
        SingleContainer.__init__(self, **kwds)
        self.visibility = kwds.get('visibility', self.VIS_VISIBLE)
    def getminsize(self):
        """
        Obtain the minimum size of this widget

        This implements collapsing behavior. Subclasses should override
        inner_minsize() instead of this.
        """
        if self.visibility == self.VIS_COLLAPSE:
            return (0, 0)
        else:
            return self.inner_minsize()
    def inner_minsize(self):
        """
        Obtain the minimum size of this widget

        This method should be overridden instead of getminsize().
        """
        return SingleContainer.getminsize(self)
    def getprefsize(self):
        """
        Obtain the preferred size of this widget

        This implements collapsing behavior. Subclasses should override
        inner_prefsize() instead of this.
        """
        if self.visibility == self.VIS_COLLAPSE:
            return (0, 0)
        else:
            return self.inner_prefsize()
    def inner_prefsize(self):
        """
        Obtain the preferred size of this widget

        This method should be overridden instead of getminsize().
        """
        return SingleContainer.getprefsize(self)
    def make(self):
        "Perform layout"
        if self.visibility == self.VIS_COLLAPSE: return
        SingleContainer.make(self)
    def draw(self, win):
        """
        Draw this widget to the given window

        The standard implementation skips rendering if the container is not
        VISIBLE, and forwards to the draw_inner() method otherwise.
        """
        if self.visibility != self.VIS_VISIBLE or self.valid_display:
            return
        self.draw_inner(win)
    def draw_inner(self, win):
        """
        Actually draw this widget to the given window

        Overriding the drawing behavior should happen here. The standard
        implementation forwards to the draw() method of SingleContainer.
        """
        SingleContainer.draw(self, win)
    def focus(self, rev=False):
        "Perform focus traversal"
        if self.visibility == self.VIS_COLLAPSE:
            if self._focused is not None:
                self._refocus(None)
            return False
        return SingleContainer.focus(self, rev)

class BoxContainer(VisibilityContainer):
    """
    A VisiblityContainer implementing the CSS box model

    This container puts a margin, border, and padding around its child (in
    addition to being able to change its visibility). The margin and padding
    are four-tuples of top/right/bottom/left spacings to be used around the
    respective edge of the child; shorter tuples (or scalars) are interpreted
    similarly to CSS. Specifying None as one of those makes the corresponding
    inset flexible, i.e. it absorbs any space left along the corresponding
    axis (*both* vertical and horizontal), or half if the opposite inset is
    flexible as well. If both the margin and the padding along a certain axis
    are flexible, the margin takes precedence. In contrast to those, the
    border always has a fixed width, of either zero or one; where it is
    present, it is filled with appropriate box-drawing characters.

    Attributes are:
    margin     : The margin width.
    border     : The border width.
    padding    : The padding width.
    attr_margin: The attribute to fill the margin with.
    ch_margin  : The character used for filling the margin.
    attr_box   : The attribute to use for the border, padding, and as a
                 background for the content.
    ch_box     : The character to fill the background with.
    """
    @classmethod
    def calc_pads_1d(cls, outer, margin, border, padding, size, minsize):
        "Helper method for layout calculations"
        def inset(avl, pad, prefsize, minsize):
            free = avl[1] - prefsize
            if free < 0:
                size = max(avl[1], minsize)
                free = avl[1] - size
            else:
                size = prefsize
            if pad[0] is None and pad[1] is None:
                return (avl[0] + free // 2, size)
            elif pad[0] is None:
                return (avl[0] + free, size)
            elif pad[1] is None:
                return (avl[0], size)
            else:
                return (avl[0] + pad[0], avl[1] - pad[0] - pad[1])
        zin = lambda x: 0 if x is None else x
        prefsize_bp = (border[0] + zin(padding[0]) + size +
                       zin(padding[1]) + border[1])
        minsize_bp = (border[0] + zin(padding[0]) + minsize +
                      zin(padding[1]) + border[1])
        ret = [inset((0, outer), margin, prefsize_bp, minsize_bp)]
        avl = (ret[0][0] + border[0], ret[0][1] - border[0] - border[1])
        ret.append(inset(avl, padding, size, minsize))
        return ret
    @classmethod
    def calc_pads(cls, outer, margin, border, padding, size, minsize):
        "Helper method for layout calculations"
        pdsx = cls.calc_pads_1d(outer[0], margin[3::-2], border[3::-2],
                                padding[3::-2], size[0], minsize[0])
        pdsy = cls.calc_pads_1d(outer[1], margin[::2], border[::2],
                                padding[::2], size[1], minsize[1])
        return ((pdsx[0][0], pdsy[0][0], pdsx[0][1], pdsy[0][1]),
                (pdsx[1][0], pdsy[1][0], pdsx[1][1], pdsy[1][1]))
    def __init__(self, **kwds):
        "Initializer"
        VisibilityContainer.__init__(self, **kwds)
        self.margin = parse_quad(kwds.get('margin', 0))
        self.border = parse_quad(kwds.get('border', 0))
        self.padding = parse_quad(kwds.get('padding', 0))
        self.attr_margin = kwds.get('attr_margin', None)
        self.attr_box = kwds.get('attr_box', None)
        self.ch_margin = kwds.get('ch_margin', '\0')
        self.ch_box = kwds.get('ch_box', '\0')
        self._box_rect = None
        self._widget_rect = None
    def calc_insets(self):
        "Helper method for layout calculations"
        # Lambda calculus!
        x = lambda d: lambda k: (lambda v: 0 if v is None else v)(d[k])
        m, b, p = x(self.margin), x(self.border), x(self.padding)
        return (m(0) + bool(b(0)) + p(0),
                m(1) + bool(b(1)) + p(1),
                m(2) + bool(b(2)) + p(2),
                m(3) + bool(b(3)) + p(3))
    def inner_minsize(self):
        "Get the minimum size of this widget"
        chms, ins = self._child_minsize(), self.calc_insets()
        return inflate(chms, ins)
    def inner_prefsize(self):
        "Get the preferred size of this widget"
        chps, ins = self._child_prefsize(), self.calc_insets()
        return inflate(chps, ins)
    def relayout(self):
        "Perform the actual layout"
        chps, chms = self._child_prefsize(), self._child_minsize()
        br, wr = self.calc_pads(self.size, self.margin,
            list(map(bool, self.border)), self.padding, chps, chms)
        self._box_rect = shiftrect(br, self.pos)
        self._widget_rect = shiftrect(wr, self.pos)
        if self.children:
            self.children[0].pos = self._widget_rect[:2]
            self.children[0].size = self._widget_rect[2:]
    def draw_self(self, win):
        "Actually draw this widget"
        BoxWidget.draw_box(win, self.pos, self.size, self.attr_margin,
                           self.ch_margin, False)
        BoxWidget.draw_box(win, self._box_rect[:2], self._box_rect[2:],
                           self.attr_box, self.ch_box, self.border)
        VisibilityContainer.draw_self(self, win)
    def invalidate_layout(self):
        "Mark this widget as in need of a layout refresh"
        VisibilityContainer.invalidate_layout(self)
        self._box_rect = None
        self._widget_rect = None

class AlignContainer(VisibilityContainer):
    """
    A VisibilityContainer that allows to align its content in its area

    The child is rendered at its preferred size, with any excesss space
    being distributed in accordance to the align and scale attributes:
    align: A two-tuple of horizontal and vertical alignments for the child.
           The ALIGN_* constants are usually used as mnemonics, but
           intermediate values can be specified as well. The default is
           to center the child.
    scale: A two-tuple of horizontal and vertical scaling modes. The
           default is (SCALE_COMPRESS, SCALE_COMPRESS), i.e. to render the
           child at its preferred size.
    """
    @classmethod
    def calc_wbox_1d(cls, pref, avl, scale, align):
        "Helper method for layout calculations"
        if avl < pref:
            size = avl
        else:
            size = pref + int((avl - pref) * scale)
        return (int((avl - size) * align), size)
    @classmethod
    def calc_wbox(cls, pref, avl, scale, align, pos=(0, 0)):
        "Helper method for layout calculations"
        return shiftrect(sum(zip(
            cls.calc_wbox_1d(pref[0], avl[0], scale[0], align[0]),
            cls.calc_wbox_1d(pref[1], avl[1], scale[1], align[1])
            ), ()), pos)
    def __init__(self, **kwds):
        "Initializer"
        VisibilityContainer.__init__(self, **kwds)
        self.scale = parse_pair(kwds.get('scale', SCALE_COMPRESS))
        self.align = parse_pair(kwds.get('align', ALIGN_CENTER))
        self._pads = (0, 0, 0, 0)
        self._wbox = None
    def inner_minsize(self):
        "Get the minimum size of this widget"
        pms, sp = VisibilityContainer.inner_minsize(self), self._pads
        return (sp[3] + pms[0] + sp[1], sp[0] + pms[1] + sp[2])
    def inner_prefsize(self):
        "Get the preferred size of this widget"
        pps, sp = VisibilityContainer.inner_prefsize(self), self._pads
        return (sp[3] + pps[0] + sp[1], sp[0] + pps[1] + sp[2])
    def relayout(self):
        "Perform a layout refresh"
        sp = self._pads
        if self._wbox is None:
            rchps = self._child_prefsize()
            chps = (sp[3] + rchps[0] + sp[1], sp[0] + rchps[1] + sp[2])
            self._wbox = self.calc_wbox(chps, self.size, self.scale,
                                        self.align, self.pos)
        if self.children:
            wb = self._wbox
            self.children[0].pos = (sp[3] + wb[0], sp[0] + wb[1])
            self.children[0].size = (wb[2] - sp[3] - sp[1],
                                     wb[3] - sp[0] - sp[2])
    def invalidate_layout(self):
        "Mark this widget as in need of a layout refresh"
        VisibilityContainer.invalidate_layout(self)
        self._wbox = None

class TeeContainer(AlignContainer):
    """
    An AlignContainer that draws horizontal "tees" around its content

    This is meant to be used in conjunction with MarginContainer.

    Attributes are:
    tees : A two-tuple of (integral) character codes to be displayed as the
           "tees". Defaults to (curses.ACS_RTEE, curses.ACS_LTEE).
    attrs: A two-tuple of attributes to be used for the tees. Defaults to
           (0, 0).
    """
    def __init__(self, **kwds):
        "Initializer"
        AlignContainer.__init__(self, **kwds)
        self.tees = parse_pair(kwds.get('tees',
            (_curses.ACS_RTEE, _curses.ACS_LTEE)))
        self.attrs = parse_pair(kwds.get('attrs', 0))
        self._pads = (0, 1, 0, 1)
    def draw_self(self, win):
        "Draw this widget to the given window"
        sw = win.derwin(self._wbox[3], self._wbox[2],
                        self._wbox[1], self._wbox[0])
        sw.addch(0, 0, self.tees[0], self.attrs[0])
        sw.insch(self._wbox[3] - 1, self._wbox[2] - 1, self.tees[1],
                 self.attrs[1])
        AlignContainer.draw_inner(self, win)

class Viewport(SingleContainer, Scrollable):
    """
    A container showing only part of its child

    A Viewport renders its child to an offscreen pad and then displays part
    of it in its display area. Thus, the child can be (significantly) larger
    than the viewport itself.

    Attributes are:
    restrict_size: Attempt to adapt the child to the viewport's size as far
                   as possible.
    cmaxsize     : The maximum size of the Viewport.
    default_attr : The attribute to be used as the "default" attribute of the
                   offscreen pad.
    default_ch   : The "default" character of the offscreen pad.
    background   : The background attribute of the offscreen pad.
    background_ch: The background character of the offscreen pad.
    """
    @classmethod
    def calc_shift(cls, offset, maxoffs, size, rect):
        ret = list(offset)
        br = subpos(addpos(rect[:2], rect[2:]), size)
        if ret[0] < br[0]: ret[0] = br[0]
        if ret[1] < br[1]: ret[1] = br[1]
        if ret[0] > rect[0]: ret[0] = rect[0]
        if ret[1] > rect[1]: ret[1] = rect[1]
        ret[:] = (zbound(ret[0], maxoffs[0]), zbound(ret[1], maxoffs[1]))
        return ret
    def __init__(self, **kwds):
        "Initializer"
        SingleContainer.__init__(self, **kwds)
        Scrollable.__init__(self)
        self.restrict_size = kwds.get('restrict_size', True)
        self.cmaxsize = kwds.get('cmaxsize', (None, None))
        self.default_attr = kwds.get('default_attr', None)
        self.default_ch = kwds.get('default_ch', '\0')
        self.background = kwds.get('background', None)
        self.background_ch = kwds.get('background_ch', '\0')
        self.focusable = False
        self.padsize = (0, 0)
        self._pad = None
    def getminsize(self):
        "Obtain the minimum sie of this widget"
        ps, ms = SingleContainer.getminsize(self), self.cmaxsize
        return ((ps[0] if ms[0] is None else min(ps[0], ms[0])),
                (ps[1] if ms[1] is None else min(ps[1], ms[1])))
    def getprefsize(self):
        "Obtain the preferred size of this widget"
        ps, ms = SingleContainer.getprefsize(self), self.cmaxsize
        return ((ps[0] if ms[0] is None else min(ps[0], ms[0])),
                (ps[1] if ms[1] is None else min(ps[1], ms[1])))
    def relayout(self):
        "Perform a layout refresh"
        chps, chms = self._child_prefsize(), self._child_minsize()
        if self.children:
            if self.restrict_size:
                chs = maxpos(minpos(self.size, chps), chms)
            else:
                chs = chps
            self.children[0].pos = (0, 0)
            self.children[0].size = maxpos(self.size, chs)
            self.padsize = maxpos(self.children[0].size, self.size)
            self.maxscrollpos = subpos(self.padsize, self.size)
            self.contentsize = self.children[0].size
        else:
            self.padsize = self.size
            self.maxscrollpos = (0, 0)
            self.contentsize = (0, 0)
        oldpos = tuple(self.scrollpos)
        self.scrollpos[:] = (
            zbound(self.scrollpos[0], self.maxscrollpos[0]),
            zbound(self.scrollpos[1], self.maxscrollpos[1]))
        self.on_scroll(oldpos)
    def draw_self(self, win):
        "Draw this widget to the given window"
        Widget.draw_self(self, win)
        chsz = self.padsize
        if self._pad is None:
            self._pad = _curses.newpad(chsz[1] + 1, chsz[0] + 1)
            if self.default_attr is not None:
                self._pad.bkgd(self.default_ch, self.default_attr)
            pad_changed = True
        else:
            padsz = self._pad.getmaxyx()
            if padsz[1] != chsz[0] + 1 or padsz[0] != chsz[1] + 1:
                self._pad.resize(chsz[1] + 1, chsz[0] + 1)
                pad_changed = True
            else:
                pad_changed = False
        if pad_changed:
            if self.background is not None:
                fill = self._pad.derwin(0, 0)
                fill.bkgd(self.background_ch, self.background)
                fill.clear()
            if self.children:
                self.children[0].invalidate(True)
        if self.children:
            self.children[0].draw(self._pad)
        sp = self.scrollpos
        self._pad.overwrite(win, sp[1], sp[0], self.pos[1], self.pos[0],
                            self.pos[1] + self.size[1] - 1,
                            self.pos[0] + self.size[0] - 1)
    def event(self, event):
        "Handle an event"
        ret = SingleContainer.event(self, event)
        if not ret:
            if self.scroll_event(event):
                self.grab_input(None)
                return True
        return ret
    def grab_input(self, rect, pos=None, child=None, full=False):
        "Make this widget in charge of the focus"
        if rect is not None:
            oldpos = tuple(self.scrollpos)
            new_offset = self.calc_shift(oldpos, self.maxscrollpos,
                                         self.size, rect)
            if pos is not None:
                new_offset = self.calc_shift(new_offset, self.maxscrollpos,
                    self.size, (pos[0], pos[1], 1, 1))
            self.scrollpos[:] = new_offset
            if new_offset[0] != oldpos[0] or new_offset[1] != oldpos[1]:
                self.on_scroll(oldpos)
            effpos = subpos(self.pos, new_offset)
            rect = shiftrect(rect, effpos)
            # Constrain rect to own bounds.
            rect = boundrect(rect, self.rect)
        else:
            effpos = subpos(self.pos, self.scrollpos)
        if pos is not None:
            pos = (zbound(pos[0], self.padsize[0] - 1),
                   zbound(pos[1], self.padsize[1] - 1))
            pos = addpos(effpos, pos)
        SingleContainer.grab_input(self, rect, pos, child, full)
    def invalidate(self, rec=False, child=None):
        "Mark this widget as in need of a redraw"
        # Child is rendered to offscreen pad, and cannot be invalidated
        # by anything that happens to me (invalidated in draw() if
        # necessary).
        Widget.invalidate(self, rec)
    def invalidate_layout(self):
        "Mark this widget as in need of a layout refresh"
        SingleContainer.invalidate_layout(self)
        self._pad = None
    def on_scroll(self, oldpos):
        "Handle a scroll event"
        Scrollable.on_scroll(self, oldpos)
        if tuple(oldpos) != tuple(self.scrollpos):
            self.invalidate()

class StackContainer(Container):
    """
    A container that draws its children on top of other in a defined order

    Every widget is on a numbered "layer", with widgets on the same one
    being drawn in insertion order. The default layer is integer zero, but
    any object that implements ordering comparisons can be used. The children
    are expanded to the size of the container.

    The ordering is achieved by sorting the children list in place; be aware
    of that.
    """
    def __init__(self, **kwds):
        "Initializer"
        Container.__init__(self, **kwds)
        self._layers = {}
    def relayout(self):
        "Perform a layout update"
        ps = self.prefsize
        for w in self.children:
            w.pos = self.pos
            w.size = self.size
    def invalidate(self, rec=False, child=None):
        "Mark this container as in need of a redraw"
        if child in self.children:
            Container.invalidate(self, rec, child)
            idx = self.children.index(child)
            for i in self.children[idx + 1:]:
                i.invalidate(True)
        else:
            Container.invalidate(self, True, child)
    def add(self, widget, **config):
        """
        Add another child to this container

        The "layer" keyword argument can be passed to place the widget on a
        non-default layer (the default being layer 0).
        """
        Container.add(self, widget, **config)
        self._layers[widget] = config.get('layer', 0)
        self.children.sort(key=self._layers.__getitem__)
        return widget
    def remove(self, widget):
        "Remove a widget from this container"
        Container.remove(self, widget)
        del self._layers[widget]
    def set_layer(self, widget, layer):
        """
        Set the layer the given widget should reside on

        The layer argument denotes the new layer for the widget to be on;
        pass 0 (integer zero) for the default.
        """
        self._layers[widget] = layer
        self.children.sort(key=self._layers.__getitem__)

class PlacerContainer(StackContainer):
    """
    A container that places its children at user defined-locations

    The position for each widget must be specified during the add() call;
    an optional size can be specified; the child's preferred size is used
    otherwise.
    """
    def __init__(self, **kwds):
        "Initializer"
        StackContainer.__init__(self, **kwds)
        self._positions = {}
        self._sizes = {}
    def getminsize(self):
        "Get the minimum size of this container"
        # Everything is rigid anyway.
        return self.prefsize
    def getprefsize(self):
        "Get the preferred size of this container"
        wh = (0, 0)
        for i in self.children:
            s = self._sizes.get(i)
            if not s: s = i.prefsize
            wh = maxpos(wh, addpos(self._positions[i], s))
        return wh
    def relayout(self):
        "Refresh the layout of this container"
        for w in self.children:
            w.pos = addpos(self.pos, self._positions[w])
            s = self._sizes[w]
            if s is None:
                w.size = w.prefsize
            else:
                w.size = s
    def add(self, widget, **config):
        """
        Add a child to the container

        config can contain the following keyword arguments:
        pos : The position where to put the child. REQUIRED.
        size: The (optional) size to override the child's preferred size.
        """
        self._positions[widget] = config['pos']
        self._sizes[widget] = config.get('size')
        return StackContainer.add(self, widget, **config)
    def remove(self, widget):
        "Remove the given child from this container"
        StackContainer.remove(self, widget)
        del self._positions[widget]
        del self._sizes[widget]

class MarginContainer(Container):
    """
    A container placing its children in nine "regions"

    The regions form a 3x3 grid and should be referenced using the POS_*
    constants defined on the class.
    The widgets in the "outer" regions are laid out according to their
    preferred size along those axes where they do not touch the center
    region (in particular, the corners are thus along both axes), and
    according to the remaining size along the other axes (thus, the widget
    in the  center stretches/shrinks to accomodate changes of the
    container's size). If the optional border specified, the corner widgets
    are drawn *on top of it*, and all border regions have a size of at least
    1x1.
    If a child is inserted into a region that is already occupied, the
    previous inhabitant is evicted, so that there always is at most one
    child per region.
    The purpose of this container is to accomodate bordered "panes", where
    a title can be placed in the top region and scrollbars into the bottom
    and right one, or dialog boxes with a title on top and buttons in the
    bottom region (possibly offset from the border).

    Attributes are:
    border       : Whether to show a border.
    insets       : Fixed offsets of the contents from the border. Can be
                   used to push regions off the border.
    background   : The attribute to display the box with (None for
                   "transparent").
    background_ch: The character to fill the box with (defaults to nothing).
    """
    class Position(Constant):
        "The position of a widget in a MarginContainer's grid"
    POS_TOPLEFT  = Position('POS_TOPLEFT',  x=0, y=0)
    POS_TOP      = Position('POS_TOP',      x=1, y=0)
    POS_TOPRIGHT = Position('POS_TOPRIGHT', x=2, y=0)
    POS_LEFT     = Position('POS_LEFT',     x=0, y=1)
    POS_CENTER   = Position('POS_CENTER',   x=1, y=1)
    POS_RIGHT    = Position('POS_RIGHT',    x=2, y=1)
    POS_BOTLEFT  = Position('POS_BOTLEFT',  x=0, y=2)
    POS_BOTTOM   = Position('POS_BOTTOM',   x=1, y=2)
    POS_BOTRIGHT = Position('POS_BOTRIGHT', x=2, y=2)
    @classmethod
    def calc_sizes(cls, full, minimum, preferred):
        "Helper method for layout."
        sm, sp = sum(minimum), sum(preferred)
        diff = full - sp
        if diff >= 0:
            return (preferred[0], full - preferred[0] - preferred[2],
                    preferred[2])
        if sm == sp:
            weights = (1, 1, 1)
        else:
            weights = (preferred[0] - minimum[0],
                       preferred[1] - minimum[1],
                       preferred[2] - minimum[2])
        incs = weight_distrib(diff, weights)
        return (preferred[0] + incs[0],
                preferred[1] + incs[1],
                preferred[2] + incs[2])
    def __init__(self, **kwds):
        "Initializer"
        Container.__init__(self, **kwds)
        self.border = parse_quad(kwds.get('border', False))
        self.insets = parse_quad(kwds.get('insets', 0))
        self.background = kwds.get('background', None)
        self.background_ch = kwds.get('background_ch', '\0')
        self._slots = {}
        self._revslots = {}
        self._presizes = None
        self._boxes = None
    def getminsize(self):
        "Calculate the minimum size of this container"
        self._make_preboxes()
        return self._minsize
    def getprefsize(self):
        "Calculate the preferred size of this container"
        self._make_preboxes()
        return self._prefsize
    def relayout(self):
        "Perform a layout refresh"
        self._make_boxes(self.size)
        for w, pos, size in self._boxes:
            w.pos = addpos(self.pos, pos)
            w.size = size
    def invalidate_layout(self):
        "Mark this widget as in need of a layout refresh"
        Container.invalidate_layout(self)
        self._presizes = None
        self._boxes = None
    def invalidate(self, rec=False, child=None):
        "Mark this widget as in need of a redraw"
        Container.invalidate(self, rec, child)
        if child is None:
            for ch in self.children:
                if self._slots[ch] == self.POS_CENTER: continue
                ch.invalidate(True)
    def draw_self(self, win):
        "Draw this widget to the given window"
        BoxWidget.draw_box(win, self.pos, self.size, self.background,
                           self.background_ch, self.border)
        Container.draw_self(self, win)
    def add(self, widget, **config):
        """
        Add the given child to this container

        The "slot" keyword argument (defaulting to POS_CENTER) can be used
        to put the child into a particular slot.
        """
        slot = config.get('slot', self.POS_CENTER)
        try:
            self.remove(self._revslots[slot])
        except KeyError:
            pass
        ret = Container.add(self, widget, **config)
        self._slots[widget] = slot
        self._revslots[slot] = widget
        return ret
    def remove(self, widget):
        "Remove this given child from this container"
        Container.remove(self, widget)
        del self._revslots[self._slots[widget]]
        del self._slots[widget]
    def _make_preboxes(self):
        "Internal helper method for layout"
        if self._presizes is not None: return
        if not self.children:
            self._minsize = inflate((0, 0), self.insets)
            self._prefsize = inflate((0, 0), self.insets)
            self._presizes = ((0, 0, 0),) * 4
            return
        mws, mhs = [0, 0, 0], [0, 0, 0]
        pws, phs = [0, 0, 0], [0, 0, 0]
        for w, slot in self._slots.items():
            ms, ps = w.minsize, w.prefsize
            mws[slot.x] = max(mws[slot.x], ms[0])
            mhs[slot.y] = max(mhs[slot.y], ms[1])
            pws[slot.x] = max(pws[slot.x], ps[0])
            phs[slot.y] = max(phs[slot.y], ps[1])
        if self.border[0] and not self.insets[0]:
            mhs[0], phs[0] = max(mhs[0], 1), max(phs[0], 1)
        if self.border[1] and not self.insets[1]:
            mws[2], pws[2] = max(mws[2], 1), max(pws[2], 1)
        if self.border[2] and not self.insets[2]:
            mhs[2], phs[2] = max(mhs[2], 1), max(phs[2], 1)
        if self.border[3] and not self.insets[3]:
            mws[0], pws[0] = max(mws[0], 1), max(pws[0], 1)
        self._minsize = inflate((sum(mws), sum(mhs)), self.insets)
        self._prefsize = inflate((sum(pws), sum(phs)), self.insets)
        self._presizes = (mws, mhs, pws, phs)
    def _make_boxes(self, size):
        "Internal helper method for layout"
        if self._boxes is not None: return
        self._make_preboxes()
        mws, mhs, pws, phs = self._presizes
        bx, by, bw, bh = deflate((0, 0, size[0], size[1]), self.insets)
        ws = self.calc_sizes(bw, mws, pws)
        hs = self.calc_sizes(bh, mhs, phs)
        xs = (bx, bx + ws[0], bx + ws[0] + ws[1])
        ys = (by, by + hs[0], by + hs[0] + hs[1])
        self._boxes = []
        for w, slot in self._slots.items():
            self._boxes.append((w,
                (xs[slot.x], ys[slot.y]),
                (ws[slot.x], hs[slot.y])))

class LinearContainer(Container):
    """
    A container that lays out its children in one direction

    The actual implementation is flexible enough to have groups of widgets
    in different directions or diagonally; the VerticalContainer and
    HorizontalContainer subclasses configure the machinery to be of practical
    use.

    The container has two "mode"s of layout (one per axis), which are chosen
    from the the MODE_* class constants:
    MODE_NORMAL     : Children are laid out at their preferred sizes. If
                      there are children with nonzero "weights", they are
                      expanded proportionally to fill the available space.
                      If there are none, free space remains at the "end" of
                      the container.
    MODE_STRETCH    : Similar to MODE_NORMAL, except that all children are
                      stretched uniformly instead of leaving free space.
    MODE_EQUAL      : Children are laid out at equal sizes, gradually
                      degrading to their preferred sizes if there is not
                      enough additional space.
    MODE_EQUAL_FORCE: Children are always laid out at equal sizes, at the
                      cost of potentially high space consumption.

    Each child has a "rule" that defines how its successor is placed:
    RULE_STAY : The successor is placed "on top of" the current child.
    RULE_RIGHT: The successor is placed on the right of the current child.
    RULE_DOWN : The successor is placed below the current child.
    RULE_DIAG : The successor is placed both below and to the right of the
                current child.
    Although the layour algorithm can cope with any combination of those,
    typically, only RULE_RIGHT or RULE_DOWN are used, for all children
    homogeneously (as do VerticalContainer and HorizontalContainer).

    In addition, each child has a (growing) weight and a shrinking weight;
    these (together with the mode) are used to determine how excess (or
    lacking) space is distributed amongst the children. The growing weight
    defaults to zero (so that a child would never grow in MODE_NORMAL); the
    shrinking weights defaults to one (so that all children can be squished
    to their minimum sizes if that be needed).

    If there are multiple children occupying the same (x-axis or y-axis)
    slot, the maximum of their minimum and preferred sizes, respectively, is
    used for layout. Thus, in VerticalContainer and HorizontalContainer, the
    minimum / preferred size along the "non-main" axis is the maximum of
    of the minimum / preferred sizes along that axis.

    Attributes of the container are:
    default_rule: The default rule to use for a child. Defaults to RULE_STAY
                  on LinearContainer and appropriate values on
                  VerticalContainer and HorizontalContainer.
    mode_x      : The layout mode to be used in the x direction. The default
                  is MODE_STRETCH.
    mode_y      : The layout mode to be used in the y direction. The default
                  is MODE_STRETCH as well.
    """
    class Rule(Constant):
        "An item's layout mode of LinearContainer"
    RULE_STAY = Rule('RULE_STAY', advances=(0, 0))
    RULE_RIGHT = Rule('RULE_RIGHT', advances=(1, 0))
    RULE_DOWN = Rule('RULE_DOWN', advances=(0, 1))
    RULE_DIAG = Rule('RULE_DIAG', advances=(1, 1))
    class Mode(Constant):
        "The overall layout mode of LinearContainer"
    MODE_NORMAL = Mode('MODE_NORMAL')
    MODE_STRETCH = Mode('MODE_STRETCH')
    MODE_EQUAL = Mode('MODE_EQUAL')
    MODE_EQUAL_FORCE = Mode('MODE_EQUAL_FORCE')
    @classmethod
    def _make_groups(cls, initial, mins, advances, weights, sweights):
        "Internal layout helper"
        glengths, gmins, gsizes, gweights, gsweights = [], [], [], [], []
        first = True
        for i, m, a, w, s in zip(initial, mins, advances, weights, sweights):
            if a or first:
                first = False
                glengths.append(0)
                gmins.append(0)
                gsizes.append(0)
                gweights.append(0)
                gsweights.append(1)
            glengths[-1] += 1
            gmins[-1] = max(gmins[-1], m)
            gsizes[-1] = max(gsizes[-1], i)
            gweights[-1] = w
            gsweights[-1] = s
        return (glengths, gmins, gsizes, gweights, gsweights)
    @classmethod
    def _unpack_groups(cls, values, lengths):
        "Internal layout helper"
        return sum(((v,) * l for v, l in zip(values, lengths)), ())
    @classmethod
    def _shrink(cls, r, full, gmins, gsweights):
        "Internal layout helper"
        while 1:
            indices, weights, diffs = [], [], []
            for i, w in enumerate(gsweights):
                if w == 0: continue
                d = gmins[i] - r[i]
                if d >= 0: continue
                indices.append(i)
                weights.append(w)
                diffs.append(d)
            if not indices: break
            incs = [max(i, j) for i, j in zip(diffs,
                weight_distrib(full - sum(r), weights))]
            for idx, inc in zip(indices, incs):
                r[idx] += inc
            if sum(r) == full: break
        return r
    @classmethod
    def _distrib_normal(cls, full, initial, mins, advances, weights,
                        sweights, mode):
        "Internal layout helper"
        glengths, gmins, gsizes, gweights, gsweights = cls._make_groups(
            initial, mins, advances, weights, sweights)
        if sum(gweights) == 0:
            if mode == cls.MODE_STRETCH:
                gweights = (1,) * len(gweights)
            else:
                return cls._unpack_groups(gsizes, glengths)
        diff = full - sum(gsizes)
        if diff > 0:
            incs = weight_distrib(diff, gweights)
            r = [l + i for l, i in zip(gsizes, incs)]
        elif diff < 0:
            r = cls._shrink(list(gsizes), full, gmins, gsweights)
        else:
            r = gsizes
        return cls._unpack_groups(r, glengths)
    @classmethod
    def _distrib_equal(cls, full, initial, mins, advances, weights,
                       sweights, mode):
        "Internal layout helper"
        glengths, gmins, gsizes, gweights, gsweights = cls._make_groups(
            initial, mins, advances, weights, sweights)
        distr = linear_distrib(full, len(advances))
        if mode != cls.MODE_EQUAL_FORCE:
            while True:
                if all((i <= d) for i, d in zip(initial, distr)): break
                used, fitting = 0, []
                for n, (i, d) in enumerate(zip(initial, distr)):
                    if i < d:
                        fitting.append(n)
                    else:
                        distr[n] = i
                        used += i
                if not fitting: break
                ndis = linear_distrib(full - used, len(fitting))
                for n, l in zip(fitting, ndis):
                    distr[n] = l
            if sum(distr) > full:
                distr = cls._shrink(distr, full, gmins, (1,) * len(gmins))
        return cls._unpack_groups(distr, glengths)
    @classmethod
    def distribute(cls, full, initial, mins, advances, weights,
                   sweights, mode=MODE_NORMAL):
        "Internal layout helper"
        if not (len(initial) == len(mins) == len(advances) == len(weights) ==
                len(sweights)):
            raise ValueError('Incoherent lists given to distribute().')
        elif not initial:
            return ()
        elif mode in (cls.MODE_NORMAL, cls.MODE_STRETCH):
            return cls._distrib_normal(full, initial, mins, advances,
                                       weights, sweights, mode)
        elif mode in (cls.MODE_EQUAL, cls.MODE_EQUAL_FORCE):
            return cls._distrib_equal(full, initial, mins, advances,
                                      weights, sweights, mode)
        else:
            raise ValueError('Invalid mode: %r' % (mode,))
    def __init__(self, **kwds):
        "Initializer"
        Container.__init__(self, **kwds)
        self.default_rule = kwds.get('default_rule', self.RULE_STAY)
        self.mode_x = kwds.get('mode_x', self.MODE_STRETCH)
        self.mode_y = kwds.get('mode_y', self.MODE_STRETCH)
        self._rules = {}
        self._weights_x = {}
        self._weights_y = {}
        self._sweights_x = {}
        self._sweights_y = {}
        self._preboxes = None
        self._boxes = None
    def getminsize(self):
        "Calculate the minimum size of this container"
        self._make_preboxes()
        return self._minsize
    def getprefsize(self):
        "Calculate the preferred size of this container"
        self._make_preboxes()
        return self._prefsize
    def relayout(self):
        "Perform a layout refresh"
        self._make_boxes(self.size)
        for w, xy, wh in self._boxes:
            w.pos = addpos(self.pos, xy)
            w.size = wh
    def invalidate_layout(self):
        "Mark this container as in need of a layout refresh"
        Container.invalidate_layout(self)
        self._preboxes = None
        self._boxes = None
    def add(self, widget, **config):
        """
        Add a new child to the container

        The following configuration parameters can be passed:
        rule     : The advancement rule to be used for this child.
                   Defaults to the default_rule attribute of the
                   container.
        weight   : The default for weight_x and weight_y; defaults
                   itself to zero.
        weight_x : The relative weight to be used when stretching the
                   layout in the x direction.
        weight_y : The relative weight to be used when stretching the
                   layout in the y direction.
        sweight  : The default for sweight_x and sweight_y; defaults
                   itself to one.
        sweight_x: The relative weight to be used when shrinking the
                   layout in the x direction.
        sweight_y: The relative weight to be used when shrinking the
                   layout in the y direction.
        """
        self._rules[widget] = config.get('rule', self.default_rule)
        w = config.get('weight', 0.0)
        self._weights_x[widget] = config.get('weight_x', w)
        self._weights_y[widget] = config.get('weight_y', w)
        sw = config.get('sweight', 1.0)
        self._sweights_x[widget] = config.get('sweight_x', sw)
        self._sweights_y[widget] = config.get('sweight_y', sw)
        return Container.add(self, widget, **config)
    def remove(self, widget):
        "Remove a child from this container"
        Container.remove(self, widget)
        del self._rules[widget]
        del self._weights_x[widget]
        del self._weights_y[widget]
        del self._sweights_x[widget]
        del self._sweights_y[widget]
    def _make_preboxes(self):
        "Internal layout helper"
        if self._preboxes is not None: return
        cpp, cpm, mps, mms = (0, 0), (0, 0), (0, 0), (0, 0)
        amnt, tps, tms = [0, 0], (0, 0), (0, 0)
        self._preboxes = []
        for w in self.children:
            ps, ms, r = w.prefsize, w.minsize, self._rules[w]
            mps, mms = maxpos(mps, ps), maxpos(mms, ms)
            self._preboxes.append((w, tuple(ps), tuple(ms)))
            tps = maxpos(tps, (cpp[0] + ps[0], cpp[1] + ps[1]))
            tms = maxpos(tms, (cpm[0] + ms[0], cpm[1] + ms[1]))
            amnt[0] += r.advances[0]
            amnt[1] += r.advances[1]
            cpp = (cpp[0] + ps[0] * r.advances[0],
                   cpp[1] + ps[1] * r.advances[1])
            cpm = (cpm[0] + ms[0] * r.advances[0],
                   cpm[1] + ms[1] * r.advances[1])
        tps = list(tps)
        if self.mode_x in (self.MODE_EQUAL, self.MODE_EQUAL_FORCE):
            tps[0] = mps[0] * amnt[0]
        if self.mode_y in (self.MODE_EQUAL, self.MODE_EQUAL_FORCE):
            tps[1] = mps[1] * amnt[1]
        self._prefsize = tps
        self._minsize = tms
    def _make_boxes(self, size):
        "Internal layout helper"
        if self._boxes is not None: return
        self._make_preboxes()
        if len(self._preboxes) == 0:
            self._boxes = []
            return
        sizes, mins, advances, weights, sweights = [], [], [], [], []
        for w, wh, ms in self._preboxes:
            sizes.append(wh)
            mins.append(ms)
            advances.append(self._rules[w].advances)
            weights.append((self._weights_x[w], self._weights_y[w]))
            sweights.append((self._sweights_x[w], self._sweights_y[w]))
        zl = tuple(zip(*sizes))
        zm = tuple(zip(*mins))
        za = tuple(zip(*advances))
        zw = tuple(zip(*weights))
        zs = tuple(zip(*sweights))
        esizes = zip(self.distribute(size[0], zl[0], zm[0],
                                     za[0], zw[0], zs[0], self.mode_x),
                     self.distribute(size[1], zl[1], zm[1],
                                     za[1], zw[1], zs[1], self.mode_y))
        esizes = list(esizes)
        self._boxes = []
        cp = (0, 0)
        for w, s in zip(self.children, esizes):
            self._boxes.append((w, cp, s))
            r = self._rules[w]
            cp = (cp[0] + s[0] * r.advances[0],
                  cp[1] + s[1] * r.advances[1])

class HorizontalContainer(LinearContainer):
    """
    A container arranging its children horizontally

    The is a LinearContainer whose default rule is RULE_RIGHT. The "mode_x"
    constructor argument is aliased to "mode".
    """
    def __init__(self, **kwds):
        "Initializer"
        if 'mode' in kwds: kwds.setdefault('mode_x', kwds['mode'])
        LinearContainer.__init__(self, default_rule=self.RULE_RIGHT, **kwds)

class VerticalContainer(LinearContainer):
    """
    A container arranging its children vertically

    The is a LinearContainer whose default rule is RULE_DOWN. The "mode_y"
    constructor argument is aliased to "mode".
    """
    def __init__(self, **kwds):
        "Initializer"
        if 'mode' in kwds: kwds.setdefault('mode_y', kwds['mode'])
        LinearContainer.__init__(self, default_rule=self.RULE_DOWN, **kwds)

class GridContainer(Container):
    """
    A container that lays out its children as a grid

    This class reuses the layout algorithms from LinearContainer; see there
    for the different layout "modes".
    For vertical/horizontal layout, columns/rows are regarded as unities for
    layout purposes, and have common growing and shrinking weights, as well
    as user-definable minimum sizes. Layout along the vertical axis is
    independent from that along the horizontal one.
    Each grid cell can be populated by at most one child; trying to add
    another one will evict the previous one.

    Attributes are:
    mode_x: Layout mode to be used along the X axis. See LinearContainer for
            details.
    mode_y: Layout mode to be used along the Y axis. See LinearContainer for
            details.
    """
    def __init__(self, **kwds):
        "Initializer"
        Container.__init__(self, **kwds)
        self.mode_x = kwds.get('mode_x', LinearContainer.MODE_STRETCH)
        self.mode_y = kwds.get('mode_y', LinearContainer.MODE_STRETCH)
        self._widgets = {}
        self._places = {}
        self._columnConfig = {}
        self._rowConfig = {}
        self._presizes = None
        self._minsizes = None
        self._offsets = None
        self._sizes = None
    def getminsize(self):
        "Calculate the minimum size of this container"
        self._make_presizes()
        return self._minsize
    def getprefsize(self):
        "Calculate the preferred size of the container"
        self._make_presizes()
        return self._prefsize
    def relayout(self):
        "Perform a layout refresh"
        self._make_sizes(self.size)
        ofx, ofy = self._offsets
        szx, szy = self._sizes
        for pos, w in self._widgets.items():
            w.pos = addpos(self.pos, (ofx[pos[0]], ofy[pos[1]]))
            w.size = (szx[pos[0]], szy[pos[1]])
    def invalidate_layout(self):
        "Mark this widget as in need of a layout refresh"
        Container.invalidate_layout(self)
        self._presizes = None
        self._minsizes = None
        self._sizes = None
    def add(self, widget, **config):
        """
        Add a child to the container

        The mandatory "pos" keyword argument specifies into which cell to
        put the child.
        """
        pos = config['pos']
        try:
            self.remove(self._widgets[pos])
        except KeyError:
            pass
        self._widgets[pos] = widget
        self._places[widget] = pos
        return Container.add(self, widget, **config)
    def remove(self, widget):
        "Remove a child from the container"
        Container.remove(self, widget)
        pos = self._places.pop(widget)
        del self._widgets[pos]
    def _config(self, d, idx, kwds):
        "Internal helper"
        conf = d.setdefault(idx, {'weight': 0, 'sweight': 1, 'minsize': 0})
        if 'weight' in kwds:
            conf['weight'] = kwds['weight']
        if 'sweight' in kwds:
            conf['sweight'] = kwds['sweight']
        if 'minsize' in kwds:
            conf['minsize'] = kwds['minsize']
        self.invalidate_layout()
    def config_row(self, row, **kwds):
        """
        Configure a row

        Keyword arguments are:
        weight : The growing weight of the row.
        sweight: The shrinking weight of the row.
        minsize: The minimum size of the row.
        """
        self._config(self._rowConfig, row, kwds)
    def config_col(self, col, **kwds):
        """
        Configure a column

        Keyword arguments are:
        weight : The growing weight of the column.
        sweight: The shrinking weight of the column.
        minsize: The minimum size of the column.
        """
        self._config(self._columnConfig, col, kwds)
    def _make_presizes(self):
        "Internal layout helper"
        if self._presizes is not None: return
        psx, psy, msx, msy = [], [], [], []
        for pos, w in self._widgets.items():
            x, y = pos
            xp1, yp1 = x + 1, y + 1
            while len(psx) < xp1: psx.append(0)
            while len(msx) < xp1: msx.append(0)
            while len(psy) < yp1: psy.append(0)
            while len(msy) < yp1: msy.append(0)
            wps, wms = w.prefsize, w.minsize
            psx[x] = max(psx[x], wps[0])
            msx[x] = max(msx[x], wms[0])
            psy[y] = max(psy[y], wps[1])
            msy[y] = max(msy[y], wms[1])
        for x, conf in self._columnConfig.items():
            xp1 = x + 1
            while len(psx) < xp1: psx.append(0)
            while len(msx) < xp1: msx.append(0)
            psx[x] = max(psx[x], conf['minsize'])
            msx[x] = max(msx[x], conf['minsize'])
        for y, conf in self._rowConfig.items():
            yp1 = y + 1
            while len(psy) < yp1: psy.append(0)
            while len(msy) < yp1: msy.append(0)
            psy[y] = max(psy[y], conf['minsize'])
            msy[y] = max(msy[y], conf['minsize'])
        lm = (LinearContainer.MODE_EQUAL,
              LinearContainer.MODE_EQUAL_FORCE)
        tps = [sum(psx), sum(psy)]
        tms = [sum(msx), sum(msy)]
        if psx and self.mode_x in lm:
            tps[0] = max(psx) * len(psx)
        if psy and self.mode_y in lm:
            tps[1] = max(psy) * len(psy)
        self._presizes = (psx, psy)
        self._minsizes = (msx, msy)
        self._prefsize = tps
        self._minsize = tms
    def _make_sizes(self, size):
        "Internal layout helper"
        if self._sizes is not None: return
        self._make_presizes()
        # Distribute sizes
        weights_x = [0] * len(self._presizes[0])
        weights_y = [0] * len(self._presizes[1])
        sweights_x = [1] * len(self._presizes[0])
        sweights_y = [1] * len(self._presizes[1])
        advances_x = (1,) * len(self._presizes[0])
        advances_y = (1,) * len(self._presizes[1])
        for x, conf in self._columnConfig.items():
            weights_x[x] = conf['weight']
            sweights_x[x] = conf['sweight']
        for y, conf in self._rowConfig.items():
            weights_y[y] = conf['weight']
            sweights_y[y] = conf['sweight']
        sizes_x = LinearContainer.distribute(size[0], self._presizes[0],
            self._minsizes[0], advances_x, weights_x, sweights_x,
            self.mode_x)
        sizes_y = LinearContainer.distribute(size[1], self._presizes[1],
            self._minsizes[1], advances_y, weights_y, sweights_y,
            self.mode_y)
        self._sizes = (sizes_x, sizes_y)
        # Make offsets
        ofx, ofy, x, y = [], [], 0, 0
        for i in self._sizes[0]:
            ofx.append(x)
            x += i
        for i in self._sizes[1]:
            ofy.append(y)
            y += i
        self._offsets = (ofx, ofy)

class BoxWidget(Widget):
    """
    A widget whose contents can be enclosed in a box-like border

    This class is meant to be extended with more specific functionality by
    subclasses.

    Attributes are:
    border       : Whether to display the border. Should be an actual bool
                   instance. Defaults to False.
    background   : The background attribute to fill the area of the widget
                   with. Can be None to indicate that it should be
                   "transparent", which is the default.
    background_ch: The character to be used for filling the background.
    """
    @staticmethod
    def draw_box(win, pos, size, attr, ch, border):
        """
        Draw a possibly bordered box to the given curses window

        Arguments are:
        win   : The window to draw to.
        pos   : The top-left corner of the box.
        size  : The size of the box.
        attr  : If not None, which attribute to fill the box (and draw the
                border) with.
        ch    : The character to use for filling the box.
        border: If a boolean, specifies whether to draw a border from
                box-drawing characters inside the box. If an iterable (must
                have four items), specifies whether to draw each of the
                top/right/bottom/left parts of the border.
        """
        if pos[0] < 0 or pos[1] < 0 or size[0] <= 0 or size[1] <= 0:
            return
        try:
            sw = win.derwin(size[1], size[0], pos[1], pos[0])
        except _curses.error:
            return
        if attr is not None:
            sw.bkgd(ch, attr)
            sw.clear()
        if border == True:
            sw.border()
            return
        elif border == False:
            return
        try:
            border = tuple(border)
        except TypeError:
            border = (border, border, border, border)
        if all(border):
            sw.border()
            return
        elif not any(border):
            return
        # OK, this is going to be hard...
        bottom, right = size[1] - 1, size[0] - 1
        if border[0]:
            sw.hline(0, 0, _curses.ACS_HLINE, size[0])
        if border[1]:
            sw.vline(0, right, _curses.ACS_VLINE, size[1])
        if border[2]:
            sw.hline(bottom, 0, _curses.ACS_HLINE, size[0])
        if border[3]:
            sw.vline(0, 0, _curses.ACS_VLINE, size[1])
        if border[0] and border[1]:
            sw.insch(0, right, _curses.ACS_URCORNER)
        if border[1] and border[2]:
            sw.insch(bottom, right, _curses.ACS_LRCORNER)
        if border[2] and border[3]:
            sw.addch(0, bottom, _curses.ACS_LLCORNER)
        if border[3] and border[0]:
            sw.addch(0, 0, _curses.ACS_ULCORNER)
    def __init__(self, **kwds):
        "Initializer"
        Widget.__init__(self, **kwds)
        self.background = kwds.get('background', None)
        self.background_ch = kwds.get('background_ch', '\0')
        self.border = kwds.get('border', False)
    def draw_self(self, win):
        "Draw this widget to the given window"
        Widget.draw_self(self, win)
        self.draw_box(win, self.pos, self.size, self.background,
                      self.background_ch, self.border)

class TextWidget(BoxWidget, Scrollable):
    """
    A widget that displays text

    TextWidget contains the algorithms for laying out (possibly multiline)
    text within a widget. Unicode support is limited, and bounded by the
    underlying curses library and the terminal. This class is meant to be
    extended by subclasses.

    TextWidget supports a (class-specific) "prefix" and "suffix" for the
    text, which can be used as visual cues for the role of a widget. For
    example, buttons have "<" and ">" as such. Checkboxes use the prefix
    to display the current status. A TextWidget is scrollable, and can
    hence be immediately bound to scrollbars; this is recommended instead
    of putting it into a Viewport (in particular for multi-line entry boxes,
    which do not fully function otherwise).

    Attributes are:
    text    : Which text to display.
    attr    : Which attribute to display the text with.
    textbg  : Which attribute to use as a background for the text. If
              specified, this covers most of the widget area (except the
              border, if enabled, and the columns below/above the
              class-specific prefix and suffix).
    textbgch: Which character to fill the "text background" with.
    align   : How to align the text. Can be a single alignment, which is
              use for both axes, or a (horizontal, pair) pair. The default
              is (ALIGN_LEFT, ALIGN_TOP).
    """
    def __init__(self, text='', **kwds):
        "Initializer"
        BoxWidget.__init__(self, **kwds)
        Scrollable.__init__(self)
        self.attr = kwds.get('attr', 0)
        self.textbg = kwds.get('textbg', Ellipsis)
        self.textbgch = kwds.get('textbgch', '\0')
        self.align = parse_pair(kwds.get('align'), (ALIGN_LEFT, ALIGN_TOP))
        self.cmaxsize = parse_pair(kwds.get('cmaxsize'))
        self._extra_col = False
        self._text = text
        self._lines = None
        self._indents = None
        self._vindent = None
        self._natsize = None
        self.contentsize = (0, 0)
        self.focusable = False
    def getprefsize(self):
        "Calculate the preferred size of this widget"
        # Force calculation of the relevant values.
        self.text = self._text
        ps, cm = self._natsize, self.cmaxsize
        return (ps[0] if cm[0] is None else min(ps[0], cm[0]),
                ps[1] if cm[1] is None else min(ps[1], cm[1]))
    def _update_indents(self):
        "Internal layout helper"
        self.text = self._text
        i = (1 if self.border else 0)
        tp, ctp = self._text_prefix()
        cts, ts = self._text_suffix()
        if self._text: tp, ts = tp + ctp, cts + ts
        ew = self.size[0] - len(tp) - len(ts) - 2 * i
        eh = self.size[1] - 2 * i
        self._indents = tuple(int((ew - len(l)) * self.align[0])
                              for l in self._lines)
        self._vindent = int((eh - len(self._lines)) * self.align[1])
    def make(self):
        "Perform a layout refresh on this widget"
        BoxWidget.make(self)
        self._update_indents()
        ps = self.prefsize
        self.maxscrollpos = subpos(ps, self.size)
        self.contentsize = maxpos(ps, self.size)
    def draw_self(self, win):
        "Draw this widget to the given window"
        BoxWidget.draw_self(self, win)
        self.text = self._text
        i = (1 if self.border else 0)
        pref, cpref = self._text_prefix()
        csuff, suff = self._text_suffix()
        if self._text: pref, suff = pref + cpref, csuff + suff
        x, y = self.pos
        x += len(pref)
        w = self.size[0] - 2 * i - len(pref) - len(suff)
        h = self.size[1] - 2 * i
        if self.textbg is None:
            pass
        elif self.textbg is Ellipsis:
            self.draw_box(win, (x + i, y + i), (w, h),
                          self.attr, self.textbgch, False)
        else:
            self.draw_box(win, (x + i, y + i), (w, h),
                          self.textbg, self.textbgch, False)
        y += self._vindent
        if _ENCODING is None:
            enc = lambda x: x
        else:
            enc = lambda x: x.encode(_ENCODING)
        sx, sy = self.scrollpos
        for d, l in zip(self._indents[sy:sy+h], self._lines[sy:sy+h]):
            win.addnstr(y + i, x + i + d, enc(l[sx:]), w, self.attr)
            y += 1
        win.addstr(self.pos[1] + i, self.pos[0] + i, pref, self.attr)
        if suff:
            win.addstr(self.pos[1] + i + h - 1, self.pos[0] + i + w +
                       len(pref), suff, self.attr)
    def _text_prefix(self):
        """
        Obtain the "text prefix" of this widget

        The prefix is put before the first line of the widget's text on
        display and does not participate in scrolling; see the class
        description for behavioral details.
        Returns a two-tuple of a required and an optional part (in that
        order); the optional part is not shown when the widget's text is
        empty (for example, a checkbox without text does not have any
        unintended "margins").
        The default implementation returns two empty strings.
        """
        return ('', '')
    def _text_suffix(self):
        """
        Obtain the "text suffix" of this widget

        The suffix is similar to the prefix, but displayed after the
        last line of the text.
        Returns a two-tuple of an optional and a required part (in that
        order); the optional part is not shown when the widget's text is
        empty.
        The default implementation returns two empty strings.
        """
        return ('', '')
    @property
    def text(self):
        """
        The textual content of this widget

        Assigning to this automatically updates the widget; no further steps
        are necessary.
        """
        return self._text
    @text.setter
    def text(self, text):
        if text == self._text and self._lines is not None: return
        self._text = text
        self._lines = text.split('\n')
        ps = [0, 0]
        if self._lines:
            ps = [max(len(i) for i in self._lines), len(self._lines)]
        if self.border:
            ps[0] += 2
            ps[1] += 2
        tp, ctp = self._text_prefix()
        cts, ts = self._text_suffix()
        if text: tp, ts = tp + ctp, cts + ts
        ps[0] += len(tp) + len(ts)
        if self._extra_col: ps[0] += 1
        self._natsize = tuple(ps)
        self.invalidate_layout()

class Label(TextWidget):
    """
    A mere piece of text

    This widget does not override any of TextWidget's functionality, and
    should be used when nothing further is desired.
    """

class Button(TextWidget):
    """
    A UI element that can be focused and "invoked", performing some action

    The "attr" attribute is replaced by attr_normal or attr_active depending
    on the focus status of the button; assigning it leads to erratic behvior.

    A button can be tabbed to to become focused, and then invoked by pressing
    Return or Space. What the button does is specified by the programmer, and
    should be deducible from its text (and perhaps context).

    Additional attributes are:
    callback   : A nullary function to be invoked when the button is
                 activated.
    attr_normal: The attribute to use for the text when the button is not
                 focused.
    attr_focus : The attribute to use for the text when the button is
                 focused.
    """
    def __init__(self, text='', callback=None, **kwds):
        "Initializer"
        TextWidget.__init__(self, text, **kwds)
        self.attr_normal = kwds.get('attr_normal', 0)
        self.attr_active = kwds.get('attr_active', _curses.A_STANDOUT)
        self.callback = callback
        self.attr = self.attr_normal
        self.focused = False
    def event(self, event):
        "Handle an input event"
        ret = TextWidget.event(self, event)
        if event[0] in (_KEY_RETURN, ' '):
            self.on_activate()
            return True
        elif event[0] == FocusEvent:
            self._set_focused(event[1])
        return ret
    def focus(self, rev=False):
        "Perform focus traversal"
        return (not self.focused)
    def _text_prefix(self):
        "Return the text prefix"
        return ('<', '')
    def _text_suffix(self):
        "Return the text suffix"
        return ('', '>')
    def _set_focused(self, state):
        "Internal focus helper"
        if self.focused == state: return
        self.focused = state
        self.on_focuschange()
        self.invalidate()
    def on_focuschange(self):
        """
        Handle a change of focus
        """
        self.attr = (self.attr_active if self.focused else self.attr_normal)
        if self.focused:
            self.grab_input(self.rect, self.pos)
    def on_activate(self):
        """
        Handle an activation of the button

        Subclasses should implement their behavior here instead of replacing
        the callback.
        """
        if self.callback is not None:
            self.callback()

class ToggleButton(Button):
    """
    A button that can alternate between multiple "states"

    This is a base class meant to be extended by subclasses, and does not
    actually implement any specific mode of alteration.

    Additional attributes are:
    state: The state this widget is in.
    """
    def __init__(self, text='', **kwds):
        "Initializer"
        Button.__init__(self, text, **kwds)
        self._state = kwds.get('state', None)
        self._state_set = False
    def _set_state(self, value):
        """
        Switch to the given state

        This can be extended by subcclasses to implement custom behavior.
        """
        self._state = value
    @property
    def state(self):
        "The state this widget is currently in"
        if not self._state_set: self.state = self._state
        return self._state
    @state.setter
    def state(self, value):
        self._state_set = True
        self._set_state(value)

class CheckBox(ToggleButton):
    """
    A UI element that can be toggled between "on" and "off" states

    The concrete interpretation of the state is up to the programmer;
    generally, if the checkbox is enabled, whatever is described by
    its label should "apply", and do "not apply" otherwise.
    """
    def _set_state(self, value):
        "Change the state of this widget to another"
        ToggleButton._set_state(self, value)
        self.invalidate()
    def _text_prefix(self):
        """
        The text prefix of this widget

        Used to display the state of the checkbox.
        """
        if self._state:
            return ('[X]', ' ')
        else:
            return ('[ ]', ' ')
    def _text_suffix(self):
        "The text suffix of this widget"
        return ('', '')
    def on_activate(self):
        "Handle the invocation of this widget by the user"
        ToggleButton.on_activate(self)
        self.state = (not self.state)

class RadioBox(ToggleButton):
    """
    A UI element that is part of a mutually exclusive group

    Of a RadioGroup (see the corresponding class), only one RadioBox can
    be chosen at a time.
    """
    def __init__(self, text='', **kwds):
        "Initializer"
        ToggleButton.__init__(self, text, **kwds)
        self.group = None
    def delete(self):
        "Remove this widget from the hierarchy"
        ToggleButton.delete(self)
        if self.group:
            self.group.remove(self)
    def _set_state(self, value):
        "Change the chosenness state of this widget"
        ToggleButton._set_state(self, value)
        if self.group:
            self.group.on_set(self, value)
        self.invalidate()
    def _text_prefix(self):
        "Return the text prefix of this widget"
        if self._state:
            return ('(*)', ' ')
        else:
            return ('( )', ' ')
    def _text_suffix(self):
        "Return the text suffix of this widget"
        return ('', '')
    def on_activate(self):
        "Handle the invocation of this widget by the user"
        ToggleButton.on_activate(self)
        self.state = True

class EntryBox(TextWidget):
    """
    An editable TextWidget

    This class implements editing of its content by the user. For the
    supported editing actions, see the event() method.

    Attributes are:
    attr_normal   : Which attribute to use for the teext when the entry is
                    not focused.
    attr_active   : Which attribute to use for the text when the entry is
                    focused.
    multiline     : Whether the input may have multiple lines. If false,
                    pressing Return is handled similarly to the Button class.
    backspace_hack: Whether to interpret the DEL character (127) equivalently
                    to Backspace. Since the "backspace" key normally produces
                    that code, this defaults to True.
    callback      : A nullary function to be invoked when this is a
                    single-line input and the user pressed Return.
    """
    def __init__(self, text='', **kwds):
        "Initializer"
        TextWidget.__init__(self, text, **kwds)
        self.attr_normal = kwds.get('attr_normal', 0)
        self.attr_active = kwds.get('attr_active', _curses.A_STANDOUT)
        self.multiline = kwds.get('multiline', False)
        self.backspace_hack = kwds.get('backspace_hack', True)
        self.callback = kwds.get('callback', None)
        self._extra_col = True
        self._curpos = [0, 0, 0]
        self.focused = False
        self.attr = self.attr_normal
    def make(self):
        "Perform a layout update"
        TextWidget.make(self)
        self._update_curpos()
    def event(self, event):
        """
        Handle an input event

        The following editing actions are supported (all-uppercase key names
        are correspond to curses constants that do not obviously map to
        standard QWERTY keyboards):
        Return    (^M): Append a newline character at the cursor position, or
                        "invoke" the widget if in single-line mode.
        EOL           : Insert a new line unconditionally (FIXME).
        BACKSPACE     : Remove the character just before the cursor.
        Backspace (^?): Remove the character just before the cursor.
        Down          : Move the cursor one line down.
        Up            : Move the cursor one line up.
        Left          : Move the cursor backwards by one position.
        Right         : Move the cursor forwards by one position.
        Home          : Move the cursor to the first column of the line.
        End           : Move the cursor to the end of the line.
        PgUp          : Move the cursor upwards by one "page".
        PgDn          : Move the cursor downwards by one "page".
        Ctrl-A    (^A): Move the cursor to the very beginning of the input.
        Ctrl-E    (^E): Move the cursor to the very end of the input.
        All other (textual) characters are inserted at the current cursor
        position.
        """
        ret = TextWidget.event(self, event)
        st = self.text
        if event[0] == FocusEvent:
            self._set_focused(event[1])
        elif event[0] == _KEY_RETURN:
            if self.multiline:
                self.insert('\n')
            else:
                self.on_activate()
            return True
        elif event[0] == _curses.KEY_EOL:
            self.insert('\n')
            return True
        elif (event[0] == _curses.KEY_BACKSPACE or
                self.backspace_hack and event[0] == 127):
            if self.curpos[2]:
                self.edit(delete=(-1, 0), adjust=-1, rel=True)
                return True
        elif event[0] == _curses.KEY_DC:
            if self.curpos[2] < len(st):
                self.edit(delete=(0, 1), rel=True)
                return True
        elif event[0] == _curses.KEY_UP:
            if self.curpos[1]:
                self.edit(adjust=(0, -1))
                return True
        elif event[0] == _curses.KEY_DOWN:
            if self.curpos[1] < len(self._lines) - 1:
                self.edit(adjust=(0, 1))
                return True
        elif event[0] == _curses.KEY_LEFT:
            if self.curpos[2]:
                self.edit(adjust=-1)
                return True
        elif event[0] == _curses.KEY_RIGHT:
            if self.curpos[2] < len(st):
                self.edit(adjust=1)
                return True
        elif event[0] == _curses.KEY_HOME:
            scp = self.curpos
            if scp[0] != 0:
                self.edit(moveto=(0, self.curpos[1]))
                return True
        elif event[0] == _curses.KEY_END:
            scp = self.curpos
            lcl = len(self._lines[scp[1]])
            if scp[1] != lcl:
                self.edit(moveto=(lcl, scp[1]))
                return True
        elif event[0] == _curses.KEY_PPAGE:
            scp = self.curpos
            if scp[1] > 0:
                self.edit(adjust=(0, -self.size[1]))
                return True
        elif event[0] == _curses.KEY_NPAGE:
            scp = self.curpos
            if scp[1] < len(self._lines) - 1:
                self.edit(adjust=(0, self.size[1]))
                return True
        elif event[0] == 1: # Ctrl-A
            if self.curpos[2]:
                self.edit(moveto=0)
                return True
        elif event[0] == 5: # Ctrl-E
            if self.curpos[2] != len(self._text):
                self.edit(moveto=len(self._text))
                return True
        elif isinstance(event[0], _unicode):
            self.insert(event[0])
            return True
        return ret
    def focus(self, rev=False):
        "Perform focus traversal"
        return (not self.focused)
    def _set_focused(self, state):
        "Internal focus handling helper"
        if self.focused == state: return
        self.focused = state
        self.on_focuschange()
        self.invalidate()
    def _update_curpos(self, first=False):
        "Internal cursor positioning helper"
        if self.focused:
            x, y = self.curpos[:2]
            x += self._indents[y]
            y += self._vindent
            if self.border:
                x += 1
                y += 1
            ps = self.prefsize
            if x >= ps[0]:
                x = ps[0] - 1
            if y >= ps[1]:
                y = ps[1] - 1
            nsp = list(self.scrollpos)
            if x < nsp[0]:
                nsp[0] = x
            elif x - self.size[0] + 1 >= nsp[0]:
                nsp[0] = x - self.size[0] + 1
            if y < nsp[1]:
                nsp[1] = y
            elif y - self.size[1] + 1 >= nsp[1]:
                nsp[1] = y - self.size[1] + 1
            if x < 0:
                x = 0
            if y < 0:
                y = 0
            self.scroll(nsp)
            cpos = addpos(self.pos, subpos((x, y), self.scrollpos))
            if first:
                rect = self.rect
            else:
                rect = (cpos[0], cpos[1], 1, 1)
            self.grab_input(rect, cpos)
    def on_focuschange(self):
        """
        Handle the change of focus state
        """
        self.attr = (self.attr_active if self.focused else self.attr_normal)
        self._update_curpos(True)
    def on_activate(self):
        """
        Handle the "activation" of the widget
        """
        if self.callback is not None:
            self.callback()
    def _calc_curpos(self, value, rel=False, xy=True):
        "Internal cursor positioning helper"
        if rel:
            scp = self.curpos
            if not self._text:
                return (0, 0, 0)
            elif isinstance(value, int):
                ni = zbound(scp[2] + value, len(self._text))
                return self._calc_curpos(ni, xy=xy)
            elif len(value) == 3:
                dx, dy, di = value
                ni = zbound(scp[2] + di, len(self._text))
                ny = zbound(scp[1] + dy, len(self._lines) - 1)
                nx = zbound(scp[0] + dx, len(self._lines[ny]))
                return self._calc_curpos((nx, ny, ni), xy=xy)
            else:
                dx, dy = value
                ny = zbound(scp[1] + dy, len(self._lines) - 1)
                nx = zbound(scp[0] + dx, len(self._lines[ny]))
                return self._calc_curpos((nx, ny), xy=xy)
        else:
            if isinstance(value, int):
                if value < 0:
                    value = len(self._text) - value
                value = zbound(value, len(self._text))
                if not xy:
                    return (None, None, value)
                x, y = value, 0
                for l in self._lines:
                    if x <= len(l): break
                    x -= len(l) + 1
                    y += 1
                return (x, y, value)
            else:
                if len(value) == 3:
                    x, y, test = value
                    do_test = True
                else:
                    x, y = value
                    do_test = False
                if y < 0:
                    y = len(self._lines) - y
                y = zbound(y, len(self._lines) - 1)
                idx = 0
                for n, l in enumerate(self._lines):
                    ll = len(l)
                    if n == y:
                        if x < 0:
                            x = ll - x
                        x = zbound(x, ll)
                        idx += x
                        break
                    idx += ll + 1
                if do_test and idx != test:
                    raise ValueError('Invalid cursor position')
                return (x, y, idx)
    def edit(self, delete=None, moveto=None, insert=None, adjust=None,
             rel=False):
        """
        Perform an editing actions

        The arguments (except rel) are processed in the order they are
        passed:
        delete: If not None, a two-tuple of cursor placements denoting
                a range of characters to delete.
        moveto: If not None, a cursor placement to move the cursor to.
        insert: If not None, a string of characters to insert at the
                (new) cursor position (without moving the cursor).
        adjust: If not None, a cursor placement to move the cursor to
                after inserting text. Always relative.
        rel   : Specifies whether delete and moveto are absolute (False)
                or relative (True).

        A cursor placement is either an integer denoting an amount of
        characters (either into the text or before/after the cursor,
        depending on the sign in the latter case), or an X/Y (i.e.
        column/line) pair of coordinates.
        """
        st, invalid = self.text, False
        if delete is not None:
            fromval, toval = delete
            fromidx = self._calc_curpos(fromval, rel, True)[2]
            toidx = self._calc_curpos(toval, rel, True)[2]
            invalid |= (fromidx != toidx)
            st = st[:fromidx] + st[toidx:]
            self.text = st
        if moveto is not None:
            self._curpos[:] = self._calc_curpos(moveto, rel)
        if insert is not None:
            cp = self._curpos[2]
            st = st[:cp] + insert + st[cp:]
            invalid |= bool(insert)
            self.text = st
        if adjust is not None:
            self.curpos = self._calc_curpos(adjust, rel=True)
        self._update_indents()
        self._update_curpos()
        if invalid:
            self.invalidate_layout()
        else:
            self.invalidate()
    def insert(self, text, moveto=None):
        """
        Insert the text at the given position, or the current one

        Equivalent to edit(moveto=moveto, insert=text, adjust=len(text))
        """
        self.edit(moveto=moveto, insert=text, adjust=len(text))
    @property
    def curpos(self):
        """
        The current cursor position
        """
        return tuple(self._curpos)
    @curpos.setter
    def curpos(self, value):
        self._curpos[:] = self._calc_curpos(value)

class BaseStrut(Widget):
    """
    A widget that is conceptually similar to a straight line

    The base class provides "direction" constants that combine an orientation
    with the potential presence of something unspecified at no, one, or both
    ends of the strut.
    In addition, a strut can be aligned in its available space if it is
    smaller that that (for example, in the "cross" direction).
    """
    class Direction(Constant):
        "A strut orientation storing whether to show leading/trailing tees"
    DIR_VERTICAL = Direction('DIR_VERTICAL',
        vert=True , lo=False, hi=False)
    DIR_UP = Direction('DIR_UP',
        vert=True , lo=True , hi=False)
    DIR_DOWN = Direction('DIR_DOWN',
        vert=True , lo=False, hi=True )
    DIR_UPDOWN = Direction('DIR_UPDOWN',
        vert=True, lo=True , hi=True )
    DIR_HORIZONTAL = Direction('DIR_HORIZONTAL',
        vert=False, lo=False, hi=False)
    DIR_LEFT = Direction('DIR_LEFT',
        vert=False, lo=True , hi=False)
    DIR_RIGHT = Direction('DIR_RIGHT',
        vert=False, lo=False, hi=True )
    DIR_LEFTRIGHT = Direction('DIR_LEFTRIGHT',
        vert=False, lo=True , hi=True )
    def __init__(self, dir=None, **kwds):
        "Initializer"
        Widget.__init__(self, **kwds)
        self.dir = dir
        self.align = parse_pair(kwds.get('align', ALIGN_CENTER))

class Strut(BaseStrut):
    """
    A straight line with optional "tees" at the ends

    The strut is displayed, depending on the orientation, as either a
    vertical or horizontal line, ending either without anything or with
    a short line segment in the cross direction if the corresponding
    end is specified in the direction.

    Attributes are:
    attr  : The attribute to draw the strut with.
    margin: A CSS-like margin to put aroung the strut. It is not filled
            with anything.
    """
    @staticmethod
    def draw_strut(win, pos, len, dir, attr):
        """
        Draw a pseudographical strut

        Arguments are:
        win : The curses window to draw to.
        pos : The top-left corner of the strut.
        len : The length of the strut.
        dir : The direction of the strut (a DIR_* constant).
        attr: The attribute to draw the strut with.
        """
        # derwin()s to avoid weird character drawing glitches
        if dir.vert:
            sw = win.derwin(len, 1, pos[1], pos[0])
            sw.bkgd('\0', attr)
            sw.clear()
            sw.vline(0, 0, _curses.ACS_VLINE, len)
            if dir.lo:
                sw.addch(0, 0, _curses.ACS_TTEE)
            if dir.hi:
                sw.insch(len - 1, 0, _curses.ACS_BTEE)
        else:
            sw = win.derwin(1, len, pos[1], pos[0])
            sw.bkgd('\0', attr)
            sw.clear()
            sw.hline(0, 0, _curses.ACS_HLINE, len)
            if dir.lo:
                sw.addch(0, 0, _curses.ACS_LTEE)
            if dir.hi:
                sw.insch(0, len - 1, _curses.ACS_RTEE)
    def __init__(self, dir=None, **kwds):
        "Initializer"
        BaseStrut.__init__(self, dir, **kwds)
        self.attr = kwds.get('attr', 0)
        self.margin = parse_quad(kwds.get('margin', 0))
    def getprefsize(self):
        "Calculate the preferred size of this widget"
        ret = (self.dir.lo + self.dir.hi, 1)
        if self.dir.vert: ret = ret[::-1]
        ret = inflate(ret, self.margin)
        return maxpos(ret, BaseStrut.getprefsize(self))
    def draw_self(self, win):
        "Draw this widget to the given window"
        BaseStrut.draw_self(self, win)
        ir = deflate(
            (self.pos[0], self.pos[1], self.size[0], self.size[1]),
            self.margin)
        x, y = ir[:2]
        if self.dir.vert:
            x += int(ir[2] * self.align[0])
            l = ir[3]
        else:
            y += int(ir[3] * self.align[1])
            l = ir[2]
        self.draw_strut(win, (x, y), l, self.dir, self.attr)

class Scrollbar(BaseStrut):
    """
    A scrollbar

    This widget displays the currently visible region of a scrollable widget
    (if not everything is) along one direction, and allows changing that
    (i.e. scrolling).

    To be effective, a Scrollbar must be "bound" to a Scrollable using the
    bind() method of the latter. If two scrollbars are bound to a widget and
    one of them is focused, the other one is "highlighted", indicating that
    either scrolling action can be done from either scrollbar.

    Attributes are:
    attr_normal   : The attribute to use as default.
    attr_highlight: The attribute to use when the scrollbar is highlighted.
    attr_active   : The attribute to use when the scrollbar is focused.
    visibility    : Whether the scrollbar is visible; one of the
                    VisibilityContainer.VIS_* constants, with the
                    corresponding semantics.
    """
    def __init__(self, dir=None, **kwds):
        "Initializer"
        BaseStrut.__init__(self, dir, **kwds)
        self.attr_normal = kwds.get('attr_normal', 0)
        self.attr_active = kwds.get('attr_active', _curses.A_STANDOUT)
        self.attr_highlight = kwds.get('attr_highlight', _curses.A_STANDOUT)
        self.visibility = kwds.get('visibility',
            VisibilityContainer.VIS_VISIBLE)
        self.attr = self.attr_normal
        self.focused = False
        self.highlighted = False
        self.bound = None
        self._handle = None
    def getprefsize(self):
        "Obtain the preferred size of this widget"
        if self.visibility == VisibilityContainer.VIS_COLLAPSE:
            return (0, 0)
        ret = (2, 1)
        if self.dir.vert: ret = ret[::-1]
        return maxpos(ret, BaseStrut.getprefsize(self))
    def draw_self(self, win):
        "Draw this widget to the given window"
        if self.visibility != VisibilityContainer.VIS_VISIBLE:
            return
        BaseStrut.draw_self(self, win)
        if self.dir.vert:
            x = self.pos[0] + int(self.size[0] * self.align[0])
            sw = win.derwin(self.size[1], 1, self.pos[1], x)
            sw.bkgd('\0', self.attr)
            sw.clear()
            if self._handle:
                sw.vline(self._handle[0] + 1, 0, '#', self._handle[1])
            sw.addch(0, 0, _curses.ACS_UARROW)
            sw.insch(self.size[1] - 1, 0, _curses.ACS_DARROW)
        else:
            y = self.pos[1] + int(self.size[1] * self.align[1])
            sw = win.derwin(1, self.size[0], y, self.pos[0])
            sw.bkgd('\0', self.attr)
            sw.clear()
            if self._handle:
                sw.hline(0, self._handle[0] + 1, '#', self._handle[1])
            sw.addch(0, 0, _curses.ACS_LARROW)
            sw.insch(0, self.size[0] - 1, _curses.ACS_RARROW)
    def event(self, event):
        """
        Handle user input events

        See Scrollable.scroll_event() for the events handled.
        """
        ret = BaseStrut.event(self, event)
        if event[0] == FocusEvent:
            self._set_focused(event[1])
        if not ret and self.bound:
            return self.bound.scroll_event(event)
        return ret
    def focus(self, rev=False):
        "Perform focus traversal"
        return (not self.focused and
                not (self.bound and self.bound.focusable) and
                self.visibility == VisibilityContainer.VIS_VISIBLE)
    def _set_focused(self, state):
        "Internal focus helper"
        if self.focused == state: return
        self.focused = state
        self.on_focuschange()
        self.invalidate()
        self.highlight(state)
    def _update_grab(self):
        "Internal cursor placement helper"
        if self.focused:
            if self._handle:
                idx = (1 if self.dir.vert else 0)
                npos = list(self.pos)
                npos[idx] += 1 + self._handle[0]
                cpos = list(npos)
                cpos[idx] += self._handle[2]
                self.grab_input(self.rect, tuple(cpos))
            else:
                self.grab_input(self.rect, self.pos)
    def on_focuschange(self):
        """
        Handle a change of the focus state
        """
        self.attr = (self.attr_active if self.focused else
            self.attr_highlight if self.highlighted else self.attr_normal)
        self._update_grab()
    def bind(self, parent):
        """
        Bind this scrollbar to the given parent

        This is equivalent to parent.bind(self). Returns the widget now bound
        to.
        """
        if parent is self.bound: return parent
        if self.bound is not None: self.unbind(self.bound)
        self.bound = parent
        parent.bind(self)
        return parent
    def unbind(self, parent):
        """
        Unbind this scrollbar from the given parent

        Equivalent to parent.unbind(self). Returns the widget unbound from.
        """
        if parent is not self.bound: return parent
        self.bound = None
        parent.unbind(self)
        return parent
    def highlight(self, active):
        """
        Change the highlighting state of this
        """
        if active == self.highlighted: return
        self.highlighted = active
        self.on_focuschange()
        self.invalidate()
        if self.bound is not None: self.bound.on_highlight(active)
    def update(self):
        """
        Update to reflect the state of the bound widget
        """
        if not self.bound: return
        idx = (1 if self.dir.vert else 0)
        offs = self.bound.scrollpos[idx]
        maxoffs = self.bound.maxscrollpos[idx]
        size = self.bound.size[idx]
        isize = self.bound.contentsize[idx]
        ssize = self.size[idx] - 2
        if isize == size or ssize == 0:
            self._handle = None
        else:
            hlen = max(size * ssize // isize, 1)
            hrem = ssize - hlen
            self._handle = ((offs * hrem + maxoffs // 2) // maxoffs,
                            hlen,
                            (offs * (hlen - 1) + maxoffs // 2) // maxoffs)
            npos = list(self.pos)
            npos[idx] += 1 + self._handle[0]
        self._update_grab()
        self.invalidate()

class Slider(BaseStrut):
    """
    A means of inputting a number from a given range

    The slider displays the chosen number proportionally within the range
    bounds. The value can be modified using the "+" and "-" characters.

    Attributes are:
    min        : The minimal value.
    max        : The maximal value.
    step       : The step the value may change with. Note that this does
                 not guarantee the value will be a multiple of that step
                 (or value-min will be one).
    value      : The (initial) value of the slider.
    attr_normal: The attribute to use when the slider is inactive.
    attr_active: The attribute to use when the slider is focused.
    """
    def __init__(self, min=0, max=1, step=None, **kwds):
        "Initializer"
        kwds.setdefault('dir', self.DIR_HORIZONTAL)
        BaseStrut.__init__(self, **kwds)
        self.min = min
        self.max = max
        self.step = step
        self._value = kwds.get('value', self.min)
        self.attr_normal = kwds.get('attr_normal', 0)
        self.attr_active = kwds.get('attr_active', _curses.A_STANDOUT)
        self.focused = False
        self.attr = self.attr_normal
    def getprefsize(self):
        "Obtain the preferred size of this widget"
        ret = (1, 1)
        if self.dir.vert: ret = ret[::-1]
        return maxpos(ret, BaseStrut.getprefsize(self))
    def _handle_pos(self):
        "Internal cursor placement helper"
        if self.min == self.max: return (0, 0)
        perc = (float(self._value) - self.min) / (self.max - self.min)
        return ((0, int((self.size[1] - 1) * perc)) if self.dir.vert else
                (int((self.size[0] - 1) * perc), 0))
    def draw_self(self, win):
        "Draw this widget to the given window"
        BaseStrut.draw_self(self, win)
        Strut.draw_strut(win, self.pos, self.size[self.dir.vert],
                         self.dir, self.attr)
        if self.min != self.max:
            rp = addpos(self.pos, self._handle_pos())
            win.addch(rp[1], rp[0], _curses.ACS_SSSS, self.attr)
    def event(self, event):
        """
        Handle an input event
        """
        ret = BaseStrut.event(self, event)
        if event[0] == '+':
            if self.step is None:
                self.change(1, True)
            else:
                self.change(1)
            return True
        elif event[0] == '-':
            if self.step is None:
                self.change(-1, True)
            else:
                self.change(-1)
            return True
        elif event[0] == FocusEvent:
            self._set_focused(event[1])
        return ret
    def focus(self, rev=False):
        "Focus traversal helper"
        return (not self.focused)
    def _set_focused(self, state):
        "Internal focusing helper"
        if self.focused == state: return
        self.focused = state
        self.on_focuschange()
        self.invalidate()
    def on_focuschange(self):
        "Handle a focus state change"
        self.attr = (self.attr_active if self.focused else self.attr_normal)
        if self.focused:
            self.grab_input(self.rect, addpos(self.pos, self._handle_pos()))
    @property
    def value(self):
        "The current value of the slider"
        return self._value
    @value.setter
    def value(self, newvalue):
        newvalue = max(self.min, min(newvalue, self.max))
        if newvalue == self._value: return
        self._value = newvalue
        if self.focused:
            self.grab_input(self.rect, addpos(self.pos, self._handle_pos()))
        self.invalidate()
    def change(self, delta, visual=False):
        """
        Change the value by the given delta

        If visual is false, the value itself is changed by delta directly;
        otherwise, it is changed such that the slider tick advances by
        approximately delta units.
        """
        if visual:
            if self.size[self.dir.vert] == 1: return
            d = (float(delta) * (self.max - self.min) /
                 (self.size[self.dir.vert] - 1))
            self.value += d
        else:
            self.value += delta

class BaseRadioGroup(object):
    """
    A group of buttons

    This class provides base methods that are specified by RadioGroup.
    """
    def __init__(self):
        "Initializer"
        self.widgets = []
    def add(self, widget):
        """
        Add the widget to this group

        If it is in any other, it is removed from there, in any case, it is
        returned.
        """
        if widget in self.widgets: return widget
        if widget.group is not None: widget.group.remove(widget)
        widget.group = self
        self.widgets.append(widget)
        return widget
    def remove(self, widget):
        """
        Remove the widget from the group and return it
        """
        if widget not in self.widgets: return widget
        widget.group = None
        self.widgets.remove(widget)
        return widget
        widget.group = None
    def on_set(self, widget, value):
        """
        Event handler invoked by the widget when its state changes
        """
        pass

class RadioGroup(BaseRadioGroup):
    """
    A group of mutually exclusive buttons

    Whenever a button's state becomes a true value, the state of the
    previously active button is set to False.
    """
    def __init__(self):
        "Initializer"
        BaseRadioGroup.__init__(self)
        self.active = None
    def add(self, widget):
        """
        Add a widget to the group

        If if is active, it becomes the group's new active widget, possibly
        disabling the previously active one.
        """
        BaseRadioGroup.add(self, widget)
        if widget.state:
            self._set_active(widget)
        return widget
    def remove(self, widget):
        """
        Remove a widget from the group

        If the widget was the active one, it is deactivated.
        """
        BaseRadioGroup.remove(self, widget)
        if widget is self.active:
            self._set_active(None)
        return widget
    def _set_active(self, widget):
        "Actually update the currently active widget"
        if widget is self.active: return
        if self.active:
            self.active.state = False
        self.active = widget
        if self.active:
            self.active.state = True
    def on_set(self, widget, value):
        """
        Event handler invoked by widgets changing their state

        This method actually enforces the mutual exclusion constraint.
        """
        if not value: return
        self._set_active(widget)

def init():
    """
    Initialize the library

    Should be called once before performing any actions.

    WARNING: This modifies the module's global state, and the program-wide
             locale.
    """
    global _ENCODING
    _locale.setlocale(_locale.LC_ALL, '')
    _ENCODING = _locale.getpreferredencoding(True)

def mainloop(scr):
    "Inner function of the debugging routine"
    class DebugStrut(Widget):
        def __init__(self, **kwds):
            Widget.__init__(self, **kwds)
            self.min_size = kwds.get('min_size', None)
            self.pref_size = kwds.get('pref_size', None)
        def getminsize(self):
            if self.min_size is None:
                return Widget.getminsize(self)
            else:
                return self.min_size
        def getprefsize(self):
            if self.pref_size is None:
                return Widget.getprefsize(self)
            else:
                return self.pref_size
    def text_changer():
        btnt.text = 'test... 42'
    def text_back_changer():
        btnt.text = 'test...'
    def wr_make():
        make_counter[0] += 1
        twgc.text = str(make_counter[0])
        WidgetRoot.make(wr)
    def grow():
        stru.pref_size[0] += 1
        stru.pref_size[1] += 1
        stru.min_size[0] += 1
        stru.min_size[1] += 1
        stru.invalidate_layout()
    def shrink():
        stru.pref_size[0] -= 1
        stru.pref_size[1] -= 1
        stru.min_size[0] -= 1
        stru.min_size[1] -= 1
        stru.invalidate_layout()
    import sys
    make_counter = [0]
    wr = WidgetRoot(scr)
    wr.make = wr_make
    grp = RadioGroup()
    _curses.init_pair(1, _curses.COLOR_WHITE, _curses.COLOR_BLUE)
    _curses.init_pair(2, _curses.COLOR_BLACK, _curses.COLOR_WHITE)
    _curses.init_pair(3, _curses.COLOR_BLACK, _curses.COLOR_RED)
    _curses.init_pair(4, _curses.COLOR_GREEN, _curses.COLOR_BLACK)
    _curses.init_pair(5, _curses.COLOR_WHITE, _curses.COLOR_RED)
    rv = wr.add(Viewport())
    obx = rv.add(BoxContainer(margin=None, border=(0, 0, 0, 1),
                              padding=(1, 2),
                              attr_margin=_curses.color_pair(1),
                              attr_box=_curses.color_pair(4)))
    box = obx.add(MarginContainer(border=True,
                                  background=_curses.color_pair(2)))
    top = box.add(TeeContainer(attrs=_curses.color_pair(2)),
                  slot=MarginContainer.POS_TOP)
    hdr = top.add(Label('cwidgets test', attr=_curses.color_pair(2)))
    lo = box.add(HorizontalContainer())
    c1 = lo.add(VerticalContainer())
    btnt = c1.add(Button('test', text_changer))
    chb1 = c1.add(CheckBox('NOP'))
    spc1 = c1.add(Widget(), weight=1)
    btne = c1.add(Button('exit', sys.exit,
                         attr_normal=_curses.color_pair(3)))
    s1 = lo.add(Strut(Strut.DIR_VERTICAL, attr=_curses.color_pair(2),
                      margin=(0, 1)))
    c2 = lo.add(VerticalContainer())
    btnr = c2.add(Button('----------------\nback\n----------------',
                         text_back_changer, align=ALIGN_CENTER,
                         background=_curses.color_pair(3), border=0),
                  weight=1)
    s2 = c2.add(Strut(Strut.DIR_HORIZONTAL, attr=_curses.color_pair(2)))
    tvc = c2.add(MarginContainer(border=1,
                                 background=_curses.color_pair(2)))
    tvph = tvc.add(TeeContainer(align=ALIGN_LEFT,
                                attrs=_curses.color_pair(2)),
                   slot=MarginContainer.POS_TOP)
    tvpl = tvph.add(Label('entry test', attr=_curses.color_pair(2)))
    entr = tvc.add(EntryBox(multiline=True, cmaxsize=(60, 10),
                            attr_normal=_curses.color_pair(1)))
    tvv = tvc.add(entr.bind(Scrollbar(Scrollbar.DIR_VERTICAL,
                                      attr_highlight=_curses.color_pair(5))),
                  slot=MarginContainer.POS_RIGHT)
    tvh = tvc.add(entr.bind(Scrollbar(Scrollbar.DIR_HORIZONTAL,
                                      attr_highlight=_curses.color_pair(5))),
                  slot=MarginContainer.POS_BOTTOM)
    vpc = c2.add(MarginContainer(border=1,
                                 background=_curses.color_pair(2)))
    vpt = vpc.add(TeeContainer(align=ALIGN_RIGHT,
                               attrs=_curses.color_pair(2)),
                  slot=MarginContainer.POS_TOP)
    vptl = vpt.add(Label('scrolling test',
                         attr=_curses.color_pair(2)))
    vp = vpc.add(Viewport(background=_curses.color_pair(1),
                          cmaxsize=(60, 10)), weight=1)
    sbv = vpc.add(vp.bind(Scrollbar(Scrollbar.DIR_VERTICAL,
                                    attr_highlight=_curses.color_pair(5))),
                  slot=MarginContainer.POS_RIGHT)
    sbh = vpc.add(vp.bind(Scrollbar(Scrollbar.DIR_HORIZONTAL,
                                    attr_highlight=_curses.color_pair(5))),
                  slot=MarginContainer.POS_BOTTOM)
    gbox = vp.add(BoxContainer(margin=(1, 2),
                               attr_margin=_curses.color_pair(1),
                               attr_box=_curses.color_pair(2)))
    grid = gbox.add(GridContainer(mode_x=LinearContainer.MODE_EQUAL))
    rdb2 = grid.add(grp.add(RadioBox('grow', callback=grow)),
                    pos=(0, 0))
    rdb3 = grid.add(grp.add(RadioBox('shrink', callback=shrink)),
                    pos=(3, 2))
    twgc = grid.add(Label(background=_curses.color_pair(3),
                          align=ALIGN_CENTER), pos=(2, 0))
    lbl1 = grid.add(Label('[3,3]', align=ALIGN_RIGHT,
                          background=_curses.color_pair(3)),
                    pos=(3, 3))
    lbl2 = grid.add(Label('[0,3]'), pos=(0, 3))
    chw1 = grid.add(AlignContainer(), pos=(4, 1))
    chb2 = chw1.add(CheckBox())
    stru = grid.add(DebugStrut(pref_size=[20, 0], min_size=[10, 0]),
                    pos=(1, 1))
    grid.config_col(0)
    grid.config_col(1, minsize=1)
    grid.config_col(2, weight=1)
    grid.config_col(3)
    grid.config_row(1, weight=1)
    wtc = c2.add(MarginContainer(border=1, background=_curses.color_pair(0)))
    wtlc = wtc.add(TeeContainer(align=0.25), slot=MarginContainer.POS_TOP)
    wtl = wtlc.add(Label('further widget tests'))
    sld1 = wtc.add(Slider(0, 10, 1))
    wr.main()

def main():
    """
    Debugging main function

    Invoked when cwidgets is run as a script.
    """
    try:
        init()
        _curses.wrapper(mainloop)
    finally:
        if _LOG:
            _LOG.append('')
            import sys
            sys.stderr.write('\n'.join(map(str, LOG)))
            sys.stderr.flush()

if __name__ == '__main__': main()
