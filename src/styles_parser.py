# parser para los estilos

import pyparsing as pp
from enum import Enum

from logger import get_logger
from commons import store_false, store_true, store_int, store_dict_value, print_item, parse_args


# Estilos para las celdas
class Style:

    def __init__(self, style):
        self.style = {}
        for option, value in style.items():
            if option == 'style_id':
                self.style_id = value
                continue
            elif option == 'border':
                self.style[option] = value.value
            else:
                self.style[option] = value

    # Devuelve el estilo como una cadena
    def __str__(self):
        attributes = [f'style_id="{self.style_id}"']

        for attribute, value in self.style.items():
            value = f'"{value}"' if isinstance(value, str) else value
            attributes. append(f'{attribute}={value}')

        return f'Style({", ".join(attributes)})'


# FIXME: lo mismo que para los colores
# Estilos de bordes de las celdas en Excel
class Border(Enum):
    no_line = 0  # weight :  0   -   style :
    thin = 1  # weight :  1   -   style :  -----------
    medium = 2  # weight :  2   -   style :  -----------
    dashed = 3  # weight :  1   -   style :  - - - - - -
    dotted = 4  # weight :  1   -   style :  . . . . . .
    thick = 5  # weight :  3   -   style :  -----------
    double = 6  # weight :  3   -   style :  ===========
    hair = 7  # weight :  0   -   style :  -----------
    medium_dashed = 8  # weight :  2   -   style :  - - - - - -
    thin_dash_dotted = 9  # weight :  1   -   style :  - . - . - .
    medium_dash_dotted = 10  # weight :  2   -   style :  - . - . - .
    thin_dash_dot_dotted = 11  # weight :  1   -   style :  - . . - . .
    medium_dash_dot_dotted = 12  # weight :  2   -   style :  - . . - . .
    slanted_medium_dash_dotted = 13  # weight :  2   -   style :  / - . / - .


border_names = [x.name for x in Border]

# Opciones de alineación vertical en excel
valign_options = {
    'top': 'top',
    'bottom': 'bottom',
    'center': 'vcenter',
    'justify': 'vjustify'
}

# reglas de la gramática

text = pp.dbl_quoted_string.copy().set_parse_action(pp.remove_quotes)

# nombre/identificador del estilo
# style_id = pp.Word(pp.alphas, pp.alphanums)
style_id = pp.pyparsing_common.identifier

integer = pp.Word(pp.nums)

# expresión de formato numérico de celdas en excel
# más información: https://xlsxwriter.readthedocs.org/format.html#set_num_format
number_format = pp.CaselessLiteral('format').suppress() + text.set_results_name('num_format')

font_name = pp.CaselessLiteral('font').suppress() + text.set_results_name('font_name')
 
font_size = pp.CaselessLiteral('size').suppress() + \
            integer.copy().set_parse_action(store_int).set_results_name('font_size')

font_bold = pp.CaselessLiteral('bold').set_parse_action(store_true).set_results_name('bold')

font_italic = pp.CaselessLiteral('italic').set_parse_action(store_true).set_results_name('italic')

font_underline = pp.CaselessLiteral('underline').set_parse_action(store_true).set_results_name('underline')

font_outline = pp.CaselessLiteral('strikeout').set_parse_action(store_true).set_results_name('font_strikeout')

horizontal_align = pp.CaselessLiteral('align').suppress() + \
                   pp.one_of('left center right justify').set_results_name('align')

vertical_align = pp.CaselessLiteral('valign').suppress() + \
    pp.one_of(list(valign_options.keys())).set_parse_action(store_dict_value(valign_options)).set_results_name('valign')

# color en formato hexadecimal RRGGBB (ejemplo AABB11)
# no incluyo # porque el parser lo interpreta como un comentario dentro del archivo de la gramática, lo añado más tarde
# prefijamos el código del color con #
color_code = pp.Word(pp.srange('[a-fA-F0-9]'), exact=6).set_parse_action(lambda tokens: '#' + tokens[0])

color_name = pp.one_of('black blue brown cyan gray green lime magent navy orange pink purple red silver white yellow')

color_id = (color_name | color_code).set_results_name('color_id')

border_line = pp.one_of(border_names).set_parse_action(store_dict_value(Border))

background_color = pp.CaselessLiteral('background').suppress() + color_id.set_results_name('bg_color')

foreground_color = pp.CaselessLiteral('color').suppress() + color_id.set_results_name('font_color')

# El color del borde es opcional
borderStyle = pp.CaselessLiteral('border').suppress() + \
    (pp.Opt(color_id.set_results_name('border_color')) & border_line.set_results_name('border'))
 
unlocked_cell = pp.CaselessLiteral('unlocked').set_parse_action(store_false).set_results_name('locked')

hidden_cell = pp.CaselessLiteral('hidden').set_parse_action(store_true).set_results_name('hidden')

wrap_text = pp.CaselessLiteral('wrap').set_parse_action(store_true).set_results_name('text_wrap')

shrink_ext = pp.CaselessLiteral('shrink').set_parse_action(store_true).set_results_name('shrink')

style_options =                  \
    pp.Opt(number_format) &      \
    pp.Opt(font_name) &          \
    pp.Opt(font_size) &          \
    pp.Opt(font_bold) &          \
    pp.Opt(font_italic) &        \
    pp.Opt(font_underline) &     \
    pp.Opt(font_outline) &       \
    pp.Opt(horizontal_align) &   \
    pp.Opt(vertical_align) &     \
    pp.Opt(borderStyle) &        \
    pp.Opt(background_color) &   \
    pp.Opt(foreground_color) &   \
    pp.Opt(unlocked_cell) &      \
    pp.Opt(hidden_cell) &        \
    pp.Opt(wrap_text) &          \
    pp.Opt(shrink_ext)

cell_style = pp.CaselessLiteral('style').suppress() + style_id.set_results_name('style_id') + style_options

styles_grammar = pp.OneOrMore(pp.Group(cell_style)).set_results_name('styles')

# los comentarios estilo python están permitidos pero son ignorados
styles_grammar.ignore(pp.python_style_comment)


# Pretty printer para los estilos
def print_style(style, align_level=0):

    print_item('style', style.style_id)
    align_level += 1  # nivel de indentación

    for attribute, value in style.style.items():
        print_item(attribute, value, align_level)


if __name__ == '__main__':

    # Inicia el sistema de log
    logger = get_logger()

    # procesa los argumentos pasados en la línea de comandos
    args = parse_args('Procesa un fichero de estilos')
    
    try:

        with open(args.file) as styles:
            result = styles_grammar.parse_file(styles)

        for current_style in result.styles:
            a_style = Style(current_style)
            # print_style(a_style)
            print(a_style)

    except pp.ParseException as e:
        logger.error(f'Ha ocurrido un error interpretando el archivo {args.styles_file}')
        logger.error(f'Linea {e.lineno}, Columna {e.col}:\n"{e.line}"')
    
    except Exception as e:
        logger.error('Ha ocurrido un error inesperado.')
        raise e
