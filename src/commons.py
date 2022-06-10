from enum import Enum
from decimal import Decimal
from datetime import datetime

import argparse
import re


# autor y nombre de la aplicación
app_name = 'Redaxtor (https://github.com/JeCuRoz/Redaxtor)'

separator = '_'

# símbolos para formatos numéricos
comma = ','
dot = '.'
minus = '-'
default_decimal_separator = dot

# codificaciones de los ficheros de entrada
encodings = ['utf-8', 'ascii', 'latin-1', 'utf-16', 'utf_16_le']
default_encoding = encodings[0]  # utf-8


# convierte una cadena con un formato numérico en un número del tipo indicado
# usando esta clase facilitamos añadir números con otros formatos numéricos
class NumericType:

    def __init__(self, pattern, decimal_separator='', thousands_separator='', return_type=int):

        if decimal_separator and decimal_separator == thousands_separator:
            raise Exception(
                f'El separador decimal "{decimal_separator}" es igual al separador de millar "{thousands_separator}"'
            )

        self.regex = re.compile(pattern)  # regex para comprobar que el numero cumple el formato numerico
        self.decimal_separator = decimal_separator  # caracter usado como separador decimal
        self.thousands_separator = thousands_separator  # caracter usado como separador de millar
        self.type = return_type  # tipo del numero devuelto

    def __str__(self):
        return f'{{pattern: "{self.regex.pattern}", thousands_separator: "{self.thousands_separator}", ' \
               f'decimal_separator: "{self.decimal_separator}", type: {self.type}}}'

    def to_number(self, value):
        if not value:
            # si el valor esta vacio devolvemos el 0 del tipo indicado
            return self.type()
        elif self.regex.fullmatch(value):
            # el valor cumple el formato numérico
            # quitamos los separadores de millar
            new_value = value.replace(self.thousands_separator, '') if self.thousands_separator else value
            # forzamos que el separador decimal sea el .
            if self.decimal_separator and self.decimal_separator != default_decimal_separator:
                new_value = new_value.replace(self.decimal_separator, default_decimal_separator)
            # casting
            return self.type(new_value)
        else:
            # el valor de entrada no sigue el formato numérico esperado
            raise ValueError


# posibles formatos de salida
output_formats = Enum('OutputFormats', 'xlsx csv html xml json')
default_format = output_formats.xlsx


# Tipos de campos
#
# campos especiales, no existen en el fichero de entrada sino que se añaden al fichero de salida
#
#     function        campo calculado, cadena que representa una fórmula de excel
#     empty           campo vacío, añade una celda vacía, puede llevar un entero para indicar más de una celda
#     const           campo valor, constante que puede ser una cadena o un número
#
# campos extraídos, datos que se extraen del fichero de entrada y formaran parte del fichero de salida
#
#     campos de texto
#         string          campo de cadena de ancho variable, se eliminan los espacios del final
#         fixed           campo de cadena de ancho fijo, se mantienen los espacios del inicio y del final
#
#     campos numéricos, formato numérico solo para interpretar los datos de entrada, no se aplica a los datos de salida
#
#         números enteros, se mapean a un int de python
#             integer         sin separador de millar
#             integerc        usa , como separador de millar
#             integerd        usa . como separador de millar
#
#         números en coma flotante, se mapean a un float de python
#             float           sin separador de millar y usa . como separador decimal
#             floatc          sin separador de millar y usa , como separador decimal
#             floatcd         usa , como separador de millar y usa . como separador decimal
#             floatdc         usa . como separador de millar y usa , como separador decimal
#
#         números decimales, se mapean a un Decimal de python (módulo decimal)
#             decimal         sin separador de millar y usa . como separador decimal
#             decimalc        sin separador de millar y usa , como separador decimal
#             decimalcd       usa , como separador de millar y usa . como separador decimal
#             decimaldc       usa . como separador de millar y usa , como separador decimal


field_types = Enum(
    'Types',
    'function empty const string fixed '
    'integer integerc integerd '
    'float floatc floatdc floatcd '
    'decimal decimalc decimaldc decimalcd'
)

# campos especiales, pueden ser cadenas, fórmulas de excel o celdas vacías
special_types = frozenset([field_types.function, field_types.empty, field_types.const])

# campos numéricos
numeric_fields = frozenset([
    field_types.integer, field_types.integerc, field_types.integerd,
    field_types.float, field_types.floatc, field_types.floatdc, field_types.floatcd,
    field_types.decimal, field_types.decimalc, field_types.decimaldc, field_types.decimalcd
])

# campos que necesitan ser procesados antes de almacenarlos
need_transform_types = frozenset.union(numeric_fields, [field_types.string])

# campos extraídos del fichero de entrada
extracted_types = frozenset.union(need_transform_types, [field_types.fixed])

# estos campos representan fórmulas de excel
calculated_fields = frozenset([field_types.function])

# información sobre el formato de los distintos tipos numéricos
numeric_types_info = {
    field_types.integer: NumericType(
        pattern=fr'{minus}?\d+'  # formato numérico que debe cumplir el número de entrada
    ),
    field_types.integerc: NumericType(
        pattern=fr'{minus}?\d{{1,3}}(?:{comma}\d{{3}})*', 
        thousands_separator=comma  # separador de millar del número de entrada
    ),
    field_types.integerd: NumericType(
        pattern=fr'{minus}?\d{{1,3}}(?:\{dot}\d{{3}})*', 
        thousands_separator=dot
    ),
    field_types.float: NumericType(
        pattern=fr'{minus}?\d+(?:\{dot}\d+)?', 
        decimal_separator=dot,  # separador decimal del número de entrada
        return_type=float  # tipo numérico en el que se transformara el número de entrada
    ),        
    field_types.floatc: NumericType(
        pattern=fr'{minus}?\d+(?:\{comma}\d+)?', 
        decimal_separator=comma, 
        return_type=float
    ),
    field_types.floatcd: NumericType(
        pattern=fr'{minus}?\d{{1,3}}(?:{comma}\d{{3}})*(?:\{dot}\d+)?', 
        thousands_separator=comma, 
        decimal_separator=dot, 
        return_type=float
    ),
    field_types.floatdc: NumericType(
        pattern=fr'{minus}?\d{{1,3}}(?:\{dot}\d{{3}})*(?:{comma}\d+)?', 
        thousands_separator=dot, 
        decimal_separator=comma, 
        return_type=float
    ),
    field_types.decimal: NumericType(
        pattern=fr'{minus}?\d+(?:\{dot}\d+)?', 
        decimal_separator=dot, 
        return_type=Decimal
    ),
    field_types.decimalc: NumericType(
        pattern=fr'{minus}?\d+(?:\{comma}\d+)?', 
        decimal_separator=comma, 
        return_type=Decimal
    ),
    field_types.decimalcd: NumericType(
        pattern=fr'{minus}?\d{{1,3}}(?:{comma}\d{{3}})*(?:\{dot}\d+)?', 
        thousands_separator=comma, 
        decimal_separator=dot, 
        return_type=float
    ),
    field_types.decimaldc: NumericType(
        pattern=fr'{minus}?\d{{1,3}}(?:\{dot}\d{{3}})*(?:{comma}\d+)?', 
        thousands_separator=dot, 
        decimal_separator=comma, 
        return_type=float
    )
}


# funciones auxiliares


# crea una marca de tiempo actual para agreagar al nombre de los archivos
def time_mark(sep=separator):
    return datetime.now().strftime(f'%Y%m%d{sep}%H%M%S{sep}')


# itera línea a línea sobre un fichero
# se puede aplicar una función (func) a cada línea antes de devolverla
def file_by_line(filename, func=None, **kwargs):
    with open(filename, **kwargs) as f:
        for line in f:
            yield func(line) if func else line


# devuelve la lista de nombres de los tipos
def type_names(types_list):
    return [x.name for x in types_list]


# devuelve la lista de valores de los tipos
def type_values(types_list):
    return [x.value for x in types_list]


# convierte una cadena en un miembro de Types
def store_type(tokens):
    return field_types[tokens[0]]


# almacena el booleano True
def store_true(tokens):
    return True


# almacena el booleano False
def store_false(tokens):
    return False


# almacena el valor entero de tokens
def store_int(tokens):
    return int(tokens[0])


# almacena el valor de un campo empty (número de repeticiones), devuelve 1 si se ha omitido
def store_empty(tokens):
    value = int(tokens[0]) if tokens else 1
    # lanza una excepcion si el valor es menor que 1
    if value < 1:
        raise ValueError(f'El valor de un campo empty no puede se menor que 1. Valor definido: {value}')
    return value


# almacena True si existe un elemento opcional, False en caso contrario
def store_optional(tokens):
    result = True if tokens else False
    return result


# almacena el valor de una clave
def store_dict_value(_dict):
    return lambda tokens: _dict[tokens[0]]


# devuelve todos los tokens unidos
def join_tokens(tokens):
    return ''.join(tokens)


# usada para imprimir los resultados en depuración
def print_item(label, value='', level=0, tab='\t'):
    alignment = tab * level
    print(f'{alignment}- {label}: {value}')
    

# usada para imprimir los resultados en depuración
def print_single_item(label, level=0, tab='\t'):
    alignment = tab * level
    print(f'{alignment}- {label}')


def string_list(container, sep='\n'):
    return f',{sep}'.join([str(item) for item in container])


# parser básico para la línea de comandos
def parse_args(description=None):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('file', help='Fichero de a procesar')
    return parser.parse_args()


# convierte una cadena en un número teniendo en cuenta el formato numérico
def to_number(value, numeric_type):
    try:
        type_info = numeric_types_info[numeric_type]
        return type_info.to_number(value)
    except ValueError:
        raise ValueError(f'El numero {value} de formato {numeric_type} no sigue el patron {type_info.regex.pattern}')
    except Exception as e:
        raise e
