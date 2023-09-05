import itertools
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
        current_block = []
        ## fucntion to check if block is empty; if not, add to self.blocks using self.add_recipe_block
        def add_recipe_block_if_nonempty(block):
            if len(block) != 0:
                self.add_recipe_block(RecipeBlock(block, self.recipe_file))
            return
        ## iterate through all blocks
        for block in self.raw_data:
            ## if is list of alternative blocks, use RecipeBlockAlt
            if isinstance(block, list):
                add_recipe_block_if_nonempty(current_block)
                current_block = []
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
    ## generator of SubstitutionFile objects with every possible combination of blocks and values
    def substitution_combos(self, overwrite_earlier = True):
        combos = itertools.product(*[block.substitution_combos() for block in self.blocks])
        for combo in combos:
            output = SubstitutionFile(suppress_warning = True)
            for sub_file in combo:
                output.merge(sub_file, overwrite = overwrite_earlier)
            yield output
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
                    self.variables[variable] = values
            else:
                self.variables[variable] = values
        return
    ## generator of SubstitutionFile objects with every possible combination of values
    def substitution_combos(self):
        variables = list(self.variables.keys())
        combos = itertools.product(*[self.variables[var] for var in variables])
        for combo in combos:
            output_sub_file = SubstitutionFile(suppress_warning = True)
            str_header = self.generate_str_header()
            str_variables = [f"{variables[i]}={combo[i]}" for i in range(len(variables))]
            sub_block = SubstitutionBlockSubFile([str_header] + str_variables, output_sub_file)
            output_sub_file.add_substitution_block(sub_block)
            yield output_sub_file
        return
    ## generate variables as string that can be written to a recipe file (will be used by self.generate_string)
    def generate_str_variables(self):
        return '\n'.join([f"{varname}={';'.join(values)}" for varname, values in self.variables.items()])


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
    ## generator of SubstitutionFile objects with every possible combination of blocks and values
    def substitution_combos(self, overwrite_earlier = True):
        for recipe in self.recipes:
            combos = recipe.substitution_combos(overwrite_earlier = overwrite_earlier)
            for sub_file in combos:
                yield sub_file
        return

class RecipeFile(SubstitutionFile):
    ## differs from SubstitutionBlockGen in that variable values are list of possible values, not a single value
    multi_line = pp.OneOrMore(pp.Regex( "[^{}]+" ))
    body = pp.nestedExpr( '{', '}', content = multi_line )
    def __init__(self, fname, modules):
        super().__init__(fname, modules)
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
    def substitution_files(self):
        ## generate all possible SubstitutionFile objects with
        ## all possible combination of values and modules according to recipe file
        return self.recipe.substitution_combos()
    def slim_files(self):
        ## generate all possible slim files with
        ## all possible combination of values and modules according to recipe file
        pass

## test
txt = '''
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
'''

txt2 = '''[general.slim]
VAR1=1;2;3
VAR2=a
VAR3=0.5, "f", 0.0;0.5, "f", 0.5
VAR4=$VAR4$'''

txt3 = '''[general.slim]
VAR1=1;2;3
VAR2=a

[module1.slim]
VAR3=0.5, "f", 0.0;0.5, "f", 0.5
VAR4=$VAR4$'''

## unlevel_list is from code_blocks.py
multi_line = pp.OneOrMore(pp.Regex( "[^{}]+" ))
body = pp.nestedExpr( '{', '}', content = multi_line )
unlevel_list(body.searchString('{' + txt + '}').asList())

y = RecipeBlock(txt2.split('\n'), None)
y_subs = list(y.substitution_combos())
for y_sub in y_subs:
    print(y_sub.generate_string())

z = RecipeBlockMulti([txt3], None)
z_subs = list(z.substitution_combos())
for z_sub in z_subs:
    print("---")
    print(z_sub.generate_string())

## test all :)
dir_base = '/mnt/d/OneDrive_doysd/OneDrive - Default Directory/scripts/SLiMerge'
fname = dir_base + '/test/recipes/scd.slim.recipe'
modules = [dir_base + '/test/modules/output_full.slim', dir_base + '/test/modules/general_WF.slim', dir_base + '/test/modules/add_new_drawn_mutation.slim']
x = RecipeFile(fname, modules)
x_subs = x.substitution_files()
print(next(x_subs).generate_string())
