import pyparsing as pp

from styles_parser import integer, text
from commons import join_tokens, parse_args

# parser para expresiones y fórmulas de excel

# NOTA: el parser no verifica que los nombres de las funciones de excel sean los correctos

# FIXME: estos identificadores necesitan mejorar
identifier = pp.pyparsing_common.identifier
file_name = identifier + pp.Optional(pp.Literal('.') + identifier)  # nombre de fichero, sin espacios
folder_name = identifier  # nombre de carpeta
server_name = identifier  # nombre del servidor
share = identifier  # nombre de carpeta compartida

path_separator = pp.one_of(r"\ /")
partial_path = folder_name + path_separator

drive = pp.Word(pp.alphas, exact=1) + pp.Literal(":")
server_header = pp.Literal(r"\\") | (pp.Optional(pp.Literal(r'smb:')) + pp.Literal(r'//'))
server_address = pp.pyparsing_common.ipv4_address | pp.pyparsing_common.ipv6_address
server_id = server_address | server_name
server = server_header + server_id + path_separator + share

base_path = drive | server

workbook_file = file_name
workbook_path = pp.Optional(base_path) + path_separator + pp.ZeroOrMore(partial_path)
quote = pp.Literal("'")
address_operator = pp.Literal("!")
linked_workbook = quote + pp.Optional(workbook_path) + workbook_file + quote
sheet_name = pp.Word(pp.alphanums + '-_', max=31)  # nombre de hoja de cálculo, no espacios
sheet = pp.Optional(linked_workbook) + sheet_name + address_operator
workbook = linked_workbook + address_operator

# separador de argumentos de las fórmulas de excel
# Nota: debe usarse la coma (,) como separador de argumentos en las funciones de Excel
parameter_separator = pp.Literal(',')

separator = pp.Suppress(',')
key_separator = pp.Suppress(':')
range_separator = pp.Literal(':')  # separador de rangos de excel
decimal_separator = pp.one_of('.')  # separadores decimal en las expresiones excel
quote = pp.Literal("'") | pp.Literal('"')
left_parenthesis = pp.Literal('(')
right_parenthesis = pp.Literal(')')
assign_operator = pp.Literal('=')
absolute_operator = pp.Literal('$')
unary_operator = pp.Literal('-') | pp.Opt(pp.Suppress('+'))  # el + unario es opcional y lo eliminamos si aparece
add_operator = pp.one_of('+ -')  # operadores de suma y resta
mult_operator = pp.one_of('* /')  # operadores de multiplicación y división
relational_operator = pp.one_of('= <> > >= < <=')  # operadores relacionales

real = pp.Combine(integer + decimal_separator + integer)
number = integer ^ real  # se usa ^ en vez de | para que busque la coincidencia más larga

# desplazamiento sobre la celda actual para calcular un índice relativo de fila o columna
# siempre añadimos un desplazamiento aunque no se indique
# si no se pone se añade un desplazamiento 0. Esto significa que
# <row> se sustituye por <row:0> y <col> se sustituye por <col:0>
# el + unario se suprime si se indica (<row:+5> se sustituye por <row:5>)
offset = pp.Opt(
    range_separator + unary_operator + integer
).set_parse_action(lambda tokens: ''.join(tokens) if tokens else ':0')

# identificador de columna relativo a la columna actual
relative_col = pp.Literal('<col') + offset + pp.Literal('>')

# identificador de columna:
# índice de columna: A, AB, AAC,....
# <col> es la columna actual
# <col:-1> es la columna anterior a la actual (a la izquierda)
# <col:-i> es la i-ésima columna anterior a la actual (a la izquierda)
# <col:+1> es la columna siguiente a la actual (a la derecha)
# <col:+i> es la i-ésima columna siguiente a la actual (a la derecha)
col_id = pp.Word(pp.alphas) | relative_col

# identificador de fila relativo a la fila actual
relative_row = pp.Literal('<row') + offset + pp.Literal('>')

# identificador de fila
# indice de fila: 1,2,8,50,..
# <row> es la fila actual
# <row:-1> es la fila anterior a la actual (encima)
# <row:-i> es la i-ésima fila anterior a la actual (encima)
# <row:+1> es la fila siguiente a la actual (debajo)
# <row:+i> es la i-ésima fila siguiente a la actual (debajo)
# <startrow> es la fila inicial de la seccion actual (sin inlcuir el posible encabezado)
# <rows> es el número de columnas totales del listado (incluye encabezados y pies)
row_id = integer | relative_row | pp.Literal('<rows>') | pp.Literal('<startrow>')

# identificador de celda (direccionamiento absoluto o relativo)
cell = (
    pp.Combine(pp.Opt(absolute_operator) + col_id + pp.Opt(absolute_operator) + row_id)
).set_parse_action(pp.pyparsing_common.upcase_tokens)

# identificador de rango de celdas
cell_range = (pp.Combine(cell + range_separator + cell)).set_parse_action(pp.pyparsing_common.upcase_tokens)

# rango con nombre, ambito de hoja
sheet_named_range = pp.pyparsing_common.identifier
# rango con nombre, ambito de libro
book_named_range = workbook + sheet_named_range

# direcciones de celda dentro de una hoja
sheet_address = cell ^ cell_range ^ sheet_named_range
# direcciones de celda dentro de un libro
cell_reference = pp.Combine((pp.Optional(sheet) + sheet_address) | book_named_range)

constant = identifier
expression = pp.Forward()
condition = expression + relational_operator + expression
parameter = expression ^ pp.dbl_quoted_string ^ condition ^ constant ^ cell_range
parameters_list = parameter + pp.ZeroOrMore(parameter_separator + parameter)
function_name_separator = pp.Literal('.')
function_name = identifier + pp.ZeroOrMore(function_name_separator + identifier)
formula_excel = function_name + left_parenthesis + parameters_list + right_parenthesis
term = pp.Forward()
factor = number ^ add_operator + expression ^ left_parenthesis + expression + right_parenthesis ^ \
         formula_excel ^ constant ^ cell_reference
term << factor + pp.ZeroOrMore(mult_operator + factor)
expression << term + pp.ZeroOrMore(add_operator + term)
excel_parser = text | pp.Combine(pp.Opt(unary_operator) + number) | assign_operator + expression
excel_parser.set_parse_action(join_tokens)

# los comentarios estilo python están permitidos pero son ignorados
excel_parser.ignore(pp.python_style_comment)


if __name__ == '__main__':

    # procesa los argumentos pasados en la línea de comandos
    args = parse_args('Procesa un fichero con expresiones y formulas de excel')

    with open(args.file) as test_file:
        # ignora líneas en blanco
        expressions = (test for line in test_file.readlines() if (test := line.strip()))

    for expression in expressions:
        if expression:
            print(f'{expression}  => ', end='')
            try:
                parse_result = excel_parser.parse_string(expression, parse_all=True)
                print(f'{parse_result}')
            except pp.exceptions.ParseException as e:
                print('ERROR')
                print('Ha ocurrido un error mientras se procesaba la expresion en curso:')
                print(f'{e}\n\n')
            except Exception as e:
                print('Ha ocurrido un error inesperado')
                raise e
