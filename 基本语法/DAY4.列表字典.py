# names = ["涂绍林","陶玲玲","涂艺桃"]
# print(names)
# print(names[0])
# print(names[1])
# print(names[2])
# for name in names:
#     print(name)
# user = {"name" : "涂绍林",
#         "age"  : 40,
#         "city" :"成都"
#         }
# print(user["name"])
# # print(user["age"])
# print(user["city"])
# user["age"] = 20
# print(user["age"])
# user["job"] = "程序员"
# print(user)
user = [{"name": "涂绍林", "age": 39},
        {"name": "陶玲玲", "age": 39},
        {"name": "涂艺桃", "age": 11},
        ]

#     if i["age"]>=18:
#      print(i["name"],"是成年人")
user.append({"name" :"何建琼","age":59})
for i in user:
 print(i["name"],i["age"])
print("未成年人：")
for i in user:
  if (i["age"] < 18):
     print(i["name"])
count = 0
for i in user:
  if (i["age"] > 18):
     count += 1
print(count)





