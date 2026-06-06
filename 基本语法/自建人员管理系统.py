persons = {}
def add_person(name,age,dep):
    if name in persons:
     return False
    persons[name] = {'age':age,
                     'dep':dep}
    return True

def seek_person(name):
    return persons.get(name)
def list_persons():
    return persons
