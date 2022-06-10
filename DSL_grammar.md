
	
# Redaxtor: Gramática del DSL para procesar textos tabulares

Símbolos usados en la definición de la gramática (no deben teclearse):

	:=  El símbolo a la izquierda es un no terminal que se descompone según lo indicado en la parte derecha.

	""  El texto que aparece entre comillas debe introducirse literalmente (sin las comillas).

	()  Usados para agrupar elementos que deben aparecer juntos.

	[]  Los elementos que parecen dentro son opcionales (aparecen cero o una vez)

	{}  Elementos que pueden aparecer cero o más veces.

	Dos elementos que aparecen seguidos en una regla se concatenan.

Hay algunos identificadores que corresponden a elementos definidos por el módulo pyparsing: **rest_of_line**, **delimited_list**, **dbl_quoted_string**, **Word**, **alphas**, **alphanums**, **nums**, **Regex**, **integer**, **identifier**, **ipv4_address**, **ipv6_address**. Más información en (https://pyparsing-docs.readthedocs.io/en/latest/pyparsing.html).

Aunque no aparezca en la gramática, el DSL permite comentarios estilos python, es decir, usando el carácter **#**.

El lenguaje es **case insensitive** (da igual que se usen mayúsculas o minúsculas).

## La gramática
---

**report_grammar** := title [description] [encoding] [columns_width] [exclude_filters] [styles] sections

**title** := "title" rest_of_line

**description** := *"description"*  text *"/description"*

**text** := dbl_quoted_string

**encoding** := *"encoding"* codec

**codec** := *"ascii"* | *"utf-8"* | *"utf-16"* | *"latin-1"* | *"utf_16_le"*

**columns_width** := *"columns_width"* widths

**widths** := integer {integer}

**exclude_filters** := *"exclude_filters"* filters

**sections** := section {sections}

**section** := *"section"* section_flags [header] body [footer]

**section_flags** := [process_only_one_time] [blank_row]

**process_only_one_time** := *"process_only_one_time"*

**blank_row** := *"blank_row"*

**styles** := style {style}

**style** = *"style"* style_id style_options

**style_id** := identifier

style_options := [font_name] [font_size] [font_bold] [font_italic] [font_underline] [font_outline] [horizontal_align] [vertical_align] [border_style] [background_color] [foreground_color] [unlocked_cell] [hidden_cell] [wrap_text] [shrink_text]

**font_name** := *"font"* text

**font_size** := *"size"* integer

**font_bold** := *"bold"*

**font_italic** := *"italic"*

**font_underline** := *"underline"*

**font_outline** := *"strikeout"*

**horizontal_align** := *"align"* (*"left"* | *"center"* | *"right"* | *"justify"*)

**vertical_align** := *"valign"* (*"top"* | *"center"* | *"bottom"* | *"justify"*)

**border_style** := *"border"* [color_id] border_line

**background_color** := *"background"* color_id

**foreground_color** := *"color"* color_id

**unlocked_cell** := *"unlocked"*

**hidden_cell** := *"hidden"*

**wrap_text** := *"wrap"*

**shrink_text** := *"shrink"*

**color_id** := color_code | color_name

(* Color en formato de 6 digitos hexadecimales sin el caracter # al principio *)
**color_code** := Regex("[0-9a-fA-F]{6}")

**color_name** := *"black"* | *"blue"* | *"brown"* | *"cyan"* | *"gray"* | *"green"* | *"lime"* | *"magent"* | *"navy"* | *"orange"* | *"pink"* | *"purple"* | *"red"* | *"silver"* | *"white"* | *"yellow"*

**border_line** := *"no_line"* | *"thin"* | *"medium"* | *"dashed"* | *"dotted"* | *"thick"* | *"double"* | *"hair"* | *"medium_dashed"* | *"thin_dash_dotted"* | *"medium_dash_dotted"* | *"thin_dash_dot_dotted"* | *"medium_dash_dot_dotted"* | *"slanted_medium_dash_dotted"*

**header** := *"header"* special_fieldsets

**footer** := *"footer"* special_fieldsets

**special_fieldsets** := special_fieldset {special_fieldset}

**special_fieldset** := *"fieldset"* special_field_defs

**special_field_defs** := special_field_def {special_field_def}

**special_field_def** := special_field [field_name] [style_def]

**body** := *"body"* fieldsets

**fieldsets** := fieldset {fieldset}

**fieldset** := *"fieldset"* include_filters field_flags field_defs

**include_filters** := *"include_filters"* filters

**filters** = delimited_list(text)

**field_flags** := [new_row] [keep_in_row]

**new_row** := *"new_row"*

**keep_in_row** := *"keep_in_row"*

**field_defs** := field_def {field_def}

**field_def** := (extracted_field | special_field) [field_name] [style_def]

**extracted_field** := column_type left_index right_index

**column_type** := *"string"* | *"fixed"* | *"integer"* | *"integerc"* | *"integerd"* | "float" | "floatc" | *"floatdc"* | *"floatcd"* | *"decimal"* | *"decimalc"* | *"decimaldc"* | *"decimalcd"*

**left_index** := integer

**right_index** := integer

**special_field** := const_field | calculated_field | empty_field

**const_field** := *"const"* (text | number)

**calculated_field** := *"function"* excel_expression

**empty_field** := *"empty"* [integer]

**field_name** := *"as"* identifier

**style_def** := key_separator style_id

**excel_expression** := text | ([unary_op] number) | (assign_op expression)

**expression** := term {add_op term}

**term** := factor {mult_op factor}

**factor** := number | (add_op expression) | (left_paren expression right_paren) | formula_excel | constant | cell_reference

**formula_excel** := function_name left_paren parameters right_paren

**function_name** := identifier {function_name_separator identifier}

**function_name_separator** := *"."*

**parameters** := parameter {parameter_separator parameter}

**parameter** := expression | text | condition | constant | cell_range

**condition** := expression relational_op expression

**constant** := identifier

**cell_range** := cell range_separator cell

**cell** := [absolute_op] col_id [absolute_op] row_id

**col_id** := alphas | relative_col

**relative_col** := *"<col"* [offset] *">"*

**row_id** := integer | relative_row | *"<rows>"* | *"<startrow>"*

**relative_row** := "*<row" *[offset] *">"*

**offset** := range_separator [unary_op] integer

**identifier** := Word(alphas, alphanums)

**integer** := Word(nums)

**real** := integer decimal_separator integer

**number** := integer | real 

**separator** := *","*

**key_separator** := *":"*

**parameter_separator** := *","*

**range_separator** := *":"*

**decimal_separator** := *"."*

**quote** := *"'"* | *'"'*

**left_paren** := *"("*

**right_paren** := *")"*

**assign_op** := *"="*

**absolute_op** := *"$"*

**unary_op** := *"-"* | *"+"*

**add_op** := *"+"* | *"-"*

**mult_op** := "*" | *"/"*

**relational_op** := *"="* | *"<>"* | *">"* | *">="* | *"<"* | *"<="*

**file_name** := identifier [*"."* identifier ]

**folder_name** := identifier  

**server_name** := identifier  

**share** := identifier  

**path_separator** := *"\"* | *"/"*

**partial_path** := folder_name path_separator

**drive** = Regex("[a-zA-Z]:") 

**server_header** := *"\\\\"* | [*"smb:"*] *"//"*

**server_address** := ipv4_address | ipv6_address

**server_id** := server_address | server_name

**server** := server_header server_id path_separator share

**base_path** := drive | server

**workbook_file** := file_name

**workbook_path** := [base_path] path_separator {partial_path}

**quote** := *"'"*

**address_operator** := *"!"*

**linked_workbook** := quote [workbook_path] workbook_file quote

**sheet_name** := Regex("[0-9a-zA-Z_-]{1,31}")

**sheet** := [linked_workbook] sheet_name address_operator

**workbook** := linked_workbook address_operator

**sheet_named_range** := identifier

**book_named_range** := workbook sheet_named_range

**sheet_address** := cell ^ cell_range ^ sheet_named_range

**cell_reference** := ([sheet] sheet_address) | book_named_range