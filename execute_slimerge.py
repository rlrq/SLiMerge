#!/usr/bin/python3

import itertools
import os
import pathlib
import shutil
import subprocess
import time
import argparse
import tqdm

from datetime import datetime
# from threading import Thread

dir_slimerge = os.path.dirname(os.path.realpath(__file__))

default_module_paths = [os.path.join(dir_slimerge, "test", "modules")]
dir_slimerge_src = os.path.join(dir_slimerge, "slimerge")

import sys
sys.path.append(dir_slimerge_src)

from recipe_file import RecipeFile

parser = argparse.ArgumentParser(description="generate all SLiM files from recipe file and execute")
parser.add_argument("recipe", type=os.path.abspath, help="path to .slim.recipe file")
parser.add_argument("--module-path", help="path to directory containing .slim module files",
                    action="append", nargs='*', dest="module_paths", type=os.path.abspath,
                    default=[])
parser.add_argument("--dir", "--output-dir", type=os.path.abspath, help="path to output directory",
                    dest="dir_output", required=True)
parser.add_argument("--rep", "--replicate", "-n", type=int,
                    help="number of replicates to execute per simulation",
                    dest="replicates", default=1)
parser.add_argument("--prefix", type=str, help="prefix of output files",
                    default=f"scd_{int(datetime.timestamp(datetime.now()))}")
parser.add_argument("-t", "--thread", "--threads", type=int,
                    help="number of parallel processes",
                    dest="threads", default=1)
parser.add_argument("-z", "--zip", action="store_true", dest="zip")
parser.add_argument("--zip-rep", "--zip-replicates", action="store_true", dest="zip_reps")
# parser.add_argument("--progress-increment", type=int,
#                     help=("number of simulations to run before printing progress to stdout;"
#                           " set to any values <= 0 to skip printing of progress"
#                           " (does not affect simulations themselves, but does provide some"
#                           " peace of mind to know that the programme is still running)"),
#                     default=20)
parser.add_argument("--slim", type=str,
                    help="full path to slim executable; ignore if executable is in path",
                    dest="exe_slim", default=None)
args = parser.parse_args()

test_args_only = False

f_recipe = args.recipe
module_paths = list(itertools.chain(*args.module_paths))
module_paths = module_paths + [path for path in default_module_paths if path not in module_paths]
prefix = args.prefix
dir_output = args.dir_output
replicates = args.replicates
to_zip = args.zip
zip_reps = args.zip_reps
threads = args.threads
exe_slim = "slim" if args.exe_slim is None else args.exe_slim

print("recipe:", f_recipe)
print("module_paths:", module_paths)
print("dir_output:", dir_output)
print("replicates:", replicates)
print("prefix:", prefix)
print("zip:", to_zip)
print("zip replicates:", zip_reps)
print("threads:", threads)
# print("progress increment:", args.progress_increment)

if test_args_only:
    exit

## function to generate name for output substitution + script files
def mk_run_prefix(dir_output, prefix, combo_id):
    return os.path.join(dir_output, f"{prefix}_{combo_id}")

def mkfname_subfile(*args):
    return f"{mk_run_prefix(*args)}.txt"

def mkfname_scriptfile(*args):
    return f"{mk_run_prefix(*args)}.slim"

def mkfname_zip(*args):
    return f"{mk_run_prefix(*args)}.zip"

# print("Not args checking mode")

## parse recipe file
recipe_file = RecipeFile(fname = f_recipe, module_paths = module_paths)
recipe_combos = recipe_file.substitution_files()
print(f"Number of combinations: {recipe_file.num_combos()}")

## make substitution files + their scripts and run and then zip each combo separately
def parse_combo(substitution_file):
    ## make file names
    sub_id = substitution_file.substitution_id
    ## all files generated from this substitution file iteration will be written within dir_sub
    dir_sub = mk_run_prefix(dir_output, prefix, sub_id)
    mk_args = [dir_sub, prefix, sub_id]
    f_subfile = mkfname_subfile(*mk_args)
    f_scriptfile = mkfname_scriptfile(*mk_args)
    dir_slimoutput = os.path.join(dir_sub, "slim_out")
    os.makedirs(dir_slimoutput, exist_ok = True)
    ## write files
    with open(f_subfile, "w+") as f:
        f.write(substitution_file.generate_string().replace("$OUTPUT_DIRECTORY$", f"\"{dir_slimoutput}\""))
    with open(f_scriptfile, "w+") as f:
        script = substitution_file.build_script()
        f.write(script.make_string().replace("$OUTPUT_DIRECTORY$", f"\"{dir_slimoutput}\""))
    ## execute slim 'replicates' number of times
    for i in range(replicates):
        subprocess.run(args = [exe_slim, "-l", "0", f_scriptfile], check = True)
    ## zip stuff :)
    if zip_reps:
        ## zip files (args: destination (without .zip extension), format, source
        shutil.make_archive(base_name = dir_slimoutput, format = "zip", root_dir = dir_sub, base_dir = os.path.basename(dir_slimoutput))
        ## delete directory
        shutil.rmtree(dir_slimoutput)
    if to_zip:
        ## zip files (args: destination (without .zip extension), format, source
        shutil.make_archive(base_name = dir_sub, format = "zip", root_dir = dir_output, base_dir = os.path.basename(dir_sub))
        ## delete directory
        shutil.rmtree(dir_sub)
    return 1

## import multiprocess only if threads > 1
if threads > 1:
    import multiprocess as mp
    with mp.Pool(processes = threads) as p:
        list(tqdm.tqdm(p.imap(parse_combo, recipe_combos, chunksize = 30), total = recipe_file.num_combos()))
## execute in sequence otherwise
else:
    for substitution_file in recipe_combos:
        _ = parse_combo(substitution_file)
