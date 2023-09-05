Custom SLiM Modules
===================

The bits of codes in these files do not form complete SLiM programmes. Instead, they are modules that need to be pieced together.

Requirements
------------

The python script used to combine files requires that:

* no curly braces should be present anywhere except where they indicate a code block (i.e. curly braces in comment lines are NOT allowed)

Creating the pieces
-------------------

Where the top level is identical, contents will be merged into the same top level callback. Duplicate code blocks within the same top level block will be removed. Code will be added in order from the first to last input file. Note that line containing callback MUST be exactly identical, including any whitespace. A simple string comparison will be used to determine if the top level callbacks match. For simplicity, lines that are comment-only will NOT be reproduced in the output.

Example
+++++++

File 1::

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

File 2::

  initialize() {
      initializeMutationRate(1e-7);
  }

  $START$:$END$ late() {
      p1.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m3, 10000);
  }

  1 late() {
      sim.addSubpop("p1", population_size);
  }

Output file::

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


Substitution file
-----------------

The substitution file, provided using keyword ``--sub`` or ``--substitution``, details values to substitute into each module before integrating into a final output. For example, if multiple mutations are to be drawn, ``add_new_drawn_mutation.slim`` will be passed as an argument multiple times. As duplicate code is ignored, this will effectively result in only a single copy of the code being present in the output template. To work around this, a substitution file can be used to alter placeholder values (present in module files as ``$<variable_name>$``) so that they are no longer identical. A block starting with header line ``[]`` can be used to specify variable substitutions to be handled at the end of script integration.

Sample ``substitution.txt`` substitution file contents::

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

Where values for each file is separated by a blank line, and starts with header line ``[<file name with extension>]``. Where multiple versions of the file are passed as input, the header line should be suffixed by ``.<order number>``. For variables where substitution does not occur at this template-merging stage, they can be excluded from this file (alternatively, you can use the general block header ``[]`` to define shared variables; in the above example, ``N_INDIVIDUALS`` will be set to ``10`` for both ``add_new_drawn_mutation.slim`` copies after all module files have been integrated). For variables that use default values, ``<variable name>=.`` is used to specify this. Otherwise, all other variables can be defined as seen above. There will be no conversion--the values supplied in the substitution file will replace ``$<variable name>$`` in the template modules as-is.

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

The output of

.. code-block::
   
   slimerge output.slim --sub substitution.txt add_new_drawn_mutation.slim add_new_drawn_mutation.slim

will be::

  $GENERATION$ late() {
          $SUBPOPULATION$.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m2, 10000)
          $SUBPOPULATION$.sampleIndividuals(10, F).genomes.addNewDrawnMutation(m3, 70000)
  }
