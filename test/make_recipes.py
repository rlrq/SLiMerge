import sys
sys.path.append("/mnt/chaelab/rachelle/scripts/SLiMerge/slimerge")

import recipe_file

dir_proj = "/mnt/chaelab/rachelle/scripts/SLiMerge"

f_recipe_basename = "test.1"
f_recipe = dir_proj + "/test/recipes/" + f_recipe_basename + ".recipe"
rfile = recipe_file.RecipeFile(f_recipe, module_paths = [dir_proj + "/test/modules"])
for sub_file in rfile.substitution_files():
    with open(dir_proj + f"/test/scripts/{f_recipe_basename}.{sub_file.substitution_id}.slim", "w+") as f:
        f.write(sub_file.build_script().make_string())

