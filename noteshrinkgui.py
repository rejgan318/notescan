"""
GUI for noteshrink
https://github.com/mzucker/noteshrink
https://mzucker.github.io/2016/09/20/noteshrink.html
"""
# TODO Основной модуль обработки
# TODO Размер по горизонтали
# TODO Окно просмотра - разметка на 2 файла? КЛик на картинке = показать обработанный файл?
# TODO Непонятный таймаут после FileBrowse
# TODO Мультипоточность
# TODO считывание параметров слайдеров с таймаутом
# TODO Увеличение при просмотре?
# TODO сохранение в pdf через PIL (в noteshrink сделано чрез вызов внешнего процесса):
#   вариант через PIL (не подходит, исходный файл должен быть jpg)
#    PILimage.save(r'C:\Users\Ron\Desktop\Test\myImages.pdf',save_all=True, append_images=PILimageslist)
#   вариант https://pypi.org/project/img2pdf/ - вроде норм. Протестировать. Позволяет задать размеры pdf в мм
# TODO сворачивающиеся вкладки меню
# DONE Окно параметров
# DONE Сохранение параметров выбора директории и остальных
# DONE статусная строка с прогрессбаром и процентами
# DONE список файлов - добавление, очистка
# DONE иконку

import enum
import io
from PIL import Image, ImageOps
from pathlib import Path
import PySimpleGUI as sg


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
}
icon_base64 = b'iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAABmJLR0QA/wD/AP+gvaeTAAAA/ElEQVRoge3aSwrCQBBF0avbMduR' \
              b'DFxItuCeFeLEgHaS/uRD12vqQgZOpA6BxC4Er2q32gMc0R14Ac/ag+xpQozfSxLT848Yv5+7mkOVFt6JEXgDj5pDleYIK5lGjMG1' \
              b'lmkE5EHMIyANkUBAHCKDgHWIFAKWIXIImEMkETCHLP126qtNV1AIkbsTU6chLrtHKyv2No+VnPO68YvN5RDP87TKfY+c9vw/qmae' \
              b'Wg5praXzRM6WxFQphARkbaEsBYkdT2UgqTO2BCRnUWAekrvtMA0pWdmYhZTunUxCtizPzEFkN4C/OcJKTSA6hBfKYQPCdyJsoAHE' \
              b'VBN/IZLtA/9g/jmly8UBAAAAAElFTkSuQmCC'


class NSFlags(enum.IntFlag):
    LOADED = enum.auto()
    CALCULATED = enum.auto()


class NSFileInfo:
    def __init__(self, file):
        self.state = 0
        f = Path(file).resolve()
        self.name = str(f.name)
        self.fullname = str(f)
        self.pil_img = None
        self.png_img = None
        self.result_img = None

class NoteShrink:
    def __init__(self, file=None):
        self.files = []
        self.finfo = {}
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

# _ = [nsfiles.add(f) for f in settings["-files-"]]

layout_setup = [
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

layout_files = [
    [sg.FilesBrowse(' + ', key='-SELECT_FILES-', tooltip='Добавить файлы для обработки', enable_events=True, target='-SELECT_FILES-'),
     sg.Button(' - ', key='-CLEAR_FILES-', tooltip='Очистить список файлов', enable_events=True, ), ],
    [sg.Listbox(key='-FILES-', values=nsfiles.get_files_name(), enable_events=True, size=(27, 15),
                select_mode=sg.LISTBOX_SELECT_MODE_SINGLE)],
]

layout_left_column = [
    [sg.Frame(layout=layout_setup, title='Установки', tooltip='Установить режинмы')],
    [sg.Frame(layout=layout_files, title='Файлы', tooltip='Файлы для обработки')],
    # layout_status_bar,
]
layout_right_column = [[sg.Image(key='-IMAGE-', data=nsfiles.get_img(0), enable_events=True, )]]

layout_status_bar = [
    [sg.Text(key='-FICTION_LINE_FOR_EXPAND-', font='ANY 1', pad=(0, 0))],
    [sg.StatusBar(key='-STATUS2-', size=(20, None), text='Информация статусная'),  # text_color='yellow',
     sg.StatusBar(key='-STATUS3-', size=(30, None), text='И еще что-то выводим...', justification='right'),
     sg.ProgressBar(key='-PROGRESS-', size=(10, 20), orientation='horizontal', max_value=100,
                    bar_color=(sg.theme_element_text_color(), sg.theme_background_color(),), ),
     sg.Text('', key='-PERCENT-', size=(5, None), justification='right'),
     ]
]
layout = [[sg.Column(layout_left_column, vertical_alignment='top'), sg.Column(layout_right_column)], layout_status_bar]
window = sg.Window('NoteshrinkGUI', layout=layout, return_keyboard_events=True, resizable=True, icon=icon_base64,
                   finalize=True, )
window['-FICTION_LINE_FOR_EXPAND-'].expand(expand_x=True, expand_y=True, expand_row=True)
window.Maximize()
# window['-PROGRESS-'].update(20)

show_result = False
files_name = []
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
            if f not in settings['-files-']:
                settings['-files-'] += [f]
                nsfiles.add(f)
                nsfiles.process(index)
                index += 1
        # files_name = [str(Path(f).name) for f in settings['-files-']]
        window['-FILES-'].update(values=nsfiles.get_files_name())
    if event in ('-CLEAR_FILES-'):
        settings['-files-'] = []
        del nsfiles
        nsfiles = NoteShrink()
        window['-FILES-'].update(values=[])
        window['-IMAGE-'].update(data=None)
    if event in ('-FILES-'):
        file_num = window['-FILES-'].get_indexes()[0]
        nsfiles.set_curent(file_num)
        window['-IMAGE-'].update(data=nsfiles.get_img(file_num))
        show_result = False
    if event in ('-IMAGE-'):
        if show_result:
            window['-IMAGE-'].update(data=nsfiles.files[nsfiles.curent].png_img)
        else:
            # window['-IMAGE-'].update(data=None)
            window['-IMAGE-'].update(data=nsfiles.files[nsfiles.curent].result_img)
        show_result = not show_result

window.close()
del window
