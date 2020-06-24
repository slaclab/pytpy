"""
"pytmc-summary" is a command line utility for inspecting TwinCAT3
.tsproj projects.
"""

import argparse
import ast
import fnmatch
import pathlib
import sys

from .. import parser, pragmas
from . import util


DESCRIPTION = __doc__


def build_arg_parser(argparser=None):
    if argparser is None:
        argparser = argparse.ArgumentParser()

    argparser.description = DESCRIPTION
    argparser.formatter_class = argparse.RawTextHelpFormatter

    argparser.add_argument(
        'filename', type=str,
        help='Path to project or solution (.tsproj, .sln)'
    )

    argparser.add_argument(
        '--all', '-a', dest='show_all',
        action='store_true',
        help='All possible information'
    )

    argparser.add_argument(
        '--outline', dest='show_outline',
        action='store_true',
        help='Outline XML'
    )

    argparser.add_argument(
        '--boxes', '-b', dest='show_boxes',
        action='store_true',
        help='Show boxes'
    )

    argparser.add_argument(
        '--code', '-c', dest='show_code',
        action='store_true',
        help='Show code'
    )

    argparser.add_argument(
        '--plcs', '-p', dest='show_plcs',
        action='store_true',
        help='Show plcs'
    )

    argparser.add_argument(
        '--nc', '-n', dest='show_nc',
        action='store_true',
        help='Show NC axes'
    )

    argparser.add_argument(
        '--symbols', '-s', dest='show_symbols',
        action='store_true',
        help='Show symbols'
    )

    argparser.add_argument(
        '--types', dest='show_types',
        action='store_true',
        help='Show TMC types and record suffixes, if available'
    )

    argparser.add_argument(
        '--filter-types',
        action='append',
        type=str,
        help='Filter the types shown by name'
    )

    argparser.add_argument(
        '--links', '-l', dest='show_links',
        action='store_true',
        help='Show links'
    )

    argparser.add_argument(
        '--markdown', dest='use_markdown',
        action='store_true',
        help='Make output more markdown-friendly, for easier sharing'
    )

    argparser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Post-summary, open an interactive Python session'
    )

    return argparser


def outline(item, *, depth=0, f=sys.stdout):
    indent = '  ' * depth
    num_children = len(item._children)
    has_container = 'C' if hasattr(item, 'container') else ' '
    flags = ''.join((has_container, ))
    name = item.name or ''
    print(f'{flags}{indent}{item.__class__.__name__} {name} '
          f'[{num_children}]', file=f)
    for child in item._children:
        outline(child, depth=depth + 1, f=f)


def list_types(plc, pragma='pv: @(PREFIX)', filter_types=None,
               file=sys.stdout):
    tmc = plc.tmc
    if not tmc:
        print('* TMC unavailable to show types', file=file)
        return

    for data_type in tmc.find(parser.DataType):
        if filter_types:
            if not any(fnmatch.fnmatch(data_type.name, filter_type)
                   for filter_type in filter_types):
                continue

        symbol = pragmas.make_fake_symbol_from_data_type(
            data_type, pragma)
        try:
            packages = list(pragmas.record_packages_from_symbol(symbol))
        except Exception as ex:
            print(f'Failed: {ex}', file=file)
            print(file=file)
            continue

        if not packages:
            continue

        util.sub_heading(f'Data type {data_type.name}', file=file)
        block = [
            record.pvname
            for record in sorted((record for pkg in packages
                                  for record in pkg.records),
                key=lambda r: r.pvname)
        ]
        util.text_block('\n'.join(block))

        print(file=file)


def summary(tsproj_project, use_markdown=False, show_all=False,
            show_outline=False, show_boxes=False, show_code=False,
            show_plcs=False, show_nc=False, show_symbols=False,
            show_links=False, show_types=False, filter_types=None,
            log_level=None, debug=False):

    if not any((show_all, show_outline, show_boxes, show_code, show_plcs,
                show_nc, show_symbols, show_links, show_types, debug)):
        # Show _something_
        show_plcs = True

    proj_path = pathlib.Path(tsproj_project)
    proj_root = proj_path.parent.resolve().absolute()

    if proj_path.suffix.lower() not in ('.tsproj', ):
        raise ValueError('Expected a .tsproj file')

    project = parser.parse(proj_path)

    if show_plcs or show_all or show_code or show_symbols or show_types:
        for i, plc in enumerate(project.plcs, 1):
            util.heading(f'PLC Project ({i}): {plc.project_path.stem}')
            print(f'    Project root: {proj_root}')
            print('    Project path:',
                  plc.project_path.resolve().relative_to(proj_root))
            print('    TMC path:    ',
                  plc.tmc_path.resolve().relative_to(proj_root))
            print(f'    AMS ID:       {plc.ams_id}')
            print(f'    IP Address:   {plc.target_ip} (* based on AMS ID)')
            print(f'    Port:         {plc.port}')
            print()
            proj_info = [
                ('Source files', [pathlib.Path(fn).relative_to(proj_root)
                                  for fn in plc.source_filenames]),
                ('POUs', plc.pou_by_name),
                ('GVLs', plc.gvl_by_name),
            ]

            for category, items in proj_info:
                if items:
                    print(f'    {category}:')
                    for j, text in enumerate(items, 1):
                        print(f'        {j}.) {text}')
                    print()

            if show_code:
                source_items = (
                    list(plc.dut_by_name.items()) +
                    list(plc.gvl_by_name.items()) +
                    list(plc.pou_by_name.items())
                )
                for name, source in source_items:
                    util.sub_heading(f'{source.tag}: {name}')

                    fn = source.filename.resolve().relative_to(proj_root)
                    print(f'File: {fn}')
                    print()

                    if not hasattr(source, 'get_source_code'):
                        continue

                    source_text = source.get_source_code() or ''
                    if source_text.strip():
                        util.text_block(
                            source_text,
                            markdown_language='vhdl' if use_markdown else None
                        )
                        print()

            if show_symbols or show_all:
                util.sub_heading('Symbols')
                symbols = list(plc.find(parser.Symbol))
                for symbol in sorted(symbols, key=lambda symbol: symbol.name):
                    info = symbol.info
                    print('    {name} : {summary_type_name} ({bit_offs} '
                          '{bit_size})'.format(**info))
                print()

            if show_types:
                list_types(plc, filter_types=filter_types)

    if show_boxes or show_all:
        util.sub_heading('Boxes')
        boxes = list(project.find(parser.Box))
        for box in sorted(boxes, key=lambda box: int(box.attributes['Id'])):
            print(f'    {box.attributes["Id"]}.) {box.name}')

    if show_nc or show_all:
        util.sub_heading('NC axes')
        ncs = list(project.find(parser.NC))
        for nc in ncs:
            for axis_id, axis in sorted(nc.axis_by_id.items()):
                print(f'    {axis_id}.) {axis.name!r}:')
                for category, info in axis.summarize():
                    try:
                        info = ast.literal_eval(info)
                    except Exception:
                        ...
                    print(f'        {category} = {info!r}')
                print()

    if show_links or show_all:
        util.sub_heading('Links')
        links = list(project.find(parser.Link))
        for i, link in enumerate(links, 1):
            print(f'    {i}.) A {link.a}')
            print(f'          B {link.b}')
        print()

    if show_outline:
        outline(project)

    if debug:
        util.python_debug_session(
            namespace=locals(),
            message=('The top-level project is accessible as `project`, and '
                     'TWINCAT_TYPES are in the IPython namespace as well.'
                     )
        )

    return project


def main(filename, use_markdown=False, show_all=False,
         show_outline=False, show_boxes=False, show_code=False,
         show_plcs=False, show_nc=False, show_symbols=False,
         show_links=False, show_types=False, filter_types=None, log_level=None,
         debug=False):
    '''
    Output a summary of the project or projects provided.
    '''

    path = pathlib.Path(filename)
    if path.suffix.lower() in ('.tsproj', ):
        project_fns = [path]
    elif path.suffix.lower() in ('.sln', ):
        project_fns = parser.projects_from_solution(path)
    else:
        raise ValueError(f'Expected a tsproj or sln file, got: {path.suffix}')

    projects = []
    for fn in project_fns:
        project = summary(
            fn, use_markdown=use_markdown, show_all=show_all,
            show_outline=show_outline, show_boxes=show_boxes,
            show_code=show_code, show_plcs=show_plcs, show_nc=show_nc,
            show_symbols=show_symbols, show_links=show_links,
            show_types=show_types, filter_types=filter_types,
            log_level=log_level, debug=debug
        )
        projects.append(project)

    return projects
