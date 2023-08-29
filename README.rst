Custom SLiM Modules
===================

The bits of codes in these files do not form complete SLiM programmes. Instead, they are modules that need to be pieced together.

Requirements
------------

The python script used to combine files requires that:

* indentation be such that anything within curly braces MUST be indented
* closing curly braces MUST be aligned to the first non-whitespace character of the line where the matching opening curly braces are
* uses of spaces and/or tabs MUST be consistent because the python script counts whitespace characters to find matching curly braces, not the amount of space taken up by each whitespace character


Creating the pieces
-------------------

Where the top level is identical, contents will be merged into the same top level callback. Duplicate code blocks within the same top level block will be removed. Code will be added in order from the first to last input file. Note that line containing callback MUST be exactly identical, including any whitespace. A simple string comparison will be used to determine if the top level callbacks match.

Example
+++++++

File 1::

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

