#!/usr/bin/python3

import os
import shutil
import tempfile

dir_slimerge = os.path.dirname(os.path.realpath(__file__))

dir_slimerge_src = os.path.join(dir_slimerge, "slimerge")
default_module_paths = [os.path.join(dir_slimerge, "test", "modules")]

import sys
sys.path.append(dir_slimerge_src)

from substitution_file import SubstitutionFile


###############################
##  PARSE SUBSTITUTION FILE  ##
###############################
## (i.e. extract substitution values)

## functions to extract variable values
def get_variable_values(sub_file, varnames):
    set_varnames = set(varnames)
    values = {}
    for block in sub_file.blocks():
        values = {**values,
                  **{varname: value for varname, value in block.variables.items() if varname in set_varnames}}
    return values

def get_constant_values(sub_file, varnames):
    set_varnames = set(varnames)
    values = {}
    blocks = sub_file.get_blocks_by_module("add_constant.slim")
    for block in blocks:
        constant_name = block.variables["CONSTANT_NAME"]
        if constant_name in set_varnames:
            values[constant_name] = block.variables["CONSTANT_VALUE"]
    return values

## if leftmost and rightmost characters are compatible quote characters, remove them
## (currently doesn't support directional quote characters)
def _strip_quotes(s):
    if not isinstance(s, str):
        return s
    quote_chars = {'"', "'"}
    if (s[0] in quote_chars and s[0] == s[-1] and s[-1]):
        return s[1:-1]
    return s

## extract values from substitution files
def get_substitution_values(sub_file, variable_varnames = [], constant_varnames = [], strip_quotes = True):
    output = {**get_variable_values(sub_file, variable_varnames),
              **get_constant_values(sub_file, constant_varnames)}
    if strip_quotes:
        output = {varname: _strip_quotes(value) for varname, value in output.items()}
    return output


########################
##  EXECUTABLE STUFF  ##
########################

import argparse

default_variables = []
default_constants = []

def parse_variables_for_one_substitution(fname, variables = default_variables, constants = default_constants):
    id_sim, id_substitution = os.path.splitext(os.path.basename(fname))[0].split('_')[-2:]
    sub_file = SubstitutionFile(fname)
    ## get values from substitution file
    try:
        variable_values = get_substitution_values(
            sub_file, strip_quotes = True,
            variable_varnames = variables, constant_varnames = constants)
    except Exception as e:
        print(fname)
        raise e
    ## include substitution id
    variable_values = {"SUBSTITUTION_ID": id_substitution, **variable_values}
    return variable_values

def summarise_run_gen(dir_run, variables = default_variables, constants = default_constants,
                      print_progress = lambda i:None, is_zipped = True):
    ## extract variable values and write to file
    fout = os.path.join(dir_run, "run_summary.txt")
    with tempfile.TemporaryDirectory() as dir_tmp:
        colnames = ["SUBSTITUTION_ID"] + variables + constants
        with open(fout, "w+") as f:
            f.write('\t'.join(colnames) + '\n')
            for i, file_folder in enumerate(os.listdir(dir_run)):
                print_progress(i)
                if is_zipped and os.path.isfile(os.path.join(dir_run, file_folder)):
                    ## unzip archive
                    basename, ext = os.path.splitext(file_folder)
                    # print(basename, ext)
                    if ext != ".zip":
                        continue
                    shutil.unpack_archive(os.path.join(dir_run, file_folder), dir_tmp)
                    zipped_dir = os.path.join(dir_tmp, basename)
                    ## filenames
                    f_substitution = os.path.join(zipped_dir, basename + ".txt")
                    variable_values = parse_variables_for_one_substitution(
                        f_substitution, variables = variables, constants = constants)
                    ## delete tmp directory
                    shutil.rmtree(zipped_dir)
                elif not is_zipped and os.path.isdir(os.path.join(dir_run, file_folder)):
                    f_substitution = os.path.join(dir_run, file_folder, f"{file_folder}.txt")
                    variable_values = parse_variables_for_one_substitution(
                        f_substitution, variables = variables, constants = constants)
                else:
                    continue
                f.write('\t'.join([variable_values.get(colname, "NA") for colname in colnames]) + '\n')
    return


def summarise_run(dir_run, variables = default_variables, constants = default_constants,
                  print_progress = lambda i:None):
    ## extract variable values and write to file
    fout = os.path.join(dir_run, "run_summary.txt")
    with tempfile.TemporaryDirectory() as dir_tmp:
        colnames = ["SUBSTITUTION_ID"] + variables + constants
        with open(fout, "w+") as f:
            f.write('\t'.join(colnames) + '\n')
            for i, zip_file in enumerate(os.listdir(dir_run)):
                print_progress(i)
                ## unzip archive
                basename, ext = os.path.splitext(zip_file)
                # print(basename, ext)
                if ext != ".zip":
                    continue
                shutil.unpack_archive(os.path.join(dir_run, zip_file), dir_tmp)
                zipped_dir = os.path.join(dir_tmp, basename)
                ## get common output variables
                id_sim, id_substitution = basename.split('_')[-2:]
                ## filenames
                f_substitution = os.path.join(zipped_dir, basename + ".txt")
                # f_slim = os.path.join(zipped_dir, basename + ".slim")
                ## parsed files
                sub_file = SubstitutionFile(f_substitution)
                ## get values from substitution file
                variable_values = get_substitution_values(
                    sub_file, strip_quotes = True,
                    variable_varnames = variables, constant_varnames = constants)
                ## include substitution id
                variable_values = {"SUBSTITUTION_ID": id_substitution, **variable_values}
                ## write
                f.write('\t'.join([variable_values.get(colname, "NA") for colname in colnames]) + '\n')
                ## delete directory
                shutil.rmtree(zipped_dir)
    return


parser = argparse.ArgumentParser(description="generate txt file summarising variables for all runs (output of execute_slim_parallel.py)")
parser.add_argument("dir_run", type=os.path.abspath, help="path to directory containing run outputs (of execute_slim_parallel.py)")
parser.add_argument("-v", "--var", "--variables", type=str, help="comma-separated names of variables",
                    dest="variables")
parser.add_argument("-c", "--constants", type=str, help="comma-separated names of constants",
                    dest="constants")
parser.add_argument("--unzipped", help="raise if run output is not zipped", action="store_false",
                    dest="is_zipped")
parser.add_argument("--progress-increment", type=int,
                    help=("number of archives to process before printing progress to stdout;"
                          " set to any values <= 0 to skip printing of progress"
                          " (does not affect simulations themselves, but does provide some"
                          " peace of mind to know that the programme is still running)"),
                    default=500)
args = parser.parse_args()

if args.progress_increment <= 0:
    def print_progress(i):
        return
else:
    def print_progress(i):
        if i % args.progress_increment == 0:
            print(i)
        return

summarise_run_gen(args.dir_run,
                  variables = default_variables if args.variables is None else args.variables.split(','),
                  constants = default_constants if args.constants is None else args.constants.split(','),
                  print_progress = print_progress,
                  is_zipped = args.is_zipped)

# ## get common output variables
# dir_output = "/mnt/chaelab/rachelle/scd/results/recipe_run_20230911_sample/scd_1_1"
# base_output = os.path.basename(dir_output)
# id_sim, id_substitution = base_output.split('_')[-2:]

# ## filenames
# f_substitution = os.path.join(dir_output, base_output + ".txt")
# f_slim = os.path.join(dir_output, base_output + ".slim")

# ## parsed files
# sub_file = SubstitutionFile(f_substitution)

# ## simulation variables defined in substitution file using <VARNAME>=<VALUE>
# variables = ["BREEDING_SYSTEM", "N_INTERACTING_LOCI", "NEUTRAL_FREQ_A", "NEUTRAL_FREQ_B", "NEUTRAL_FREQ_C",
#              "EPISTASIS_PHENOTYPE", "RECOMBINATION_RATE", "POPULATION_SIZE"]
# ## simulation variables defined in substitution file using
# ##   [add_constant.slim]
# ##   CONSTANT_NAME=<VARNAME>
# ##   CONSTANT_VALUE=<VALUE>
# constants = ["EPISTATIC_S", "ORGANISMS"]
# ## get value from substitution file
# variable_values = get_substitution_values(sub_file, strip_quotes = True,
#                                           variable_varnames = variables, constant_varnames = constants)
# ## include substitution id
# variable_values = {"SUBSTITUTION_ID": id_substitution, **variable_values}

