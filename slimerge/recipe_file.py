import copy
import itertools
import numpy
import warnings
import pyparsing as pp

from substitution_file import SubstitutionBlockSubFile, SubstitutionFile, SubstitutionParser
from code_blocks import unlevel_list

## alternative blocks are contiguous elements which are lists separated by '|'
## only parses top-level
## alternative blocks will be grouped into a single list
## (e.g. [1, [2], '|', [3, [3.5], '|', [3.8]], [4], '|', [5]] -> [1, [2, 3, [3.5], '|', [3.8]], [4, 5]]) (if unlist = True)
## (e.g. [1, [2], '|', [3, [3.5], '|', [3.8]], [4], '|', [5]] -> [1, [[2], [3, [3.5], '|', [3.8]]], [[4], [5]]]) (if unlist = False) (this one retains structure of nested alternative blocks)
def group_alt_blocks(l, unlist = False):
    output = []
    curr_alt = []
    i = 0
    while i < len(l):
        e = l[i]
        if isinstance(e, list):
            if unlist:
                curr_alt.extend(e) ## this one unlists e
            else:
                curr_alt.append(e) ## this one retains e as a list
            ## if last or end of alternate blocks
            if i == len(l)-1 or l[i+1] != '|':
                ## add curr_alt to output, reset
                output.append(curr_alt)
                curr_alt = []
                i += 1
            else:
                i += 2
        else:
            ## if not alternative block, just add as-is to output
            output.append(e)
            i += 1
    return output

# ## alternative to itertools.product, which unfortunately converts the iterable to a concrete sequence
# ## function from https://stackoverflow.com/a/26153911
# def product(*args):
#     if len(args) == 1:
#         for i in args[0]:
#             yield [i]
#     else:
#         for i in args[0]:
#             for j in product(*args[1:]):
#                 yield [i] + j
#     return

# ## alternative to itertools.product, which unfortunately converts the iterable to a concrete sequence
# ## adapted from https://stackoverflow.com/a/26153911
# def generator_product(*args):
#     if len(args) == 1:
#         ## tee it
#         args_0_1, args_0_2 = itertools.tee(args[0])
#         for i in args_0_2:
#             yield [i]
#     else:
#         ## tee it
#         args_0_1, args_0_2 = itertools.tee(args[0])
#         for i in args_0_2:
#             for j in generator_product(*args[1:]):
#                 yield [i] + j
#     return

class CachedIter():
    def __init__(self, iterable):
        self.iterable = iterable
        self.cache = []
    def __iter__(self):
        if not self.cache:
            for e in self.iterable:
                self.cache.append(e)
                yield e
        else:
            yield from self.cache
        return

def product_cached(*args):
    if args:
        new_args = [args[0]] + [CachedIter(arg) for arg in args[1:]]
    else:
        return []
    def product(*args):
        if len(args) == 1:
            for i in args[0]:
                yield [i]
        else:
            for i in args[0]:
                for j in product(*args[1:]):
                    yield [i] + j
        return
    yield from product(*new_args)
    return

# def test_gen():
#     while True:
#         yield 1
#         yield 2
#         raise StopIteration
#         # next(generator, None)
#     return

# i = 0
# g = test_gen()
# for i, e in enumerate(g):
#     if i >= 4:
#         break
#     print(e)

# while i <= 4:
#     print(next(g))
#     i += 1

## class that collects multiple recipe blocks joined with AND
## ignores comment lines
class RecipeBlockMulti():
    ## raw data should be output of group_alt_blocks, with newline characters retained in string
    def __init__(self, raw_data, recipe_file):
        self.raw_data = raw_data
        self.recipe_file = recipe_file
        self.blocks = []
        self._parser = SubstitutionParser(comment_function = lambda line: line[:2] == "//")
        self.parse()
    def parse(self):
        ## iterate through all blocks
        for block in self.raw_data:
            ## if is list of alternative blocks, use RecipeBlockAlt
            if isinstance(block, list):
                self.add_recipe_block(RecipeBlockAlt(block, self.recipe_file))
            else:
                ## else split string into lines and create RecipeBlock objects for each module's block
                blocks = self._parser.split_blocks(block,
                                                   lambda block: RecipeBlock(block, self.recipe_file))
                for block in blocks:
                    self.add_recipe_block(block)
    def add_recipe_block(self, new_recipe_block):
        self.blocks.append(new_recipe_block)
        return
    ## just well count the number of combinations
    def num_combos(self):
        return numpy.prod([block.num_combos() for block in self.blocks])
    ## generator of SubstitutionFile objects with every possible combination of blocks and values
    def substitution_combos(self, overwrite_earlier = True):
        combos = product_cached(*[block.substitution_combos() for block in self.blocks if block is not None])
        for i, combo in enumerate(combos):
            output = SubstitutionFile(suppress_warning = True)
            for sub_file in combo:
                output.merge(sub_file, overwrite = overwrite_earlier, deepcopy = True)
            output.substitution_id = i+1
            yield output
        return
    def print_recipe(self, indentation = ''):
        for block in self.blocks:
            block.print_recipe(indentation = indentation)
        return

class RecipeBlock(SubstitutionBlockSubFile):
    ## raw_data: list, where each entry is a line (includes header)
    def __init__(self, raw_data, recipe_file):
        super().__init__([line for line in raw_data if line[:2] != "//"], recipe_file)
        self.recipe_file = self.substitution_file
    def parse_variable(self, s):
        name, vals = super().parse_variable(s)
        vals = vals.split(';')
        return name, vals
    def merge(self, new_recipe_block, union = False, overwrite = False, suppress_warning = False):
        if new_recipe_block.filename != self.filename and not suppress_warning:
            warnings.warn(("Warning: Unable to merge RecipeBlocks."
                           " Blocks must be for same module (self.filename)."))
            return
        ## union: combine values from self and other if True, else see overwrite
        ## overwrite: replaces self's values with others if True, else do nothing
        for variable, values in new_recipe_block.variables:
            if variable in self.variables:
                if union:
                    self.variables[variable] = set(self.variables[variable]).union(set(values))
                elif overwrite:
                    self.variables[variable] = copy.copy(values)
            else:
                self.variables[variable] = copy.copy(values)
        return
    ## count number of possible combinations
    def num_combos(self):
        return numpy.prod([len(values) for values in self.variables.values()])
    ## generator of SubstitutionFile objects with every possible combination of values
    def substitution_combos(self):
        variables = list(self.variables.keys())
        if variables:
            combos = product_cached(*[self.variables[var] for var in variables])
        else:
            combos = [[]]
        for i, combo in enumerate(combos):
            output_sub_file = SubstitutionFile(suppress_warning = True)
            str_header = self.generate_str_header()
            str_variables = [f"{variables[i]}={combo[i]}" for i in range(len(variables))]
            sub_block = SubstitutionBlockSubFile([str_header] + str_variables, output_sub_file)
            output_sub_file.add_substitution_block(sub_block)
            output_sub_file.substitution_id = i+1
            yield output_sub_file
        return
    ## generate variables as string that can be written to a recipe file (will be used by self.generate_string)
    def generate_str_variables(self):
        return '\n'.join([f"{varname}={';'.join(values)}" for varname, values in self.variables.items()])
    def print_recipe(self, indentation = ''):
        print(indentation + self.generate_str_header())
        print(indentation + self.generate_str_variables().replace('\n', '\n' + indentation))
        return

## class that collects multiple recipe blocks joined with OR
class RecipeBlockAlt():
    def __init__(self, raw_data, recipe_file):
        ## raw data is list of strings (possibly nested), where each element is an alterantive block
        self.raw_data = raw_data
        self.recipe_file = recipe_file
        self.recipes = []
        self.parse()
    def parse(self):
        current_block = []
        for block in self.raw_data:
            self.add_recipe_block(RecipeBlockMulti(group_alt_blocks(block), self.recipe_file))
        return
    def add_recipe_block(self, new_recipe_block):
        self.recipes.append(new_recipe_block)
        return
    ## count number of possible combinations
    def num_combos(self):
        output = 0
        for recipe in self.recipes:
            output += recipe.num_combos()
        return output
    ## generator of SubstitutionFile objects with every possible combination of blocks and values
    def substitution_combos(self, overwrite_earlier = True):
        i = 0
        for recipe in self.recipes:
            combos = recipe.substitution_combos(overwrite_earlier = overwrite_earlier)
            for sub_file in combos:
                sub_file.substitution_id = i+1
                i += 1
                yield sub_file
        return
    def print_recipe(self, indentation = ''):
        new_indentation = indentation + "  "
        print(indentation + '{')
        for i, recipe in enumerate(self.recipes):
            recipe.print_recipe(indentation = new_indentation)
            if i < len(self.recipes)-1:
                print(indentation + "}|{")
            else:
                print(indentation + "}")
        return

class RecipeFile(SubstitutionFile):
    ## differs from SubstitutionBlockGen in that variable values are list of possible values, not a single value
    multi_line = pp.OneOrMore(pp.Regex( "[^{}]+" ))
    body = pp.nestedExpr( '{', '}', content = multi_line )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def recipe_to_blocks(self, string):
        '''
        Parses string of recipe into list, splits and grouped only at curly braces.
        I.e. newlines retained in string. E.g.
          [general.slim]
          VAR1=1
          {
            [module1.slim]
            VAR2=3
            [module2.slim]
            VAR3=2
          }|{
            [module3.slim]
            VAR4=0
            {
              [module1.slim]
              VAR2=3
            }|{
              [module2.slim]
              VAR3=2
            }
          }
        becomes
          ['[general.slim]\nVAR1=1\n', ['[module1.slim]\n  VAR2=3\n  [module2.slim]\n  VAR3=2\n'], '|', ['[module3.slim]\n  VAR4=0\n  ', ['[module1.slim]\n    VAR2=3\n  '], '|', ['[module2.slim]\n    VAR3=2\n  ']]]
          (note retained whitespace characters and '|')
        '''
        return unlevel_list(self.body.searchString('{' + string + '}').asList())
    def parse(self, filename = None, string = None):
        if filename is not None: self.parse_file(filename)
        elif string is not None: self.parse_string(string)
        else: raise Exception("SubstitutionFile.parse requires either filename or string.")
    def parse_file(self, filename):
        with open(self.fname, 'r') as f:
            raw_string = f.read()
        self.parse_string(raw_string)
    def parse_string(self, string):
        self.recipe = RecipeBlockMulti(group_alt_blocks(self.recipe_to_blocks(string)), self)
    def num_combos(self):
        return self.recipe.num_combos()
    def substitution_files(self):
        ## generate all possible SubstitutionFile objects with
        ## all possible combination of values and modules according to recipe file
        sub_files = self.recipe.substitution_combos()
        for i, sub_file in enumerate(sub_files):
            sub_file.substitution_id = i+1
            sub_file.modules_d = self.modules_d
            sub_file.module_paths = self.module_paths
            sub_file._defaults = self._defaults
            yield sub_file
        return 
    def slim_files(self):
        ## generate all possible slim files with
        ## all possible combination of values and modules according to recipe file
        pass
    def print_recipe(self):
        self.recipe.print_recipe(indentation = '')

# ## test
# txt = '''
# [general.slim]
# VAR1=1
# {
#   [module1.slim]
#   VAR2=3

#   [module2.slim]
#   VAR3=2
# }|{
#   [module3.slim]
#   VAR4=0
#   {
#     [module1.slim]
#     VAR2=3
#   }|{
#     [module2.slim]
#     VAR3=2
#   }
# }
# '''

# txt2 = '''[general.slim]
# VAR1=1;2;3
# VAR2=a
# VAR3=0.5, "f", 0.0;0.5, "f", 0.5
# VAR4=$VAR4$'''

# txt3 = '''[general.slim]
# VAR1=1;2;3
# VAR2=a

# [module1.slim]
# VAR3=0.5, "f", 0.0;0.5, "f", 0.5
# VAR4=$VAR4$'''

# ## test
# txt4 = '''[general.slim]
# VAR1=1
# {
#   [general.slim]
#   VAR2=1

#   [module2.slim]
#   VAR3=2
# }|{
#   [module3.slim]
#   VAR4=0
#   {
#     [general.slim]
#     VAR2=3
#   }|{
#     [module2.slim]
#     VAR3=2
#   }
# }
# '''

# ## unlevel_list is from code_blocks.py
# multi_line = pp.OneOrMore(pp.Regex( "[^{}]+" ))
# body = pp.nestedExpr( '{', '}', content = multi_line )
# unlevel_list(body.searchString('{' + txt + '}').asList())

# y = RecipeBlock(txt2.split('\n'), None)
# y_subs = list(y.substitution_combos())
# for y_sub in y_subs:
#     print(y_sub.generate_string())

# z = RecipeBlockMulti([txt3], None)
# z_subs = list(z.substitution_combos())
# for z_sub in z_subs:
#     print("---")
#     print(z_sub.generate_string())

# z = RecipeBlockMulti(group_alt_blocks(unlevel_list(body.searchString('{' + txt4 + '}').asList())), None)
# z_subs = list(z.substitution_combos())
# for z_sub in z_subs:
#     print("---")
#     print(z_sub.generate_string())

# ## test all :)
# dir_base = '/mnt/d/OneDrive_doysd/OneDrive - Default Directory/scripts/SLiMerge'
# dir_base = "/mnt/chaelab/rachelle/scripts/SLiMerge"
# fname = dir_base + '/test/recipes/scd.slim.recipe'
# fname = dir_base + '/test/recipes/scd_less.slim.recipe'
# modules = [dir_base + '/test/modules/output_full.slim', dir_base + '/test/modules/general_WF.slim', dir_base + '/test/modules/add_new_drawn_mutation.slim']
# x = RecipeFile(fname, modules)

# x = RecipeFile(fname = fname, module_paths = [dir_base + "/test/modules"])
# x.num_combos()
# x_subs = x.substitution_files()
# x_subs1 = next(x_subs)
# x_subs1.get_module_path("general_WF.slim")
# print(x_subs1.generate_string())
# x_subs1_script = x_subs1.build_script()
# print(x_subs1_script.make_string())

# with open(dir_base + "/test/scripts/test_recipe_subs1.slim", "w+") as f:
#     f.write(x_subs1_script.make_string())


# x_subs2 = next(x_subs)
# print(x_subs2.generate_string())

# def print_sub_files(iterable):
#     for e in iterable:
#         print('---')
#         print(e.generate_string())
#     return

# def print_recipes(iterable):
#     for e in iterable:
#         e.print_recipe()
#     return
