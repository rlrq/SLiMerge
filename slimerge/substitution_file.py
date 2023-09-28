import os
import re
import copy
import warnings

from code_blocks import Script, ScriptModule

# class A:
#     def __init__(self, a):
#         self.name = a
#         self.parse()
#     def parse(self):
#         print(self.name)

# class B(A):
#     def __init__(self, a):
#         super().__init__(a)
#         self.b = 'b'
#     def parse(self):
#         print("hello") ## raises error because B.__init__ calls super().__init__ (A.__init__) which calls B.parse() but self.b is only defined after calling super().__init__. So yes B's parse will override A's parse even if parse is called in an A method
#         super().parse()

class PathsSearch():
    def __init__(self, paths = []):
        self.paths = paths
        self.files = {}
        self.update()
    def update(self):
        for path in self.paths:
            self.files[path] = set(os.listdir(path))
        return
    def search(self, filename):
        for path in self.paths:
            if path not in self.files:
                self.update()
                break
        for path in self.paths:
            if filename in self.files[path]:
                return os.path.join(path, filename)
        return None
    def add_path(self, *paths, update = True):
        for path in paths:
            if path not in self.paths:
                self.paths.append(path)
        if update: self.update()

class SubstitutionParser():
    def __init__(self, comment_function = lambda line: line[:2] == "//"):
        self.description = "Parser for substitution & recipe files"
        self.comment_function = comment_function
    def split_blocks(self, s, make_block_function,
                     comment_function = None, ignore_comments = True):
        if comment_function is None: comment_function = self.comment_function
        ## splits string into block_class objects, returns list of block_class objects
        lines = s.splitlines()
        ## instantiate ignore_function, which determines whether to exclude a line
        ## returns True if line should be excluded, False otherwise
        if ignore_comments: ignore_function = comment_function
        else: ignore_function = lambda line: False
        ## iterate through lines
        current_block = []
        output = []
        def add_if_nonempty(block):
            if len(block) != 0: output.append(make_block_function(block))
            return
        for line in lines:
            stripped_line = line.strip()
            ## check if line should be ignored
            if ignore_function(stripped_line): continue
            ## if end of block, pass to block_class to make new object
            elif stripped_line == '': ## blank line marking end of module
                add_if_nonempty(current_block)
                current_block = []
            elif stripped_line[0] == '[': ## if no blank line marking end of module
                add_if_nonempty(current_block)
                current_block = [stripped_line]
            else:
                current_block.append(stripped_line)
        ## if last block doesn't end with blank line, don't forget to also add it
        add_if_nonempty(current_block)
        return output
    def split_blocks_from_file(self, filename, *args, **kwargs):
        with open(filename, 'r') as f:
            s = f.read()
        return self.split_blocks(s, *args, **kwargs)

class SubstitutionBlockGen():
    def __init__(self, raw_data):
        self.raw_data = raw_data ## raw data from substitution file in list, where each entry is a line
        self.filename = None ## name of module file
        self.variables = {} ## variable values to substitute
        self.parse()
    def parse(self):
        '''
        Parses raw data into self.variables.
        Does not clear self.variables, but does overwrite any existing values.
        '''
        header = self.raw_data[0]
        ## get file name
        header_close = header.rindex(']')
        self.filename = header[1:header_close]
        ## parse variables
        for var in self.raw_data[1:]:
            self.parse_and_add_variable(var)
        return
    def parse_variable(self, s):
        delim_pos = s.index('=')
        name = s[:delim_pos]
        val = s[delim_pos + 1:]
        return name, val
    def parse_and_add_variable(self, s):
        name, val = self.parse_variable(s)
        self.add_variable(name, val)
        return
    def add_variable(self, name, val):
        self.variables[name] = val
    def merge(self, new_sub_block, overwrite = False):
        for variable, value in new_sub_block.variables.items():
            if variable in self.variables and not overwrite:
                continue
            else:
                self.add_variable(variable, copy.copy(value))
        return
    def generate_str_header(self):
        return f"[{self.filename}]"
    def generate_str_variables(self):
        return '\n'.join([f"{varname}={value}" for varname, value in self.variables.items()])
    def generate_string(self):
        return self.generate_str_header() + '\n' + self.generate_str_variables() + "\n\n"
    ## takes a string and substitutes all stored variables into it
    def substitute(self, string):
        for varname, val in self.variables.items():
            string = string.replace(f"${varname}$", val)
        return string


## parse .default file
class SubstitutionBlockDefaultFile(SubstitutionBlockGen):
    def __init__(self, filepath):
        raw_data = []
        with open(filepath, 'r') as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line: raw_data.append(stripped_line)
        super().__init__(raw_data)
        self.filepath = filepath.rstrip(".default") ## path to module file for which the default file applies
        if os.path.basename(self.filepath) != self.filename:
            warnings.warn((f"Name of .default file ({os.path.basename(filename)})"
                           f" does not match module file name specified within ({self.filename})."))
        return

## parse blocks of variables in substitution file
class SubstitutionBlockSubFile(SubstitutionBlockGen):
    def __init__(self, raw_data, sub_file):
        self.substitution_file = sub_file ## SubstitutionFile object
        self.order = 1 ## order of block relative to other blocks for the same module
        super().__init__(raw_data)
        return
    def parse(self):
        ## get order of module substitution block
        header = self.raw_data[0]
        order = re.search("(?<=\]\.)\d+$", header)
        if order: self.order = int(order.group(0))
        ## call super's parse
        super().parse()
        return
    def parse_variable(self, s):
        ## parse normally
        name, val = super().parse_variable(s)
        ## if value is '.' (i.e. default value),
        ## then we retrieve the default value from self.substitution_file, else return empty string
        if val == '.': val = self.substitution_file.defaults(self.filename).get(name, '')
        return name, val
    def generate_str_header(self):
        return f"[{self.filename}].{self.order}"
    @property
    def variables_full(self):
        if self.substitution_file is not None:
            return {**variables, "SUBSTITUTION_ID": self.substitution_file.substitution_id}
        return variables


class SubstitutionFile():
    def __init__(self, fname = None, string = None,
                 modules = [], module_paths = [], suppress_warning = False):
        self.fname = fname
        ## modules should contain paths to all module files
        ## this helps us to find the corresponding files for default values
        ## (files with default values should be named <path/to/module.slim>.template)
        self._modules = modules
        self.module_paths = PathsSearch(module_paths)
        self.modules_d = {}
        self._defaults = {}
        self.substitution_id = 0
        self.parse_modules()
        '''
        self.data format:
        {"<filename>": [SubstitutionBlockSubFile,  ## first substitution (header = [<filename>].1)
                        SubstitutionBlockSubFile  ## second substitution (header = [<filename>].2)
                        ]}
        '''
        self.data = {}
        self.order = []
        self._parser = SubstitutionParser(comment_function = lambda line: line[:2] == "//")
        if fname is not None:
            self.parse_file(fname)
        elif string is not None:
            self.parse_string(string)
        elif not suppress_warning:
            print("Use SubstitutionFile.parse_file(<filename>) or Script.parse_string(<string>) to input data")
        return
    # @property
    # def data(self):
    #     return self._data
    ## update .substitution_file attribute of all SubstitutionBlockX objects in self.data to self
    def update_substitution_file(self):
        for blocks in self.data.values():
            for block in blocks:
                block.substitution_file = self
        return
    ## create new module
    def _new_module(self, module):
        if module not in self.data:
            self.data[module] = []
        if module not in self.order:
            self.order.append(module)
    ## add SubstitutionBlockSubFile object
    def add_substitution_block(self, sub_block, overwrite = False):
        module = sub_block.filename
        if module not in self.data:
            self._new_module(module)
        current_data = self.data[module]
        if len(current_data) < sub_block.order:
            current_data.extend([None] * (sub_block.order - len(current_data)))
        if current_data[sub_block.order - 1] != None:
            current_data[sub_block.order - 1].merge(sub_block, overwrite = overwrite)
        else:
            current_data[sub_block.order - 1] = sub_block
        # self.data[sub_block.filename] = current_data
        return
    ## parses list of paths to modules to dictionary indexed by module name
    def parse_modules(self):
        for module in self._modules:
            self.modules_d[os.path.basename(module)] = module
        return
    def get_module_path(self, module):
        if module in self.modules_d:
            return self.modules_d[module]
        else:
            return self.module_paths.search(module)
    ## parses contents of substitution file
    def parse(self, filename = None, string = None):
        if filename is not None:
            blocks = self._parser.split_blocks_from_file(filename,
                                                         lambda block: SubstitutionBlockSubFile(block, self))
        elif string is not None:
            blocks = self._parser.split_blocks(string,
                                               lambda block: SubstitutionBlockSubFile(block, self))
        else:
            raise Exception("SubstitutionFile.parse requires either filename or string.")
        for block in blocks:
            self.add_substitution_block(block)
        return
    def parse_string(self, string):
        self.parse(string = string)
    def parse_file(self, filename):
        self.parse(filename = filename)
    ## caches requested default file and returns corresponding SubstitutionBlockDefaultFile object
    ## filename should be the basename of the module file (e.g. module.slim, not /path/to/module.slim)
    def defaults(self, filename):
        if filename not in self._defaults:
            f_module = self.get_module_path(filename)
            f_default = f_module if f_module is None else f_module + ".default"
            if (not f_module) or (not os.path.exists(f_module)):
                return {}
            else:
                self._defaults[filename] = SubstitutionBlockDefaultFile(f_default)
        return self._defaults[filename].variables
    def merge(self, new_substitution_file, overwrite = False, deepcopy = False):
        for other_filename, other_blocks in new_substitution_file.data.items():
            blocks_to_add = other_blocks if not deepcopy else copy.deepcopy(other_blocks)
            if other_filename not in self.data:
                self._new_module(other_filename)
                self.data[other_filename] = blocks_to_add
            else:
                self_blocks = self.data[other_filename]
                for i, other_block in enumerate(blocks_to_add):
                    if other_block is None:
                        continue
                    else:
                        self.add_substitution_block(other_block, overwrite = overwrite)
        return
    def blocks(self):
        for module, sub_blocks in self.data.items():
            for sub_block in sub_blocks:
                yield sub_block
        return
    @property
    def modules(self):
        return list(self.data.keys())
    ## returns empty list if module not in self
    ## else returns list of SubstitutionBlockSubFile objects for the module
    def get_blocks_by_module(self, module):
        return self.data.get(module, [])
    def generate_string(self):
        output = ""
        for blocks in self.data.values():
            for block in blocks:
                output += block.generate_string()
        return output
    def generate_script(self):
        pass
    def build_script(self, order = None, exclude_if_not_in_order = True, indentation = '\t',
                     ignore_comments = True):
        '''
        Builds a Script object based on SubstitutionFile contents.
        order (list): default = None.
            Modules will be added to script in this order, if specified.
            Otherwise, they will be added according to self.order.
            If neither is specified, order will be random.
        exclude_if_not_in_order (bool): default = True.
            (For the rest of this description, 'order' refers to argument order if specified,
            self.order if not.)
            If True and 'order' is not None, modules not in 'order' will be excluded from output Script.
            If False and 'order' is not None, modules not in 'order' will be appended to end of
            ordered modules in random order.
            If False and 'order' is None, modules will be added in random order
            (in theory, but since dictionaries seem to be ordered these days...who knows :))
        '''
        ## determine order of modules
        order = (order if order is not None else self.order if self.order else self.modules)
        if not exclude_if_not_in_order:
            missing_modules = [module for module in self.modules if module not in order]
            order.extend(missing_modules)
        ## create final Script object
        new_script = ScriptModule(indentation = indentation, suppress_warning = True)
        ## start adding modules to script
        general_block = None
        for module in order:
            sub_blocks = self.get_blocks_by_module(module)
            ## check if module is general block. If yes, we store that and continue
            ## we'll only substitution general block variables after all modules have been integrated
            if module == '':
                general_block = sub_blocks
                continue
            ## get path to module file
            module_path = self.get_module_path(module)
            if module_path is None: continue
            ## add module and substitute
            module_script = ScriptModule(filename = module_path)
            for sub_block in sub_blocks:
                if sub_block is None: continue
                new_script.merge_script(module_script.copy(substitute = True,
                                                           substitution_block = sub_block,
                                                           ignore_comments = ignore_comments))
        ## integrate general block if it exists
        if general_block is not None:
            for sub_block in general_block:
                final_script_str = new_script.make_string(substitute = True,
                                                          substitution_block = sub_block,
                                                          ignore_comments = ignore_comments)
        else:
            final_script_str = new_script.make_string(substitute = False,
                                                      ignore_comments = ignore_comments)
        ## substitute SUBSTITUTION_ID (defined in self.substitution_file)
        final_script_str = final_script_str.replace("$SUBSTITUTION_ID$", str(self.substitution_id))
        ## output final Script object
        return Script(string = final_script_str, indentation = indentation, suppress_warning = True)


# ## test
# dir_base = '/mnt/d/OneDrive_doysd/OneDrive - Default Directory/scripts/SLiMerge'
# fname = dir_base + '/test/substitution_1.txt'
# modules = [dir_base + '/test/modules/output_full.slim', dir_base + '/test/modules/general_WF.slim', dir_base + '/test/modules/add_new_drawn_mutation.slim']
# x = SubstitutionFile(fname, modules)
# x.data
# x.data["output_full.slim"][0].variables

# txt = '''
# []
# VAR1=a
# VAR2=b

# [hello.slim]

# [ohno.slim]
# HEY=1
# 34=GH
# '''
