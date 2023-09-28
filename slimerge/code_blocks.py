import pyparsing as pp

## adapted from https://stackoverflow.com/a/54715720
def unlevel_list(obj):
    while isinstance(obj, list) and len(obj) == 1 and isinstance(obj[0], list):
        obj = obj[0]
    if isinstance(obj, list):
        return [unlevel_list(item) for item in obj]
    else:
        return obj


def indentation(s):
    return (len(s) - len(s.lstrip()))

class CodeBlock:    
    ## raw_data should be a list of lines. Will be str.strip()ed
    def __init__(self, raw_data):
        self.main = raw_data[0].strip()
        self.sub_blocks = []
        if len(raw_data) > 1:
            self.parse_sub_block(raw_data[1])
    def parse_sub_block(self, code_block):
        '''
        Parse raw sub blocks ([potentially nested] list of strings) for this code block into 
        list of CodeBlock objects, then store this list of CodeBlock objects into self.sub_blocks
        '''
        num_chunks = len(code_block)
        i = 0
        while i < num_chunks:
            if ( (i == num_chunks - 1) or
                 (not isinstance(code_block[i+1], list)) ):
                self.sub_blocks.append(CodeBlock(code_block[i:i+1]))
                i += 1
            else: ## if next chunk is a list (i.e. is within curly braces therefore is a sub block)
                ## make new CodeBlock from both current chunk and next chunk (sub block)
                self.sub_blocks.append(CodeBlock(code_block[i:i+2]))
                i += 2
        return
    def make_string(self, indent_level = 0, indentation = '\t', ignore_comments = True):
        '''
        Generate string for this code block (including its sub blocks) by 
        - restoring opening and closing braces
        - inserting appropriate indentation
        Formatted so that it is a valid script (assuming input script is valid),
        directly writable to script file.
        '''
        curr_indent = (indent_level * indentation)
        ## if ignore_comments = True and self.main is a comment
        if ignore_comments and self.main[:2] == "//":
            ## if no sub-blocks, just return empty string
            if not self.sub_blocks: return ''
            ## if has sub-blocks, add indentation but not self.main
            else: str_main = curr_indent
        else:
            str_main = curr_indent + self.main
        ## format sub-blocks
        if self.sub_blocks:
            str_sub_blocks = [sub_block.make_string(indent_level = indent_level + 1,
                                                    indentation = indentation,
                                                    ignore_comments = ignore_comments)
                              for sub_block in self.sub_blocks]
            return (str_main + "{\n" +
                    ''.join(str_sub_blocks) +
                    curr_indent + "}\n")
        else:
            return str_main + '\n'
    def add_sub_blocks(self, new_sub_blocks):
        '''
        Integrate new sub-blocks (list of CodeBlock object) into script.
        CodeBlock objects in new_sub_blocks are assumed to be same level as 
        CodeBlock objects in self.sub_blocks.
        '''
        ## new_sub_blocks should be list of CodeBlock objects
        if len(new_sub_blocks) == 0:
            return
        sub_block_index = {sub_block.main: sub_block for sub_block in self.sub_blocks}
        for sub_block in new_sub_blocks:
            sub_block_main = sub_block.main
            if sub_block_main in sub_block_index:
                sub_block_index[sub_block_main].add_sub_blocks(sub_block.sub_blocks)
            else:
                self.sub_blocks.append(sub_block)
        return

class Script:
    ## from https://stackoverflow.com/a/43443894
    # single_line = pp.OneOrMore(pp.Word(pp.printables, excludeChars="{}").setWhitespaceChars(' ')).setParseAction(' '.join)
    single_line = pp.OneOrMore(pp.Regex( "[^{}\\n]+" ))
    multi_line = pp.OneOrMore(pp.Optional(single_line) + pp.LineEnd().suppress())
    body = pp.nestedExpr( '{', '}', content = multi_line | single_line )
    def code_string_to_nested_list(self, string):
        '''
        Parses string of code into nested list where each nested list is a nested code block.
        Each new line of code will be distinct elements in the list.
        Note that the line that opens a nested code block will be an unnested string stored in
        the index right before the nexted code block. I.e.
          some_code;
          1 early() {
            sim.addSubpop("p1", 500);
          }
        becomes
          ['some_code;', '1 early()', ['sim.addSubpop("p1", 500);']]
        '''
        return unlevel_list(self.body.searchString('{' + string + '}').asList())
    def __init__(self, filename = None, string = None, indentation = '\t', suppress_warning = False):
        self.indentation = indentation
        self.code_blocks = []
        if filename is not None:
            self.parse_file(filename)
        elif string is not None:
            self.parse_string(string)
        elif not suppress_warning:
            print("Use Script.parse_file(<filename>) or Script.parse_string(<string>) to input data")
    def parse_file(self, filename):
        '''
        Parse Eidos code from file.
        '''
        with open(filename, 'r') as f:
            string = f.read()
            self.parse_string(string)
        return
    def parse_string(self, string):
        '''
        Parse Eidos code from string.
        '''
        chunks = self.code_string_to_nested_list(string)
        num_chunks = len(chunks)
        i = 0
        while i < num_chunks:
            if ( (i == num_chunks - 1) or
                 (not isinstance(chunks[i+1], list)) ):
                self.code_blocks.append(CodeBlock(chunks[i:i+1]))
                i += 1
            else: ## if next chunk is a list (i.e. is within curly braces therefore is a sub block)
                self.code_blocks.append(CodeBlock(chunks[i:i+2]))
                i += 2
        return
    def make_string(self, ignore_comments = True):
        '''
        Generate string for this script (including all blocks and sub blocks) by 
        - restoring opening and closing braces
        - inserting appropriate indentation
        Formatted so that it is a valid script (assuming input script is valid),
        directly writable to script file.
        '''
        output = ''.join([code_block.make_string(indent_level = 0,
                                                 indentation = self.indentation,
                                                 ignore_comments = ignore_comments)
                          for code_block in self.code_blocks])
        return output
    def copy(self, *args, **kwargs):
        '''
        Uses output of self.make_string to create a completely new Script object.
        Arguments (for self.make_string): ignore_comments=T
        '''
        new_script = self.__class__(string = self.make_string(*args, **kwargs))
        new_script.indentation = self.indentation
        new_script.substitution_block = self.substitution_block
        return new_script
    def merge_block(self, new_code_block):
        '''
        Integrate new CodeBlock object (new_code_block) into script.
        New CodeBlock object is assumed to be top-level.
        '''
        ## new_code_block should be a CodeBlock object
        for code_block in self.code_blocks:
            ## if new code block's opening matches any top level opening in the script, merge and exit
            if code_block.main == new_code_block.main:
                code_block.add_sub_blocks(new_code_block.sub_blocks)
                return
        ## if no matches found, append code block to script
        self.code_blocks.append(new_code_block)
        return
    def merge_script(self, new_script):
        '''
        Merge another Script object (new_script) into self.
        Effectively calls self.merge_block on all top-level CodeBlocks objects in new_script.
        '''
        ## new_script should be a Script object
        for new_code_block in new_script.code_blocks:
            self.merge_block(new_code_block)
        return

class ScriptModule(Script):
    def __init__(self, *args, substitution_block = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.substitution_block = substitution_block ## SubstitutionBlockGen object
    def make_string(self, ignore_comments = True, substitute = True, substitution_block = None):
        '''
        Generate string for this script (including all blocks and sub blocks) by 
        - restoring opening and closing braces
        - inserting appropriate indentation
        Formatted so that it is a valid script (assuming input script is valid),
        directly writable to script file.
        If substitute = True and self.substitution_block is not None, variable values from
        self.substitution_block will be substituted into the output.
        '''
        sub_block = substitution_block if substitution_block is not None else self.substitution_block
        output = super().make_string(ignore_comments = ignore_comments)
        if substitute and sub_block is not None:
            return sub_block.substitute(output)
        return output
    def copy(self, *args, **kwargs):
        '''
        Uses output of self.make_string to create a completely new Script object.
        If substitute = True and self.substitution_block is not None, variable values from
        self.substitution_block will be substituted in output of self.make_string before
        creating the new object.
        Arguments (for self.make_string): ignore_comments=T, substitute=T
        (created a child method just so I can update the docs with new argument)
        '''
        return super().copy(*args, **kwargs)


# class ScriptSubstitution(Script):
#     def __init__(self, *args, **kwargs, substitution_file = None, substitution_fname = None, order = None):
#         super().__init__(*args, **kwargs)
#         if substitution_file:
#             self.substitution_file = substitution_file ## SubstitutionFile object
#         elif substitution_fname:
#             self.substitution_file = SubstitutionFile(fname = substitution_fname)
#         self.order = order ## order of modules, if so desired (e.g. ['module1.slim', 'module2.slim']). There is currently no means to separately specify order for copies of modules (e.g. module1.slim with headers [module1.slim].1 and [module1.slim].2 will be collectively specified by 'module1.slim'). Otherwise modules will be added in random order (although copies of the same module will be clustered together in order).
#     def build_script(self, order = None, exclude_if_not_in_order = True):
#         '''
#         Builds a Script object based on SubstitutionFile contents.
#         order (list): default = None. If not specified, defaults to self.order.
#             Modules will be added to script in this order.
#         exclude_if_not_in_order (bool): default = True. If True, and 'order' or self.order is not None,
#             modules not in 'order' (or self.order, if 'order' is None) will be excluded from output Script.
#             If False, and 'order' or self.order is not None, modules not in 'order' (or self.order,
#             if 'order' is None) will be appended to end of ordered modules in random order.
#             If False, and 'order' and self.order are None, modules will be added in random order
#             (in theory, but since dictionaries seem to be ordered these days...who knows :))
#         '''
#         sub_file = self.substitution_file
#         ## determine order of modules
#         order = (order if order is not None else
#                  self.order if self.order is not None else
#                  sub_file.modules())
#         if not exclude_if_not_in_order:
#             missing_modules = [module for module in sub_file.modules if module not in order]
#             order.extend(missing_modules)
#         ## create final Script object
#         new_script = Script(indentation = self.indentation)
#         ## start adding modules to script
#         general_block = None
#         for module in order:
#             sub_blocks = sub_file.get_blocks_by_module(module)
#             ## check if module is general block. If yes, we store that and continue
#             ## we'll only substitution general block variables after all modules have been integrated
#             if module == '':
#                 general_block = sub_blocks
#                 continue
#             ## get path to module file
#             module_path = sub_file.get_module_path(module)
#             if module_path is None: continue
#             ## add module and substitute
#             module_script = ScriptModule(filename = module_path, indentation = self.indentation)
#             for sub_block in sub_blocks:
#                 if sub_block is None: continue
#                 new_script.merge_script(module_script.copy(substitute = True,
#                                                            substitution_block = sub_block))
#         ## integrate general block if it exists
#         if general_block is not None:
#             final_script_str = new_script.make_string(substitute = True,
#                                                       substitution_block = general_block)
#             ## substitute SUBSTITUTION_ID (defined in self.substitution_file)
#             final_script_str = final_script_str.replace("$SUBSTITUTION_ID$", str(substitution_id))
#         ## output final Script object
#         return Script(string = final_script_str, indentation = self.indentation)


############
##  TEST  ##
############

# txt = '''
# initialize() {
#   initializeSex("A");
#   initializeMutationRate(1e-7);
# }
# 1 early() {
#   sim.addSubpop("p1", 500);
#   p1.addNewDrawnMutation(hello);
# }
# sample() {
#   sample2() {
#     inner_function;
#     // more inner
#   }
#   new_line;
#   sample3() {
#     inner_function2;
#   }
# }
# '''

# txt_blk_new = [
#     'initialize()',
#     ['initializeMutationType("m1", 0.5, "f", 0.0);']
# ]

# txt_blk_new_2 = [
#     'sample()',
#     ['sample2()',
#      ['// another comment',
#       'new_code_line;']
#      ]
# ]

# txt_blk_new_3 = [
#     'sample()',
#     ['sample3()',
#      ['sample4()',
#       ['new_code_line;']
#       ]
#      ]
# ]

# txt_blk_redundant = [
#     'initialize()',
#     ['initializeSex("A");']
# ]

# script = Script()
# script.parse_string(txt)
# blk_new = CodeBlock(txt_blk_new)
# blk_new_2 = CodeBlock(txt_blk_new_2)
# blk_new_3 = CodeBlock(txt_blk_new_3)
# blk_redundant = CodeBlock(txt_blk_redundant)
# script.merge_block(blk_new)
# script.merge_block(blk_redundant)
# script.merge_block(blk_new_2)
# script.merge_block(blk_new_3)
# print('\n' + script.make_string(ignore_comments = True))
# print('\n' + script.make_string(ignore_comments = False))
