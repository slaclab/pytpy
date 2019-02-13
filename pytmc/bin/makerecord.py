import logging
logger = logging.getLogger(__name__)

import argparse
#from pytmc import TmcFile
#import pytmc
from .. import TmcFile


def main():
    description = """\
    Commandline utility for generating epics records files from TwinCAT3 .tmc
    files. This program is designed to work in conjunction with ESSS'
    m-epics-twincat-ads driver."""
    
    parser = argparse.ArgumentParser(
        description = description,
        formatter_class = argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        'tmc_file', metavar="INPUT", type=str, help='Path to interpreted .tmc file'
    )
    
    parser.add_argument(
        'record_file', metavar="OUTPUT", type=str, help='Path to output .db file'
    )
    
    args = parser.parse_args()
    tmc_file = open(args.tmc_file,'r')
    tmc_obj = pytmc.TmcFile(tmc_file)
    tmc_obj.create_chains()
    tmc_obj.isolate_chains()
    tmc_obj.create_packages()
    tmc_obj.configure_packages()
    db_string = tmc_obj.render()
    record_file = open(args.record_file,'w')
    record_file.write(db_string)
    tmc_file.close()
    record_file.close()

if __name__ == '__main__':
    main()

