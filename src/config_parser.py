# parser para los ficheros de definición de informes

import pyparsing as pp

from commons import extracted_types, type_names, store_empty, store_type, store_optional, \
    print_item, print_single_item, encodings, parse_args

from styles_parser import Style, styles_grammar, print_style, text, style_id

from excel_parser import key_separator, number, excel_parser

# codificación de los ficheros de entrada
codec = pp.one_of(encodings, caseless=True)
encoding = pp.CaselessLiteral('encoding').suppress() + codec('encoding')

# estilo de formato para aplicar a cada campo 
# es el estilo de la celda en la hoja de cálculo resultante
style_def = pp.Suppress(key_separator) + style_id.set_results_name('style_id')

# el tipo de campo extraído
# indica que tipo de valor se ha extraído
# dependiendo del tipo de campo el valor extraído será procesado de una forma u otra
# puede que se convierta en un número, o se quiten los espacios en blanco,...
column_type = pp.one_of(type_names(extracted_types), caseless=True).set_parse_action(store_type)

integer = pp.common.integer

# cada línea del archivo original es una cadena de texto
# índice izquierdo para extraer el valor
left_index = integer
# índice derecho para extraer el valor
right_index = integer
value = pp.Group(left_index + right_index)

# campos extraídos
# su valor se extrae del archivo de entrada entre los caraceteres
# con índices left y right
extracted_field = column_type('type') + value('value')

# campo en blanco, se usa para crear relleno
# si no se especifica un valor solo se deja en blanco una celda
# si se indica un valor se añadiran ese número de celdas en blanco
empty_field = \
    pp.CaselessLiteral('empty').set_parse_action(store_type).set_results_name('type') + \
    pp.Opt(integer).set_parse_action(store_empty).set_results_name('value')

# campo de valor
# el valor de la celda será el indicado en el campo
# está pensado para títulos de encabezado, constantes,....
const_field = \
    pp.CaselessLiteral('const').set_parse_action(store_type).set_results_name('type') + \
    (text | number).set_results_name('value')

# campo de fórmula
# el valor del campo es una fórmula de excel
# el valor final será el calculado por la fórmula
calculated_field = \
    pp.CaselessLiteral('function').set_parse_action(store_type).set_results_name('type') + \
    excel_parser.set_results_name('value')

# los campos especiales son aquellos cuyo valor no se extrae del listado original
special_field = const_field | calculated_field | empty_field

# definición de los filtros de exclusión/inclusión
filters = pp.delimited_list(text)

# nombre del campo, opcional
field_name = pp.CaselessLiteral('as') + pp.pyparsing_common.identifier.set_results_name('name')

# definición de campo estandar
field_def = (extracted_field | special_field) + pp.Opt(field_name) + pp.Opt(style_def)

# grupo de definiciones de campos
field_defs = pp.OneOrMore(pp.Group(field_def))

# hace que no se añada una nueva fila a la salida despúes de procesar la línea en curso
# los campos de las siguientes líneas se situarán en la misma fila que los de la línea en curso
keep_in_row = pp.Opt(pp.CaselessLiteral('keep_in_row')).set_parse_action(store_optional)

# fuerza a que los campos de la línea en curso se añadan en una nueva línea aunque se haya usado el flag keep_in_row
new_row = pp.Opt(pp.CaselessLiteral('new_row')).set_parse_action(store_optional)

# flags opcionales para el fieldSet
field_flags = new_row('new_row') + keep_in_row('keep_in_row')

# Lista de filtros de inclusión
# las líneas que concuerden con algún filtro de inclusión seran procesadas por
# el fieldSet correspondiente
include_filters = pp.CaselessLiteral('include_filters').suppress() + filters

# los fieldsets se componen de una lista de campos (de cualquier tipo)
# más información (flags) sobre como se procesan
field_set = pp.CaselessLiteral('fieldset').suppress() + include_filters('include_filters') + \
             field_flags + field_defs('fields')
field_set_def = pp.OneOrMore(pp.Group(field_set))

body = pp.CaselessLiteral('body').suppress() + field_set_def('fieldsets*')

# en el encabezado o en el pie solo se permiten campos especiales
special_field_def = special_field + pp.Opt(field_name) + pp.Opt(style_def)

# grupo de definiciones de campos especiales
special_field_defs = pp.OneOrMore(pp.Group(special_field_def))

special_field_set = pp.CaselessLiteral('fieldset').suppress() + special_field_defs('fields')
special_field_set_def = pp.OneOrMore(pp.Group(special_field_set))

# pie de la sección (opcional)
# son los pies de las columnas
footer = pp.CaselessLiteral('footer').suppress() + special_field_set_def('fieldsets*')
footer_def = pp.Opt(footer)

# encabezado de la sección (opcional)
# son los encabezados de las columnas
header = pp.CaselessLiteral('header').suppress() + special_field_set_def('fieldsets*')
header_def = pp.Opt(header)

# añadir una línea (fila) en blanco despúes de la sección
blank_row = pp.Opt(pp.CaselessLiteral('blank_row')).set_parse_action(store_optional)

# la sección solo se procesa una vez
# las sucesivas veces que se encuentren líneas del archivo de entrada susceptibles
# de ser procesadas por esta sección, serán descartadas
process_only_one_time = pp.Opt(pp.CaselessLiteral('process_only_one_time')).set_parse_action(store_optional)

# flags globales para la sección (opcionales)
section_flags = process_only_one_time('process_only_one_time') + blank_row('blank_row')

# cada sección define como se procesa parte del archivo de entrada

section = pp.CaselessLiteral('section').suppress() + section_flags + \
          header_def('header') + body('body') + footer_def('footer')

# lista de secciones
sections = pp.OneOrMore(pp.Group(section))

# lista de filtros de exclusión (opcional)
# las líneas del listado original que concuerden con alguno de los filtros
# serán descartadas inmediatamente sin ser procesadas
exclude_filters = pp.CaselessLiteral('exclude_filters').suppress() + filters
exclude_filters_def = pp.Opt(exclude_filters)

# ancho de las columnas (opcional)
# se define globalmente para todo el reporte (hoja de calculo)
columns_width = pp.CaselessLiteral('columns_width').suppress() + \
                pp.Group(pp.OneOrMore(integer)).set_results_name('columns_width')

# texto descriptivo sobre el listado (opcional)
description = pp.QuotedString('description', end_quote_char='/description', multiline=True)
description_def = pp.Opt(description)

# título descriptivo del listado (requerido)
title = pp.CaselessLiteral('title').suppress() + pp.rest_of_line.set_results_name('title')

styles_grammar_def = pp.Opt(styles_grammar)

# raíz de la gramática
report_grammar =  \
    title + description_def('description') + pp.Opt(encoding) + pp.Opt(columns_width) + \
    exclude_filters_def('exclude_filters') + styles_grammar_def + sections('sections')

# los comentarios estilo python dentro de los archivos de configuración
# están permitidos y son ignorados
report_grammar.ignore(pp.python_style_comment)


def test_report_conf(report_file):

    from logger import get_logger

    # Inicia el sistema de log
    logger = get_logger()

    def print_fields(fields, level=0):
        for index, field in enumerate(fields):
            print_item('field', index, level)
            print_item('type', field.type.name, level+1)
            print_item('value', field.value, level+1)
            print_item('name', field.name, level+1)
            if field.style_id:
                print_item('style', field.style_id, level+1)

    def print_list(items, level=0):
        for item in items:
            print_single_item(item, level=level)

    try:

        with open(report_file) as report:
            result = report_grammar.parse_file(report, parse_all=True)

        print_item('title', result.title)

        if result.description:
            print_item('description', result.description)

        if result.encoding:
            print_item('encoding', result.encoding)

        if result.columnsWidth:
            print_item('columns_width', result.columns_width)

        if result.excludeFilters:
            print_item('exclude_filters')
            print_list(result.exclude_filters, 1)

        if result.styles:
            for style in result.styles:
                a_style = Style(style)
                print_style(a_style)

        for i, sec in enumerate(result.sections):
            print_item('section', i, 0)
            print_item('process_only_one_time', sec.process_only_one_time, level=1)
            print_item('blank_row', sec.blank_row, level=1)

            if sec.header:
                print_item('header', level=1)
                for j, fs in enumerate(sec.header):
                    print_item('fieldset', j, level=2)
                    print_item('fields', level=3)
                    print_fields(fs.fields, 4)

            print_item('body', level=1)
            for j, fs in enumerate(sec.body):
                print_item('fieldset', j, level=2)
                print_item('include_filters', level=3)
                print_list(fs.include_filters, 4)
                print_item('keep_in_row', fs.keep_in_row, level=3)
                print_item('new_row', fs.new_row, level=3)
                print_item('fields', level=3)
                print_fields(fs.fields, 4)

            if sec.footer:
                print_item('footer', level=1)
                for j, fs in enumerate(sec.footer):
                    print_item('fieldset', j, level=2)
                    print_item('fields', level=3)
                    print_fields(fs.fields, 4)

    except pp.ParseException as e:
        logger.error(f'Ha ocurrido un error interpretando el archivo {report_file}')
        logger.error(f'Linea {e.lineno}, Columna {e.col}:\n"{e.line}"')

    except Exception as e:
        logger.error('Ha ocurrido un error inesperado')
        raise e


if __name__ == '__main__':

    # procesa los argumentos pasados en la línea de comandos
    args = parse_args('Procesa un fichero de definicion de un reporte')

    test_report_conf(args.file)
