# def say_hello():
#     print("hello")
# say_hello()
# def say_hello(name):
#     print(f"你好,{name}")
# say_hello("涂绍林")
# say_hello("陶玲玲")
# say_hello("涂艺桃")
# def add(a, b):
#     return a + b
#
# result = add(3, 5)
# print(result)
# def is_even(num):
#     return(num % 2 == 0)
# print(is_even(3))
# print(is_even(4))
user = [{"name": "涂绍林", "age": 39},
        {"name": "陶玲玲", "age": 39},
        {"name": "涂艺桃", "age": 11},
        ]
# user1 = [
#     {"name": "王五", "age": 30},
#     {"name": "赵六", "age": 12}
# ]



#     if i["age"]>=18:
#      print(i["name"],"是成年人")
user.append({"name" :"何建琼","age":59})
for i in user:
 print(i["name"],i["age"])
print("未成年人：")
for i in user:
  if (i["age"] < 18):
     print(i["name"])
# count = 0
# for i in user:
#   if (i["age"] > 18):
#      count += 1
# print(count)
# def count_adults(users):
#     count = 0
#     for u in users:
#         if u["age"] >= 18:
#             count += 1
#     return count
# result = count_adults(user1)
# print(result)
def add_user(abs,name, age):
    abs.append({"name": name, "age": age})
    return abs
add_user(user,"涂述均",61)

print(user)