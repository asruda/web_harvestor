import ast
with open('src/crawler/crawler_engine.py', 'r', encoding='utf-8') as f:
    ast.parse(f.read())
print('语法检查通过')