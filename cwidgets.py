#!/usr/bin/env python3
# -*- coding: ascii -*-

# *** Minimalistic curses-based widget library for Python ***

import curses as _curses

_KEY_RETURN = ord('\n')
_KEY_TAB = ord('\t')
_KEY_SPACE = ord(' ')

#LOG = []

def addpos(p1, p2):
    return (p1[0] + p2[0], p1[1] + p2[1])
def subpos(p1, p2):
    return (p1[0] - p2[0], p1[1] - p2[1])
def minpos(p1, p2):
    return (min(p1[0], p2[0]), min(p1[1], p2[1]))
def maxpos(p1, p2):
    return (max(p1[0], p2[0]), max(p1[1], p2[1]))
def shiftrect(r, p):
    return (r[0] + p[0], r[1] + p[1], r[2], r[3])
def unshiftrect(r, p):
    return (r[0] - p[0], r[1] - p[1], r[2], r[3])

def linear_distrib(full, amnt):
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
    try:
        v = tuple(v)
    except TypeError:
        v = (v, v)
    return (default[0] if v[0] is None else v[0],
            default[1] if v[1] is None else v[1])
def parse_quad(v, default=(None, None, None, None)):
    try:
        v = tuple(v)
    except TypeError:
        v = (v,)
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
    return inflate(rect, margin, -mul)

class Singleton:
    def __init__(self, __name__, **__dict__):
        self.__dict__ = __dict__
        self.__name__ = __name__
    def __repr__(self):
        return '<%s>' % (self.__name__,)
    def __str__(self):
        return str(self.__name__)

class Event(Singleton): pass
FocusEvent = Event('FocusEvent')

class Alignment(Singleton, float):
    def __new__(cls, __value__, __name__, **__dict__):
        return float.__new__(cls, __value__)
    def __init__(self, __value__, __name__, **__dict__):
        Singleton.__init__(self, __name__, **__dict__)
ALIGN_TOP = Alignment(0.0, 'ALIGN_TOP')
ALIGN_LEFT = Alignment(0.0, 'ALIGN_LEFT')
ALIGN_CENTER = Alignment(0.5, 'ALIGN_CENTER')
ALIGN_RIGHT = Alignment(1.0, 'ALIGN_RIGHT')
ALIGN_BOTTOM = Alignment(1.0, 'ALIGN_BOTTOM')

class WidgetRoot(object):
    def __init__(self, window):
        self.window = window
        self.widget = None
        self._cursorpos = None
        self.valid_display = False
        self.valid_layout = False
    def make(self):
        if not self.widget is None:
            hw = self.window.getmaxyx()
            self.widget.pos = (0, 0)
            self.widget.size = (hw[1], hw[0])
            self.widget.make()
        self.valid_layout = True
        self.invalidate()
    def redraw(self):
        if not self.widget is None:
            self.widget.draw(self.window)
            if self._cursorpos is None:
                _curses.curs_set(0)
                self.window.refresh()
            else:
                self.window.refresh()
                _curses.curs_set(1)
                _curses.setsyx(self._cursorpos[1], self._cursorpos[0])
                _curses.doupdate()
        self.valid_display = True
    def grab_input(self, rect, pos=None, child=None, full=False):
        self._cursorpos = pos
    def event(self, event):
        if event[0] == _KEY_TAB:
            return self.focus()
        elif event[0] == _curses.KEY_BTAB:
            return self.focus(True)
        if not self.widget is None:
            return self.widget.event(event)
        return False
    def focus(self, rev=False):
        if self.widget is None:
            return False
        if not self.widget.focus(rev):
            if not self.widget.focus(rev):
                return False
        return True
    def invalidate(self, rec=False, child=None):
        if rec:
            self.valid_display = False
            self.widget.invalidate(rec)
            return
        if not self.valid_display: return
        self.valid_display = False
        self.widget.invalidate()
    def invalidate_layout(self):
        if not self.valid_layout: return
        self.valid_layout = False
        self.widget.invalidate_layout()
    def add(self, widget):
        if widget is self.widget: return
        widget.delete()
        self.widget = widget
        widget.parent = self
        return widget
    def remove(self, widget):
        if widget is self.widget:
            self.widget = None
            widget.parent = None
    def main(self):
        while 1:
            if not self.valid_layout:
                self.make()
            if not self.valid_display:
                self.redraw()
            ch = self.window.getch()
            if ch == _curses.KEY_RESIZE:
                self.invalidate_layout()
            elif ch == _curses.KEY_MOUSE:
                self.event((ch, _curses.getmouse()))
            else:
                self.event((ch,))

class Widget(object):
    def __init__(self, **kwds):
        self.minsize = kwds.get('minsize', (0, 0))
        self.parent = None
        self.pos = None
        self.size = None
        self.valid_display = False
        self.valid_layout = False
        self.grabbing = None
        self.grabbing_full = False
        self.cursor_pos = None
    @property
    def rect(self):
        return (self.pos[0], self.pos[1], self.size[0], self.size[1])
    def getminsize(self):
        return self.getprefsize()
    def getprefsize(self):
        return self.minsize
    def make(self):
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
        self.valid_display = True
    def grab_input(self, rect, pos=None, child=None, full=False):
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
        if event[0] == FocusEvent and not event[1]:
            self.grabbing = None
            self.grabbing_full = False
            self.cursor_pos = None
        return False
    def focus(self, rev=False):
        return False
    def invalidate(self, rec=False, child=None):
        ov, self.valid_display = self.valid_display, False
        if ov: self.parent.invalidate(child=self)
    def invalidate_layout(self):
        ov, self.valid_layout = self.valid_layout, False
        if ov: self.parent.invalidate_layout()
    def _delete_layout(self):
        if self.parent is not None:
            self.parent.remove(self)
    def delete(self):
        self._delete_layout()

class Container(Widget):
    def __init__(self, **kwds):
        Widget.__init__(self, **kwds)
        self.children = []
        self._focused = None
        self._cprefsize = None
        self._cminsize = None
    def getminsize(self):
        if not self._cminsize:
            self._cminsize = self.layout_minsize()
        return maxpos(self.minsize, self._cminsize)
    def getprefsize(self):
        if not self._cprefsize:
            self._cprefsize = self.layout_prefsize()
        return maxpos(self.minsize, self._cprefsize)
    def layout_minsize(self):
        wh = (0, 0)
        for i in self.children: wh = maxpos(wh, i.getminsize())
        return wh
    def layout_prefsize(self):
        wh = (0, 0)
        for i in self.children: wh = maxpos(wh, i.getprefsize())
        return wh
    def make(self):
        if self.valid_layout: return
        self.relayout()
        for i in self.children:
            i.make()
        Widget.make(self)
    def relayout(self):
        for i in self.children:
            i.pos = self.pos
            i.size = minpos(self.size, i.getprefsize())
    def draw(self, win):
        if self.valid_display: return
        for i in self.children:
            i.draw(win)
        Widget.draw(self, win)
    def event(self, event):
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
        Widget.invalidate(self, rec, child)
        if rec:
            for i in self.children:
                i.invalidate(rec)
    def invalidate_layout(self):
        Widget.invalidate_layout(self)
        self._cminsize = None
        self._cprefsize = None
        for w in self.children:
            w.invalidate_layout()
    def _refocus(self, new):
        if new is self._focused: return
        if self._focused is not None:
            self._focused.event((FocusEvent, False))
        self._focused = new
        if self._focused is not None:
            self._focused.event((FocusEvent, True))
    def add(self, widget, **config):
        widget._delete_layout()
        self.children.append(widget)
        widget.parent = self
        self.invalidate_layout()
        return widget
    def remove(self, widget):
        self.children.remove(widget)
        if self._focused is widget:
            self._focused = None
        widget.parent = None
        self.invalidate_layout()
    def clear(self):
        for i in self.children[:]:
            self.remove(i)

class SingleContainer(Container):
    def __init__(self, **kwds):
        Container.__init__(self, **kwds)
        self.cmaxsize = kwds.get('cmaxsize', (None, None))
        self._chms = None
        self._chps = None
    def _child_minsize(self, **kwds):
        if self._chms is not None:
            pass
        elif not self.children:
            self._chms = (0, 0)
        else:
            c, cms = self.children[0].getminsize(), self.cmaxsize
            self._chms = (min(c[0], cms[0]) if cms[0] is not None else c[0],
                          min(c[1], cms[1]) if cms[1] is not None else c[1])
        return self._chms
    def _child_prefsize(self):
        if self._chps is not None:
            pass
        elif not self.children:
            self._chps = (0, 0)
        else:
            c, cms = self.children[0].getprefsize(), self.cmaxsize
            self._chps = (min(c[0], cms[0]) if cms[0] is not None else c[0],
                          min(c[1], cms[1]) if cms[1] is not None else c[1])
        return self._chps
    def add(self, widget, **config):
        while self.children:
            self.remove(self.children[0])
        return Container.add(self, widget, **config)
    def invalidate_layout(self):
        Container.invalidate_layout(self)
        self._chms = None
        self._chps = None

class VisibilityContainer(SingleContainer):
    class Visibility(Singleton): pass
    VIS_VISIBLE = Visibility('VIS_VISIBLE')
    VIS_HIDDEN = Visibility('VIS_HIDDEN')
    VIS_COLLAPSE = Visibility('VIS_COLLAPSE')
    def __init__(self, **kwds):
        SingleContainer.__init__(self, **kwds)
        self.visibility = kwds.get('visibility', self.VIS_VISIBLE)
    def getprefsize(self):
        if self.visibility == self.VIS_COLLAPSE:
            return (0, 0)
        else:
            return SingleContainer.getprefsize(self)
    def draw(self, win):
        if self.visibility != self.VIS_VISIBLE or self.valid_display:
            return
        self.draw_inner(win)
    def draw_inner(self, win):
        SingleContainer.draw(self, win)

class BoxContainer(VisibilityContainer):
    class ScalePolicy(Singleton): pass
    # Leave widget at preferred size.
    SCALE_PREFERRED = ScalePolicy('SCALE_PREFERRED')
    # Push widget to minimum of preferred size and available size.
    SCALE_COMPRESS = ScalePolicy('SCALE_COMPRESS')
    # Stretch widget to maximum of preferred size and available size.
    SCALE_STRETCH = ScalePolicy('SCALE_STRETCH')
    # Force widget to fit available size.
    SCALE_FIT = ScalePolicy('SCALE_FIT')
    @classmethod
    def calc_pads_1d(cls, outer, margin, border, padding, size, minsize):
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
        pdsx = cls.calc_pads_1d(outer[0], margin[3::-2], border[3::-2],
                                padding[3::-2], size[0], minsize[0])
        pdsy = cls.calc_pads_1d(outer[1], margin[::2], border[::2],
                                padding[::2], size[1], minsize[1])
        return ((pdsx[0][0], pdsy[0][0], pdsx[0][1], pdsy[0][1]),
                (pdsx[1][0], pdsy[1][0], pdsx[1][1], pdsy[1][1]))
    def __init__(self, **kwds):
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
        # Lambda calculus!
        x = lambda d: lambda k: (lambda v: 0 if v is None else v)(d[k])
        m, b, p = x(self.margin), x(self.border), x(self.padding)
        return (m(0) + bool(b(0)) + p(0),
                m(1) + bool(b(1)) + p(1),
                m(2) + bool(b(2)) + p(2),
                m(3) + bool(b(3)) + p(3))
    def layout_minsize(self):
        chms, ins = self._child_minsize(), self.calc_insets()
        return inflate(chms, ins)
    def layout_prefsize(self):
        chps, ins = self._child_prefsize(), self.calc_insets()
        return inflate(chps, ins)
    def relayout(self):
        chps, chms = self._child_prefsize(), self._child_minsize()
        br, wr = self.calc_pads(self.size, self.margin,
            list(map(bool, self.border)), self.padding, chps, chms)
        self._box_rect = shiftrect(br, self.pos)
        self._widget_rect = shiftrect(wr, self.pos)
        if self.children:
            self.children[0].pos = self._widget_rect[:2]
            self.children[0].size = self._widget_rect[2:]
    def draw_inner(self, win):
        BoxWidget.draw_box(win, self.pos, self.size, self.attr_margin,
                           self.ch_margin, False)
        BoxWidget.draw_box(win, self._box_rect[:2], self._box_rect[2:],
                           self.attr_box, self.ch_box, self.border)
        VisibilityContainer.draw_inner(self, win)
    def invalidate(self, rec=False, child=None):
        VisibilityContainer.invalidate(self, True, child)
    def invalidate_layout(self):
        VisibilityContainer.invalidate_layout(self)
        self._box_rect = None
        self._widget_rect = None

class AlignContainer(VisibilityContainer):
    @classmethod
    def calc_wbox_1d(cls, pref, avl, scale, align):
        if avl == pref or scale == cls.SCALE_PREFERRED:
            size = pref
        elif scale == cls.SCALE_COMPRESS:
            size = min(pref, avl)
        elif scale == cls.SCALE_STRETCH:
            size = max(pref, avl)
        elif scale == cls.SCALE_FIT:
            size = avl
        else:
            raise ValueError('Invalid scale for calc_wbox()')
        return (int((avl - size) * align), size)
    @classmethod
    def calc_wbox(cls, pref, avl, scale, align, pos=(0, 0)):
        return shiftrect(sum(zip(
            cls.calc_wbox_1d(pref[0], avl[0], scale[0], align[0]),
            cls.calc_wbox_1d(pref[1], avl[1], scale[1], align[1])
            ), ()), pos)
    def __init__(self, **kwds):
        VisibilityContainer.__init__(self, **kwds)
        self.scale = parse_pair(kwds.get('scale', self.SCALE_FIT))
        self.align = parse_pair(kwds.get('scale', ALIGN_CENTER))
        self._wbox = None
    def relayout(self):
        if self._wbox is None:
            chps = self._child_prefsize()
            self._wbox = self.calc_wbox(chps, self.size, self.scale,
                                        self.align, self.pos)
        if self.children:
            self.children[0].pos = self._wbox[:2]
            self.children[0].size = self._wbox[2:]
    def invalidate_layout(self):
        VisibilityContainer.invalidate_layout(self)
        self._wbox = None

class Viewport(SingleContainer):
    @classmethod
    def calc_shift(cls, offset, size, rect):
        ret = list(offset)
        br = subpos(addpos(rect[:2], rect[2:]), size)
        if ret[0] < br[0]: ret[0] = br[0]
        if ret[1] < br[1]: ret[1] = br[1]
        if ret[0] > rect[0]: ret[0] = rect[0]
        if ret[1] > rect[1]: ret[1] = rect[1]
        return ret
    def __init__(self, **kwds):
        SingleContainer.__init__(self, **kwds)
        self.restrict_size = kwds.get('restrict_size', True)
        self.default_attr = kwds.get('default_attr', None)
        self.default_ch = kwds.get('default_ch', '\0')
        self.background = kwds.get('background', None)
        self.background_ch = kwds.get('background_ch', '\0')
        self.scrollpos = [0, 0]
        self.maxscrollpos = (0, 0)
        self._pad = None
    def getminsize(self):
        ps, ms = SingleContainer.getminsize(self), self.cmaxsize
        return ((ps[0] if ms[0] is None else min(ps[0], ms[0])),
                (ps[1] if ms[1] is None else min(ps[1], ms[1])))
    def getprefsize(self):
        ps, ms = SingleContainer.getprefsize(self), self.cmaxsize
        return ((ps[0] if ms[0] is None else min(ps[0], ms[0])),
                (ps[1] if ms[1] is None else min(ps[1], ms[1])))
    def relayout(self):
        chps, chms = self._child_prefsize(), self._child_minsize()
        if self.children:
            if self.restrict_size:
                chs = maxpos(minpos(self.size, chps), chms)
            else:
                chs = chps
            self.children[0].pos = (0, 0)
            self.children[0].size = maxpos(self.size, chs)
    def draw(self, win):
        if self.valid_display: return
        Widget.draw(self, win)
        if not self.children:
            chsz = self.size
        else:
            chsz = maxpos(self.children[0].size, self.size)
        if self._pad is None:
            self._pad = _curses.newpad(chsz[1], chsz[0])
            if self.default_attr is not None:
                self._pad.bkgd(self.default_ch, self.default_attr)
            pad_changed = True
        else:
            padsz = self._pad.getmaxyx()
            if padsz[1] != chsz[0] or padsz[0] != chsz[1]:
                self._pad.resize(chsz[1], chsz[0])
                pad_changed = True
            else:
                pad_changed = False
        if pad_changed:
            self.maxscrollpos = subpos(self._pad.getmaxyx()[::-1],
                                       self.size)
            if self.background is not None:
                fill = self._pad.derwin(0, 0)
                fill.bkgd(self.background_ch, self.background)
                fill.clear()
            if self.children:
                self.children[0].invalidate(True)
        if self.children:
            self.children[0].draw(self._pad)
        sp = minpos(self.scrollpos, self.maxscrollpos)
        self.scrollpos[:] = sp
        self._pad.overwrite(win, sp[1], sp[0], self.pos[1], self.pos[0],
                            self.pos[1] + self.size[1] - 1,
                            self.pos[0] + self.size[0] - 1)
    def grab_input(self, rect, pos=None, child=None, full=False):
        if rect is not None:
            new_offset = self.calc_shift(self.scrollpos, self.size, rect)
            if new_offset != self.scrollpos:
                self.invalidate()
            self.scrollpos[:] = new_offset
            effpos = addpos(self.pos, new_offset)
            rect = shiftrect(rect, effpos)
        else:
            effpos = addpos(self.pos, self.scrollpos)
        if pos is not None: pos = addpos(effpos, pos)
        SingleContainer.grab_input(self, rect, pos, child, full)
    def invalidate(self, rec=False, child=None):
        # Child is rendered to offscreen pad, and cannot be invalidated
        # by anything that happens to me (invalidated in draw() if
        # necessary).
        Widget.invalidate(self, rec, child)
    def invalidate_layout(self):
        SingleContainer.invalidate_layout(self)
        self._pad = None

class StackContainer(Container):
    def __init__(self, **kwds):
        Container.__init__(self, **kwds)
        self._layers = {}
    def layout_minsize(self):
        wh = (0, 0)
        for i in self.children: wh = maxpos(wh, i.getminsize())
        return wh
    def relayout(self):
        ps = self.getprefsize()
        for w in self.children:
            w.pos = self.pos
            w.size = self.size
    def invalidate(self, rec=False, child=None):
        if child in self.children:
            Container.invalidate(self, rec, child)
            idx = self.children.index(child)
            for i in self.children[idx + 1:]:
                i.invalidate(True)
        else:
            Container.invalidate(self, True, child)
    def add(self, widget, **config):
        Container.add(self, widget, **config)
        self._layers[widget] = config.get('layer', 0)
        self.children.sort(key=self._layers.__getitem__)
        return widget
    def remove(self, widget):
        Container.remove(self, widget)
        del self._layers[widget]
    def set_layer(self, widget, layer):
        self._layers[widget] = layer
        self.children.sort(key=self._layers.__getitem__)

class PlacerContainer(StackContainer):
    def __init__(self, **kwds):
        StackContainer.__init__(self, **kwds)
        self._positions = {}
        self._sizes = {}
    def layout_prefsize(self):
        wh = (0, 0)
        for i in self.children:
            s = self._sizes.get(i)
            if not s: s = i.getprefsize()
            wh = maxpos(wh, addpos(self._positions[i], s))
        return wh
    def relayout(self):
        for w in self.children:
            w.pos = addpos(self.pos, self._positions[w])
            s = self._sizes[w]
            if s is None:
                w.size = w.getprefsize()
            else:
                w.size = s
    def add(self, widget, **config):
        self._positions[widget] = config['pos']
        self._sizes[widget] = config.get('size')
        return StackContainer.add(self, widget, **config)
    def remove(self, widget):
        StackContainer.remove(self, widget)
        del self._positions[widget]
        del self._sizes[widget]

class MarginContainer(Container):
    class Position(Singleton): pass
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
        Container.__init__(self, **kwds)
        self.border = parse_quad(kwds.get('border', False))
        self.insets = parse_quad(kwds.get('insets', 0))
        self.background = kwds.get('background', None)
        self.background_ch = kwds.get('background_ch', '\0')
        self._slots = {}
        self._revslots = {}
        self._minsize = None
        self._prefsize = None
        self._presizes = None
        self._boxes = None
    def layout_minsize(self):
        self._make_preboxes()
        return self._minsize
    def layout_prefsize(self):
        self._make_preboxes()
        return self._prefsize
    def relayout(self):
        self._make_boxes(self.size)
        for w, pos, size in self._boxes:
            w.pos = addpos(self.pos, pos)
            w.size = size
    def invalidate_layout(self):
        Container.invalidate_layout(self)
        self._minsize = None
        self._prefsize = None
        self._presizes = None
        self._boxes = None
    def draw(self, win):
        if self.valid_display: return
        BoxWidget.draw_box(win, self.pos, self.size, self.background,
                           self.background_ch, self.border)
        Container.draw(self, win)
    def add(self, widget, **config):
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
        Container.remove(self, widget)
        del self._revslots[self._slots[widget]]
        del self._slots[widget]
    def _make_preboxes(self):
        if self._presizes is not None: return
        if not self.children:
            self._minsize = inflate((0, 0), self.insets)
            self._prefsize = inflate((0, 0), self.insets)
            self._presizes = ((0, 0, 0),) * 4
            return
        mws, mhs = [0, 0, 0], [0, 0, 0]
        pws, phs = [0, 0, 0], [0, 0, 0]
        for w, slot in self._slots.items():
            ms, ps = w.getminsize(), w.getprefsize()
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
    class Rule(Singleton): pass
    RULE_STAY = Rule('RULE_STAY', advances=(0, 0))
    RULE_RIGHT = Rule('RULE_RIGHT', advances=(1, 0))
    RULE_DOWN = Rule('RULE_DOWN', advances=(0, 1))
    RULE_DIAG = Rule('RULE_DIAG', advances=(1, 1))
    class Mode(Singleton): pass
    MODE_NORMAL = Mode('MODE_NORMAL')
    MODE_STRETCH = Mode('MODE_STRETCH')
    MODE_EQUAL = Mode('MODE_EQUAL')
    MODE_EQUAL_FORCE = Mode('MODE_EQUAL_FORCE')
    @classmethod
    def _make_groups(cls, initial, mins, advances, weights, sweights):
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
        return sum(((v,) * l for v, l in zip(values, lengths)), ())
    @classmethod
    def _shrink(cls, r, full, gmins, gsweights):
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
        self._prefsize = None
        self._minsize = None
        self._boxes = None
    def layout_minsize(self):
        self._make_preboxes()
        return self._minsize
    def layout_prefsize(self):
        self._make_preboxes()
        return self._prefsize
    def relayout(self):
        self._make_boxes(self.size)
        for w, xy, wh in self._boxes:
            w.pos = addpos(self.pos, xy)
            w.size = wh
    def invalidate_layout(self):
        Container.invalidate_layout(self)
        self._preboxes = None
        self._prefsize = None
        self._minsize = None
        self._boxes = None
    def add(self, widget, **config):
        self._rules[widget] = config.get('rule', self.default_rule)
        w = config.get('weight', 0.0)
        self._weights_x[widget] = config.get('weight_x', w)
        self._weights_y[widget] = config.get('weight_y', w)
        sw = config.get('sweight', 1.0)
        self._sweights_x[widget] = config.get('sweight_x', sw)
        self._sweights_y[widget] = config.get('sweight_y', sw)
        return Container.add(self, widget, **config)
    def remove(self, widget):
        Container.remove(self, widget)
        del self._rules[widget]
        del self._weights_x[widget]
        del self._weights_y[widget]
        del self._sweights_x[widget]
        del self._sweights_y[widget]
    def _make_preboxes(self):
        if self._preboxes is not None: return
        cpp, cpm, mps, mms = (0, 0), (0, 0), (0, 0), (0, 0)
        amnt, tps, tms = [0, 0], (0, 0), (0, 0)
        self._preboxes = []
        for w in self.children:
            ps, ms, r = w.getprefsize(), w.getminsize(), self._rules[w]
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
        if self._boxes is not None: return
        self._make_preboxes()
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
    def __init__(self, **kwds):
        if 'mode' in kwds: kwds.setdefault('mode_x', kwds['mode'])
        LinearContainer.__init__(self, default_rule=self.RULE_RIGHT, **kwds)

class VerticalContainer(LinearContainer):
    def __init__(self, **kwds):
        if 'mode' in kwds: kwds.setdefault('mode_y', kwds['mode'])
        LinearContainer.__init__(self, default_rule=self.RULE_DOWN, **kwds)

class GridContainer(Container):
    def __init__(self, **kwds):
        Container.__init__(self, **kwds)
        self.mode_x = kwds.get('mode_x', LinearContainer.MODE_STRETCH)
        self.mode_y = kwds.get('mode_y', LinearContainer.MODE_STRETCH)
        self._widgets = {}
        self._places = {}
        self._columnConfig = {}
        self._rowConfig = {}
        self._presizes = None
        self._minsizes = None
        self._prefsize = None
        self._minsize = None
        self._offsets = None
        self._sizes = None
    def layout_minsize(self):
        self._make_presizes()
        return self._minsize
    def layout_prefsize(self):
        self._make_presizes()
        return self._prefsize
    def relayout(self):
        self._make_sizes(self.size)
        ofx, ofy = self._offsets
        szx, szy = self._sizes
        for pos, w in self._widgets.items():
            w.pos = addpos(self.pos, (ofx[pos[0]], ofy[pos[1]]))
            w.size = (szx[pos[0]], szy[pos[1]])
    def invalidate_layout(self):
        Container.invalidate_layout(self)
        self._presizes = None
        self._minsizes = None
        self._prefsize = None
        self._minsize = None
        self._sizes = None
    def add(self, widget, **config):
        pos = config['pos']
        try:
            self.remove(self._widgets[pos])
        except KeyError:
            pass
        self._widgets[pos] = widget
        self._places[widget] = pos
        return Container.add(self, widget, **config)
    def remove(self, widget):
        Container.remove(self, widget)
        pos = self._places.pop(widget)
        del self._widgets[pos]
    def _config(self, d, idx, kwds):
        conf = d.setdefault(idx, {'weight': 0, 'sweight': 1, 'minsize': 0})
        if 'weight' in kwds:
            conf['weight'] = kwds['weight']
        if 'sweight' in kwds:
            conf['sweight'] = kwds['sweight']
        if 'minsize' in kwds:
            conf['minsize'] = kwds['minsize']
        self.invalidate_layout()
    def config_row(self, row, **kwds):
        self._config(self._rowConfig, row, kwds)
    def config_col(self, col, **kwds):
        self._config(self._columnConfig, col, kwds)
    def _make_presizes(self):
        if self._presizes is not None: return
        psx, psy, msx, msy = [], [], [], []
        for pos, w in self._widgets.items():
            x, y = pos
            xp1, yp1 = x + 1, y + 1
            while len(psx) < xp1: psx.append(0)
            while len(msx) < xp1: msx.append(0)
            while len(psy) < yp1: psy.append(0)
            while len(msy) < yp1: msy.append(0)
            wps, wms = w.getprefsize(), w.getminsize()
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
    @staticmethod
    def draw_box(win, pos, size, attr, ch, border):
        if pos[0] < 0 or pos[1] < 0 or size[0] <= 0 or size[1] <= 0:
            return
        try:
            sw = win.derwin(size[1], size[0], pos[1], pos[0])
        except _curses.error:
            return
        if not attr is None:
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
        Widget.__init__(self, **kwds)
        self.background = kwds.get('background', None)
        self.background_ch = kwds.get('background_ch', '\0')
        self.border = kwds.get('border', False)
    def draw(self, win):
        if self.valid_display: return
        Widget.draw(self, win)
        self.draw_box(win, self.pos, self.size, self.background,
            self.background_ch, self.border)

class TextWidget(BoxWidget):
    def __init__(self, text='', **kwds):
        BoxWidget.__init__(self, **kwds)
        self.attr = kwds.get('attr', 0)
        self.textbg = kwds.get('textbg', Ellipsis)
        self.textbgch = kwds.get('textbgch', '\0')
        self.align = parse_pair(kwds.get('align'), (ALIGN_LEFT, ALIGN_TOP))
        self._text = None
        self._lines = ()
        self._indents = ()
        self._vindent = 0
        self._prefsize = (0, 0)
        self.text = text
    def getprefsize(self):
        return maxpos(self.minsize, self._prefsize)
    def make(self):
        BoxWidget.make(self)
        i = (1 if self.border else 0)
        ew = (self.size[0] - len(self._text_prefix()) -
              len(self._text_suffix()) - 2 * i)
        eh = self.size[1] - 2 * i
        self._indents = tuple(int((ew - len(l)) * self.align[0])
                              for l in self._lines)
        self._vindent = int((eh - len(self._lines)) * self.align[0])
    def draw(self, win):
        if self.valid_display: return
        BoxWidget.draw(self, win)
        i = (1 if self.border else 0)
        pref = self._text_prefix()
        suff = self._text_suffix()
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
        for d, l in zip(self._indents[:h], self._lines[:h]):
            win.addnstr(y + i, x + i + d, l, w, self.attr)
            y += 1
        win.addstr(self.pos[1] + i, self.pos[0] + i, pref,
                   self.attr)
        if suff:
            win.addstr(self.pos[1] + i + h - 1,
                       self.pos[0] + i + w + len(pref),
                       suff, self.attr)
    def _text_prefix(self):
        return ''
    def _text_suffix(self):
        return ''
    @property
    def text(self):
        return self._text
    @text.setter
    def text(self, text):
        if text == self._text: return
        self._text = text
        self._lines = text.split('\n')
        ps = [0, 0]
        if len(self._lines) != 0:
            ps = [max(len(i) for i in self._lines), len(self._lines)]
        if self.border:
            ps[0] += 2
            ps[1] += 2
        ps[0] += len(self._text_prefix()) + len(self._text_suffix())
        self._prefsize = tuple(ps)
        self.invalidate_layout()

class Label(TextWidget): pass

class Button(TextWidget):
    def __init__(self, text='', callback=None, **kwds):
        TextWidget.__init__(self, text, **kwds)
        self.attr_normal = kwds.get('attr_normal', 0)
        self.attr_active = kwds.get('attr_active', _curses.A_STANDOUT)
        self.focused = False
        self.callback = callback
        self.attr = self.attr_normal
        self._raw_text = None
    def event(self, event):
        ret = TextWidget.event(self, event)
        if event[0] in (_KEY_RETURN, _KEY_SPACE):
            self.on_activate()
            return True
        elif event[0] == FocusEvent:
            self._set_focused(event[1])
        return ret
    def focus(self, rev=False):
        return (not self.focused)
    def _text_prefix(self):
        return '<'
    def _text_suffix(self):
        return '>'
    def _set_focused(self, state):
        if self.focused == state: return
        self.focused = state
        self.on_focuschange()
        self.invalidate()
    def on_focuschange(self):
        self.attr = (self.attr_active if self.focused else self.attr_normal)
        if self.focused:
            self.grab_input(self.rect, self.pos)
    def on_activate(self):
        if self.callback is not None:
            self.callback()

class ToggleButton(Button):
    def __init__(self, text='', **kwds):
        self._state = None
        Button.__init__(self, text, **kwds)
        self.state = kwds.get('state', None)
    def _set_state(self, value):
        self._state = value
    @property
    def state(self):
        return self._state
    @state.setter
    def state(self, value):
        self._set_state(value)

class CheckBox(ToggleButton):
    def _set_state(self, value):
        ToggleButton._set_state(self, value)
        self.invalidate()
    def _text_prefix(self):
        if self._state:
            return '[X] '
        else:
            return '[ ] '
    def _text_suffix(self):
        return ''
    def on_activate(self):
        ToggleButton.on_activate(self)
        self.state = (not self.state)

class RadioBox(ToggleButton):
    def __init__(self, text='', **kwds):
        self.group = None
        ToggleButton.__init__(self, text, **kwds)
    def delete(self):
        ToggleButton.delete(self)
        if self.group:
            self.group.remove(self)
    def _set_state(self, value):
        ToggleButton._set_state(self, value)
        if self.group:
            self.group.on_set(self, value)
        self.invalidate()
    def _text_prefix(self):
        if self._state:
            return '(*) '
        else:
            return '( ) '
    def _text_suffix(self):
        return ''
    def on_activate(self):
        ToggleButton.on_activate(self)
        self.state = True

class BaseStrut(Widget):
    class Direction(Singleton): pass
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
        Widget.__init__(self, **kwds)
        self.dir = dir
        self.align = parse_pair(kwds.get('align', ALIGN_CENTER))

class Strut(BaseStrut):
    def __init__(self, dir=None, **kwds):
        BaseStrut.__init__(self, dir, **kwds)
        self.attr = kwds.get('attr', 0)
        self.margin = parse_quad(kwds.get('margin', 0))
    def getprefsize(self):
        ret = (self.dir.lo + self.dir.hi, 1)
        if self.dir.vert: ret = ret[::-1]
        ret = inflate(ret, self.margin)
        return maxpos(ret, BaseStrut.getprefsize(self))
    def draw(self, win):
        if self.valid_display: return
        # derwin()s to avoid weird character drawing glitches
        ir = deflate(
            (self.pos[0], self.pos[1], self.size[0], self.size[1]),
            self.margin)
        if self.dir.vert:
            x = ir[0] + int(ir[2] * self.align[0])
            sw = win.derwin(ir[3], 1, ir[1], x)
            sw.bkgd('\0', self.attr)
            sw.vline(0, 0, _curses.ACS_VLINE, ir[3])
            if self.dir.lo:
                sw.addch(0, 0, _curses.ACS_TTEE)
            if self.dir.hi:
                sw.insch(ir[3] - 1, 0, _curses.ACS_BTEE)
        else:
            y = ir[1] + int(ir[3] * self.align[1])
            sw = win.derwin(1, ir[2], y, ir[0])
            sw.bkgd('\0', self.attr)
            sw.hline(0, 0, _curses.ACS_HLINE, ir[2])
            if self.dir.lo:
                sw.addch(0, 0, _curses.ACS_LTEE)
            if self.dir.hi:
                sw.insch(0, ir[2] - 1, _curses.ACS_RTEE)

class BaseRadioGroup(object):
    def __init__(self):
        self.widgets = []
    def add(self, widget):
        self.widgets.append(widget)
        og = widget.group
        widget.group = self
        return widget
    def remove(self, widget):
        self.widgets.remove(widget)
        widget.group = None
    def on_set(self, widget, value):
        pass

class RadioGroup(BaseRadioGroup):
    def __init__(self):
        BaseRadioGroup.__init__(self)
        self.active = None
    def add(self, widget):
        BaseRadioGroup.add(self, widget)
        if widget.state:
            self._set_active(widget)
        return widget
    def remove(self, widget):
        BaseRadioGroup.remove(self, widget)
        if widget is self.active:
            self.active = None
    def _set_active(self, widget):
        if widget is self.active: return
        if self.active:
            self.active.state = False
        self.active = widget
        if self.active:
            self.active.state = True
    def on_set(self, widget, value):
        if not value: return
        self._set_active(widget)

def mainloop(scr):
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
        stru.pref_size[0] += 10
        stru.min_size[0] += 10
        stru.invalidate_layout()
    def shrink():
        stru.pref_size[0] -= 10
        stru.min_size[0] -= 10
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
    rv = wr.add(Viewport())
    obx = rv.add(BoxContainer(margin=None, border=(0, 0, 0, 1),
                              padding=(1, 2),
                              attr_margin=_curses.color_pair(1),
                              attr_box=_curses.color_pair(4)))
    box = obx.add(MarginContainer(border=True,
        background=_curses.color_pair(2)))
    lo = box.add(HorizontalContainer())
    c1 = lo.add(VerticalContainer())
    btnt = c1.add(Button('test', text_changer))
    rdb1 = c1.add(grp.add(RadioBox('NOP')))
    mct1 = c1.add(MarginContainer(), weight=1)
    mct1.add(Widget(minsize=(0, 1)), slot=MarginContainer.POS_TOP)
    mct1.add(DebugStrut(pref_size=(5, 0), min_size=(0, 0)),
             slot=MarginContainer.POS_LEFT)
    mct1.add(BoxWidget(background=_curses.color_pair(1), minsize=(5, 1)))
    mct1.add(DebugStrut(pref_size=(5, 0), min_size=(0, 0)),
             slot=MarginContainer.POS_RIGHT)
    mct1.add(Widget(minsize=(0, 1)), slot=MarginContainer.POS_BOTTOM)
    btne = c1.add(Button('exit', sys.exit,
                         attr_normal=_curses.color_pair(3)))
    s1 = lo.add(Strut(Strut.DIR_VERTICAL, attr=_curses.color_pair(2),
                      margin=(0, 1)))
    vp = lo.add(Viewport(background=_curses.color_pair(2)))
    c2 = vp.add(VerticalContainer())
    btnr = c2.add(Button('----------------\nback\n----------------',
                         text_back_changer, align=ALIGN_CENTER,
                         background=_curses.color_pair(3), border=0),
                  weight=1)
    s2 = c2.add(Strut(Strut.DIR_HORIZONTAL, attr=_curses.color_pair(2)))
    gbox = c2.add(BoxContainer(margin=(1, 2),
                               attr_margin=_curses.color_pair(1),
                               attr_box=_curses.color_pair(2)))
    grid = gbox.add(GridContainer(mode_x=LinearContainer.MODE_EQUAL))
    rdb2 = grid.add(grp.add(RadioBox('grow', callback=grow)),
                    pos=(0, 0))
    rdb3 = grid.add(grp.add(RadioBox('shrink', callback=shrink)),
                    pos=(3, 1))
    twgc = grid.add(Label(background=_curses.color_pair(3),
                          align=ALIGN_CENTER), pos=(2, 0))
    lbl1 = grid.add(Label('[3,2]', align=ALIGN_RIGHT,
                          background=_curses.color_pair(3)),
                    pos=(3, 2))
    lbl2 = grid.add(Label('[0,3]'), pos=(0, 3))
    stru = grid.add(DebugStrut(pref_size=[20, 0], min_size=[10, 0]),
                    pos=(1, 3))
    grid.config_col(0)
    grid.config_col(1, minsize=1)
    grid.config_col(2, weight=1)
    grid.config_col(3)
    grid.config_row(1)
    wr.main()

def main():
    #try:
        _curses.wrapper(mainloop)
    #finally:
    #    if LOG:
    #        LOG.append('')
    #        import sys
    #        sys.stderr.write('\n'.join(map(str, LOG)))
    #        sys.stderr.flush()

if __name__ == '__main__': main()
