"""
Converts sequence of images to compact PDF while removing speckles, bleedthrough, etc.
    https://habr.com/ru/post/351266/
    https://mzucker.github.io/2016/09/20/noteshrink.html - оригинал
"""
# for some reason pylint complains about members being undefined :(
# pylint: disable=E1101

from __future__ import print_function

import os
import re
import shlex
import subprocess
import sys
from argparse import ArgumentParser

import img2pdf
import numpy as np
from PIL import Image
from scipy.cluster.vq import kmeans, vq


def quantize(image, bits_per_channel=None):
    """ Reduces the number of bits per channel in the given image """

    if bits_per_channel is None:
        bits_per_channel = 6
    assert image.dtype == np.uint8
    shift = 8 - bits_per_channel # 2
    halfbin = (1 << shift) >> 1     # вычисляем средний бит из удаляемых. =2
    ''' очистка младших бит. Добавляем средний для коррекции изображения, 
    т.к. просто очистка младших бит установит их в 0, 
    изображение немного потемнеет. Это компенсация '''
    return ((image.astype(int) >> shift) << shift) + halfbin    


def pack_rgb(rgb):
    """ Packs a 24-bit RGB triples into a single integer, works on both arrays and tuples. """

    orig_shape = None
    if isinstance(rgb, np.ndarray):
        assert rgb.shape[-1] == 3
        orig_shape = rgb.shape[:-1]
    else:
        assert len(rgb) == 3
        rgb = np.array(rgb)

    rgb = rgb.astype(int).reshape((-1, 3))
    packed = (rgb[:, 0] << 16 |
              rgb[:, 1] << 8 |
              rgb[:, 2])
    if orig_shape is None:
        return packed
    else:
        return packed.reshape(orig_shape)


def unpack_rgb(packed):
    """ Unpacks a single integer or array of integers into one or more 24-bit RGB values """

    orig_shape = None
    if isinstance(packed, np.ndarray):  # Возвращает флаг, указывающий на то, является ли указанный объект экземпляром указанного класса (классов).
        assert packed.dtype == int
        orig_shape = packed.shape
        packed = packed.reshape((-1, 1))
    rgb = ((packed >> 16) & 0xff,
           (packed >> 8) & 0xff,
           (packed) & 0xff)
    if orig_shape is None:
        return rgb
    else:
        return np.hstack(rgb).reshape(orig_shape + (3,))


def get_bg_color(image, bits_per_channel=None):
    """
    Obtains the background color from an image or array of RGB colors
    by grouping similar colors into bins and finding the most frequent
    one 
    Определяем цвет фона как наиболее часто встречающийся
    """
    assert image.shape[-1] == 3
    quantized = quantize(image, bits_per_channel).astype(int)  # очистка младших бит
    packed = pack_rgb(quantized)    # объеденим 3 цвета RGB как одно int число
    ''' https://docs.scipy.org/doc/numpy-1.15.1/reference/generated/numpy.unique.html 
    Returns the sorted unique elements of an array.
    counts: The number of times each of the unique values comes up in the original array. '''
    unique, counts = np.unique(packed, return_counts=True)
    packed_mode = unique[counts.argmax()]
    return unpack_rgb(packed_mode)


def rgb_to_sv(rgb):
    """
    onvert an RGB image or array of RGB colors to saturation and value, returning each one as a separate 32-bit floating
    point array or value
    Вычисляем из тройки RGB Saturation и Value в цветовом пространстве HSV
    """

    if not isinstance(rgb, np.ndarray):
        rgb = np.array(rgb)
    axis = len(rgb.shape)-1
    cmax = rgb.max(axis=axis).astype(np.float32)
    cmin = rgb.min(axis=axis).astype(np.float32)
    delta = cmax - cmin
    saturation = delta.astype(np.float32) / cmax.astype(np.float32)
    saturation = np.where(cmax == 0, 0, saturation) # https://docs.scipy.org/doc/numpy/reference/generated/numpy.where.html
    value = cmax/255.0
    return saturation, value


def postprocess(output_filename, options):
    """ Runs the postprocessing command on the file provided. """

    assert options.postprocess_cmd
    base, _ = os.path.splitext(output_filename)
    post_filename = base + options.postprocess_ext

    cmd = options.postprocess_cmd
    cmd = cmd.replace('%i', output_filename)
    cmd = cmd.replace('%o', post_filename)
    cmd = cmd.replace('%e', options.postprocess_ext)

    subprocess_args = shlex.split(cmd)

    if os.path.exists(post_filename):
        os.unlink(post_filename)
    if not options.quiet:
        print('  running "{}"...'.format(cmd), end=' ')
        sys.stdout.flush()

    try:
        result = subprocess.call(subprocess_args)
        before = os.stat(output_filename).st_size
        after = os.stat(post_filename).st_size
    except OSError:
        result = -1

    if result == 0:
        if not options.quiet:
            print('{:.1f}% reduction'.format(
                100*(1.0-float(after)/before)))
        return post_filename
    else:
        sys.stderr.write('warning: postprocessing failed!\n')
        return None


def percent(string):
    """ Convert a string (i.e. 85) to a fraction (i.e. .85). """
    return float(string)/100.0


def get_argument_parser():
    '''Parse the command-line arguments for this program.'''

    parser = ArgumentParser(
        description='convert scanned, hand-written notes to PDF')
    show_default = ' (default %(default)s)'
    parser.add_argument('filenames', metavar='IMAGE', nargs='+',
                        help='files to convert')
    parser.add_argument('-d', dest='usewxgui', action='store_true',
                        default=False, help='Use GUI dialog')
    parser.add_argument('-q', dest='quiet', action='store_true',
                        default=False,
                        help='reduce program output')
    parser.add_argument('-b', dest='basename', metavar='BASENAME',
                        default='ns_page',
                        help='output PNG filename base' + show_default)
    parser.add_argument('-o', dest='pdfname', metavar='PDF',
                        default='output.pdf',
                        help='output PDF filename' + show_default)
    parser.add_argument('-v', dest='value_threshold', metavar='PERCENT',
                        type=percent, default='25',
                        help='background value threshold %%'+show_default)
    parser.add_argument('-s', dest='sat_threshold', metavar='PERCENT',
                        type=percent, default='20',
                        help='background saturation '
                        'threshold %%'+show_default)
    parser.add_argument('-n', dest='num_colors', type=int,
                        default='8',
                        help='number of output colors '+show_default)
    parser.add_argument('-p', dest='sample_fraction',
                        metavar='PERCENT',
                        type=percent, default='5',
                        help='%% of pixels to sample' + show_default)
    parser.add_argument('-w', dest='white_bg', action='store_true',
                        default=False, help='make background white')
    parser.add_argument('-g', dest='global_palette',
                        action='store_true', default=False,
                        help='use one global palette for all pages')
    parser.add_argument('-S', dest='saturate', action='store_false',
                        default=True, help='do not saturate colors')
    parser.add_argument('-K', dest='sort_numerically',
                        action='store_true', default=False,
                        help='keep filenames ordered as specified; '
                        'use if you *really* want IMG_10.png to '
                        'precede IMG_2.png')
    parser.add_argument('-P', dest='postprocess_cmd', default=None,
                        help='set postprocessing command (see -O, -C, -Q)')
    parser.add_argument('-e', dest='postprocess_ext',
                        default='_post.png',
                        help='filename suffix/extension for '
                        'postprocessing command')
    parser.add_argument('-O', dest='postprocess_cmd',
                        action='store_const',
                        const='optipng -silent %i -out %o',
                        help='same as -P "%(const)s"')
    parser.add_argument('-C', dest='postprocess_cmd',
                        action='store_const',
                        const='pngcrush -q %i %o',
                        help='same as -P "%(const)s"')
    parser.add_argument('-Q', dest='postprocess_cmd',
                        action='store_const',
                        const='pngquant --ext %e %i',
                        help='same as -P "%(const)s"')
    parser.add_argument('-c', dest='pdf_cmd', metavar="COMMAND",
                        default = 'magick convert %i %o',
                        help='PDF command (default "%(default)s")')
    return parser


def GetFilesMask(MaskList):
    # переделать, не требуется
    from glob import glob

    fl = []
    for f in MaskList:
        fl += glob(f)
    return fl


def get_filenames(options):
    """
    Не потребуется, через параметры
    Get the filenames from the command line, optionally sorted by number, so that IMG_10.png is re-arranged to come
    after IMG_9.png. This is a nice feature because some scanner programs (like Image Capture on Mac OS X)
    automatically number files without leading zeros, and this way you can supply files using a wildcard and still
    have the pages ordered correctly.
    """

    options.filenames = GetFilesMask(options.filenames)

    if not options.sort_numerically:
        return options.filenames

    filenames = []
    for filename in options.filenames:
        basename = os.path.basename(filename)
        root, _ = os.path.splitext(basename)
        matches = re.findall(r'[0-9]+', root)
        if matches:
            num = int(matches[-1])
        else:
            num = -1
        filenames.append((num, filename))
    return [fn for (_, fn) in sorted(filenames)]


def load(input_filename):
    """
    Load an image with Pillow and convert it to numpy array. Also returns the image DPI in x and y as a tuple.
    """
    try:
        pil_img = Image.open(input_filename)
    except IOError:
        sys.stderr.write(f'warning: error opening {input_filename}\n')
        return None, None

    if pil_img.mode != 'RGB':
        pil_img = pil_img.convert('RGB')

    if 'dpi' in pil_img.info:
        dpi = pil_img.info['dpi']
    else:
        dpi = (300, 300)

    img = np.array(pil_img)
    return img, dpi


def sample_pixels(img, options):
    """
    Pick a fixed percentage of pixels in the image, returned in random order.
    получаем случайную выборку 5% точек (по умолчанию) от исходного изображения -p
    """

    pixels = img.reshape((-1, 3))
    num_pixels = pixels.shape[0]    # длина по 0-му изверению
    num_samples = int(num_pixels * options.sample_fraction)  # уменьшаем количество точек для выборки
                    # по умолчанию берем только 5% от первоночального
    idx = np.arange(num_pixels)     # аналог range, создает массив np
    np.random.shuffle(idx)  # https://docs.scipy.org/doc/numpy/reference/generated/numpy.random.shuffle.html
                            # перемешивает элементы массива
    return pixels[idx[:num_samples]]    # выборка из массива pixel 
                    # по индексам первых num_samples элементов idx, индексы которого до этого были перемешаны


def get_fg_mask(bg_color, samples, options):
    """
    Determine whether each pixel in a set of samples is foreground by comparing it to the background color.
    A pixel is classified as a foreground pixel if either its value or saturation differs from the background by
    a threshold.
    
    Выделение переднего плана (значимые цвета, которые нужно сохранить)
    Конвертируем RGB-цвет в HSV, Hue-Saturation(насыщенность)-Value(Общая яркость)
    пиксель принадлежит к переднему плану, если он соответствует одному из критериев:
      - значение цвета (V) отличается более чем на 0,3 от цвета фона или
      - насыщенность (S) отличается более чем на 0,2 от фона
    """

    s_bg, v_bg = rgb_to_sv(bg_color)
    s_samples, v_samples = rgb_to_sv(samples)
    s_diff = np.abs(s_bg - s_samples)
    v_diff = np.abs(v_bg - v_samples)
    return ((v_diff >= options.value_threshold) |   # -v по умолчанию 0.25 background value threshold
            (s_diff >= options.sat_threshold))      # -s по умолчанию 0.20 background saturation


def get_palette(samples, options, return_mask=False, kmeans_iter=40):
    """
    Extract the palette for the set of sampled RGB values. The first palette entry is always the background color;
    the rest are determined from foreground pixels by running K-means clustering. Returns the palette, as well as
    a mask corresponding to the foreground pixels.
    """

    if not options.quiet:
        print('  getting palette... ', end='')
    bg_color = get_bg_color(samples, 6) # 6 - бит на канал, будем уменьшать с 8. Определили цвет фона
    fg_mask = get_fg_mask(bg_color, samples, options)
    ''' https://docs.scipy.org/doc/scipy-0.18.1/reference/generated/scipy.cluster.vq.kmeans.html 
    samples[fg_mask] возвращает подмассив элементов samles, для которых индесы fg_mask == true
    т.е. испольшуем только нефоновые цвета переднего плана '''
    centers, _ = kmeans(samples[fg_mask].astype(np.float32),
                        options.num_colors-1,
                        iter=kmeans_iter)
    ''' https://docs.scipy.org/doc/numpy-1.15.0/reference/generated/numpy.vstack.html 
    объеденим полученыый результат с bg_color '''
    palette = np.vstack((bg_color, centers)).astype(np.uint8)
    if not return_mask:
        return palette
    else:
        return palette, fg_mask


def apply_palette(img, palette, options):
    """
    Apply the pallete to the given image. The first step is to set all background pixels to the background color;
    then, nearest-neighbor matching is used to map each foreground color to the closest one in the palette.
    """

    if not options.quiet:
        print('applying palette... ', end='')
    bg_color = palette[0]
    fg_mask = get_fg_mask(bg_color, img, options)
    orig_shape = img.shape
    pixels = img.reshape((-1, 3))
    fg_mask = fg_mask.flatten() # копия массива, свернутого в одно измерение
    num_pixels = pixels.shape[0]
    labels = np.zeros(num_pixels, dtype=np.uint8)
    ''' https://docs.scipy.org/doc/scipy-0.18.1/reference/generated/scipy.cluster.vq.vq.html#scipy.cluster.vq.vq  '''
    labels[fg_mask], _ = vq(pixels[fg_mask], palette)
    return labels.reshape(orig_shape[:-1])


def save(output_filename, labels, palette, dpi, options):
    """
    Save the label/palette pair out as an indexed PNG image. This optionally saturates the pallete by mapping
    the smallest color component to zero and the largest one to 255, and also optionally sets the background color
    to pure white.
    """

    if not options.quiet:
        print(f'saving {output_filename}... ', end='')

    if options.saturate:        # -S do not saturate colors. увеличивает яркость и контрастность палитры, изменяя минимальные и максимальные значения интенсивности на 0 и 255, соответственно.
        palette = palette.astype(np.float32)
        pmin = palette.min()
        pmax = palette.max()
        palette = 255 * (palette - pmin)/(pmax-pmin)
        palette = palette.astype(np.uint8)

    if options.white_bg:
        palette = palette.copy()
        palette[0] = (255, 255, 255)

    output_img = Image.fromarray(labels, 'P')   # P 8-bit pixels, mapped to any other mode using a color palette
    output_img.putpalette(palette.flatten())
    output_img.save(output_filename, dpi=dpi)


def get_global_palette(filenames, options):
    """
    Fetch the global palette for a series of input files by merging their samples together into one large array
    """

    input_filenames = []
    all_samples = []
    if not options.quiet:
        print('building global palette...')

    for input_filename in filenames:
        img, _ = load(input_filename)   # -->
        if img is None:
            continue
        if not options.quiet:
            print(f'processing {input_filename}... ', end='')
        samples = sample_pixels(img, options)  # случайная выборка 5% точек -->
        all_samples.append(samples)
        input_filenames.append(input_filename)

    num_inputs = len(input_filenames)
    all_samples = [s[:int(round(float(s.shape[0])/num_inputs))]
                   for s in all_samples]
    all_samples = np.vstack(tuple(all_samples))
    global_palette = get_palette(all_samples, options)  # -->
    if not options.quiet:
        print('  done\n')
    return input_filenames, global_palette


def emit_pdf(outputs, options):
    """
    Runs the PDF conversion command to generate the PDF.
    """

    if not options.quiet:
        print(f'convert to {options.pdfname} files '
              f'{" ".join(outputs[:3] + ["..."] if len(outputs) > 3 else outputs)}', end='')
    with open(options.pdfname,"wb") as f:
        f.write(img2pdf.convert(outputs))
    print(f'  done.')


def notescan_main(options):
    """
    Main function for this program when run as script.
    1. Читаем файл с диска  input_filename ==> image
    2. Из исходного изображения получаем случайную выборку 5% точек (-p sample_fraction)
       Уменьшаем количество цветов, понижаем разрядность с 8 до 6. "Группируем" цвета. image ==> samples
    3. Определяем цвет фона     bg_color
    3. Вычисляем маску цветов, которые "сильно" (по определенным двум критериям) отличаются от цвета фона.
       Отсекаем фоновые цвета, оставлем только цвета переднего плана  samples ==> samples[fg_mask]
    4. С помощию кластерного анализа выделяем группы и определяем центры групп цветов.
       Количество центров задано в параметрах. Определяем palette
    """

    filenames = get_filenames(options)      # -->
    outputs = []
    do_global = options.global_palette and len(filenames) > 1
    if do_global:
        filenames, palette = get_global_palette(filenames, options)     # -->

    do_postprocess = bool(options.postprocess_cmd)

    files_sizes = []
    for input_filename in filenames:
        img, dpi = load(input_filename)
        if img is None:
            continue

        output_filename = '{}{:04d}.png'.format(
            options.basename, len(outputs))

        if not options.quiet:
            print('opened', input_filename, end='')

        if not do_global:
            samples = sample_pixels(img, options)
            palette = get_palette(samples, options)

        labels = apply_palette(img, palette, options)
        save(output_filename, labels, palette, dpi, options)
        if do_postprocess:
            post_filename = postprocess(output_filename, options)
            if post_filename:
                output_filename = post_filename
            else:
                do_postprocess = False
        outputs.append(output_filename)
        if not options.quiet:
            print('  done')
        files_sizes.append([os.path.getsize(input_filename), os.path.getsize(output_filename)])
        
    emit_pdf(outputs, options)


def main():
    """
    Parse args and call notescan_main().
    """
    notescan_main(options=get_argument_parser().parse_args())


if __name__ == '__main__':
    main()
"""
main
    get_argument_parser
    notescan_main
        get_filenames
        get_global_palette
            get_global_palette
            load
            get_palette
        load
        (sample_pixels)
        (get_palette)
            get_bg_color
            get_fg_mask
        apply_palette
            get_fg_mask
        save
        (postprocess)
        emit_pdf
"""