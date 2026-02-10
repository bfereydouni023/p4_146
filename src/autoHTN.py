import pyhop
import json


def check_enough(state, ID, item, num):
	if getattr(state, item)[ID] >= num:
		return []
	return False


def produce_enough(state, ID, item, num):
	return [('produce', ID, item), ('have_enough', ID, item, num)]


# Batch method for quantity-heavy resources to reduce recursion depth.
def produce_batch(state, ID, item, num):
	have = getattr(state, item)[ID]
	need = num - have
	if need <= 0:
		return []

	# For each item type, expand to a compact sequence of subtasks/operators.
	if item == 'wood':
		return [('op_punch_for_wood', ID)] * need
	if item == 'plank':
		crafts = (need + 3) // 4
		return [('have_enough', ID, 'wood', crafts)] + [('op_craft_plank', ID)] * crafts
	if item == 'stick':
		crafts = (need + 3) // 4
		return [('have_enough', ID, 'plank', 2 * crafts)] + [('op_craft_stick', ID)] * crafts
	if item == 'cobble':
		# If stone pickaxe exists, use the faster cobble recipe directly.
		if state.stone_pickaxe[ID] >= 1:
			return [('op_stone_pickaxe_for_cobble', ID)] * need
		# Bootstrap stone pickaxe with wooden mining, then mine requested cobble quickly.
		return ([('have_enough', ID, 'wooden_pickaxe', 1)] +
			[('op_wooden_pickaxe_for_cobble', ID)] * 3 +
			[('have_enough', ID, 'bench', 1), ('have_enough', ID, 'stick', 2), ('op_craft_stone_pickaxe_at_bench', ID)] +
			[('op_stone_pickaxe_for_cobble', ID)] * need)
	# Use stone pickaxe paths to keep mining branches deterministic and fast.
	if item == 'coal':
		return [('have_enough', ID, 'stone_pickaxe', 1)] + [('op_stone_pickaxe_for_coal', ID)] * need
	if item == 'ore':
		return [('have_enough', ID, 'stone_pickaxe', 1)] + [('op_stone_pickaxe_for_ore', ID)] * need
	# Smelting is expanded in bulk once coal/ore requirements are established.
	if item == 'ingot':
		return [('have_enough', ID, 'furnace', 1), ('have_enough', ID, 'coal', need), ('have_enough', ID, 'ore', need)] + [('op_smelt_ore_in_furnace', ID)] * need
	if item == 'rail':
		crafts = (need + 15) // 16
		return [('have_enough', ID, 'bench', 1), ('have_enough', ID, 'ingot', 6 * crafts), ('have_enough', ID, 'stick', crafts)] + [('op_craft_rail_at_bench', ID)] * crafts

	return False


pyhop.declare_methods('have_enough', check_enough, produce_batch, produce_enough)


def produce(state, ID, item):
	return [('produce_{}'.format(item), ID)]


pyhop.declare_methods('produce', produce)


def _normalize_name(name):
	return name.replace(' ', '_')


# Convert one JSON recipe into an HTN method (requirements + consume + operator).
def make_method(name, rule):
	def method(state, ID):
		subtasks = []
		for item, num in rule.get('Requires', {}).items():
			subtasks.append(('have_enough', ID, item, num))
		for item, num in rule.get('Consumes', {}).items():
			subtasks.append(('have_enough', ID, item, num))
		subtasks.append(('op_{}'.format(name), ID))
		return subtasks

	method.__name__ = 'produce_{}'.format(name)
	return method


# Convert one JSON recipe into a primitive operator with precondition checks.
def make_operator(rule):
	def operator(state, ID):
		if state.time[ID] < rule['Time']:
			return False

		for item, num in rule.get('Requires', {}).items():
			if getattr(state, item)[ID] < num:
				return False

		for item, num in rule.get('Consumes', {}).items():
			if getattr(state, item)[ID] < num:
				return False

		for item, num in rule.get('Consumes', {}).items():
			getattr(state, item)[ID] -= num

		for item, num in rule.get('Produces', {}).items():
			getattr(state, item)[ID] += num

		state.time[ID] -= rule['Time']
		return state

	return operator


# Programmatically build/declare every operator from crafting.json.
def declare_operators(data):
	operators = []
	for recipe_name, rule in data['Recipes'].items():
		op = make_operator(rule)
		op.__name__ = 'op_{}'.format(_normalize_name(recipe_name))
		operators.append(op)

	pyhop.declare_operators(*operators)


# Programmatically build/declare methods from crafting.json recipes.
def declare_methods(data):
	# Build methods from recipes programmatically.
	generated = {}
	for recipe_name, rule in data['Recipes'].items():
		product = next(iter(rule['Produces']))
		method = make_method(_normalize_name(recipe_name), rule)
		generated.setdefault(product, {})[recipe_name] = method

	# Ordered recipe preference avoids expensive or cyclic alternatives.
	recipe_order = {
		'wood': ['punch for wood'],
		'plank': ['craft plank'],
		'stick': ['craft stick'],
		'bench': ['craft bench'],
		'wooden_pickaxe': ['craft wooden_pickaxe at bench'],
		'stone_pickaxe': ['craft stone_pickaxe at bench'],
		'furnace': ['craft furnace at bench'],
		'cobble': ['wooden_pickaxe for cobble', 'stone_pickaxe for cobble'],
		# Restrict these to stone-pickaxe recipes to avoid slow cyclic alternatives.
		'coal': ['stone_pickaxe for coal'],
		'ore': ['stone_pickaxe for ore'],
		'ingot': ['smelt ore in furnace'],
		'iron_pickaxe': ['craft iron_pickaxe at bench'],
		'rail': ['craft rail at bench'],
		'cart': ['craft cart at bench'],
	}

	for product, methods in generated.items():
		if product in recipe_order:
			ordered = [methods[name] for name in recipe_order[product] if name in methods]
			if ordered:
				pyhop.declare_methods('produce_{}'.format(product), *ordered)
				continue

		# Fallback for unused products.
		pyhop.declare_methods('produce_{}'.format(product), *methods.values())


# Pruning hook used by pyhop to cut obvious dead-end/cyclic branches.
def add_heuristic(data, ID):
	tools = set(data['Tools'])
	repeatable = {'wood', 'plank', 'stick', 'cobble', 'coal', 'ore', 'ingot', 'rail'}

	def heuristic(state, curr_task, tasks, plan, depth, calling_stack):
		name = curr_task[0]
		if not name.startswith('produce_'):
			return False
		item = name[len('produce_'):]

		# Prevent repeated crafting of non-consumable tools once one exists.
		if item in tools and getattr(state, item)[ID] >= 1:
			return True

		# Prune cyclic regressions: produce_X -> ... produce_Y -> ... produce_X
		# but allow straight-line repetition for quantities (e.g., repeated ore production).
		seen = None
		for i, task in enumerate(calling_stack):
			if task[0] == name:
				seen = i
		if seen is not None and item not in repeatable:
			for task in calling_stack[seen + 1:]:
				if task[0].startswith('produce_') and task[0] != name:
					return True

		return False

	pyhop.add_check(heuristic)


# Optional runtime method reordering hook (kept identity for determinism).
def define_ordering(data, ID):
	def reorder_methods(state, curr_task, tasks, plan, depth, calling_stack, methods):
		return methods

	pyhop.define_ordering(reorder_methods)


# Build a pyhop state object from Problem/Items/Tools JSON sections.
def set_up_state(data, ID):
	state = pyhop.State('state')
	setattr(state, 'time', {ID: data['Problem']['Time']})

	for item in data['Items']:
		setattr(state, item, {ID: 0})

	for item in data['Tools']:
		setattr(state, item, {ID: 0})

	for item, num in data['Problem']['Initial'].items():
		setattr(state, item, {ID: num})

	return state


# Translate Goal JSON entries into top-level have_enough tasks.
def set_up_goals(data, ID):
	goals = []
	for item, num in data['Problem']['Goal'].items():
		goals.append(('have_enough', ID, item, num))

	return goals


if __name__ == '__main__':
	import sys
	rules_filename = 'crafting.json'
	if len(sys.argv) > 1:
		rules_filename = sys.argv[1]

	with open(rules_filename) as f:
		data = json.load(f)

	state = set_up_state(data, 'agent')
	goals = set_up_goals(data, 'agent')

	declare_operators(data)
	declare_methods(data)
	add_heuristic(data, 'agent')
	define_ordering(data, 'agent')

	pyhop.pyhop(state, goals, verbose=1)
