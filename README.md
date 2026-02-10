# HTN Planner Notes

Lorelai worked on the code for setting up the functionality of the HTN and Behnood (Ben) worked on the heuristic planning. We worked together through the whole project, this was just how we split the initial work.

## Heuristic

The planner uses a simple pruning heuristic to prevent infinite regress in the
recipe graph. If the current task is a `produce_*` task and the same task name
already appears in the calling stack, the branch is pruned. This stops cycles
such as producing wood → crafting a tool → producing wood again from looping
forever while still allowing alternate recipes (e.g., punch for wood) to be
tried next. The heuristic is implemented in `autoHTN.py` and is registered via
`pyhop.add_check`.

## Method ordering

When declaring methods, recipes that produce the same item are sorted by their
recipe time in ascending order. This biases the planner toward faster recipes
first while still keeping all alternatives available.
