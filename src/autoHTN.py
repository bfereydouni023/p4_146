import pyhop
import json

def check_enough(state, ID, item, num):
	if getattr(state,item)[ID] >= num: return []
	return False

def produce_enough(state, ID, item, num):
	return [('produce', ID, item), ('have_enough', ID, item, num)]

pyhop.declare_methods('have_enough', check_enough, produce_enough)

def produce(state, ID, item):
	return [('produce_{}'.format(item), ID)]

pyhop.declare_methods('produce', produce)

def make_method(name, rule):
	def method(state, ID):
		subtasks = []
		requires = rule.get('Requires', {})
		consumes = rule.get('Consumes', {})

		for item, num in requires.items():
			subtasks.append(('have_enough', ID, item, num))

		for item, num in consumes.items():
			subtasks.append(('have_enough', ID, item, num))

		subtasks.append(('op_{}'.format(name), ID))
		return subtasks

	method.__name__ = 'produce_{}'.format(name)
	return method

def declare_methods(data):
	# some recipes are faster than others for the same product even though they might require extra tools
	# sort the recipes so that faster recipes go first

	# your code here
	# hint: call make_method, then declare the method to pyhop using pyhop.declare_methods('foo', m1, m2, ..., mk)
	method_map = {}
	for recipe_name, rule in data['Recipes'].items():
		product = next(iter(rule['Produces']))
		method = make_method(_normalize_name(recipe_name), rule)
		method_map.setdefault(product, []).append((rule['Time'], method, recipe_name))

	for product, methods in method_map.items():
		methods.sort(key=lambda item: item[0])
		ordered_methods = [method for _, method, _ in methods]
		pyhop.declare_methods('produce_{}'.format(product), *ordered_methods)

def make_operator(rule):
	def operator(state, ID):
		if state.time[ID] < rule['Time']:
			return False

		requires = rule.get('Requires', {})
		for item, num in requires.items():
			if getattr(state, item)[ID] < num:
				return False

		consumes = rule.get('Consumes', {})
		for item, num in consumes.items():
			if getattr(state, item)[ID] < num:
				return False

		for item, num in consumes.items():
			getattr(state, item)[ID] -= num

		for item, num in rule.get('Produces', {}).items():
			getattr(state, item)[ID] += num

		state.time[ID] -= rule['Time']
		return state
	return operator

def declare_operators(data):
	# your code here
	# hint: call make_operator, then declare the operator to pyhop using pyhop.declare_operators(o1, o2, ..., ok)
	operators = []
	for recipe_name, rule in data['Recipes'].items():
		operator = make_operator(rule)
		operator.__name__ = 'op_{}'.format(_normalize_name(recipe_name))
		operators.append(operator)

	pyhop.declare_operators(*operators)

def add_heuristic(data, ID):
	# prune search branch if heuristic() returns True
	# do not change parameters to heuristic(), but can add more heuristic functions with the same parameters: 
	# e.g. def heuristic2(...); pyhop.add_check(heuristic2)
	def heuristic(state, curr_task, tasks, plan, depth, calling_stack):
		if curr_task[0].startswith('produce_'):
			for task in calling_stack:
				if task[0] == curr_task[0]:
					return True
		return False # if True, prune this branch

	pyhop.add_check(heuristic)

def define_ordering(data, ID):
	# if needed, use the function below to return a different ordering for the methods
	# note that this should always return the same methods, in a new order, and should not add/remove any new ones
	def reorder_methods(state, curr_task, tasks, plan, depth, calling_stack, methods):
		return methods
	
	pyhop.define_ordering(reorder_methods)

def _normalize_name(name):
	return name.replace(' ', '_')

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

	# pyhop.print_operators()
	# pyhop.print_methods()

	# Hint: verbose output can take a long time even if the solution is correct; 
	# try verbose=1 if it is taking too long
	pyhop.pyhop(state, goals, verbose=1)
	# pyhop.pyhop(state, [('have_enough', 'agent', 'cart', 1),('have_enough', 'agent', 'rail', 20)], verbose=3)
