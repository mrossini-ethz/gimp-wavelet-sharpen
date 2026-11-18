# Test cases of the plug-in, run inside GIMP by tests/run.sh with
# python-fu-eval. Each case prints PASS or FAIL and a short description;
# the last line is "RESULT <passed> passed, <failed> failed".
#
# The test images are made here, so that nothing but GIMP is needed.
import math
import os
import random
import struct
import sys
import traceback

import gi
gi.require_version('Gimp', '3.0')
gi.require_version('Gegl', '0.4')
from gi.repository import Gimp, Gegl

PROC = 'plug-in-wavelet-sharpen'
P = Gimp.Precision

passed = failed = 0


def check(ok, msg):
    global passed, failed
    print(('PASS ' if ok else 'FAIL ') + msg, flush=True)
    if ok:
        passed += 1
    else:
        failed += 1
    return ok


# --- images and pixels ---------------------------------------------------

LINEAR = (P.U8_LINEAR, P.U16_LINEAR, P.FLOAT_LINEAR)
TYPE = {P.U8_NON_LINEAR: 'u8', P.U8_LINEAR: 'u8',
        P.U16_NON_LINEAR: 'u16', P.U16_LINEAR: 'u16',
        P.FLOAT_NON_LINEAR: 'float', P.FLOAT_LINEAR: 'float'}
STRUCT = {'u8': 'B', 'u16': 'H', 'float': 'f'}
PNAME = {P.U8_NON_LINEAR: 'u8', P.U16_NON_LINEAR: 'u16',
         P.FLOAT_NON_LINEAR: 'float', P.U16_LINEAR: 'u16-linear',
         P.FLOAT_LINEAR: 'float-linear'}


def model_name(rgb, alpha, linear):
    if rgb:
        name = 'RGBA' if alpha else 'RGB'
    else:
        name = 'YA' if alpha else 'Y'
    if not linear:
        name = ''.join(c + "'" if c != 'A' else c for c in name)
    return name


def float_format(drawable):
    return model_name(drawable.is_rgb(), drawable.has_alpha(), False) + ' float'


def native_format(drawable):
    """the format of the drawable as a name, and the struct letter"""
    prec = drawable.get_image().get_precision()
    t = TYPE[prec]
    return (model_name(drawable.is_rgb(), drawable.has_alpha(),
                       prec in LINEAR) + ' ' + t, STRUCT[t])


def n_channels(drawable):
    return (3 if drawable.is_rgb() else 1) + (1 if drawable.has_alpha() else 0)


def rect(drawable):
    return Gegl.Rectangle.new(0, 0, drawable.get_width(), drawable.get_height())


def put(drawable, values):
    """write float values (non-linear, all channels interleaved)"""
    buf = drawable.get_buffer()
    buf.set(rect(drawable), float_format(drawable),
            struct.pack('<%df' % len(values), *values))
    buf.flush()
    del buf
    drawable.update(0, 0, drawable.get_width(), drawable.get_height())


def get(drawable, native=False):
    """read the pixels, as non-linear floats or in the native format"""
    if native:
        fmt, letter = native_format(drawable)
    else:
        fmt, letter = float_format(drawable), 'f'
    buf = drawable.get_buffer()
    data = buf.get(rect(drawable), 1.0, fmt, Gegl.AbyssPolicy.NONE)
    del buf
    return list(struct.unpack('<%d%s' % (len(data) // struct.calcsize(letter),
                                          letter), data))


def noisy(w, h, nc, seed=1, sigma=0.05, lo=0.2, hi=0.8, alpha=None):
    """a gradient with noise; alpha, if given, is used for the last channel"""
    rng = random.Random(seed)
    v = []
    for y in range(h):
        for x in range(w):
            for c in range(nc):
                if alpha is not None and c == nc - 1:
                    v.append(alpha)
                else:
                    base = lo + (hi - lo) * (x + 0.5 * c) / max(w, 1)
                    v.append(base + rng.gauss(0, sigma))
    return [min(max(a, 0.0), 1.0) for a in v]


def make(w, h, rgb=True, alpha=False, prec=P.U8_NON_LINEAR, values=None,
         offset=(0, 0), image_size=None):
    iw, ih = image_size or (w, h)
    image = Gimp.Image.new_with_precision(
        iw, ih, Gimp.ImageBaseType.RGB if rgb else Gimp.ImageBaseType.GRAY,
        prec)
    if rgb:
        t = Gimp.ImageType.RGBA_IMAGE if alpha else Gimp.ImageType.RGB_IMAGE
    else:
        t = Gimp.ImageType.GRAYA_IMAGE if alpha else Gimp.ImageType.GRAY_IMAGE
    layer = Gimp.Layer.new(image, 'test', w, h, t, 100,
                           Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, None, 0)
    layer.set_offsets(*offset)
    if values is None:
        values = noisy(w, h, n_channels(layer), alpha=0.9 if alpha else None)
    put(layer, values)
    return image, layer


def channel(values, nc, c):
    return values[c::nc]


def std(v):
    m = sum(v) / len(v)
    return math.sqrt(sum((a - m) ** 2 for a in v) / len(v))


def max_diff(a, b):
    return max(abs(x - y) for x, y in zip(a, b)) if a else 0


def all_finite(v):
    return all(math.isfinite(a) for a in v)


# --- running the plug-in -------------------------------------------------

proc = Gimp.get_pdb().lookup_procedure(PROC)


def run(image, drawables, run_mode=Gimp.RunMode.NONINTERACTIVE, **args):
    config = proc.create_config()
    config.set_property('run-mode', run_mode)
    config.set_property('image', image)
    config.set_core_object_array('drawables', drawables)
    for name, value in args.items():
        config.set_property(name.replace('_', '-'), value)
    result = proc.run(config)
    return result.index(0)


OK = Gimp.PDBStatusType.SUCCESS

# every argument, to leave nothing to the defaults
def args(amount=0.0, radius=0.5, luminance=True):
    return dict(amount=amount, radius=radius, luminance=luminance)


def case(fn):
    """run one test function, a Python error in it is a failure; with
    WT_ONLY set, only the cases whose name contains it"""
    if os.environ.get('WT_ONLY', '') not in fn.__name__:
        return fn
    try:
        fn()
    except Exception:
        traceback.print_exc()
        check(False, fn.__name__ + ': Python error')
    return fn




# --- the cases ------------------------------------------------------------

@case
def registration():
    check(proc is not None, 'the procedure is registered')
    names = [p.name for p in proc.get_arguments()]
    want = ['run-mode', 'image', 'drawables', 'amount', 'radius', 'luminance']
    check(names == want, 'arguments as documented in README: %s' % names)
    spec = {p.name: p for p in proc.get_arguments()}
    check((spec['amount'].minimum, spec['amount'].maximum) == (0, 10)
          and (spec['radius'].minimum, spec['radius'].maximum) == (0, 2),
          'amount 0 to 10, radius 0 to 2')
    check(proc.get_image_types() == 'RGB*, GRAY*', 'image types RGB*, GRAY*')


PRECISIONS = (P.U8_NON_LINEAR, P.U16_NON_LINEAR, P.FLOAT_NON_LINEAR,
              P.U16_LINEAR, P.FLOAT_LINEAR)
LAYOUTS = ((True, False), (True, True), (False, False), (False, True))


def layout_name(rgb, alpha):
    return ('RGB' if rgb else 'gray') + ('A' if alpha else '')


def detail(values, nc, c):
    """the size of the differences between neighbours in a row"""
    v = channel(values, nc, c)
    return std([a - b for a, b in zip(v[1:], v)])


# Every precision, colour and gray, with and without alpha: the detail goes
# up, alpha is kept and nothing leaves the valid range.
@case
def sharpen_every_format():
    for prec in PRECISIONS:
        for rgb, alpha in LAYOUTS:
            for lum in ((True, False) if rgb else (True,)):
                name = '%s %s%s' % (PNAME[prec], layout_name(rgb, alpha),
                                    ' luminance' if lum and rgb else '')
                image, layer = make(64, 48, rgb, alpha, prec,
                                    noisy(64, 48, (3 if rgb else 1) + alpha,
                                          sigma=0.02,
                                          alpha=0.7 if alpha else None))
                nc = n_channels(layer)
                before = get(layer)
                before_n = get(layer, native=True)
                status = run(image, [layer], **args(2.0, 0.5, lum))
                after = get(layer)
                after_n = get(layer, native=True)
                d0, d1 = detail(before, nc, 0), detail(after, nc, 0)
                check(status == OK and all_finite(after) and d1 > 1.2 * d0,
                      'sharpen %s: detail %.4f -> %.4f' % (name, d0, d1))
                if alpha:
                    check(channel(before_n, nc, nc - 1)
                          == channel(after_n, nc, nc - 1),
                          'sharpen %s: alpha unchanged' % name)
                if prec not in (P.FLOAT_NON_LINEAR, P.FLOAT_LINEAR):
                    check(min(after) >= 0 and max(after) <= 1,
                          'sharpen %s: values in [0,1]' % name)
                image.delete()


# Amount 0 changes nothing, and a constant image has no detail to sharpen:
# this checks that the YCbCr conversion is an exact inverse at the precision
# of the image (no 8-bit shortcuts).
TOLERANCE = {'u8': 0, 'u16': 0, 'float': 2e-6}


@case
def identity():
    for prec in PRECISIONS:
        for rgb, alpha in LAYOUTS:
            tol = TOLERANCE[TYPE[prec]]
            nc = (3 if rgb else 1) + alpha
            cases = [('amount 0', noisy(40, 30, nc), args(0.0))]
            for lum in ((True, False) if rgb else (True,)):
                const = [0.2, 0.5, 0.9, 0.6][:nc] if rgb else [0.3, 0.6][:nc]
                cases.append(('constant, amount 10' +
                              (', luminance' if lum and rgb else ''),
                              const * 1200, args(10.0, 1.0, lum)))
            for kind, vals, a in cases:
                image, layer = make(40, 30, rgb, alpha, prec, vals)
                before = get(layer, native=True)
                status = run(image, [layer], **a)
                after = get(layer, native=True)
                if TYPE[prec] == 'float':
                    d = max(abs(x - y) / max(abs(x), 1)
                            for x, y in zip(before, after))
                else:
                    d = max_diff(before, after)
                check(status == OK and d <= tol,
                      'identity (%s) %s %s: max change %g (allowed %g)'
                      % (kind, PNAME[prec], layout_name(rgb, alpha), d, tol))
                image.delete()


@case
def luminance_only():
    # sharpening the luminance of a gray picture in an RGB image keeps it
    # gray; sharpening the channels does too, but each on its own
    for lum in (True, False):
        vals = [v for v in noisy(48, 32, 1) for _ in range(3)]
        image, layer = make(48, 32, True, False, P.FLOAT_NON_LINEAR, vals)
        status = run(image, [layer], **args(5.0, 0.5, lum))
        after = get(layer)
        spread = max(max(after[i:i + 3]) - min(after[i:i + 3])
                     for i in range(0, len(after), 3))
        check(status == OK and spread < 1e-5 and after != vals,
              'gray picture in RGB, luminance %s: stays gray (%g)'
              % (lum, spread))
        image.delete()
    # with luminance only, the colour difference of a colour picture is
    # not sharpened
    vals = noisy(48, 32, 3)
    image, layer = make(48, 32, True, False, P.FLOAT_NON_LINEAR, vals)
    before = get(layer)
    run(image, [layer], **args(5.0, 0.5, True))
    after = get(layer)

    def cr(v):
        return [0.5 * v[i] - 0.41868759 * v[i + 1] - 0.08131241 * v[i + 2]
                for i in range(0, len(v), 3)]
    d = max_diff(cr(before), cr(after))
    check(d < 1e-5, 'luminance only: Cr unchanged (max change %g)' % d)
    image.delete()


# Floating point images: values outside of [0,1] are kept, not clipped
@case
def float_out_of_range():
    for lum in (True, False):
        w, h = 32, 32
        vals = [a * 1.9 - 0.3
                for a in noisy(w, h, 3, sigma=0.0, lo=0.0, hi=1.0)]
        image, layer = make(w, h, True, False, P.FLOAT_NON_LINEAR, vals)
        status = run(image, [layer], **args(3.0, 0.5, lum))
        after = get(layer)
        check(status == OK and all_finite(after) and max(after) > 1.2
              and min(after) < -0.1,
              'float, values -0.3 to 1.6, luminance %s: finite and not '
              'clipped (%.3f to %.3f)' % (lum, min(after), max(after)))
        image.delete()


# Only the selection changes; pixels outside of it stay as they are, also
# on a layer with offsets.
@case
def selection():
    for offset in ((0, 0), (7, 5)):
        image, layer = make(60, 40, True, True, P.U16_NON_LINEAR,
                            offset=offset, image_size=(80, 60))
        before = get(layer, native=True)
        image.select_rectangle(Gimp.ChannelOps.REPLACE, 20, 15, 25, 12)
        status = run(image, [layer], **args(5.0, 0.5, False))
        after = get(layer, native=True)
        nc, w = 4, 60
        outside_changed = inside_changed = 0
        for i in range(len(before)):
            p = i // nc
            x, y = p % w + offset[0], p // w + offset[1]
            sel = 20 <= x < 45 and 15 <= y < 27
            if before[i] != after[i]:
                if sel:
                    inside_changed += 1
                else:
                    outside_changed += 1
        check(status == OK and outside_changed == 0 and inside_changed > 0,
              'selection, layer offset %s: %d values changed inside, '
              '%d outside' % (offset, inside_changed, outside_changed))
        image.delete()


@case
def selection_outside_layer():
    image, layer = make(20, 20, True, False, offset=(40, 40),
                        image_size=(80, 80))
    before = get(layer, native=True)
    image.select_rectangle(Gimp.ChannelOps.REPLACE, 0, 0, 10, 10)
    status = run(image, [layer], **args(5.0))
    check(status == OK and get(layer, native=True) == before,
          'selection not touching the layer: success, nothing changed')
    image.delete()


@case
def one_pixel_selection():
    image, layer = make(30, 30, True, False, P.FLOAT_NON_LINEAR)
    image.select_rectangle(Gimp.ChannelOps.REPLACE, 10, 10, 1, 1)
    before = get(layer)
    status = run(image, [layer], **args(10.0, 2.0, False))
    after = get(layer)
    changed = [i // 3 for i in range(len(before)) if before[i] != after[i]]
    check(status == OK and all_finite(after)
          and all(p == 10 * 30 + 10 for p in changed),
          'one pixel selection: only that pixel may change')
    image.delete()


# Tiny images and thin strips, smaller than the wavelet scales, with the
# extreme settings
@case
def tiny():
    for w, h in ((1, 1), (1, 2), (2, 1), (2, 2), (1, 50), (50, 1), (3, 5),
                 (17, 2), (33, 33)):
        for rgb, alpha in LAYOUTS:
            for radius in (0.0, 2.0):
                image, layer = make(w, h, rgb, alpha, P.FLOAT_NON_LINEAR)
                status = run(image, [layer], **args(10.0, radius, False))
                after = get(layer)
                check(status == OK and all_finite(after),
                      'tiny %dx%d %s, amount 10, radius %g: success, finite '
                      'values' % (w, h, layout_name(rgb, alpha), radius))
                image.delete()


@case
def other_drawables():
    # a layer mask and a channel are grayscale drawables
    image, layer = make(40, 30, True, False)
    mask = layer.create_mask(Gimp.AddMaskType.WHITE)
    layer.add_mask(mask)
    put(mask, noisy(40, 30, 1))
    status = run(image, [mask], **args(3.0))
    check(status == OK and all_finite(get(mask)), 'layer mask: success')
    ch = Gimp.Channel.new(image, 'c', 40, 30, 50.0, Gegl.Color.new('black'))
    image.insert_channel(ch, None, 0)
    put(ch, noisy(40, 30, 1))
    before = get(ch)
    status = run(image, [ch], **args(3.0))
    check(status == OK and get(ch) != before, 'channel: success, sharpened')
    image.delete()


@case
def drawable_count():
    image, layer = make(20, 20)
    layer2 = Gimp.Layer.new(image, 'second', 20, 20, Gimp.ImageType.RGB_IMAGE,
                            100, Gimp.LayerMode.NORMAL)
    image.insert_layer(layer2, None, 0)
    check(run(image, [layer, layer2], **args()) == Gimp.PDBStatusType.CALLING_ERROR,
          'two drawables: calling error')
    check(run(image, [], **args()) == Gimp.PDBStatusType.CALLING_ERROR,
          'no drawable: calling error')
    image.delete()


@case
def indexed():
    image = Gimp.Image.new(20, 20, Gimp.ImageBaseType.RGB)
    layer = Gimp.Layer.new(image, 'l', 20, 20, Gimp.ImageType.RGB_IMAGE, 100,
                           Gimp.LayerMode.NORMAL)
    image.insert_layer(layer, None, 0)
    put(layer, noisy(20, 20, 3))
    image.convert_indexed(Gimp.ConvertDitherType.NONE,
                          Gimp.ConvertPaletteType.GENERATE, 16, False, False,
                          '')
    layer = image.get_layers()[0]
    buf = layer.get_buffer()
    before = buf.get(rect(layer), 1.0, None, Gegl.AbyssPolicy.NONE)
    del buf
    status = run(image, [layer], **args(5.0, 0.5, False))
    buf = layer.get_buffer()
    after = buf.get(rect(layer), 1.0, None, Gegl.AbyssPolicy.NONE)
    del buf
    check(status != OK and before == after,
          'indexed image: refused (status %s), unchanged' % status.value_nick)
    image.delete()


@case
def group_layer():
    image, layer = make(20, 20)
    group = Gimp.GroupLayer.new(image, 'group')
    image.insert_layer(group, None, 0)
    image.reorder_item(layer, group, 0)
    status = run(image, [group], **args(5.0))
    check(status != OK, 'layer group: refused (status %s)' % status.value_nick)
    image.delete()


@case
def locked_layer():
    image, layer = make(20, 20)
    layer.set_lock_content(True)
    before = get(layer, native=True)
    status = run(image, [layer], **args(5.0))
    check(status != OK and get(layer, native=True) == before,
          'layer with locked pixels: refused (status %s), unchanged'
          % status.value_nick)
    image.delete()


@case
def run_modes():
    # with the last values (none saved yet in the test profile: the
    # defaults, amount 0 as in GIMP 2)
    image, layer = make(40, 40, True, False, P.FLOAT_NON_LINEAR)
    before = get(layer)
    status = run(image, [layer], Gimp.RunMode.WITH_LAST_VALS)
    check(status == OK and get(layer) == before,
          'run with last values (the defaults): success, amount 0 keeps '
          'the image')
    image.delete()


@case
def steepens_edges_keeps_flat_areas():
    # the test of the first version: gray with a soft vertical step
    w, h = 400, 60
    vals = []
    for y in range(h):
        for x in range(w):
            vals += [0.3 + 0.4 / (1 + math.exp(-(x - 200) / 1.5))] * 3
    image, layer = make(w, h, True, False, P.U8_NON_LINEAR, vals)
    src = get(layer)
    status = run(image, [layer], **args(1.0, 0.5, True))
    res = get(layer)

    def row(v):
        return [v[(30 * w + x) * 3] for x in range(190, 210)]

    s0 = max(abs(a - b) for a, b in zip(row(src)[1:], row(src)))
    s1 = max(abs(a - b) for a, b in zip(row(res)[1:], row(res)))
    check(status == OK and s1 > 1.1 * s0,
          'edge slope %.3f -> %.3f' % (s0, s1))

    def block(v):
        return [v[(y * w + x) * 3] for y in range(h) for x in range(250, 390)]
    f0, f1 = sum(block(src)) / (h * 140), sum(block(res)) / (h * 140)
    check(abs(f1 - f0) < 0.01, 'flat area %.3f -> %.3f' % (f0, f1))
    image.delete()


@case
def translation():
    # tests/run.sh runs GIMP with LANGUAGE=pl: the plug-in must find its
    # catalog in the locale folder next to it. gettext ignores LANGUAGE in
    # the C locale, so there the case is skipped.
    import locale
    messages = locale.setlocale(locale.LC_MESSAGES)
    if os.environ.get('LANGUAGE') != 'pl' or messages.split('.')[0] in (
            'C', 'POSIX'):
        print('SKIP translation: LANGUAGE %s, locale %s'
              % (os.environ.get('LANGUAGE'), messages))
        return
    check(proc.get_menu_label() == 'Wyostrzanie wavelet...',
          'translation: Polish menu label %s' % proc.get_menu_label())


print('RESULT %d passed, %d failed' % (passed, failed), flush=True)
