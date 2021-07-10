Опции Noteshrink
===



  -h, --help          show this help message and exit

  -d                  Use GUI dialog

  -q                  reduce program output

  -b BASENAME         output PNG filename base (default ns_page)

  -o PDF              output PDF filename (default output.pdf)

  **-v** PERCENT          background value threshold % (default 25)

  **-s** PERCENT          background saturation threshold % (default 20)

  **-n** NUM_COLORS       number of output colors (default 8)

  **-p** PERCENT          % of pixels to sample (default 5)

  -w                  make background white

  **-g**                  use one global palette for all pages

  -S                  do not saturate colors

  -K                  keep filenames ordered as specified; use if you *really*
                      want IMG_10.png to precede IMG_2.png

  -P POSTPROCESS_CMD  set postprocessing command (see -O, -C, -Q)

  -e POSTPROCESS_EXT  filename suffix/extension for postprocessing command

  -O                  same as -P "optipng -silent %i -out %o"

  -C                  same as -P "pngcrush -q %i %o"

  -Q                  same as -P "pngquant --ext %e %i"

  -c COMMAND          PDF command (default "magick convert %i %o")
