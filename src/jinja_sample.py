from jinja2 import Environment, FileSystemLoader


templates_folder = pathlib.Path()
template_file = 

file_loader = FileSystemLoader(str(templates_folder))
env = Environment(loader=file_loader, trim_blocks=True, lstrip_blocks=True)
template = env.get_template(template_file)

rendered_template = template.render(data=data)
filename = 
_file = pathlib.Path(output_folder) / pathlib.Path(filename)
if rendered_template:
    with open(_file, 'w') as fout:
        fout.write(rendered_template)
