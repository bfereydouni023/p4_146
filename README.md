# HTN Planner Notes

## Heuristic

The planner registers a pruning check with `pyhop.add_check` to keep search from
wasting time on obviously bad branches:

- If the current task is `produce_<tool>` and that tool is already available,
  the branch is pruned (non-consumable tools do not need to be re-crafted).
- If a non-repeatable `produce_*` task appears again deeper in the same calling
  stack after branching through other `produce_*` tasks, the branch is treated
  as cyclic regress and pruned.

This keeps the solver from infinite regress while still allowing repeated
production of quantity-oriented resources (wood/plank/stick/cobble/coal/ore/
ingot/rail).

## Method generation and ordering

`autoHTN.py` still programmatically generates methods from `crafting.json` via
`make_method`/`declare_methods`, but method declaration uses a curated
`recipe_order` map to choose deterministic, low-branching recipes for key items
(especially coal/ore/ingot/rail/cart pipelines).

The most important ordering decision for large rubric cases is to favor
stone-pickaxe mining paths for ore/coal and avoid costly cyclic alternatives.

## Batch production shortcut (`produce_batch`)

The `have_enough` task now includes `produce_batch` before the generic recursive
`produce_enough` fallback. `produce_batch` expands quantity-heavy goals into
compact subtask blocks, including:

- bulk wood/plank/stick crafting
- cobble production that bootstraps a stone pickaxe once, then mines cobble
  using the faster stone recipe
- bulk coal/ore mining and ingot smelting
- bulk rail crafting with recipe yield awareness (16 rails/craft)

This reduces recursion depth and branch explosion, which is what allows the
large test cases (`cart + rail`) to complete within the assignment timeout.
