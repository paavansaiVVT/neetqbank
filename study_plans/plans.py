LEVELS = [20,40, 56]


def generate_all_combinations(subjects=None):
    """
    Generates all 81 possible combinations for (Physics, Chemistry, Biology, Biochemistry).
    Each subject can be B/I/E.
    Returns a list of dicts like: 
        [{'Physics': 'Beginner', 'Chemistry': 'Beginner', 'Biology': 'Beginner', 'Biochemistry': 'Beginner'}, ...]
    """
    if subjects is None:
        subjects = ["Physics", "Chemistry", "Biology", "Biochemistry"]
    
    all_combos = []
    from itertools import product
    for combo in product(LEVELS, repeat=4):
        combo_dict = dict(zip(subjects, combo))
        all_combos.append(combo_dict)
    return all_combos


all_combos=generate_all_combinations()
print(len(all_combos))
print(all_combos)