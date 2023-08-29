#!/usr/bin/python3
import argparse

import sys
# sys.path.append("/mnt/chaelab/rachelle/src")

parser = argparse.ArgumentParser(description="Merge multiple custom SLiM modules into a single file")
parser.add_argument("fout", type=str, metavar="OUTPUT_FILE", help="path to output .slim file")
parser.add_argument("f_modules", type=str, nargs='+', metavar="MODULE_FILES",
                    help="input custom SLiM module files")
parser.add_argument("--sub", "--substitution", type=str, dest="f_sub", metavar="SUBSTITUTION_FILE",
                    help="file detailing substitutions to make in one or more SLiM modules before merge")
args = parser.parse_args()

print(args.fout)
print(args.f_modules)
print(args.f_sub)
