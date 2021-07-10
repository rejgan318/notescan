"""
GUI for noteshrink
https://github.com/mzucker/noteshrink
https://mzucker.github.io/2016/09/20/noteshrink.html
"""
# TODO Основной модуль обработки
# TODO Окно просмотра - разметка на 2 файла? КЛик на картинке = показать обработанный файл?
#      F5 переключение вида просмотра: исходный/обработанный/2 на экране
# TODO Непонятный таймаут после FileBrowse
# TODO Мультипоточность
# TODO считывание параметров слайдеров с таймаутом или кнопка Ok без событий?
# TODO Размер по горизонтали
# TODO Увеличение при просмотре? Иконка ниже с маштабированием?
# TODO show с внешней программой?
# TODO сделать EXE
# TODO сохранение в pdf через PIL (в noteshrink сделано чрез вызов внешнего процесса и Convert из ImageMagic):
#   вариант через PIL (не подходит, исходный файл должен быть jpg)
#    PILimage.save(r'C:\Users\Ron\Desktop\Test\myImages.pdf',save_all=True, append_images=PILimageslist)
#   вариант https://pypi.org/project/img2pdf/ - вроде норм. Протестировать. Позволяет задать размеры pdf в мм
# DONE Размеры в пикселях для полей масштабирования; изменяемые поля
# DONE Exif поворот на всякий случай
# DONE Интерфейс с Tab, горячие клавиши по вкладкам F1-F4
# DONE Окно параметров
# DONE Сохранение параметров выбора директории и остальных
# DONE статусная строка с прогрессбаром и процентами
# DONE список файлов - добавление, очистка
# DONE иконку

import enum
import io
from pathlib import Path

import PySimpleGUI as sg
from PIL import Image, ImageOps

""" 
Настройки
zip name ?
pdf name ?
Цветов на выход 1..20 8
Пикселей учитывать, в % 1..30 5
Насыщенность фона 0..1. 0.2
Пороговое значение фона 0..1. 0.25
Единая палитра цветов y/N
Оставить порядок следования Y/n
Белый фон y/N
"""
# sg.user_settings_filename(filename='noteshrinkgui.json', path='.')
settings = sg.UserSettings()
settings.load(filename='noteshrinkgui.json', path='.')

default_settings = {
    '-font-': 'Helvetica',
    '-font_size-': 10,
    '-slider_size-': (12, 12),
    '-text_size-': (11, None),
    '-colors-': 8,
    '-pixels-': 5,
    '-backgr-': 0.2,
    '-limit-': 0.25,
    '-pal-': False,
    '-order-': True,
    '-white-': True,
    "-files-": [],
    "-folder_to_save-": '.',
    "'-scale_percent-'": '100',
}
icon_base64 = b'iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAABmJLR0QA/wD/AP+gvaeTAAAA/ElEQVRoge3aSwrCQBBF0avbMduR' \
              b'DFxItuCeFeLEgHaS/uRD12vqQgZOpA6BxC4Er2q32gMc0R14Ac/ag+xpQozfSxLT848Yv5+7mkOVFt6JEXgDj5pDleYIK5lGjMG1' \
              b'lmkE5EHMIyANkUBAHCKDgHWIFAKWIXIImEMkETCHLP126qtNV1AIkbsTU6chLrtHKyv2No+VnPO68YvN5RDP87TKfY+c9vw/qmae' \
              b'Wg5praXzRM6WxFQphARkbaEsBYkdT2UgqTO2BCRnUWAekrvtMA0pWdmYhZTunUxCtizPzEFkN4C/OcJKTSA6hBfKYQPCdyJsoAHE' \
              b'VBN/IZLtA/9g/jmly8UBAAAAAElFTkSuQmCC'


class Evt:
    """ Symbolic names for hot keys and events. You can change it """
    PREV_IMG = 'F7:118'
    NEXT_IMG = 'F8:119'
    TAB_OPTIONS = 'F1:112'
    TAB_FILES = 'F2:113'
    TAB_SAVE = 'F3:114'
    TAB_SETUP = 'F4:115'
    CHANGE_VIEW = 'F5:116'


class NSFlags(enum.IntFlag):
    """ Service """
    LOADED = enum.auto()
    CALCULATED = enum.auto()


class NSFileInfo:
    """ Full info for one file from list """
    def __init__(self, file):
        self.state = 0
        f = Path(file).resolve()
        self.name = str(f.name)
        self.fullname = str(f)
        self.w = 0
        self.h = 0
        self.size = 0
        self.pil_img = None
        self.png_img = None
        self.result_img = None


class NoteShrink:
    """ Main oblect """
    def __init__(self, file=None):
        self.files = []     # list of NSFileInfo
        # self.finfo = {}
        self.num = 0
        self.curent = 0
        self.ns = None
        self.maxsize = (1510, 840)
        if file:
            self.add(file=file)

    def set_curent(self, curent):
        self.curent = curent

    def add(self, file):
        self.ns = NSFileInfo(file=file)
        self.load()
        self.files.append(self.ns)
        self.num += 1

    def load(self):
        self.ns.pil_img = Image.open(Path(self.ns.fullname))
        tag_orientation = 274
        exif = self.ns.pil_img._getexif()
        if exif and exif.get(tag_orientation, None):
            rotate = exif[tag_orientation]
            if rotate == 3:
                self.ns.pil_img = self.ns.pil_img.rotate(180, expand=True)
            elif rotate == 6:
                self.ns.pil_img = self.ns.pil_img.rotate(270, expand=True)
            elif rotate == 8:
                self.ns.pil_img = self.ns.pil_img.rotate(90, expand=True)
        else:
            rotate = None
        self.ns.w = self.ns.pil_img.width
        self.ns.h = self.ns.pil_img.height

        self.ns.pil_img.thumbnail(self.maxsize)

        # if not self.img:
        #     return None
        bio = io.BytesIO()
        self.ns.pil_img.save(bio, format="PNG")
        self.ns.png_img = bio.getvalue()
        self.ns.state = self.ns.state | NSFlags.LOADED

    def process(self, index):
        self.files[index].result_img = ImageOps.grayscale(self.files[index].pil_img)
        self.files[index].result_img.thumbnail(self.maxsize)

        bio = io.BytesIO()
        self.files[index].result_img.save(bio, format="PNG")
        self.files[index].result_img = bio.getvalue()

    def get_file_fullname(self):
        return [f.fullname for f in self.files]

    def get_files_name(self):
        return [f.name for f in self.files]

    def get_img(self, index=0):
        if not self.files:
            return None
        return self.files[index].png_img


def img2pngmem(img):
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    return bio.getvalue()


def set_new_val(num):
    """ set un new GUI values for new file or chenge current file """
    nsfiles.set_curent(num)
    window['-IMAGE-'].update(data=nsfiles.get_img(num))
    window['-FILES-'].update(set_to_index=num)
    scale = int(window['-SCALE_PERCENT-'].get())
    if scale == 100:
        w = nsfiles.files[nsfiles.curent].w
        h = nsfiles.files[nsfiles.curent].h
    else:
        w, h = calc_scale(wh=(nsfiles.files[nsfiles.curent].w, nsfiles.files[nsfiles.curent].h), scale=scale)
    window['-SCALE_W-'].update(str(w))
    window['-SCALE_H-'].update(str(h))
    show_result = False


def calc_scale(wh=None, scale=None, w=None, h=None):
    """ scale image size. calculate scale and another dimension with fixed aspect ratio
    or new sizes from defined scale"""
    if not wh:
        wh = (nsfiles.files[nsfiles.curent].w, nsfiles.files[nsfiles.curent].h)
    w0, h0 = wh     # dimensions of source image
    if scale:
        w = round(w0 * scale / 100)
        h = round(h0 * scale / 100)
        return w, h
    elif w:
        scale = round(w / w0 * 100)
        h = round(w / w0 * h0)
        return scale, h
    elif h:
        scale = round(h / h0 * 100)
        w = round(h / h0 * w0)
        return scale, w
    else:
        return w0, h0


def process_save(values):
    path_to_save = '.' if not values['-FOLDER_TO_SAVE-'] else values['-FOLDER_TO_SAVE-']
    for f in nsfiles.files if values['-CHECK_ALL_FILES-'] else [nsfiles.files[nsfiles.curent]]:
        if values['-PNG-']:
            new_f = str(Path(path_to_save) / Path(f.name).with_suffix('.png'))
            print(f'PNG {path_to_save} {f.fullname} --> {new_f}')
            f.pil_img.save(new_f, "PNG")


# если есть установки в конфигурационном файле, используем их. Иначе из значений по умолчанию
for key, value in default_settings.items():
    if not settings.get(key):
        settings[key] = value

nsfiles = NoteShrink()
index = 0
for f in settings["-files-"]:
    nsfiles.add(f)
    nsfiles.process(index)
    index += 1

lt_options = [
    [sg.Text('Количесто\nцветов', size=settings['-text_size-']),
     sg.Slider(key='-SET_COLORS-', tooltip='Количество цветов',
               range=(1, 20), default_value=settings['-colors-'], enable_events=True, orientation='horizontal',
               size=settings['-slider_size-'], font=(settings['-font-'], settings['-font_size-']), )],
    [sg.Text('Пикселей,\n%', size=settings['-text_size-']),
     sg.Slider(key='-SET_PIXELS-', tooltip='% учитываемых пикселей',
               range=(1, 30), default_value=settings['-pixels-'], enable_events=True, orientation='horizontal',
               size=settings['-slider_size-'], font=(settings['-font-'], settings['-font_size-']),)],
    [sg.Text('Фон,\nнасыщенность', size=settings['-text_size-']),
     sg.Slider(key='-SET_BACKGR-', tooltip='Насыщенность фона',
               range=(0., 1.), resolution=0.1, default_value=settings['-backgr-'], orientation='horizontal',
               size=settings['-slider_size-'], font=(settings['-font-'], settings['-font_size-']), enable_events=True)],
    [sg.Text('Фон,\nпорог', size=settings['-text_size-']),
     sg.Slider(key='-SET_LIMIT-', tooltip='Пороговое значение фона',
               range=(0., 1.), resolution=0.05, default_value=settings['-limit-'], orientation='horizontal',
               size=settings['-slider_size-'], font=(settings['-font-'], settings['-font_size-']), enable_events=True)],
    [sg.Checkbox(key='-SET_PAL-', text='Единая палитра цветов', tooltip='Единая палитра цветов для всех файлов',
                 default=settings['-pal-'], font=(settings['-font-'], settings['-font_size-']), enable_events=True,)],
    [sg.Checkbox(key='-SET_ORDER-', text='Оставить порядок следования',
                 default=settings['-order-'], font=(settings['-font-'], settings['-font_size-']), enable_events=True,)],
    [sg.Checkbox(key='-SET_WHITE-', text='Белый фон',
                 default=settings['-white-'], font=(settings['-font-'], settings['-font_size-']), enable_events=True,)],
]
lt_files = [
    [sg.FilesBrowse(' + ', key='-SELECT_FILES-', tooltip='Добавить файлы для обработки', enable_events=True, target='-SELECT_FILES-'),
     sg.Button(' - ', key='-CLEAR_FILES-', tooltip='Очистить список файлов', enable_events=True, ), ],
    [sg.Listbox(key='-FILES-', values=nsfiles.get_files_name(), enable_events=True, size=(27, 15),
                select_mode=sg.LISTBOX_SELECT_MODE_SINGLE)],
]
ls_save = [
    [sg.Text('')],
    [sg.Text('Size'),
     sg.Input(key='-SCALE_PERCENT-', size=(3, None), default_text=100, enable_events=True, pad=(0, 0)),
     sg.Text('%, ', pad=(0, 0)),
     sg.Input(key='-SCALE_W-', size=(4, None), enable_events=True, justification='right', pad=(0, 0),
              default_text=1111),
     sg.Text('*', pad=(0, 0)),
     sg.Input(key='-SCALE_H-', size=(4, None), enable_events=True, justification='right', pad=(0, 0)),
     sg.Text('px', pad=(0, 0)),
     ],
    [sg.Checkbox('All files', key='-CHECK_ALL_FILES-', default=True), ],
    [sg.Radio("PNG", group_id='-IMG_SAVE_FORMAT-', default=True, key='-PNG-'), ],
    [sg.Radio("JPG", group_id='-IMG_SAVE_FORMAT-', key='-JPG-', ), sg.Text('Qulity'), sg.Input(key='-JPG_QULITY-', size=(3, None))],
    [sg.Radio("PDF", group_id='-IMG_SAVE_FORMAT-', key='-PDF-', ), ],
    [sg.Text('2' * 30)],
    [sg.Text('')],
    [sg.Text('')],
    [sg.Input(key='-IN_FOLDER_TO_SAVE-', size=(30, None), )],
    [sg.FolderBrowse(key='-FOLDER_TO_SAVE-', button_text='Browse', target='-IN_FOLDER_TO_SAVE-', enable_events=True, ),
     sg.Button(key='-BUTTON_SAVE-', button_text='Save', )],
]
ls_setup = [
    [sg.Text('Setup')]
]
lt_left_column = [[sg.TabGroup([[
    sg.Tab('Options', lt_options, key='-TAB_OPTIONS-', ),
    sg.Tab('Files', lt_files, key='-TAB_FILES-', ),
    sg.Tab('Save', ls_save, key='-TAB_SAVE-', ),
    sg.Tab('Setup', ls_setup, key='-TAB_SETUP-', ),
]])]]
lt_right_column = [[sg.Image(key='-IMAGE-', data=nsfiles.get_img(0), enable_events=True, )]]
lt_status_bar = [
    [sg.Text(key='-FICTION_LINE_FOR_EXPAND-', font='ANY 1', pad=(0, 0))],
    [sg.StatusBar(key='-STATUS2-', size=(20, None), text='Информация статусная'),  # text_color='yellow',
     sg.StatusBar(key='-STATUS3-', size=(30, None), text='И еще что-то выводим...', justification='right'),
     sg.ProgressBar(key='-PROGRESS-', size=(10, 20), orientation='horizontal', max_value=100,
                    bar_color=(sg.theme_element_text_color(), sg.theme_background_color(),), ),
     sg.Text('', key='-PERCENT-', size=(5, None), justification='right'),
     ]
]
lt = [[sg.Column(lt_left_column, vertical_alignment='top'), sg.Column(lt_right_column)], [lt_status_bar]]
window = sg.Window('NoteshrinkGUI', layout=lt, return_keyboard_events=True, resizable=True, icon=icon_base64,
                   finalize=True, )
window['-FICTION_LINE_FOR_EXPAND-'].expand(expand_x=True, expand_y=True, expand_row=True)
window.Maximize()
window['-IMAGE-'].expand(expand_x=True, expand_y=True, expand_row=True)
# max_size = window['-IMAGE-'].get_size()
# window['-PROGRESS-'].update(20)

show_result = False
# files_name = []
if nsfiles.num:
    set_new_val(0)

while True:
    # Down:40 Up:38
    event, values = window.read()
    # event, values = window.read(timeout=100, timeout_key='_timeout_')
    print(event, values)
    if event in (sg.WIN_CLOSED, 'Escape:27'):
        break
    # if event == 'Up:38':
    #     if window['-PROGRESS-'].visible:
    #         window['-PERCENT-'].set_size(size=(0, None))
    #         window['-PERCENT-'].update(value='')
    #         window['-PROGRESS-'].update(0, visible=False)
    #     else:
    #         window['-PERCENT-'].set_size(size=(5, None))
    #         window['-PERCENT-'].update(value='123456')
    #         window['-PROGRESS-'].update(50, visible=True)
    if event in ('-SELECT_FILES-'):
        index = len(nsfiles.files)
        for f in values["-SELECT_FILES-"].split(';'):
            if f not in settings['-files-']:    # exlude duplicates
                settings['-files-'] += [f]
                nsfiles.add(f)
                nsfiles.process(index)
                index += 1
        # files_name = [str(Path(f).name) for f in settings['-files-']]
        window['-FILES-'].update(values=nsfiles.get_files_name())
        set_new_val(nsfiles.num - 1)
    if event in ('-CLEAR_FILES-'):
        settings['-files-'] = []
        del nsfiles
        nsfiles = NoteShrink()
        window['-FILES-'].update(values=[])
        window['-IMAGE-'].update(data=None)
    if event in ('-FILES-'):
        file_num = window['-FILES-'].get_indexes()[0]
        set_new_val(file_num)
    if event == Evt.PREV_IMG:
        file_num = nsfiles.num - 1 if nsfiles.curent == 0 else nsfiles.curent - 1
        set_new_val(file_num)
    if event == Evt.NEXT_IMG:
        file_num = 0 if nsfiles.curent == nsfiles.num - 1 else nsfiles.curent + 1
        set_new_val(file_num)
    if event in (Evt.PREV_IMG, Evt.NEXT_IMG, '-FILES-'):
        set_new_val(file_num)
    if event == Evt.TAB_OPTIONS:
        window['-TAB_OPTIONS-'].select()
    if event == Evt.TAB_FILES:
        window['-TAB_FILES-'].select()
    if event == Evt.TAB_SAVE:
        window['-TAB_SAVE-'].select()
    if event == Evt.TAB_SETUP:
        window['-TAB_SETUP-'].select()
    if event == '-SCALE_PERCENT-':
        try:
            scale = int(window['-SCALE_PERCENT-'].get())
            if scale > 0:
                w, h = calc_scale(scale=scale)
                window['-SCALE_W-'].update(str(w))
                window['-SCALE_H-'].update(str(h))
        except ValueError:
            pass
    if event == '-SCALE_W-':
        try:
            w = int(window['-SCALE_W-'].get())
            if w > 0:
                scale, h = calc_scale(w=w)
                window['-SCALE_PERCENT-'].update(scale)
                window['-SCALE_H-'].update(str(h))
        except ValueError:
            pass
    if event == '-SCALE_H-':
        try:
            h = int(window['-SCALE_H-'].get())
            if h > 0:
                scale, w = calc_scale(h=h)
                window['-SCALE_PERCENT-'].update(scale)
                window['-SCALE_W-'].update(str(w))
        except ValueError:
            pass
    if event in ('-IMAGE-'):
        if show_result:
            window['-IMAGE-'].update(data=nsfiles.files[nsfiles.curent].png_img)
        else:
            # window['-IMAGE-'].update(data=None)
            window['-IMAGE-'].update(data=nsfiles.files[nsfiles.curent].result_img)
        show_result = not show_result
    if event == '-BUTTON_SAVE-':
        process_save(values)
window.close()
del window
