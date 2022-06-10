import pathlib
import re
import argparse
import xlsxwriter

from xlsxwriter.utility import xl_rowcol_to_cell, xl_col_to_name
from pyparsing import ParseException
from jinja2 import Environment, FileSystemLoader

from commons import field_types, special_types, extracted_types, calculated_fields, numeric_fields, \
    need_transform_types, default_encoding, output_formats, default_format, file_by_line, \
    time_mark, app_name, to_number, string_list
from styles_parser import Style
from config_parser import report_grammar
 
from logger import get_logger


# Procesa listados de texto
# El programa es siempre el mismo, pero puede procesar distintos listados
# usando distintos ficheros de configuración

# Para cada tipo de listado a procesar necesitamos una definición del listado,
# que no es más que un archivo de configuración que nos indica como se estructura
# el listado y como vamos a procesarlo.
# Cada listado está dividido en secciones (Section) que almacenan la información
# que hemos ido recopilando.
# La información de cada section se almacena en líneas.
# Cada línea está compuesta de campos (Field).
# Cada Section se define por una SectionDef (definición de sección) que indica
# como ha de procesarse una sección. En un listado puede haber varias Section que
# hagan referencia a la misma SectionDef.
# De igual forma, cada Field se define por una FieldDef (definición de campo) que indica
# como ha de procesarse un campo. En un listado puede haber innumerables campos que
# hagan referencia a la misma FieldDef.


# Inicia el sistema de log
logger = get_logger()

# separador por defecto de los campos (csv)
field_separator = ';'

# expresiones regulares usadas para sustituir indices relativos a la celda actual de filas y columnas
row_index_regexp = re.compile(r'<ROW:(?P<offset>-?\d+)>')
col_index_regexp = re.compile(r'<COL:(?P<offset>-?\d+)>')


# excepción personalizada para alertar de errores en el archivo de configuración
class FieldException(Exception):
    pass


class Field:
    # Descripción de un campo
    # Los campos pueden ser extraídos o calculados
    # Los campos extraídos obtienen su valor del listado que está siendo procesado
    # extrayendo su valor de la línea a procesar, entre las columnas izquierda y derecha
    # indicadas en la definición del campo
    # Los no extraídos (campos especiales) pueder ser campos vacíos, campos valor o campos calculados (fórmula de excel)

    def __init__(self, field, index):
        self.index = index
        self.type = field.type
        self.style_id = field.style_id if hasattr(field, 'style_id') else None
        self.name = field.name if field.name else None
        if self.is_extracted:
            self.value = tuple(field.value)
            if self.left < 0:
                message = f'Columna {self.index}: Limite izquierdo (left={self.left}) inferior a 0'
                logger.error(message)
                raise FieldException(message)
            # comprobamos que el extremo derecho no sea inferior al izquierdo
            if self.right < self.left:
                message = f'Columna {self.index}: Limite derecho (right={self.right}) ' \
                          f'inferior al limite izquierdo (left={self.left})'
                logger.error(message)
                raise FieldException(message)
        else:
            self.value = field.value

    def __str__(self):
        value = f'"{self.value}"' if isinstance(self.value, str) else self.value
        style_id = f'"{self.style_id}"' if self.style_id else None
        name = f'"{self.name}"' if self.name else None
        return f'Field(type="{self.type.name}", index={self.index}, name={name}, value={value}, style_id={style_id})'

    def __repr__(self):
        return self.__str__()

    @property
    def is_special(self):
        # estos son los campos que no se extraen del documento, sino que se crean
        return self.type in special_types

    @property
    def need_transform(self):
        # estos campos necesitan una transformación previa antes de almacenarlos
        return self.type in need_transform_types

    @property
    def is_extracted(self):
        # campos que se extraen del listado
        return self.type in extracted_types

    @property
    def is_calculated(self):
        return self.type in calculated_fields

    @property
    def is_numeric(self):
        return self.type in numeric_fields

    @property
    def left(self):
        if self.is_extracted:
            return self.value[0]
        else:
            message = 'El campo no es extraible y no tiene el atributo "left"'
            logger.error(message)
            raise FieldException(message)

    @property
    def right(self):
        if self.is_extracted:
            return self.value[1]
        else:
            message = 'El campo no es extraible y no tiene el atributo "right"'
            logger.error(message)
            raise FieldException(message)


class Fieldset:
    # Definición de fieldset
    # Guarda la información sobre como debe procesarse una determinada sección del listado

    def __init__(self, new_row=False, keep_in_row=False, include_filters=None, is_header=False, is_footer=False):

        self.fields = []

        # filtros de inclusión
        # las líneas que concuerden con alguno de los filtros de inclusión de una sección
        # seran procesadas por dicha sección
        # los almacenamos como regexp compiladas
        self.include_filters = [
            re.compile(include_filter) for include_filter in include_filters
        ] if include_filters else []

        # FIXME: quizas new_row y keep_in_row deberian ser mutuamente excluyentes
        self.new_row = new_row
        self.keep_in_row = keep_in_row
        self.is_header = is_header
        self.is_footer = is_footer

    def __str__(self):
        new_row = f'new_row={self.new_row}'
        keep_in_row = f'keep_in_row={self.keep_in_row}'
        is_header = f'is_header={self.is_header}'
        is_footer = f'is_footer={self.is_footer}'
        patterns = [f'"{include_filter.pattern}"' for include_filter in self.include_filters]
        include_filters = f'include_filters=[{string_list(patterns, " ")}]'
        return f'Fieldset(\n{new_row},\n{keep_in_row},\n{include_filters},\n{is_header},\n{is_footer},' \
               f'\nfields=[\n{string_list(self.fields)}\n]\n)'


class Section:
    # Definición de sección
    # Guarda la información sobre como debe procesarse una determinada sección del listado

    def __init__(self, process_only_one_time=False, blank_row=False):
        # lista de encabezados de las columnas
        # puede haber una o ninguna fila de encabezados
        # puede que no todas las columnas tengan encabezados
        self.header = []

        # lista de pies de las columnas
        # puede haber una o ninguna fila de pies
        # puede que no todas las columnas tengan pies
        self.footer = []

        # lista de definición de los campos que formaran cada línea de la seccion
        self.body = []

        # si process_only_one_time == True la sección solo se procesara la primera vez que aparezca
        # las siguientes veces que se encuentre dicha sección se ignorara
        self.process_only_one_time = process_only_one_time

        # indica si se agrega una línea en blanco al final de la sección
        # en formato xls lo único que hacemos es saltar una fila de la hoja de cálculo
        self.blank_row = blank_row

        # Indica si la sección ya fue procesada
        # es un flag que se usa con el anterior
        self.processed = False

    @property
    def has_header(self):
        # indica si la sección tiene fila de encabezado de columnas
        return True if self.header else False

    @property
    def has_footer(self):
        # indica si la sección tiene fila de pies de columnas
        return True if self.footer else False

    def __str__(self):
        flags = f'blank_row={self.blank_row},\nprocess_only_one_time={self.process_only_one_time},'
        header = f'\nheader=[\n{string_list(self.header)}\n],' if self.header else ''
        body = f'\nbody=[\n{string_list(self.body)}\n],'
        footer = f'\nfooter=[\n{string_list(self.footer)}\n]' if self.footer else ''
        return f'Section(\n{flags}{header}{body}{footer}\n)'


class Cell:
    # Esto es un campo ya procesado y es el que realmente contiene información
    # Cada Cell guarda una referencia al Field que lo define

    def __init__(self, col, row, field, original_value):
        self._row = row  # fila del campo, empezando en cero
        self._col = col  # columna del campo, empezando en cero
        self.field = field  # referencia al Field correspondiente a este campo
        self._original_value = original_value  # El valor original antes de procesarlo

        field_type = field.type
        if not field.need_transform:
            # el campo no necesita transformación previa, lo devolvemos tal cual
            self._value = original_value
        else:
            # quitamos los espacios sobrantes en los extremos
            stripped_value = original_value.strip()
            if field_type == field_types.string:
                # campo de cadena
                self._value = stripped_value
            elif field_type in numeric_fields:
                # campo numérico
                self._value = to_number(stripped_value, field_type)

    @property
    def original_value(self):
        # el valor del campo sin transformaciones
        return self._original_value

    # devuelve el nombre de la celda que no es otro que el nombre dado al campo
    # util para exportar los datos a formatos como JSON y XML
    @property
    def name(self):
        name = self.field.name
        if name is None:
            # devuelve un nombre por defecto si no se ha indicado ninguno
            return f'field{self._col}'
        elif self.field.type == field_types.empty and self.field.value != 1:
            # si es un campo emtpy que se repite, los enumeramos para que no coincidan
            return f'{name}{self._col}'
        return name

    @property
    def col(self):
        # columna del campo: 0,1,2,....
        return self._col

    @property
    def row(self):
        # fila del campo: 0,1,2,...
        return self._row

    @property
    def excel_row(self):
        # excel cuenta las filas comenzando en 1
        return self._row + 1

    @property
    def excel_col(self):
        # Devuelve el nombre de la columna de excel a partir de su índice: A, B,.., Z, AB, AC,...
        return xl_col_to_name(self.col)

    @property
    def excel_cell(self):
        # nombre de la celda en formato excel: A1, D2, AA3, BC45, ....
        return xl_rowcol_to_cell(self._row, self._col)

    @property
    def value(self):
        if self.field.is_calculated:
            # Para los campos que son fórmulas de excel
            # cambiamos los marcadores de celda por sus valores correspondientes
            # <col> es la columna actual
            # <col:-1> es la columna anterior a la actual (a la izquierda)
            # <col:-i> es la i-ésima columna anterior a la actual (a la izquierda)
            # <col:+1> es la columna siguiente a la actual (a la derecha)
            # <col:+i> es la i-ésima columna siguiente a la actual (a la derecha)
            # <row> es la fila actual
            # <row:-1> es la fila anterior a la actual (encima)
            # <row:-i> es la i-ésima fila anterior a la actual (encima)
            # <row:+1> es la fila siguiente a la actual (debajo)
            # <row:+i> es la i-ésima fila siguiente a la actual (debajo)
            # <startrow> es la fila inicial de la sección actual (sin inlcuir el posible encabezado)
            # <rows> es el número de filas totales del listado (incluye encabezados y pies)

            val = row_index_regexp.sub(
                lambda match_object: f'{self.excel_row + int(match_object.group("offset"))}',
                self._value
            )
            val = col_index_regexp.sub(
                lambda match_object: xl_col_to_name(self.col + int(match_object.group('offset'))),
                val
            )
            return val
        else:
            return self._value

    def __str__(self):
        value = f'"{self.value}"' if isinstance(self.value, str) else self.value
        return f'Cell(address="{self.excel_cell}", type="{self.field.type.name}", value={value})'

    def __repr__(self):
        return self.__str__()


# representa un fila, que es un conjuto de celdas
class Row:

    def __init__(self, fieldset, cells):
        self.fieldset = fieldset
        self.cells = list(cells)  # las celdas que forma la fila

    # indica si la fila pertenece a la cabecera, útil para formatear la salida
    @property
    def is_header(self):
        return self.fieldset.is_header

    # indica si la fila pertenece al pie
    @property
    def is_footer(self):
        return self.fieldset.is_footer

    # indica si la fila pertenece al cuerpo
    @property
    def is_body(self):
        return not (self.fieldset.is_header or self.fieldset.is_footer)

    def __str__(self):
        cells = string_list((str(item) for item in self.cells))
        return f'Row(is_header={self.is_header}, is_footer={self.is_footer}, is_body={self.is_body}, ' \
               f'cells=(\n{cells}\n)\n)'

    def __iter__(self):
        # itermaos sobre el conjunto de celdas
        for cell in self.cells:
            yield cell

    def __len__(self):
        return len(self.cells)

    def append(self, other):
        self.cells.append(other)



class CellGroup:
    # Guarda la información que se va recolectando al procesar una sección
    def __init__(self, index=0, start_row=0, section=None):
        self.index = index  # índice de la seccion
        self._start_row = start_row  # fila de comienzo de la sección
        self.section = section  # referencia a la definicion de la sección
        # contiene las líneas de la sección que formarán la salida
        # incluye, si existen, la línea de encabezados y pies de la sección
        self.lines = []

    @property
    def start_row(self):
        # las filas de encabezados no cuentan como comienzo de sección
        return self._start_row + len(self.section.header) if self.section.has_header else self._start_row

    @property
    def excel_start_row(self):
        # excel cuenta las filas desde 1 en vez desde 0
        return self.start_row + 1

    def __str__(self):
        cells = [f'{line}' for line in self.lines]
        return f'CellGroup(\nindex={self.index},\nstart_row={self.start_row},\nlines=[\n{string_list(cells)}\n]\n)'

    def __repr__(self):
        return self.__str__()


class Report:
    # Clase para procesar los listados

    def __init__(self, config_file):
        # carga el fichero de configuración para procesar el listado

        self._same_row = False
        
        # definición de los parámetros de cada sección del listado
        self.sections = []
        
        self.styles = {}
        
        # grupos procesados
        self.cell_groups = []
        
        # contador de filas
        self.rows = 0
        
        # lee el archivo de configuración
        report_config = report_grammar.parse_file(config_file, parse_all=True)
        
        # creamos un estilo por defecto sin opciones para las celdas que no definan ningún estilo
        # self.styles[None] = {}
        # almacenamos los estilos definidos en el archivo de configuración
        for style in report_config.styles:
            self.styles[style.style_id] = style.as_dict()
        
        # filtros de exclusión
        # las líneas que concuerden serán descartadas sin ningún procesamiento
        # los almacenamos como regexp compiladas
        self.exclude_filters = [re.compile(exclude_filter) for exclude_filter in report_config.exclude_filters]
        
        # Ancho de las columnas
        self.columns_width = report_config.columns_width

        # si no se especifica ningún encoding, se usa utf-16 por defecto
        self.encoding = report_config.get('encoding', default_encoding)

        # título del listado
        self.title = report_config.title

        # texto explicativo del listado
        self.description = report_config.get('description', 'No hay descripcion para el listado seleccionado.').strip()

        self.include_filters = []

        for section in report_config.sections:
            current_section = Section(process_only_one_time=section.process_only_one_time, blank_row=section.blank_row)

            if section.header:
                for fieldset in section.header:
                    current_fieldset = Fieldset(is_header=True)
                    for index, field in enumerate(fieldset.fields):
                        current_fieldset.fields.append(Field(field, index))
                    current_section.header.append(current_fieldset)

            if section.footer:
                for fieldset in section.footer:
                    current_fieldset = Fieldset(is_footer=True)
                    for index, field in enumerate(fieldset.fields):
                        current_fieldset.fields.append(Field(field, index))
                    current_section.footer.append(current_fieldset)

            # body es obligatorio
            for fieldset in section.body:
                current_fieldset = Fieldset(
                    new_row=fieldset.new_row,
                    keep_in_row=fieldset.keep_in_row,
                    include_filters=fieldset.include_filters
                )
                for index, field in enumerate(fieldset.fields):
                    current_fieldset.fields.append(Field(field, index))

                for include_filter in current_fieldset.include_filters:
                    self.include_filters.append((include_filter, current_section, current_fieldset))
                current_section.body.append(current_fieldset)

            # guardamos la definición de sección actual
            self.sections.append(current_section)

    def __str__(self):
        result = 'Report(\n'
        result += f'title="{self.title}",\n'
        result += f'description="{self.description}",\n'
        result += f'encoding="{self.encoding}",\n'
        result += f'columns_width={self.columns_width},\n'
        patterns = [f'"{exclude_filter.pattern}"' for exclude_filter in self.exclude_filters]
        result += f'exclude_filters=[{string_list(patterns, " ")}],\n'
        result += 'Styles=[\n'
        for style in self.styles.values():
            result += f'{Style(style)}\n'
        result += '],\n'
        result += 'Sections=[\n'
        for section in self.sections:
            result += f'{section}\n'
        result += ']\n'
        result += ')\n'
        return result

    # comprueba si la línea en curso concuerda con alguno de los filtros de exclusión definidos
    def _exclude_line(self, line):
        for exclude_filter in self.exclude_filters:
            if exclude_filter.match(line):
                return True
        return False

    def _match_include_filters(self, line):
        for test_filter, test_section, test_fieldset in self.include_filters:
            if test_filter.match(line):
                return test_filter, test_section, test_fieldset
        return None, None, None

    def _store_row(self, fields_group, line, r_index, g_index):
        # almacena los campos de la línea actual

        # FIXME: falta por tener en cuenta los flags de los fieldsets del body

        # fields_group es un fieldset
        # r_index = row index
        # g_index = group index

        new_row = fields_group.new_row if hasattr(fields_group, 'new_row') else False
        keep_in_row = fields_group.new_row if hasattr(fields_group, 'keep_in_row') else False

        if self._same_row and not new_row:
            # mantenerse en la línea actual
            row = self.cell_groups[g_index].lines[-1] if self.cell_groups[g_index].lines else []
        else:
            # nueva línea
            if self._same_row and new_row:
                r_index += 1
                self._same_row = False
            row = []

        col_index = len(row)

        for field in fields_group.fields:

            if field.is_extracted:
                # extraemos los campos de la línea actual
                # los campos son de longitud fija
                left, right = field.value
                original_value = line[left:right]
            elif field.type == field_types.empty:
                # insertamos celdas vacías
                for i in range(field.value):
                    row.append(Cell(col_index, r_index, field, None))
                    col_index += 1
                continue
            else:
                cell_group = self.cell_groups[g_index]
                if field.type == field_types.function:
                    original_value = field.value.replace('<STARTROW>', f'{cell_group.excel_start_row}')
                    original_value = original_value.replace('<ROWS>', f'{r_index}')
                else:
                    original_value = field.value

            row.append(Cell(col_index, r_index, field, original_value))
            col_index += 1

        # guardamos la lista de campos como una tupla
        if row:
            if self._same_row:
                self.cell_groups[g_index].lines[-1] = Row(fields_group, row)
            else:
                self.cell_groups[g_index].lines.append(Row(fields_group, row))
            if keep_in_row:
                self._same_row = True
            else:
                self._same_row = False
                r_index += 1

        return r_index

    def process(self, report_file):
        # procesa el listado

        # contendrá las líneas del listado una vez procesado
        self.cell_groups = []
        current_cell_group = CellGroup()
        group_index = 0

        # iteramos sobre el listado
        row_index = 0

        try:
            for number_line, line in enumerate(file_by_line(report_file, encoding=self.encoding), 1):

                # descartamos las líneas que coinciden con algún filtro de exlcusión
                if self._exclude_line(line):
                    continue

                # Probamos cada línea contra todos los include_filters de todas las secciones
                # si la línea no concuerda con ningún filtro de inclusión simplemente la ignoramos
                include_filter, section, fieldset = self._match_include_filters(line)

                if not include_filter:
                    # avanzamos a la siguiente linea
                    continue

                if not (section.process_only_one_time and section.processed):

                    if section != current_cell_group.section:
                        # empieza una nueva sección en el listado

                        if current_cell_group.section:
                            #  ponemos los pies de columna de la sección actual, si existen
                            for footer in current_cell_group.section.footer:
                                row_index = self._store_row(
                                    footer,
                                    line,
                                    row_index,
                                    current_cell_group.index
                                )

                            if current_cell_group.section.blank_row:
                                # línea en blanco al final de la sección
                                row_index += 1

                        # hemos terminado con la sección anterior, comenzamos una nueva
                        current_cell_group = CellGroup(group_index, row_index, section)
                        self.cell_groups.append(current_cell_group)
                        group_index += 1

                        # ponemos la fila de encabezados de la nueva sección, si existe
                        for header in current_cell_group.section.header:
                            row_index = self._store_row(
                                header,
                                line,
                                row_index,
                                current_cell_group.index
                            )

                    # guardamos la línea actual
                    row_index = self._store_row(fieldset, line, row_index, current_cell_group.index)
                    self.rows = row_index  # actualizamos el contador de filas

                    # marcamos la sección actual como procesada por si solo hay que procesarla una vez
                    section.processed = True

        except Exception as e:
            logger.error('Error: Ha ocurrido un error inesperado')
            logger.error(f'Error: Fichero: {report_file} - Numero de linea: {number_line}')
            raise e

        # insertamos el pie de la última sección, si existe
        if current_cell_group:
            #  ponemos los pies de columna de la sección actual, si existen
            for footer in current_cell_group.section.footer:
                row_index = self._store_row(
                    footer,
                    line,
                    row_index,
                    current_cell_group.index
                )

    def xlsx(self, file_name, sheet_name=None):
        # listado de salida en formato XLS

        book = xlsxwriter.Workbook(file_name)  # libro vacio
        # añadimos el autor y el nombre de la aplicación al libro de Excel
        properties = {'author': app_name}
        book.set_properties(properties)
        book.set_custom_property('Aplicación', app_name)

        sheet = book.add_worksheet(sheet_name)  # creamos una hoja de cálculo

        styles = {}

        for style_id in self.styles.keys():
            style = Style(self.styles[style_id])
            styles[style_id] = book.add_format(style.style)

        for column, column_width in enumerate(self.columns_width):
            sheet.set_column(column, column, column_width)

        for cell_group in self.cell_groups:
            for line in cell_group.lines:
                for cell in line:
                    style = styles[cell.field.style_id] if cell.field.style_id in styles else None
                    if cell.field.is_calculated and cell.value.startswith("="):
                        # campos con fórmulas
                        sheet.write_formula(cell.row, cell.col, cell.value, style)
                    else:
                        # campos normales
                        sheet.write(cell.row, cell.col, cell.value, style)

        # salvamos el fichero
        book.close()


def process_report(
        spool_file, report, templates_folder, output_format=default_format,
        output_folder=".", time_stamp=False, keep_extension=False
):
    # Procesa un listado y genera otro con el formato de salida solicitado

    # procesa el listado de entrada
    report.process(spool_file)

    in_file = pathlib.Path(spool_file)

    output_file_name = f'{time_mark() if time_stamp else ""}{in_file.stem}' \
                       f'{in_file.suffix if keep_extension else ""}.{output_format.name}'

    # el fichero de salida tendrá el mismo nombre que el fichero de entrada
    # más la extension del formato de salida
    output_file = pathlib.Path.joinpath(output_folder, output_file_name)

    if output_format in (output_formats.csv, output_formats.html, output_formats.xml, output_formats.json):

        templates = {
            output_formats.csv: 'csv.jinja', 
            output_formats.html: 'html.jinja', 
            output_formats.xml: 'xml.jinja', 
            output_formats.json: 'json.jinja'
        }

        template_file = templates[output_format]
 
        file_loader = FileSystemLoader(templates_folder)
        env = Environment(loader=file_loader, trim_blocks=True, lstrip_blocks=True)
        template = env.get_template(template_file)

        rendered_template = template.render(report=report)
        if rendered_template:
            with open(output_file, 'w') as fout:
                fout.write(rendered_template)

    else:
        # por defecto, salida en formato xlsx
        report.xlsx(output_file)

    logger.info(f'Generado fichero {output_file}')
    return output_file

  
def report_processor(args):
    # Función principal
    # procesa la línea de comandos si existe y procesa los listados indicados

    output_format = args.format  # formato de salida == extensión del fichero de salida
    output_folder = args.output_folder
    templates_folder = args.templates_folder
    time_stamp = args.time_stamp
    keep_extension = args.keep_extension
    conf_file = args.conf_file

    output_files = []

    # carga el fichero de configuración adecuado para el reporte
    report = Report(conf_file)

    # procesa todos los nombres de archivos pasados como argumentos
    for input_file in args.files:

        try:
            # procesa el listado
            output_file = process_report(
                input_file, report, templates_folder,
                output_formats[output_format], output_folder, time_stamp, keep_extension
            )
            output_files.append(output_file)
        except ParseException as e:
            logger.error(f'Ha ocurrido un error interpretando el archivo {conf_file}')
            logger.error(f'Linea {e.lineno}, Columna {e.col}:\n"{e.line}"')

        except Exception as e:
            logger.error(f'Error inesperado mientras se procesaba el fichero {input_file}')
            logger.error(f'Exception: {str(e)}')
            raise e

    return output_files


def parse_args():
    # Gestor de los parámetros de la línea de comandos
    parser = argparse.ArgumentParser(description=f'Convierte un fichero de texto tabulado a formato XLSX, CSV, JSON, XML o HTML.')

    current_folder = pathlib.Path(__file__).parent.absolute()
    templates_folder = pathlib.Path.joinpath(current_folder, 'templates')

    # Parametros de la línea de comandos
    parser.add_argument(
        '-c',
        '--conf-file',
        required=True,
        help='Fichero de configuracion para transformar el listado'
    )

    parser.add_argument(
        '-o',
        '--output-folder',
        default=current_folder,
        type=pathlib.Path,
        help=f'Carpeta donde se guardaran los ficheros generados. Por defecto: {current_folder}'
    )

    parser.add_argument(
        '-tf',
        '--templates-folder',
        default=templates_folder,
        type=pathlib.Path,
        help=f'Carpeta donde estan las plantillas para los formatos csv, json, xml y html. Por defecto: {templates_folder}'
    )

    parser.add_argument(
        '-t',
        '--time-stamp',
        action='store_true',
        help='Inserta una marca de tiempo al comienzo del nombre de los ficheros de salida generados'
    )

    parser.add_argument(
        '-k',
        '--keep-extension',
        action='store_true',
        help='Mantiene las extensiones de los ficheros de entradas en los nombres de los ficheros de salida generados'
    )

    parser.add_argument(
        '-f',
        '--format',
        choices=[x.name for x in output_formats],
        default=default_format.name,
        help=f'Formato de salida. Por defecto: {default_format.name}'
    )

    # Lista de ficheros a procesar
    parser.add_argument(
        'files',
        nargs='+',
        help='Fichero/s a procesar'
    )

    # procesa la línea de comandos
    return parser.parse_args()    


if __name__ == '__main__':

    cli_args = parse_args() 

    generated_files = report_processor(cli_args)
    if generated_files:
        print('Se han creado los siguientes ficheros:')
        for _file in generated_files:
            print(_file)
