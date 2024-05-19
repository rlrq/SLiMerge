Custom SLiM Modules
===================

``execute_slimerge.py`` pieces together modules according to a SLiMerge recipe file and generates .slim files. If ``--rep`` is equal to or greater than 1, the output .slim files will also be execute for ``--rep`` number of replicates. To only generate .slim files WITHOUT execution, use ``--rep 0``.


Installation
------------

#. Download the ``execute_slimerge.py`` file, the ``modules`` directory, and the ``slimerge`` directory  (including contents) and place them into the same directory. The directory structure should look like this::

     <slimerge directory>/
     |-- execute_slimerge.py
     +-- modules/
     |   |-- <moduleA.slim>
     |   +-- <moduleB.slim>
     +-- slimerge/
         |-- code_blocks.py
         |-- generate_slim_template.py
         |-- recipe_file.py
         |-- slimerge.py
         +-- substitution_file.py
     
#. To execute::

     python3 <path to execute_slimerge.py> <arguments>


Overview: SLiMerge recipe
-------------------------

SLiMerge uses a 'recipe' file (distinct from recipes in the SLiM programme), which is required as a positional argument, to define modules to be assembled (as well as module-specific and global substitution values, but we'll get to that later). Each module file should have a unique file name. If any of the modules are stored in a different location than the ``modules`` directory located in the same directory as ``execute_slimerge.py``, the ``--module-path <path to directory>`` (can be used multiple times) should be used to tell the programme where to search for modules.

Sample recipe file 1::

  [moduleA.slim]

  [moduleB.slim]

The above recipe tells SLiMerge to assemble code blocks from two modules in the order [1] moduleA.slim, then [2]  moduleB.slim. Note that module names are enclosed in square brackets.

You can also assemble multiple copies of the same module by appending ``.<integer>`` to the module declaration lines.

Sample recipe file 2::

  [moduleA.slim].1
  
  [moduleA.slim].2

  [moduleB.slim]

However, as you'll see in the next section, both copies of ``moduleA.slim`` will be collapsed into a single copy as they are duplicate blocks.


Overview: module files
----------------------

Module files are not simply added wholesale in sequence. Where the top level is identical, contents will be merged into the same top level callback. Duplicate code blocks within the same top level block will be removed. Code will be added in order from the first to last input file. Note that line containing callback MUST be exactly identical, including any whitespace. A simple string comparison will be used to determine if the top level callbacks match. For simplicity, lines that are comment-only will NOT be reproduced in the output. 


Example
+++++++

Recipe file (``example_1.recipe``)::

  [moduleA.slim]

  [moduleB.slim]

Module file 1 (``moduleA.slim``)::

  // initialize
  initialize() {
      initializeSex("A");
  }

  $START$:$END$ late() {
      p1.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m2, 10000);
  }

  $END$ late() {
      sim.simulationFinished();
  }

Module file 2 (``moduleB.slim``)::

  initialize() {
      initializeMutationRate(1e-7);
  }

  $START$:$END$ late() {
      p1.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m3, 10000);
  }

  1 late() {
      sim.addSubpop("p1", population_size);
  }

Code executed

.. code-block::

   python3 execute_slimerge.py <path to example_1.recipe> --dir <output directory> --prefix <prefix> --rep 0
  

Output directory structure::

  <output directory>
  +-- <prefix>_1/
      |-- <prefix>_1.slim
      |-- <prefix>_1.txt
      +-- slim_out/

We'll touch on ``<prefix>_1.txt`` later. But for now, the contents of the output file ``<prefix>_1.slim`` are::

  initialize() {
      initializeSex("A");
      initializeMutationRate(1e-7);
  }
  $START$:$END$ late() {
      p1.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m2, 10000);
      p1.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m3, 10000);
  }
  $END$ late() {
      sim.simulationFinished();
  }
  1 late() {
      sim.addSubpop("p1", population_size);
  }

  
Using placeholders and substitutions in reusable modules
--------------------------------------------------------

As we've just established, including a module multiple times in a recipe file results in the same output file as including it only once. So why does SLiMerge have provisions for assembling multiple copies of the same module?

This is because SLiMerge is intended to assemble modules with undefined placeholder variables that can be defined by the recipe file. When placeholders are substituted with different values for each copy of the same module, the resultant code blocks that are no longer identical when they are added to the output .slim file will not be collapsed.

The recipe file also details values to substitute into each module before integrating into a final output. For example, if multiple mutations are to be drawn, ``add_new_drawn_mutation.slim`` should be included multiple times in the recipe file. As duplicate code is ignored, this will effectively result in only a single copy of the code being present in the output file. To work around this, the recipe file can be used to alter placeholder values (present in module files as ``$<variable_name>$``) so that they are no longer identical. A block starting with header line ``[]`` can be used to specify variable substitutions to be handled at the end of script integration.

Substitutions for specific module files will be applied before the code block from the module file is added to the output. Substitutions that are to be applied globally after all code blocks are assembled will be applied last.


Sample ``example_2.recipe`` recipe file contents::

  []
  N_INDIVIDUALS=10
  
  [add_new_drawn_mutation.slim].1
  REPLACE=.
  MUTATION_NAME=m2
  POSITION=10000

  [add_new_drawn_mutation.slim].2
  REPLACE=.
  MUTATION_NAME=m3
  POSITION=70000

Where values for each file is separated by a blank line, and starts with header line ``[<file name with extension>]``. Where multiple versions of the file are passed as input, the header line should be suffixed by ``.<order number>``. For variables where substitution does not occur at this template-merging stage, they can be excluded from this file (alternatively, you can use the general block header ``[]`` to define shared variables; in the above example, ``N_INDIVIDUALS`` will be set to ``10`` for both ``add_new_drawn_mutation.slim`` copies after all module files have been integrated). For variables that use default values, ``<variable name>=.`` is used to specify this. Otherwise, all other variables can be defined as seen above. There will be no conversion--the values supplied in the recipe file will replace ``$<variable name>$`` in the template modules as-is.

Note that for variables using default values, please define them within their respective module blocks. If specified in the general ``[]`` block, the script will not know which default file to use.

Given the following ``add_new_drawn_mutation.slim`` module contents::

  // variables with defaults: GENERATION,SUBPOPULATION,N_INDIVIDUALS,REPLACE,MUTATION_NAME,POSITION
  // requires: GENERATION,SUBPOPULATION,N_INDIVIDUALS,REPLACE,MUTATION_NAME,POSITION
  $GENERATION$ late() {
          $SUBPOPULATION$.sampleIndividuals($N_INDIVIDUALS$, $REPLACE$).genomes.addNewDrawnMutation($MUTATION_NAME$, $POSITION$)
  }

And ``add_new_drawn_mutation.slim.default`` (this file containing default values MUST be in the same directory as the module file and be name ``<module file>.template``) contents::

  [add_new_drawn_mutation.slim]
  GENERATION=1
  SUBPOPULATION=p1
  N_INDIVIDUALS=10
  REPLACE=F
  MUTATION_NAME=m1
  POSITION=0

If we execute the following code

.. code-block::
   
   python3 execute_slimerge.py <path to example_2.recipe> --dir <output directory> --prefix <prefix> --rep 0

the contents of ``<prefix>_1.slim`` will be::

  $GENERATION$ late() {
          $SUBPOPULATION$.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m2, 10000)
          $SUBPOPULATION$.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m3, 70000)
  }


Specifying alternate values
---------------------------

The true power of SLiMerge is in its automation of SLiM for combinations of modules and user-defined parameter values. Alternative values for a given variable should be separated by semicolons.

In the example below, we tell SLiMerge to generate all combinations of 10 and 20 for ``N_individuals`` for both m2 and m3.

Sample ``example_3.recipe`` recipe file contents::

  [add_new_drawn_mutation.slim].1
  N_INDIVIDUALS=10;20
  REPLACE=.
  MUTATION_NAME=m2
  POSITION=10000

  [add_new_drawn_mutation.slim].2
  N_INDIVIDUALS=10;20
  REPLACE=.
  MUTATION_NAME=m3
  POSITION=70000

 
Note that ``N_individuals`` is now separately defined under each ``[add_new_drawn_mutation]`` header. Additionally, we specify the alternative values using ``N_individuals=10;20``.

If we execute the following code

.. code-block::
   
   python3 execute_slimerge.py <path to example_3.recipe> --dir <output directory> --prefix <prefix> --rep 0

the output directory will contain four directories, one for each combination of ``N_individuals`` values, suffixed with a unique ID value for each substitution combination::

  <output directory>
  |-- <prefix>_1/
  |-- <prefix>_2/
  |-- <prefix>_3/
  +-- <prefix>_4/

The contents of ``<prefix>_1.slim``::

  $GENERATION$ late() {
          $SUBPOPULATION$.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m2, 10000)
          $SUBPOPULATION$.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m3, 70000)
  }

The contents of ``<prefix>_2.slim``::

  $GENERATION$ late() {
          $SUBPOPULATION$.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m2, 10000)
          $SUBPOPULATION$.sampleIndividuals(20, F).genomes.addNewDrawnMutation(m3, 70000)
  }

The contents of ``<prefix>_3.slim``::

  $GENERATION$ late() {
          $SUBPOPULATION$.sampleIndividuals(20, F).genomes.addNewDrawnMutation(m2, 10000)
          $SUBPOPULATION$.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m3, 70000)
  }

The contents of ``<prefix>_4.slim``::

  $GENERATION$ late() {
          $SUBPOPULATION$.sampleIndividuals(20, F).genomes.addNewDrawnMutation(m2, 10000)
          $SUBPOPULATION$.sampleIndividuals(20, F).genomes.addNewDrawnMutation(m3, 70000)
  }


``<prefix>_1.txt``, which we did not cover earlier, contains the variables and their substitutions specific to a given substitution combination. For example, the contents of ``<prefix>_1.slim`` are::

  [add_new_drawn_mutation.slim].1
  N_INDIVIDUALS=10
  REPLACE=.
  MUTATION_NAME=m2
  POSITION=10000

  [add_new_drawn_mutation.slim].2
  N_INDIVIDUALS=10
  REPLACE=.
  MUTATION_NAME=m3
  POSITION=70000

which is effectively the same as ``example_2.recipe``. These resolved substitution files are intended to allow users to track parameters for each substitution combination.


Specifying alternate modules
----------------------------

Like with variable values, we can also define alternate modules. The syntax for this is to enclose altnerative modules in the SLiMerge recipe file with curly braces separated by ``|``.

Sample ``example_4.recipe`` recipe file contents::

  []
  OUTPUT_FILE="$OUTPUT_DIRECTORY$/output.txt"
  
  [add_new_drawn_mutation.slim]
  N_INDIVIDUALS=10
  REPLACE=.
  MUTATION_NAME=m2
  POSITION=10000

  {
    [simulation_finished.slim]
    CALLBACK=2:5000 late
    CONDITION=T
    WRITE_FULL=T
  }|{
    [simulation_finished_append.slim]
    CALLBACK=2:5000 late
    CONDITION=T
    APPEND_CONTENT=paste(getSeed(), sim.cycle, sep="\t")
  }

Given the following ``simulation_finished.slim`` module contents::

  // variables with defaults: CALLBACK,CONDITION,WRITE_FULL,OUTPUT_FILE
  // requires: CALLBACK,CONDITION,WRITE_FULL,OUTPUT_FILE
  $CALLBACK$() {
          if ($CONDITION$){
                  sim.simulationFinished();
                  if ($WRITE_FULL$){
                          sim.outputFull($OUTPUT_FILE$);
                  }
          }
  }

And the following ``simulation_finished_append.slim`` module contents::

  // variables with defaults: CALLBACK,CONDITION,WRITE_FULL,OUTPUT_FILE
  // requires: CALLBACK,CONDITION,OUTPUT_FILE,APPEND_CONTENT
  $CALLBACK$() {
          if ($CONDITION$){
                  sim.simulationFinished();
                  writeFile($OUTPUT_FILE$, $APPEND_CONTENT$, append=T);
          }
  }


If we execute the following code

.. code-block::
   
   python3 execute_slimerge.py <path to example_4.recipe> --dir <output directory> --prefix <prefix> --rep 0

the output directory will contain two directories, one for each alternative block, suffixed with a unique ID value for each substitution combination::

  <output directory>
  |-- <prefix>_1/
  +-- <prefix>_2/

The contents of ``<prefix>_1.slim``::

  $GENERATION$ late() {
          $SUBPOPULATION$.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m2, 10000)
  }
  2:5000 late() {
          if (T){
                  sim.simulationFinished();
                  if (F){
                          sim.outputFull("<output directory>/output.txt");
                  }
          }
  }

The contents of ``<prefix>_2.slim``::

  $GENERATION$ late() {
          $SUBPOPULATION$.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m2, 10000)
  }
  2:5000 late() {
          if (T){
                  sim.simulationFinished();
                  writeFile("<output directory>/output.txt", paste(getSeed(), sim.cycle, sep="\t"), append=T);
          }
  }

Note:

* These blocks can be nested, and there can be an arbitrary number of alternative blocks
* SLiMerge substitutes any occurrence of ``$OUTPUT_DIRECTORY$`` in the output .slim files with the path passed to the ``--dir <output directory>`` argument
* Variable values can include terms for further substitution sucha as ``$OUTPUT_DIRECTORY$``
* If using ``--rep 1`` (or ``--rep`` with any value that is greater than 0), then all substitution terms MUST BE RESOLVED in the output .slim file, as SLiMerge will attempt to execute SLiM ``--rep`` number of times using these .slim files


Input file requirements
-----------------------

Recipe file:

* NO curly braces EXCEPT where they indicate a code block
* NO semicolons EXCEPT where they separate alternative values for a given variable

The above characters are NOT allowed in comments or strings. Please find a work-around.


Modules
-------

This section describes some generic modules and their usage.

add_constant.slim, add_global.slim
++++++++++++++++++++++++++++++++++

These modules allow users to define variables in the output .slim file. This is also useful if users wish to parse metadata for each substitution combination using resolved substitution files.

add_constant.slim::

  // required: CONSTANT_NAME,CONSTANT_VALUE
  initialize() {
          defineConstant("$CONSTANT_NAME$", $CONSTANT_VALUE$);
  }

add_global.slim::

  // required: GLOBAL_NAME,GLOBAL_VALUE
  initialize() {
          defineGlobal("$GLOBAL_NAME$", $GLOBAL_VALUE$);
  }

Sample usage in ``example_5.recipe`` file::

  [add_global.slim].1
  GLOBAL_NAME=MUTATIONS
  GLOBAL_VALUE=c()
  
  [add_constant.slim].1
  CONSTANT_NAME=MISCELLANEOUS_CONSTANT
  CONSTANT_VALUE="miscellaneous constant"

  [add_constant.slim].2
  CONSTANT_NAME=BREEDING_SYSTEM
  CONSTANT_VALUE=$BREEDING_SYSTEM$
  
  {
    []
    BREEDING_SYSTEM="separate_sexes"

    [separate_sexes.slim]
    CHROMOSOME_TYPE=A
  }|{
    []
    BREEDING_SYSTEM="hermaphrodites"
  }

where the contents of  ``separate_sexes.slim`` are::

  // variables with defaults: CHROMOSOME_TYPE
  // requires: CHROMOSOME_TYPE
  initialize(){
        initializeSex("$CHROMOSOME_TYPE$");
  }


the output directory will contain two directories, one for each alternative block, suffixed with a unique ID value for each substitution combination::

  <output directory>
  |-- <prefix>_1/
  +-- <prefix>_2/

The contents of ``<prefix>_1.slim``::

  initialize() {
          defineGlobal("MUTATIONS", c());
          defineConstant("MISCELLANEOUS_CONSTANT", "miscellaneous constant");
          defineConstant("BREEDING_SYSTEM", "separate_sexes");
          initializeSex("A");
  }

The contents of ``<prefix>_2.slim``::

  initialize() {
          defineGlobal("MUTATIONS", c());
          defineConstant("MISCELLANEOUS_CONSTANT", "miscellaneous constant");
          defineConstant("BREEDING_SYSTEM", "hermaphrodites");
  }

Note that regardless of where they are located in the .recipe file, the substitutions under ``[]`` are handled last. This means that ``$CONSTANT_VALUE$`` was first replaced with ``$BREEDING_SYSTEM$``, and then ``$BREEDING_SYSTEM$`` was replaced with either ``"separate_sexes"`` or ``"hermaphrodites"`` depending on which alternative block was assembled.


Consolidating substitution combinations using ``summarise_slim_variables.py``
-----------------------------------------------------------------------------

``summarise_slim_variables.py`` is provided to extract global substitution values (i.e. substitutions under ``[]`` header) from substitution files from a single SLiMerge execution into a single tab-separated text file. Note that this script is not designed to retrieve substitutions for individual modules (e.g. substitutions under ``[add_new_drawn_mutation.slim].1``) EXCEPT constants defined using ``add_constant.slim``.

For example, if we return to ``example_5.recipe``, we can execute the following::

  python3 summarise_slim_variables.py <output directory> --variables BREEDING_SYSTEM --constants MISCELLANEOUS_CONSTANT

, where ``<output directory>`` is the output directory of the SLiMerge execute. The output file, ``run_summary.txt``, will be generated in ``<output directory>``, to obtain the following directory structure::
  
  <output directory>
  |-- run_summary.txt
  |-- <prefix>_1/
  +-- <prefix>_2/

The contents of ``run_summary.txt`` are::

  SUBSTITUTION_ID	BREEDING_SYSTEM	MISCELLANEOUS_CONSTANT
  1	"separate_sexes"	"miscellaneous constant"
  2	"hermaphrodites"	"miscellaneous constant"
